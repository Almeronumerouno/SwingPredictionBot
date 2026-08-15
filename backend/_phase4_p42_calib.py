"""
_phase4_p42_calib.py — P4.2: Calibration-in-the-large + calibration slope.

Regresi calibration: logit(y) = a0 + a1*logit(p_hat), di-fit pada observasi
non-censored, per target x horizon, pada DEV dan VALIDATION (protocol frozen).

  a0 (intercept) ideal 0 : overall over/underestimate
  a1 (slope)     ideal 1 : slope<1 -> prediksi terlalu ekstrem; slope>1 -> moderat
  95% CI dari Hessian (asymptotic); CI bootstrap stock-cluster di P4.5.
  E/O & O/E ratio dilaporkan.

Output: data/phase4_p42_calib.json
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


def _split(date: np.ndarray, h: int):
    dev = (date <= CUTOFF_DT) & (date + np.timedelta64(h, "D") <= CUTOFF_DT)
    val = date > EMBARGO_DT
    return dev, val


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def _calib_fit(p: np.ndarray, y: np.ndarray) -> dict:
    y = y.astype(float)
    obs = np.isfinite(y)
    p, y = p[obs], y[obs]
    n = int(len(y))
    if n == 0:
        return {"n": 0}
    if len(set(y.tolist())) < 2:
        return {"n": n, "note": "y konstan — slope tidak dapat diidentifikasi"}
    lp = _logit(p)
    X = np.column_stack([np.ones(n), lp])
    beta = np.zeros(2)
    for _ in range(50):
        mu = 1.0 / (1.0 + np.exp(-(X @ beta)))
        mu = np.clip(mu, EPS, 1.0 - EPS)
        w = mu * (1.0 - mu)
        XWX = X.T @ (X * w[:, None])
        try:
            XWX_inv = np.linalg.inv(XWX)
        except np.linalg.LinAlgError:
            return {"n": n, "note": "singular — slope tidak dapat diidentifikasi"}
        step = XWX_inv @ (X.T @ (y - mu))
        beta_new = beta + step
        if np.max(np.abs(step)) < 1e-9:
            beta = beta_new
            break
        beta = beta_new
    mu = 1.0 / (1.0 + np.exp(-(X @ beta)))
    w = mu * (1.0 - mu)
    XWX = X.T @ (X * w[:, None])
    try:
        cov = np.linalg.inv(XWX)
    except np.linalg.LinAlgError:
        cov = np.full((2, 2), np.nan)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    z = 1.96
    mean_p = float(p.mean())
    rate = float(y.mean())
    return {
        "n": n,
        "intercept": round(float(beta[0]), 4),
        "slope": round(float(beta[1]), 4),
        "ci_intercept": [round(float(beta[0] - z * se[0]), 4),
                         round(float(beta[0] + z * se[0]), 4)],
        "ci_slope": [round(float(beta[1] - z * se[1]), 4),
                     round(float(beta[1] + z * se[1]), 4)],
        "mean_p": round(mean_p, 4),
        "observed_rate": round(rate, 4),
        "O_over_E": round(rate / mean_p, 3) if mean_p > 0 else None,
    }


def main() -> None:
    data = D.load()
    result = {"phase": "P4.2 — Global calibration (intercept & slope)",
              "method": "fit logit(y)=a0+a1*logit(p_hat); CI asymptotic (Hessian); "
                        "CI bootstrap stock-cluster di P4.5",
              "targets": {}}
    for tgt in ("previous_close", "prior_peak"):
        ht = {}
        for h in HORIZONS:
            try:
                blk = D.get(tgt, h, data)
            except KeyError:
                continue
            dev, val = _split(blk["date"], h)
            ht[str(h)] = {
                "dev": _calib_fit(blk["p"][dev], blk["y"][dev]),
                "validation": _calib_fit(blk["p"][val], blk["y"][val]),
                "n_gap": int((~dev & ~val).sum()),
            }
        result["targets"][tgt] = ht
    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(r"data\phase4_p42_calib.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
    print("[ok] data/phase4_p42_calib.json", file=sys.stderr)

    print("=== P4.2 global calibration (intercept[95%CI] | slope[95%CI] | O/E) ===",
          file=sys.stderr)
    for tgt, ht in result["targets"].items():
        for h in HORIZONS:
            if str(h) not in ht:
                continue
            for sp in ("dev", "validation"):
                r = ht[str(h)].get(sp)
                if not r or "slope" not in r:
                    print(f"{tgt:14s} h={h:>2} {sp:10s} n=0", file=sys.stderr)
                    continue
                print(f"{tgt:14s} h={h:>2} {sp:10s} n={r['n']:>7} "
                      f"int={r['intercept']}[{r['ci_intercept'][0]},{r['ci_intercept'][1]}] "
                      f"slope={r['slope']}[{r['ci_slope'][0]},{r['ci_slope'][1]}] "
                      f"O/E={r['O_over_E']}", file=sys.stderr)


if __name__ == "__main__":
    main()