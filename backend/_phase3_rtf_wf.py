"""
_phase3_rtf_wf.py — Phase 3 (RTF validation): true walk-forward threshold
tuning + OOS evaluation (eval-only, produksi TIDAK diubah).

Acceptance user:
  1. Cutoff global disimpan sebagai tanggal ABSOLUT (selection_metadata).
  2. Purge memakai horizon label MAKSIMUM (63).
  3. Tuning sequential & freeze: density -> heavy -> min_heavy -> tau -> cutoff
     (dimensi sebelumnya TIDAK diulang).
  4. OOS TIDAK dipakai untuk memilih konfigurasi — hanya membandingkan
     winner vs production default.
  5. Near-tie: report tie; prefer default yang lebih sederhana/stabil
     (tol lift 0.05, tol AUC 0.01).

Output:
  data/phase3_rtf_tune.json   (selection_metadata + train_metrics per kandidat)
  data/phase3_rtf_oos.json    (winner vs default, CI bootstrap stock-cluster)

Usage:
  python _phase3_rtf_wf.py            # pakai cache rows (harus ada)
  python _phase3_rtf_wf.py --build    # build rows dulu bila cache kosong
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import numpy as np

import _phase3_rtf_common as C


# ─────────────────────────────────────────────────────────────
# Pemilihan pemenang per dimensi (near-tie aware)
# ─────────────────────────────────────────────────────────────
def pick_winner(candidates: list[dict], default_value: float, key: str,
                tol: float, n_min: int, param_name: str) -> dict:
    """candidates: [{'value', 'train_metrics'}, ...]; key = 'lift_b10' | 'auc'."""
    valid = [c for c in candidates if c["train_metrics"].get(key) is not None
             and c["train_metrics"].get("n_signals", 0) >= n_min]
    if not valid:
        return {"winner": default_value, "near_tie": False,
                "rationale": "TIDAK ADA kandidat valid (n<min atau metrik None) -> default",
                "skipped": True}
    ordered = sorted(valid, key=lambda c: c["train_metrics"][key], reverse=True)
    best = ordered[0]
    best_val = best["train_metrics"][key]
    # default ada di grid? ambil metrics default
    def_metrics = next((c["train_metrics"] for c in valid if c["value"] == default_value), None)
    def_val = def_metrics.get(key) if def_metrics else None
    near_tie = False
    if def_val is not None and def_val != best_val and abs(best_val - def_val) <= tol:
        near_tie = True
    if near_tie:
        return {
            "winner": default_value,
            "near_tie": True,
            "rationale": (f"near-tie: best {param_name}={best_val} vs default={def_val} "
                          f"(delta {abs(best_val - def_val):.3f} <= tol {tol}) -> "
                          f"prefer default (stabil/sederhana)"),
            "best_candidate": best["value"],
        }
    return {
        "winner": best["value"],
        "near_tie": False,
        "rationale": (f"best {param_name}={best_val} (> default {def_val}) "
                      f"dgn n_signals={best['train_metrics']['n_signals']}"),
    }


def _candidate_metrics(rows: np.ndarray, arm: np.ndarray,
                       ctrl: np.ndarray) -> dict:
    return C.train_metrics(rows, arm, ctrl)


# ─────────────────────────────────────────────────────────────
# Tuning sequential (acceptance #3: freeze per dimensi)
# ─────────────────────────────────────────────────────────────
def run_tuning(rows: np.ndarray, ctrl: np.ndarray, train: np.ndarray,
               codes: list[str], code_idx: np.ndarray) -> dict:
    steps: list[dict] = []

    # ── STEP 1: density (mult=2.0, min_heavy=2 — default produksi) ──
    cands = []
    for thr in C.DENSITY_GRID:
        arm = C.arm_mask(rows, thr, 2.0, 2) & train
        cands.append({"value": thr, "train_metrics": _candidate_metrics(rows, arm, ctrl & train)})
    w = pick_winner(cands, C.CFG.ACCUM_DENSITY_PCT, "lift_b10", C.NEAR_TIE_TOL_LIFT,
                    C.N_MIN_SIGNALS, "density")
    steps.append({"parameter": "density", "grid": list(C.DENSITY_GRID), "candidates": cands, **w})
    dens_win = float(w["winner"])

    # ── STEP 2: heavy_rvol (density=winner, min_heavy=2) ──
    cands = []
    for mult in C.MULT_GRID:
        arm = C.arm_mask(rows, dens_win, mult, 2) & train
        cands.append({"value": mult, "train_metrics": _candidate_metrics(rows, arm, ctrl & train)})
    w = pick_winner(cands, C.CFG.ACCUM_HEAVY_RVOL, "lift_b10", C.NEAR_TIE_TOL_LIFT,
                    C.N_MIN_SIGNALS, "heavy_rvol")
    steps.append({"parameter": "heavy_rvol", "grid": list(C.MULT_GRID), "candidates": cands, **w})
    mult_win = float(w["winner"])

    # ── STEP 3: min_heavy (density+heavy winner) ──
    cands = []
    for mh in C.MIN_HEAVY_GRID:
        arm = C.arm_mask(rows, dens_win, mult_win, mh) & train
        cands.append({"value": mh, "train_metrics": _candidate_metrics(rows, arm, ctrl & train)})
    w = pick_winner(cands, C.CFG.ACCUM_MIN_HEAVY_DAYS, "lift_b10", C.NEAR_TIE_TOL_LIFT,
                    C.N_MIN_SIGNALS, "min_heavy")
    steps.append({"parameter": "min_heavy", "grid": list(C.MIN_HEAVY_GRID), "candidates": cands, **w})
    mh_win = int(w["winner"])

    # ── STEP 4: decay tau (gates final; metrik = AUC strength -> up1_21) ──
    arm_final = C.arm_mask(rows, dens_win, mult_win, mh_win)
    arm_tr = arm_final & train
    cutoff_def = C.CFG.ACCUM_DECAY_CUTOFF_DAYS  # 5 (produksi)
    cands = []
    for tau in C.TAU_GRID:
        score = C.strength_score(rows, mult_win, tau, cutoff_def)
        auc_up = C.auc_score(rows, arm_tr, score, "up1", 21)
        auc_b10 = C.auc_score(rows, arm_tr, score, "b10", 21)
        tm = _candidate_metrics(rows, arm_tr, ctrl & train)
        tm["auc_up1_21"] = auc_up
        tm["auc_b10_21"] = auc_b10
        cands.append({"value": tau, "train_metrics": tm})
    w = pick_winner(cands, C.CFG.ACCUM_DECAY_TAU, "auc_up1_21", C.NEAR_TIE_TOL_AUC,
                    C.N_MIN_SIGNALS, "decay_tau")
    steps.append({"parameter": "decay_tau", "grid": list(C.TAU_GRID), "candidates": cands, **w})
    tau_win = float(w["winner"])

    # ── STEP 5: decay cutoff (tau=winner; None = tanpa cutoff) ──
    cands = []
    for cut in C.CUTOFF_GRID:
        score = C.strength_score(rows, mult_win, tau_win, cut)
        auc_up = C.auc_score(rows, arm_tr, score, "up1", 21)
        auc_b10 = C.auc_score(rows, arm_tr, score, "b10", 21)
        tm = _candidate_metrics(rows, arm_tr, ctrl & train)
        tm["auc_up1_21"] = auc_up
        tm["auc_b10_21"] = auc_b10
        cands.append({"value": cut, "train_metrics": tm})
    w = pick_winner(cands, C.CFG.ACCUM_DECAY_CUTOFF_DAYS, "auc_up1_21",
                    C.NEAR_TIE_TOL_AUC, C.N_MIN_SIGNALS, "decay_cutoff")
    steps.append({"parameter": "decay_cutoff", "grid": list(C.CUTOFF_GRID), "candidates": cands, **w})
    cutoff_win = w["winner"]  # None | 5 | 7 | 10

    return {
        "steps": steps,
        "density": dens_win,
        "heavy_rvol": mult_win,
        "min_heavy": mh_win,
        "decay_tau": tau_win,
        "decay_cutoff": cutoff_win,
        "arm_final_mask": arm_final,
    }


# ─────────────────────────────────────────────────────────────
# OOS evaluation (winner vs default — acceptance #4)
# ─────────────────────────────────────────────────────────────
def evaluate_oos(rows: np.ndarray, ctrl: np.ndarray, test: np.ndarray,
                 arm_final: np.ndarray, winner_cfg: dict, default_cfg: dict,
                 mult_win: float) -> dict:
    arm_w = arm_final & test
    arm_d = C.arm_mask(rows, default_cfg["ACCUM_DENSITY_PCT"], default_cfg["ACCUM_HEAVY_RVOL"],
                       default_cfg["ACCUM_MIN_HEAVY_DAYS"]) & test
    ctrl_t = ctrl & test

    def _rank_block(arm: np.ndarray, mult: float, tau: float, cutoff) -> dict:
        score = C.strength_score(rows, mult, tau, cutoff)
        return {
            "auc_up1_21": C.auc_score(rows, arm, score, "up1", 21),
            "auc_b10_21": C.auc_score(rows, arm, score, "b10", 21),
            "precision_at_k": [
                C.precision_at_k(rows, arm, score, "up1", 21, K) for K in (5, 10, 20)
            ],
        }

    return {
        "winner": {
            "config": winner_cfg,
            "metrics": C.metrics_arm(rows, arm_w, ctrl_t),
            "ranking": _rank_block(arm_w, mult_win,
                                   winner_cfg["ACCUM_DECAY_TAU"],
                                   winner_cfg["ACCUM_DECAY_CUTOFF_DAYS"]),
        },
        "default": {
            "config": default_cfg,
            "metrics": C.metrics_arm(rows, arm_d, ctrl_t),
            "ranking": _rank_block(arm_d, default_cfg["ACCUM_HEAVY_RVOL"],
                                   default_cfg["ACCUM_DECAY_TAU"],
                                   default_cfg["ACCUM_DECAY_CUTOFF_DAYS"]),
        },
    }


def bootstrap_oos(rows: np.ndarray, code_idx: np.ndarray, test: np.ndarray,
                  arm_final: np.ndarray, winner_cfg: dict, default_cfg: dict,
                  mult_win: float, B: int = 1000, seed: int = 42) -> dict:
    """CI stock-cluster utk lift_b10 (h=10) & AUC(up1_21) — tanpa refit."""
    n_stocks = int(code_idx.max()) + 1
    ctrl_t = C.ctrl_mask(rows) & test

    def _fn_lift(stocks: np.ndarray, arm: np.ndarray) -> float | None:
        m = np.isin(code_idx, stocks) & test & arm
        c = np.isin(code_idx, stocks) & ctrl_t
        tm = C.train_metrics(rows, m, c)
        return tm.get("lift_b10")

    def _fn_auc(stocks: np.ndarray, arm: np.ndarray) -> float | None:
        m = np.isin(code_idx, stocks) & test & arm
        score = C.strength_score(rows, mult_win,
                                 winner_cfg["ACCUM_DECAY_TAU"],
                                 winner_cfg["ACCUM_DECAY_CUTOFF_DAYS"])
        return C.auc_score(rows, m, score, "up1", 21)

    arm_w = arm_final
    arm_d = C.arm_mask(rows, default_cfg["ACCUM_DENSITY_PCT"], default_cfg["ACCUM_HEAVY_RVOL"],
                       default_cfg["ACCUM_MIN_HEAVY_DAYS"])

    out = {
        "winner": {
            "lift_b10_h10": C.bootstrap_ci(lambda s: _fn_lift(s, arm_w), n_stocks, B, seed),
            "auc_up1_21": C.bootstrap_ci(lambda s: _fn_auc(s, arm_w), n_stocks, B, seed),
        },
    }
    # default: hanya lift (bandingkan CI)
    out["default"] = {
        "lift_b10_h10": C.bootstrap_ci(lambda s: _fn_lift(s, arm_d), n_stocks, B, seed),
    }
    return out


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 3 — RTF walk-forward tuning + OOS (eval-only)")
    ap.add_argument("--build", action="store_true", help="build row cache bila kosong")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--bootstrap-b", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.build or not __import__("os").path.exists(C.ROWS_NPZ_PATH):
        C.build_rows(workers=args.workers)

    rows, codes, code_idx = C.load_rows()
    print(f"rows: {len(rows):,} | kode: {len(codes)}", file=sys.stderr)

    dates_dt = C.row_dates(codes, rows, code_idx)
    split = C.make_split(codes, rows, code_idx, dates_dt)
    train, test = split["train"], split["test"]
    ctrl = C.ctrl_mask(rows)
    print(f"split: cutoff {split['cutoff_date']} | train {split['n_train_rows']:,} | "
          f"test {split['n_test_rows']:,} | gap {split['n_gap']:,}", file=sys.stderr)

    # ── tuning (train-only, sequential freeze) ──
    tuning = run_tuning(rows, ctrl, train, codes, code_idx)
    steps = tuning["steps"]

    winner_cfg = C.selected_config(
        tuning["density"], tuning["heavy_rvol"], tuning["min_heavy"],
        tuning["decay_tau"], tuning["decay_cutoff"])
    default_cfg = C.default_config()

    train_arm = tuning["arm_final_mask"] & train
    oos_arm = tuning["arm_final_mask"] & test

    sel_meta = {
        "cutoff_date": split["cutoff_date"],
        "embargo_date": split["embargo_date"],
        "purge_horizon": split["purge_horizon"],
        "embargo_days": split["embargo_days"],
        "train_signal_count": int(train_arm.sum()),
        "oos_signal_count": int(oos_arm.sum()),
        "parameter_selection_order": ["density", "heavy_rvol", "min_heavy",
                                      "decay_tau", "decay_cutoff"],
        "default_config": default_cfg,
        "selected_config": winner_cfg,
    }

    tune_doc = {
        "phase": "Phase 3 (RTF validation) — true walk-forward threshold tuning",
        "method": ("global chronological split (cutoff quantile 0.70, absolut) + "
                   "purge(horizon max 63) + embargo(90d); sequential freeze; "
                   "pemilihan parameter HANYA di TRAIN"),
        "selection_metadata": sel_meta,
        "n_min_signals": C.N_MIN_SIGNALS,
        "near_tie_rule": {
            "lift_tol": C.NEAR_TIE_TOL_LIFT,
            "auc_tol": C.NEAR_TIE_TOL_AUC,
            "rule": "jika best - default <= tol -> prefer default (stabil/sederhana)",
        },
        "steps": steps,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    C.write_json(__import__("os").path.join(C.DATA_DIR, "phase3_rtf_tune.json"), tune_doc)

    print("\n=== PEMENANG PER DIMENSI (train-only) ===", file=sys.stderr)
    for st in steps:
        print(f"  {st['parameter']:10s} -> {st['winner']}  (near_tie={st['near_tie']})",
              file=sys.stderr)
        print(f"    rationale: {st['rationale']}", file=sys.stderr)
    print(f"\n  selected_config: {winner_cfg}", file=sys.stderr)

    # ── OOS (frozen — tidak ada seleksi di OOS) ──
    oos = evaluate_oos(rows, ctrl, test, tuning["arm_final_mask"],
                       winner_cfg, default_cfg, tuning["heavy_rvol"])
    boot = bootstrap_oos(rows, code_idx, test, tuning["arm_final_mask"],
                         winner_cfg, default_cfg, tuning["heavy_rvol"],
                         B=args.bootstrap_b, seed=args.seed)

    oos_doc = {
        "phase": "Phase 3 — OOS evaluation (parameter FROZEN sebelum OOS)",
        "note": "OOS TIDAK dipakai untuk memilih konfigurasi — hanya membandingkan "
                "winner vs production default (acceptance #4).",
        "selection_metadata": sel_meta,
        "comparison": oos,
        "bootstrap_ci": boot,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    C.write_json(__import__("os").path.join(C.DATA_DIR, "phase3_rtf_oos.json"), oos_doc)

    # Ringkasan console
    for tag in ("winner", "default"):
        blk = oos[tag]
        h10 = next(h for h in blk["metrics"]["horizons"] if h["horizon"] == 10)
        h21 = next(h for h in blk["metrics"]["horizons"] if h["horizon"] == 21)
        print(f"\n[OOS {tag}] n={blk['metrics']['n_arm']} | "
              f"b10 h10: {h10['arm']['b10']} (lift {h10['lift_b10']}) | "
              f"b10 h21: {h21['arm']['b10']} (lift {h21['lift_b10']}) | "
              f"AUC up1_21: {blk['ranking']['auc_up1_21']}", file=sys.stderr)


if __name__ == "__main__":
    main()
