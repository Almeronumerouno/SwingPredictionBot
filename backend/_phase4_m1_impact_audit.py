"""
_phase4_m1_impact_audit.py — M1 impact audit (READ-ONLY, tidak menyentuh produksi).

Tujuan (keputusan user 15-08-2026): sebelum Final Locked Holdout, audit dampak
kandidat M1 (intercept-only) pada jalur sinyal produksi previous_close h=1-21:

  old_p = production shrinkage (M0, frozen)
  new_p = sigmoid(c_h + logit(old_p)), c_h dari P4.7 (window 126d terakhir dev)

Gate produksi: p_min = RECOVERY_SIGNAL_P_MIN = 0.68 (basis empirical) ->
  p >= 0.68 => POTENTIAL ; in_setup & p < 0.68 => WATCH.

Ditanyakan user:
  1. Berapa signal berubah (flips POTENTIAL<->WATCH)?
  2. Apakah recalibration mengurangi false positives (flip keluar dgn y=0)
     TANPA menghapus valid POTENTIAL (flip keluar dgn y=1)?
  3. Perilaku per regime (tidak collapse).
  4. Bukti monotonic: AUC identik, ranking tidak berubah.

Output: data/phase4_m1_impact_audit.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import roc_auc_score

import _phase4_data as D
from _calibrate_recovery_model import HORIZONS

CUTOFF_DT = np.datetime64("2026-01-23")
EMBARGO_DT = np.datetime64("2026-04-23")
P_MIN = 0.68
HORIZONS_M1 = (1, 3, 5, 10, 21)
REGIME_NAMES = {0: "sideways", 1: "bull", 2: "bear"}


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def _auc(p, y) -> float | None:
    m = np.isfinite(y)
    if m.sum() < 2 or len(set(y[m].tolist())) < 2:
        return None
    return round(float(roc_auc_score(y[m], p[m])), 5)


def _block(p_old: np.ndarray, y: np.ndarray, c: float,
           regime: np.ndarray, n_boot: int = 0) -> dict:
    p_new = 1.0 / (1.0 + np.exp(-(c + _logit(p_old))))
    y = y.astype(float)
    obs = np.isfinite(y)
    p_old, p_new, y, regime = p_old[obs], p_new[obs], y[obs], regime[obs]
    n = len(p_old)
    sig_old = p_old >= P_MIN
    sig_new = p_new >= P_MIN
    out_flip = sig_old & ~sig_new   # POTENTIAL -> WATCH
    in_flip = ~sig_old & sig_new    # WATCH -> POTENTIAL
    tp_old = int((sig_old & (y == 1)).sum())
    fp_old = int((sig_old & (y == 0)).sum())
    tp_new = int((sig_new & (y == 1)).sum())
    fp_new = int((sig_new & (y == 0)).sum())
    prec_old = tp_old / (tp_old + fp_old) if (tp_old + fp_old) else None
    prec_new = tp_new / (tp_new + fp_new) if (tp_new + fp_new) else None
    # region gate: old_p dekat 0.68 (+/- 0.05)
    gate = (p_old >= P_MIN - 0.05) & (p_old <= P_MIN + 0.05)
    # regime distribution
    reg_old = {}
    reg_new = {}
    for rg in (0, 1, 2):
        reg_old[REGIME_NAMES[rg]] = int((sig_old & (regime == rg)).sum())
        reg_new[REGIME_NAMES[rg]] = int((sig_new & (regime == rg)).sum())
    return {
        "n": n,
        "n_potential_old": int(sig_old.sum()),
        "n_potential_new": int(sig_new.sum()),
        "delta_potential": int(sig_new.sum() - sig_old.sum()),
        "flip_out_potential_to_watch": {
            "total": int(out_flip.sum()),
            "valid_y1_hilang": int((out_flip & (y == 1)).sum()),
            "invalid_y0_hilang": int((out_flip & (y == 0)).sum()),
        },
        "flip_in_watch_to_potential": {
            "total": int(in_flip.sum()),
            "valid_y1_baru": int((in_flip & (y == 1)).sum()),
            "invalid_y0_baru": int((in_flip & (y == 0)).sum()),
        },
        "net_false_positive_change": fp_new - fp_old,
        "net_true_positive_change": tp_new - tp_old,
        "precision_old": round(prec_old, 4) if prec_old is not None else None,
        "precision_new": round(prec_new, 4) if prec_new is not None else None,
        "auc_old": _auc(p_old, y),
        "auc_new": _auc(p_new, y),
        "delta_p": {
            "mean": round(float(np.mean(p_new - p_old)), 5),
            "p1": round(float(np.percentile(p_new - p_old, 1)), 5),
            "p50": round(float(np.percentile(p_new - p_old, 50)), 5),
            "p99": round(float(np.percentile(p_new - p_old, 99)), 5),
        },
        "gate_region": {
            "n": int(gate.sum()),
            "flip_out": int((gate & out_flip).sum()),
            "flip_in": int((gate & in_flip).sum()),
            "flip_out_valid": int((gate & out_flip & (y == 1)).sum()),
        },
        "regime_potential_old": reg_old,
        "regime_potential_new": reg_new,
    }


def main() -> None:
    data = D.load()
    recal = json.load(open(r"data/phase4_p47_recalib.json", encoding="utf-8"))
    result = {"phase": "M1 impact audit (candidate, read-only)",
              "note": "M1 = intercept-only recalibration (P4.7); p_min=0.68 gate "
                      "produksi; produksi TIDAK diubah",
              "p_min": P_MIN, "targets": {}}
    for h in HORIZONS_M1:
        try:
            blk = D.get("previous_close", h, data)
        except KeyError:
            continue
        c = recal["targets"]["previous_close"][str(h)]["models"]["M1_intercept"]["params"]["c"]
        dev = (blk["date"] <= CUTOFF_DT) & (blk["date"] + np.timedelta64(h, "D") <= CUTOFF_DT)
        val = blk["date"] > EMBARGO_DT
        result["targets"][str(h)] = {
            "c_M1": round(c, 4),
            "dev": _block(blk["p"][dev], blk["y"][dev], c, blk["regime"][dev]),
            "validation": _block(blk["p"][val], blk["y"][val], c, blk["regime"][val]),
        }
    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(r"data/phase4_m1_impact_audit.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
    print("[ok] data/phase4_m1_impact_audit.json", file=sys.stderr)

    print("=== M1 impact audit — previous_close (POTENTIAL count & flips) ===", file=sys.stderr)
    for h in HORIZONS_M1:
        if str(h) not in result["targets"]:
            continue
        blk = result["targets"][str(h)]
        for sp in ("dev", "validation"):
            r = blk[sp]
            fo, fi = r["flip_out_potential_to_watch"], r["flip_in_watch_to_potential"]
            print(f"h={h:>2} {sp:10s} POT {r['n_potential_old']}->{r['n_potential_new']} "
                  f"({r['delta_potential']:+d}) | out={fo['total']} "
                  f"(valid_lost={fo['valid_y1_hilang']}, fp_removed={fo['invalid_y0_hilang']}) "
                  f"in={fi['total']} (valid_new={fi['valid_y1_baru']}, fp_new={fi['invalid_y0_baru']}) "
                  f"netFP={r['net_false_positive_change']:+d} netTP={r['net_true_positive_change']:+d} "
                  f"prec {r['precision_old']}->{r['precision_new']} | AUC {r['auc_old']}=={r['auc_new']}",
                  file=sys.stderr)


if __name__ == "__main__":
    main()