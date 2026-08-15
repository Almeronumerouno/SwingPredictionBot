"""
_phase4_p46_regime.py — P4.6: Regime-conditional calibration (PIT-safe).

Regime per observasi dihitung point-in-time dari `regime.regime_series`
(ADX14 < 20 -> sideways; close > SMA200 -> bull; else bear), pada index t
observasi (tanpa lookahead).

Per target x horizon x regime (dev & validation):
  - n, n_events, mean_p, observed_rate, O/E
  - ECE (diagnostic)
  - BSS vs climatology dev (per target x horizon GLOBAL, bukan per regime)
  - INSUFFICIENT flag: n < 500 atau n_events < 30 -> tidak bisa dinilai

Regime label: 0 sideways, 1 bull, 2 bear. Output: data/phase4_p46_regime.json
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
N_BIN = 10
NAMES = {0: "sideways", 1: "bull", 2: "bear"}
MIN_N, MIN_EV = 500, 30


def _ece(p: np.ndarray, y: np.ndarray, nb: int) -> float:
    order = np.argsort(p)
    p, y = p[order], y[order]
    edges = np.quantile(p, np.linspace(0, 1, nb + 1))
    edges[0], edges[-1] = 0.0, 1.0 + 1e-9
    bins = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, nb - 1)
    tot = 0.0
    n = len(p)
    for b in range(nb):
        m = bins == b
        if m.sum() == 0:
            continue
        tot += m.sum() / n * abs(y[m].mean() - p[m].mean())
    return round(float(tot), 4)


def main() -> None:
    data = D.load()
    result = {"phase": "P4.6 — Regime-conditional calibration (PIT-safe)",
              "regime": "regime_series(ADX14<20 sideways; close>SMA200 bull; else bear)",
              "insufficient": f"n<{MIN_N} atau n_events<{MIN_EV} -> INSUFFICIENT",
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
            regimes = {}
            for rg in (0, 1, 2):
                for sp, mask in (("dev", dev), ("validation", val)):
                    m = mask & (blk["regime"] == rg) & np.isfinite(blk["y"])
                    n = int(m.sum())
                    if n == 0:
                        regimes.setdefault(NAMES[rg], {})[sp] = {"n": 0}
                        continue
                    p, y = blk["p"][m], blk["y"][m]
                    mean_p = float(p.mean())
                    rate = float(y.mean())
                    ev = int(y.sum())
                    oe = rate / mean_p if mean_p > 0 else None
                    brier = float(np.mean((p - y) ** 2))
                    brier_ref = float(np.mean((p_ref - y) ** 2))
                    bss = 1.0 - brier / brier_ref if brier_ref > 0 else None
                    regimes.setdefault(NAMES[rg], {})[sp] = {
                        "n": n, "n_events": ev, "mean_p": round(mean_p, 4),
                        "observed_rate": round(rate, 4),
                        "O_over_E": round(oe, 3) if oe is not None else None,
                        "ece10": _ece(p, y, N_BIN),
                        "bss_vs_global_dev_clim": round(bss, 4) if bss is not None else None,
                        "insufficient": n < MIN_N or ev < MIN_EV,
                    }
            ht[str(h)] = {"p_ref_dev_climatology": round(p_ref, 4), "regimes": regimes}
        result["targets"][tgt] = ht
    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(r"data\phase4_p46_regime.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
    print("[ok] data/phase4_p46_regime.json", file=sys.stderr)

    print("=== P4.6 regime (dev | validation) — O/E (ECE) [BSS] ===", file=sys.stderr)
    for tgt, ht in result["targets"].items():
        for h in (1, 5, 21, 63):
            if str(h) not in ht:
                continue
            for rg in ("sideways", "bull", "bear"):
                blk = ht[str(h)]["regimes"].get(rg)
                if not blk:
                    continue
                row = f"{tgt:14s} h={h:>2} {rg:9s}"
                for sp in ("dev", "validation"):
                    r = blk.get(sp, {})
                    if r.get("n", 0) == 0:
                        row += f" | {sp[:3]}: -"
                    else:
                        flag = " INSUF" if r.get("insufficient") else ""
                        row += (f" | {sp[:3]}: n={r['n']:>6} O/E={r['O_over_E']} "
                                f"(ECE={r['ece10']}) [BSS={r['bss_vs_global_dev_clim']}]{flag}")
                print(row, file=sys.stderr)


if __name__ == "__main__":
    main()