"""
_phase3_rtf_ablation.py — Phase 3 (ablation): komponen strength & gates (OOS).

1) Strength score (AUC up1_21 & b10_21 di OOS, arm final):
   - full        : (density/100) * ndh * decay
   - density_only: density saja
   - ndh_only    : ndh saja
   - decay_only  : decay saja
2) Gates (b10 h10 rate & lift vs ctrl, OOS):
   - full        : below & k>=mh & density>=thr & above_ma & liq
   - no_above_ma : hapus gate above_ma
   - no_liq      : hapus gate likuiditas
   - no_below    : hapus gate below (semua posisi)
   - mh_1        : min_heavy = 1 (gate longgar)

Output: data/phase3_rtf_ablation.json
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import numpy as np

import _phase3_rtf_common as C


def main() -> None:
    rows, codes, code_idx = C.load_rows()
    dates_dt = C.row_dates(codes, rows, code_idx)
    split = C.make_split(codes, rows, code_idx, dates_dt)
    test = split["test"]

    cfg = C.selected_config(50.0, 2.0, 2, 2.0, None)   # winner
    thr, mult, mh = cfg["ACCUM_DENSITY_PCT"], cfg["ACCUM_HEAVY_RVOL"], cfg["ACCUM_MIN_HEAVY_DAYS"]
    m = int(C.MULT_GRID.index(mult))
    k = rows[:, C.I_K0 + m]
    den = rows[:, C.I_DEN0 + m]
    ndh = rows[:, C.I_NDH0 + m]

    base = ((rows[:, C.I_POS] < 1.0) & (k >= mh) & (den * 100.0 >= thr))
    arm_full = base & (rows[:, C.I_ABOVE_MA] == 1.0) & (rows[:, C.I_LIQ] == 1.0) & test

    arms = {
        "full": arm_full,
        "no_above_ma": (base & (rows[:, C.I_LIQ] == 1.0)) & test,
        "no_liq": (base & (rows[:, C.I_ABOVE_MA] == 1.0)) & test,
        "no_below": ((k >= mh) & (den * 100.0 >= thr)
                     & (rows[:, C.I_ABOVE_MA] == 1.0) & (rows[:, C.I_LIQ] == 1.0)) & test,
        "mh_1": ((rows[:, C.I_POS] < 1.0) & (k >= 1) & (den * 100.0 >= thr)
                 & (rows[:, C.I_ABOVE_MA] == 1.0) & (rows[:, C.I_LIQ] == 1.0)) & test,
    }

    ctrl = C.ctrl_mask(rows) & test
    hi10 = C.HORIZONS.index(10)
    b10_ctrl = rows[ctrl, C.I_LABEL0 + hi10 * 4 + 2]
    ctrl_rate = float(np.nanmean(b10_ctrl))

    gates = {}
    for name, arm in arms.items():
        b10 = rows[arm, C.I_LABEL0 + hi10 * 4 + 2]
        rate = float(np.nanmean(b10))
        gates[name] = {
            "n_signals": int(np.isfinite(b10).sum()),
            "b10_rate": round(rate, 4),
            "lift_vs_ctrl": round(rate / ctrl_rate, 3) if ctrl_rate > 0 else None,
        }

    # ── strength ablasi (AUC pada arm full, OOS) ──
    d = rows[:, C.I_WINDOW]
    decay = np.exp(-d / 2.0)
    ndh_safe = np.where(np.isfinite(ndh), ndh, 0.5)
    scores = {
        "full": den * ndh_safe * decay,
        "density_only": den,
        "ndh_only": ndh_safe,
        "decay_only": decay,
    }
    strength = {}
    for name, s in scores.items():
        strength[name] = {
            "auc_up1_21": C.auc_score(rows, arm_full, s, "up1", 21),
            "auc_b10_21": C.auc_score(rows, arm_full, s, "b10", 21),
            "precision@5_up1_21": C.precision_at_k(rows, arm_full, s, "up1", 21, 5),
            "precision@10_up1_21": C.precision_at_k(rows, arm_full, s, "up1", 21, 10),
        }

    doc = {
        "phase": "Phase 3 — ablation study (OOS, parameter frozen, config winner)",
        "method": ("gates di-ablasikan satu per satu (rate b10 h10 & lift vs ctrl); "
                   "komponen strength di-ablasikan (AUC ranking pada arm full)"),
        "winner_config": cfg,
        "ctrl_rate_b10_h10": round(ctrl_rate, 4),
        "gates": gates,
        "strength": strength,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    C.write_json(C.DATA_DIR + r"\phase3_rtf_ablation.json", doc)

    print("[ablation OOS] gates:", file=sys.stderr)
    for name, g in gates.items():
        print(f"  {name:12s} n={g['n_signals']:6d} b10={g['b10_rate']} lift={g['lift_vs_ctrl']}",
              file=sys.stderr)
    print("[strength AUC up1_21]:", file=sys.stderr)
    for name, s in strength.items():
        print(f"  {name:12s} AUC={s['auc_up1_21']} P@5={s['precision@5_up1_21']}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
