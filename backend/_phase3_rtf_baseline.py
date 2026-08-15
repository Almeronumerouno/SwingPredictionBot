"""
_phase3_rtf_baseline.py — Phase 3 (Phase D): baseline comparison (OOS).

Membandingkan arm winner vs baseline sederhana pada OOS (parameter FROZEN):
  1. random      : sampling acak dari kontrol (n = n_arm) — distribusi b10
  2. momentum5   : kontrol dgn ret_lag5 >= quantile penyama ukuran
  3. momentum10  : kontrol dgn ret_lag10 >= quantile penyama ukuran
  4. density_only: below & k>=mh & density>=thr (TANPA above_ma & liq) — v4 style

Output: data/phase3_rtf_baseline.json
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import numpy as np

import _phase3_rtf_common as C

B = 1000
SEED = 42


def main() -> None:
    rows, codes, code_idx = C.load_rows()
    dates_dt = C.row_dates(codes, rows, code_idx)
    split = C.make_split(codes, rows, code_idx, dates_dt)
    test = split["test"]
    ctrl = C.ctrl_mask(rows) & test

    cfg = C.selected_config(50.0, 2.0, 2, 2.0, None)   # winner (hasil tuning)
    arm = C.arm_mask(rows, cfg["ACCUM_DENSITY_PCT"], cfg["ACCUM_HEAVY_RVOL"],
                     cfg["ACCUM_MIN_HEAVY_DAYS"]) & test
    n_arm = int(arm.sum())

    hi10 = C.HORIZONS.index(10)
    b10_arm = rows[arm, C.I_LABEL0 + hi10 * 4 + 2]
    b10_ctrl = rows[ctrl, C.I_LABEL0 + hi10 * 4 + 2]

    def _rate_b10(x: np.ndarray) -> float:
        x = x[np.isfinite(x)]
        return float(np.mean(x)) if len(x) else float("nan")

    # 1) random
    rng = np.random.default_rng(SEED)
    idx_ctrl = np.where(np.isfinite(b10_ctrl))[0]
    rates = []
    for _ in range(B):
        s = rng.choice(idx_ctrl, size=min(n_arm, len(idx_ctrl)), replace=True)
        rates.append(float(np.mean(b10_ctrl[s])))
    random_rate = float(np.mean(rates))

    # 2) & 3) momentum quantile penyama ukuran
    def _mom(mask_c: np.ndarray, col: int, target_n: int) -> tuple[float, int]:
        m = mask_c & np.isfinite(rows[:, col])
        if int(m.sum()) < target_n:
            return float("nan"), int(m.sum())
        order = np.argsort(-rows[m, col])
        sel = m.copy()
        keep = np.zeros(len(rows), dtype=bool)
        idx = np.where(m)[0][order][:target_n]
        keep[idx] = True
        return _rate_b10(rows[keep, C.I_LABEL0 + hi10 * 4 + 2]), int(keep.sum())

    mom5_rate, mom5_n = _mom(ctrl, C.I_RETLAG5, n_arm)
    mom10_rate, mom10_n = _mom(ctrl, C.I_RETLAG10, n_arm)

    # 4) density-only (v4 style: tanpa above_ma, tanpa liq)
    m = int(C.MULT_GRID.index(cfg["ACCUM_HEAVY_RVOL"]))
    den_only = ((rows[:, C.I_POS] < 1.0)
                & (rows[:, C.I_K0 + m] >= cfg["ACCUM_MIN_HEAVY_DAYS"])
                & (rows[:, C.I_DEN0 + m] * 100.0 >= cfg["ACCUM_DENSITY_PCT"])) & test
    den_only_rate = _rate_b10(rows[den_only, C.I_LABEL0 + hi10 * 4 + 2])

    # kontrol rate
    ctrl_rate = _rate_b10(b10_ctrl)

    doc = {
        "phase": "Phase 3 — baseline comparison (OOS, parameter frozen)",
        "method": ("OOS = periode setelah cutoff + embargo 90d; semua baseline "
                   "dievaluasi pada set yang sama (b10 horizon 10)"),
        "winner_arm": {
            "config": cfg,
            "n_signals": n_arm,
            "b10_rate": round(_rate_b10(b10_arm), 4),
            "lift_vs_ctrl": round(_rate_b10(b10_arm) / ctrl_rate, 3) if ctrl_rate > 0 else None,
        },
        "baselines": {
            "random": {
                "n_signals": n_arm,
                "b10_rate": round(random_rate, 4),
                "bootstrap_b": B,
                "seed": SEED,
            },
            "momentum_5d": {
                "n_signals": mom5_n,
                "b10_rate": round(mom5_rate, 4) if np.isfinite(mom5_rate) else None,
            },
            "momentum_10d": {
                "n_signals": mom10_n,
                "b10_rate": round(mom10_rate, 4) if np.isfinite(mom10_rate) else None,
            },
            "density_only": {
                "n_signals": int(den_only.sum()),
                "b10_rate": round(den_only_rate, 4) if np.isfinite(den_only_rate) else None,
                "note": "below & k>=mh & density>=thr, TANPA above_ma & liq (v4 style)",
            },
        },
        "ctrl_rate_b10_h10": round(ctrl_rate, 4),
        "n_ctrl": int(ctrl.sum()),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    C.write_json(C.DATA_DIR + r"\phase3_rtf_baseline.json", doc)

    print(f"[baseline OOS] ctrl b10={ctrl_rate:.4f} (n={int(ctrl.sum())})", file=sys.stderr)
    print(f"  winner n={n_arm} b10={_rate_b10(b10_arm):.4f}", file=sys.stderr)
    print(f"  random={random_rate:.4f} | mom5={mom5_rate:.4f}({mom5_n}) | "
          f"mom10={mom10_rate:.4f}({mom10_n}) | density_only={den_only_rate:.4f}({int(den_only.sum())})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
