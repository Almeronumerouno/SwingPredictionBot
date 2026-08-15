"""
_phase4_p43_curve.py — P4.3: Flexible calibration / reliability curve.

Per target x horizon (mendalam utk h = 5, 21, 63):
  - Smooth curve: isotonic regression (flexible, monotone) di (p_hat, y)
  - Quantile-bin table (20 bin): n, mean p, observed rate, |diff|, Wilson 95% CI
  - Identity line y = x (referensi ideal)
  - Region produksi: bin yang mengandung threshold p* (0.68 utk previous_close,
    0.50 utk prior_peak, horizon sinyal 21) -> deviation material?
  - ECE@10 & ECE@20 (diagnostic ONLY, bukan kriteria)

Output: data/phase4_p43_curve.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

import _phase4_data as D
from _calibrate_recovery_model import HORIZONS

CUTOFF_DT = np.datetime64("2026-01-23")
EMBARGO_DT = np.datetime64("2026-04-23")
N_BIN = 20
DEEP = (5, 21, 63)
THRESHOLDS = {"previous_close": {21: 0.68}, "prior_peak": {21: 0.50}}


def _wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * np.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, (center - half) / denom), min(1.0, (center + half) / denom))


def _ece(p: np.ndarray, y: np.ndarray, nb: int) -> float:
    order = np.argsort(p)
    p, y = p[order], y[order]
    edges = np.quantile(p, np.linspace(0, 1, nb + 1))
    edges[0], edges[-1] = 0.0, 1.0 + 1e-9
    bins = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, nb - 1)
    n = len(p)
    tot = 0.0
    for b in range(nb):
        m = bins == b
        if m.sum() == 0:
            continue
        tot += m.sum() / n * abs(y[m].mean() - p[m].mean())
    return round(float(tot), 4)


def _curve_block(p: np.ndarray, y: np.ndarray, thr: float | None) -> dict:
    y = y.astype(float)
    obs = np.isfinite(y)
    p, y = p[obs], y[obs]
    n = int(len(p))
    if n == 0:
        return {"n": 0}
    order = np.argsort(p)
    p, y = p[order], y[order]
    edges = np.quantile(p, np.linspace(0, 1, N_BIN + 1))
    edges[0], edges[-1] = 0.0, 1.0 + 1e-9
    bins = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, N_BIN - 1)
    rows = []
    for b in range(N_BIN):
        m = bins == b
        nb = int(m.sum())
        if nb == 0:
            continue
        conf = float(p[m].mean())
        acc = float(y[m].mean())
        k = int(y[m].sum())
        lo, hi = _wilson(k, nb)
        rows.append({"bin": b, "n": nb, "conf": round(conf, 4),
                     "acc": round(acc, 4), "diff": round(acc - conf, 4),
                     "ci95": [round(lo, 4), round(hi, 4)]})
    # smooth curve: isotonic di titik grid quantile
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(p, y)
    grid = np.linspace(0.0, 1.0, 101)
    smooth = iso.predict(grid)
    thr_block = None
    if thr is not None:
        idx = int(np.searchsorted(grid, thr))
        idx = min(idx, 100)
        mask_bin = (p >= thr - 0.05) & (p <= thr + 0.05)
        nb = int(mask_bin.sum())
        thr_block = {
            "threshold": thr,
            "n_region": nb,
            "conf_region": round(float(p[mask_bin].mean()), 4) if nb else None,
            "acc_region": round(float(y[mask_bin].mean()), 4) if nb else None,
            "diff_region": round(float(y[mask_bin].mean() - p[mask_bin].mean()), 4)
            if nb else None,
            "wilson95": [round(_wilson(int(y[mask_bin].sum()), nb)[0], 4),
                         round(_wilson(int(y[mask_bin].sum()), nb)[1], 4)] if nb else None,
        }
    return {
        "n": n,
        "bins": rows,
        "smooth_curve": {"grid": grid.tolist(), "yhat": smooth.tolist()},
        "ece10": _ece(p, y, 10),
        "ece20": _ece(p, y, 20),
        "threshold_region": thr_block,
        "brier": round(float(brier_score_loss(y, p)), 4),
    }


def main() -> None:
    data = D.load()
    result = {"phase": "P4.3 — Flexible calibration / reliability curve",
              "method": "isotonic smooth curve + quantile bins (20) + Wilson CI; "
                        "ECE diagnostic only; region produksi = p* ± 0.05",
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
            thr = THRESHOLDS.get(tgt, {}).get(h)
            deep = h in DEEP
            ht[str(h)] = {
                "deep_report": deep,
                "dev": _curve_block(blk["p"][dev], blk["y"][dev], thr if deep else None),
                "validation": _curve_block(blk["p"][val], blk["y"][val], thr if deep else None),
            }
        result["targets"][tgt] = ht
    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(r"data\phase4_p43_curve.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
    print("[ok] data/phase4_p43_curve.json", file=sys.stderr)

    print("=== P4.3 curve summary (h mendalam; dev | validation) ===", file=sys.stderr)
    for tgt, ht in result["targets"].items():
        for h in DEEP:
            if str(h) not in ht:
                continue
            blk = ht[str(h)]
            for sp in ("dev", "validation"):
                r = blk[sp]
                tr = r.get("threshold_region")
                s_tr = (f" | region p~{tr['threshold']}: n={tr['n_region']} "
                        f"conf={tr['conf_region']} acc={tr['acc_region']} "
                        f"diff={tr['diff_region']}") if tr and tr.get("n_region") else ""
                print(f"{tgt:14s} h={h:>2} {sp:10s} n={r['n']:>7} "
                      f"ECE10={r['ece10']} ECE20={r['ece20']} Brier={r['brier']}{s_tr}",
                      file=sys.stderr)


if __name__ == "__main__":
    main()