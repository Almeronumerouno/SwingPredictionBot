"""
_phase4_p44_scores.py — P4.4: Proper probabilistic scoring.

Per target x horizon, pada DEV & VALIDATION:
  - Brier = mean((p-y)^2)
  - BSS   = 1 - Brier/Brier_ref, dengan Brier_ref = climatology DEV
           (event rate data <= cutoff, purged — di-freeze SEBELUM melihat
           validation; DILARANG pakai validation prevalence)
  - Brier decomposition (Murphy 1973): BS = REL - RES + UNC
  - Log Loss (secondary proper score, clip p)

Output: data/phase4_p44_scores.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np

import _phase4_data as D
from _calibrate_recovery_model import HORIZONS

CUTOFF_DT = np.datetime64("2026-01-23")
EMBARGO_DT = np.datetime64("2026-04-23")
EPS = 1e-6


def _murphy(p: np.ndarray, y: np.ndarray) -> dict:
    n = len(p)
    unc = float(y.mean() * (1 - y.mean()))
    res = float(((p - y.mean()) ** 2).mean())
    rel = float(((p - y) ** 2).mean()) - res + unc
    return {"rel": round(rel, 5), "res": round(res, 5), "unc": round(unc, 5),
            "check": round(rel - res + unc, 5)}


def _block(p: np.ndarray, y: np.ndarray, p_ref: float) -> dict:
    y = y.astype(float)
    obs = np.isfinite(y)
    p, y = p[obs], y[obs]
    n = int(len(p))
    if n == 0:
        return {"n": 0}
    brier = float(np.mean((p - y) ** 2))
    brier_ref = float(np.mean((p_ref - y) ** 2))
    bss = 1.0 - brier / brier_ref if brier_ref > 0 else None
    pc = np.clip(p, EPS, 1.0 - EPS)
    logloss = float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)))
    return {
        "n": n,
        "brier": round(brier, 5),
        "brier_ref_climatology_dev": round(float(brier_ref), 5),
        "bss": round(bss, 4) if bss is not None else None,
        "logloss": round(logloss, 5),
        "decomposition": _murphy(p, y),
        "mean_p": round(float(p.mean()), 4),
        "observed_rate": round(float(y.mean()), 4),
    }


def main() -> None:
    data = D.load()
    result = {"phase": "P4.4 — Proper probabilistic scoring",
              "method": "Brier; BSS vs climatology DEV (frozen sebelum validation); "
                        "dekomposisi Murphy; Log Loss (secondary)",
              "targets": {}}
    for tgt in ("previous_close", "prior_peak"):
        ht = {}
        for h in HORIZONS:
            try:
                blk = D.get(tgt, h, data)
            except KeyError:
                continue
            dev = (blk["date"] <= CUTOFF_DT) & (blk["date"] + np.timedelta64(h, "D") <= CUTOFF_DT)
            val = blk["date"] > EMBARGO_DT
            y_dev = blk["y"][dev]
            y_dev = y_dev[np.isfinite(y_dev)]
            p_ref = float(y_dev.mean()) if len(y_dev) else float("nan")
            ht[str(h)] = {
                "p_ref_dev_climatology": round(p_ref, 4),
                "dev": _block(blk["p"][dev], blk["y"][dev], p_ref),
                "validation": _block(blk["p"][val], blk["y"][val], p_ref),
            }
        result["targets"][tgt] = ht
    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(r"data\phase4_p44_scores.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
    print("[ok] data/phase4_p44_scores.json", file=sys.stderr)

    print("=== P4.4 scores (dev | validation) ===", file=sys.stderr)
    for tgt, ht in result["targets"].items():
        for h in HORIZONS:
            if str(h) not in ht:
                continue
            blk = ht[str(h)]
            row = f"{tgt:14s} h={h:>2} ref={blk['p_ref_dev_climatology']} |"
            for sp in ("dev", "validation"):
                r = blk[sp]
                d = r.get("decomposition", {})
                row += (f" {sp[:3]} n={r['n']:>6} B={r['brier']} BSS={r['bss']} "
                        f"LL={r['logloss']} REL={d.get('rel')} RES={d.get('res')}")
            print(row, file=sys.stderr)


if __name__ == "__main__":
    main()