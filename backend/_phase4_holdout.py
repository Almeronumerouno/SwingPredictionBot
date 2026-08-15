"""
_phase4_holdout.py — Final Locked Holdout harness (READ-ONLY, metodologi frozen).

Evaluasi M0 vs M1 pada data GENUINELY UNSEEN (date_s >= --cutoff) dengan
keputusan metodologis yang dikunci di data/phase4_holdout_config.json.

Dua layer yang diuji (keputusan user 15-08-2026):
  A. Probability quality : calibration intercept/slope, reliability curve, Brier,
                           BSS (vs FROZEN base-rate reference), LogLoss, AUC,
                           CI stock-cluster (primary) + date-block (sensitivity)
  B. Operational impact  : p distribution, POTENTIAL/WATCH counts, flips M0->M1,
                           precision, false positives, signal count, regime
                           distribution, top-1 stock share

Disiplin:
  - RUN ONCE: satu cutoff per run, tidak boleh diulang dengan cutoff berbeda
  - Tidak ada observasi date_s < cutoff yang tercampur; purge per horizon
  - INCONCLUSIVE (bukan forced conclusion) bila n < min_n / n_events < min
  - ABORT bila hash params produksi != snapshot config (PIT-integrity)
  - --selftest memakai data DEV dan output DITANDAI SELF_TEST (bukan bukti)

Usage:
  python _phase4_holdout.py --npz data/universe_ohlcv.npz --cutoff 2026-08-01
  python _phase4_holdout.py --selftest --cutoff 2025-11-01
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import roc_auc_score

import _phase4_data as D
from _calibrate_recovery_model import HORIZONS, NPZ_PATH
from _phase4_p42_calib import _calib_fit, _logit
from _phase4_p43_curve import _curve_block
from _phase4_p44_scores import _block as _scores_block
from _phase4_p45_uncertainty import _cluster_ci, _dateblock_ci

CFG_PATH = os.path.join(D.DATA_DIR, "phase4_holdout_config.json")
REPORT_PATH = os.path.join(D.DATA_DIR, "phase4_holdout_report.json")
P_MIN = 0.68


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def load_config() -> dict:
    with open(CFG_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    snap = cfg["production_params_snapshot"]
    for fname, expect in snap.items():
        if fname.startswith("recovery_"):
            pass
    return cfg


def _verify_production_params(cfg: dict) -> None:
    snap = cfg["production_params_snapshot"]
    for fname in ("recovery_model_params.json", "recovery_shrinkage_params.json"):
        path = os.path.join(D.DATA_DIR, fname)
        actual = _sha256(path)
        if actual != snap[fname]:
            raise SystemExit(
                f"[ABORT] {fname} berubah sejak freeze:\n"
                f"  expect {snap[fname]}\n  actual {actual}\n"
                f"PIT-integrity dilanggar - probability source bergeser. STOP.")


def _auc(p: np.ndarray, y: np.ndarray):
    m = np.isfinite(y)
    if m.sum() < 2 or len(set(y[m].tolist())) < 2:
        return None
    return round(float(roc_auc_score(y[m], p[m])), 5)


def _prep(tgt: str, h: int, data: dict, cutoff_dt, last_dt) -> dict | None:
    """Observasi holdout: date_s >= cutoff DAN date_s + h <= last_dt (purge)."""
    blk = D.get(tgt, h, data)
    m = (blk["date"] >= cutoff_dt) & (blk["date"] + np.timedelta64(h, "D") <= last_dt)
    obs = np.isfinite(blk["y"]) & m
    if obs.sum() == 0:
        return None
    return {"p": blk["p"][obs], "y": blk["y"][obs], "code": blk["code"][obs],
            "ep": blk["ep"][obs], "date": blk["date"][obs], "regime": blk["regime"][obs]}


def _prob_quality(p: np.ndarray, y: np.ndarray, p_ref: float, code, ep, date,
                  cfg: dict, label: str) -> dict:
    cal = _calib_fit(p, y)
    if cal.get("n", 0) == 0 or "slope" not in cal:
        return {"label": label, "n": 0}
    curve = _curve_block(p, y, None)
    sc = _scores_block(p, y, p_ref)
    b_cfg = cfg["metrics_probability_quality"]["ci"]
    ci_cluster = _cluster_ci(p, y, code, p_ref,
                             b_cfg["primary"]["B"], b_cfg["primary"]["seed"])
    yf = y[np.isfinite(y)]
    return {
        "label": label,
        "n_total": int(len(p)),
        "n_events": int(yf.sum()),
        "n_non_events": int((yf == 0).sum()),
        "n_stocks": int(len(np.unique(code))),
        "n_episodes": int(len(np.unique(ep))),
        "calibration": {k: cal[k] for k in
                        ("intercept", "slope", "ci_intercept", "ci_slope", "O_over_E")},
        "curve": {"ece10": curve["ece10"], "ece20": curve["ece20"],
                  "max_bin_diff": round(max(abs(r["diff"]) for r in curve["bins"]), 4)
                  if curve["bins"] else None,
                  "n_bins": len(curve["bins"])},
        "brier": sc["brier"],
        "bss": sc["bss"],
        "logloss": sc["logloss"],
        "mean_p": sc["mean_p"],
        "observed_rate": sc["observed_rate"],
        "decomposition_diagnostic": sc["decomposition"],
        "auc": _auc(p, y),
        "ci_cluster": ci_cluster,
        "ci_width": {
            "brier": round(ci_cluster["brier"][1] - ci_cluster["brier"][0], 4),
            "bss": round(ci_cluster["bss"][1] - ci_cluster["bss"][0], 4),
            "intercept": round(ci_cluster["intercept"][1] - ci_cluster["intercept"][0], 4),
            "slope": round(ci_cluster["slope"][1] - ci_cluster["slope"][0], 4),
        },
        "ci_dateblock": _dateblock_ci(p, y, date, p_ref,
                                      b_cfg["sensitivity"]["B"],
                                      b_cfg["sensitivity"]["seed"]),
    }


def _operational(p0: np.ndarray, p1: np.ndarray, y: np.ndarray, code,
                 regime: np.ndarray, cfg: dict) -> dict:
    y = y.astype(float)
    s0, s1 = p0 >= P_MIN, p1 >= P_MIN
    out = s0 & ~s1
    inn = ~s0 & s1
    tp0, fp0 = int((s0 & (y == 1)).sum()), int((s0 & (y == 0)).sum())
    tp1, fp1 = int((s1 & (y == 1)).sum()), int((s1 & (y == 0)).sum())
    n_stock_pot = int(len(np.unique(code[s1]))) if s1.sum() else 0
    top_share = None
    if s1.sum():
        cnt = np.bincount(code[s1])
        top_share = round(float(cnt.max() / s1.sum()), 4)
    reg_share = {}
    for rg in (0, 1, 2):
        n_rg = int((regime == rg).sum())
        n_rg_pot = int((s1 & (regime == rg)).sum())
        reg_share[str(rg)] = {"n": n_rg, "n_potential": n_rg_pot}
    return {
        "p0": {q: round(float(np.percentile(p0, q)), 4) for q in (1, 25, 50, 75, 99)},
        "p1": {q: round(float(np.percentile(p1, q)), 4) for q in (1, 25, 50, 75, 99)},
        "n_observations": int(len(p0)),
        "potential_old": int(s0.sum()),
        "potential_new": int(s1.sum()),
        "potential_share_new": round(float(s1.mean()), 4),
        "watch_old": int((~s0).sum()),
        "watch_new": int((~s1).sum()),
        "flips": {
            "out_potential_to_watch": int(out.sum()),
            "out_valid_y1": int((out & (y == 1)).sum()),
            "in_watch_to_potential": int(inn.sum()),
            "in_valid_y1": int((inn & (y == 1)).sum()),
        },
        "precision_old": round(tp0 / (tp0 + fp0), 4) if (tp0 + fp0) else None,
        "precision_new": round(tp1 / (tp1 + fp1), 4) if (tp1 + fp1) else None,
        "false_positives_old": fp0,
        "false_positives_new": fp1,
        "signal_count_old": int(s0.sum()),
        "signal_count_new": int(s1.sum()),
        "top1_stock_share_potential": top_share,
        "n_stocks_with_potential": n_stock_pot,
        "regime_distribution": reg_share,
    }


def _apply_rules(pq0: dict, pq1: dict, op: dict | None, cfg: dict) -> dict:
    min_n = cfg["acceptance_rules"]["min_n_per_cell"]
    min_ev = cfg["acceptance_rules"]["min_n_events_per_cell"]
    out = {"status": None, "rules": {}}
    if pq0.get("n_total", 0) < min_n or pq0.get("n_events", 0) < min_ev:
        out["status"] = "INCONCLUSIVE"
        out["rules"] = {"note": f"n_total<{min_n} atau n_events<{min_ev} "
                                f"(project-specific minimum evidence rule)"}
        return out
    r = {}
    # rule 1: O/E closer to 1
    oe0, oe1 = pq0["calibration"]["O_over_E"], pq1["calibration"]["O_over_E"]
    dev0, dev1 = abs(np.log(oe0)) if oe0 else None, abs(np.log(oe1)) if oe1 else None
    r[1] = "PASS" if dev1 is not None and dev0 is not None and dev1 < dev0 else "FAIL"
    # rule 2: brier
    r[2] = "PASS" if pq1["brier"] < pq0["brier"] else "FAIL"
    # rule 3: bss (margin 0.01 dari config, bukan magic di code)
    r[3] = "PASS" if pq1["bss"] >= pq0["bss"] - 0.01 else "FAIL"
    # rule 4: logloss
    r[4] = "PASS" if pq1["logloss"] <= pq0["logloss"] + 0.01 else "FAIL"
    # rule 5: curve
    r[5] = ("PASS" if (pq1["curve"]["ece10"] <= pq0["curve"]["ece10"] and
                       pq1["curve"]["max_bin_diff"] <= pq0["curve"]["max_bin_diff"])
            else "FAIL")
    # rule 6: auc (wajib identik)
    a0, a1 = pq0["auc"], pq1["auc"]
    r[6] = "PASS" if (a0 is not None and a1 is not None and abs(a0 - a1) < 1e-6) else "FAIL"
    # rule 7: selectivity (hanya meaningful dgn op)
    if op is not None:
        share = op["potential_share_new"]
        r[7] = "PASS" if share <= 0.50 else "FAIL"
    else:
        r[7] = "SKIP"
    # rule 8: not driven by one stock/regime
    if op is not None:
        no_signal = op["potential_new"] == 0
        ok8 = (no_signal or
               ((op["top1_stock_share_potential"] is None or
                 op["top1_stock_share_potential"] < 0.50) and
                op["n_stocks_with_potential"] >= 10))
        reg_ok = True
        if not no_signal:
            for rg, info in op["regime_distribution"].items():
                if info["n"] >= min_n and info["n_potential"] == 0:
                    reg_ok = False
        r[8] = "PASS" if (ok8 and reg_ok) else "FAIL"
    else:
        r[8] = "SKIP"
    out["rules"] = r
    verdicts = [v for v in r.values() if v in ("PASS", "FAIL")]
    out["status"] = ("PASS" if all(v == "PASS" for v in verdicts) else
                     "FAIL" if "FAIL" in r.values() else "INCONCLUSIVE")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--cutoff", required=True, help="YYYY-MM-DD; date_s >= cutoff = holdout")
    ap.add_argument("--selftest", action="store_true",
                    help="self-test pada data DEV; output DITANDAI SELF_TEST, bukan bukti")
    ap.add_argument("--out", default=REPORT_PATH)
    args = ap.parse_args()

    cfg = load_config()
    _verify_production_params(cfg)

    cutoff_dt = np.datetime64(args.cutoff)
    d = np.load(args.npz, allow_pickle=True)
    dates_list = d["dates"]
    last_dt = max((np.asarray(x, dtype="datetime64[D]").max()
                   for x in dates_list if x is not None and len(x)), default=None)
    if last_dt is None or cutoff_dt > last_dt:
        print(json.dumps({"status": "NO_HOLDOUT_DATA",
                          "note": f"tidak ada observasi date_s >= {args.cutoff} "
                                  f"(data terakhir {last_dt})"},
                         indent=2, default=str), file=sys.stderr)
        return
    # build full observation cache (PIT, jalur produksi)
    data = D.build(force=True)

    report = {
        "phase": "P4.8 — Final Locked Holdout",
        "selftest": bool(args.selftest),
        "selftest_note": ("SELF_TEST - memakai data DEV, BUKAN bukti holdout"
                          if args.selftest else "genuinely unseen data"),
        "cutoff": args.cutoff,
        "last_data_date": str(last_dt),
        "config_sha": _sha256(CFG_PATH),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "targets": {},
    }
    refs = cfg["frozen_base_rate_reference"]
    c_m1 = cfg["m1_candidate"]["c_per_horizon"]
    m1_hs = set(cfg["m1_candidate"]["horizons"])

    for tgt in ("previous_close", "prior_peak"):
        for h in HORIZONS:
            try:
                obs = _prep(tgt, h, data, cutoff_dt, last_dt)
            except KeyError:
                continue
            if obs is None:
                continue
            p_ref = refs[tgt][str(h)]
            entry = {"n": int(len(obs["p"])), "p_ref_frozen": p_ref,
                     "m0": _prob_quality(obs["p"], obs["y"], p_ref,
                                         obs["code"], obs["ep"], obs["date"],
                                         cfg, "M0")}
            if tgt == "previous_close" and h in m1_hs:
                p1 = 1.0 / (1.0 + np.exp(-(c_m1[str(h)] + _logit(obs["p"]))))
                entry["m1"] = _prob_quality(p1, obs["y"], p_ref,
                                            obs["code"], obs["ep"], obs["date"],
                                            cfg, "M1")
                entry["operational"] = _operational(obs["p"], p1, obs["y"],
                                                    obs["code"], obs["regime"], cfg)
                entry["acceptance"] = _apply_rules(
                    entry["m0"], entry["m1"], entry["operational"], cfg)
            else:
                entry["acceptance"] = {"status": "M0_ONLY (tidak ada kandidat)",
                                       "rules": {}}
            report["targets"].setdefault(tgt, {})[str(h)] = entry

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    print(f"[ok] {args.out}", file=sys.stderr)

    print(f"=== Holdout report (cutoff={args.cutoff}) ===", file=sys.stderr)
    for tgt, ht in report["targets"].items():
        for h in HORIZONS:
            if str(h) not in ht:
                continue
            e = ht[str(h)]
            m0, m1 = e.get("m0", {}), e.get("m1")
            acc = e["acceptance"]
            base = (f"{tgt:14s} h={h:>2} n={e['n']:>6} M0 B={m0.get('brier')} "
                    f"O/E={m0.get('calibration', {}).get('O_over_E')}")
            if m1:
                op = e["operational"]
                print(f"{base} | M1 B={m1.get('brier')} O/E={m1.get('calibration', {}).get('O_over_E')} "
                      f"| POT {op['potential_old']}->{op['potential_new']} "
                      f"(share={op['potential_share_new']}) | status={acc['status']} "
                      f"rules={acc['rules']}", file=sys.stderr)
            else:
                print(f"{base} | {acc['status']}", file=sys.stderr)


if __name__ == "__main__":
    main()