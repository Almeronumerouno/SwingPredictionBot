"""
_phase4_p45_uncertainty.py — P4.5: Uncertainty via bootstrap CI.

Per target x horizon, pada DEV & VALIDATION:
  - Metrik: O/E, Brier, BSS (vs climatology dev), intercept & slope calibration
  - PRIMARY : stock-cluster bootstrap, B=1000, seed=42 (sampel kode dgn
              replacement, ambil seluruh observasinya; TANPA refit model)
  - SENSITIVITY : date-block bootstrap, B=500, seed=7 (block 10 hari kalender)

CI = 2.5/97.5 persentil. Output: data/phase4_p45_uncertainty.json
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
B_CLUSTER, SEED_CLUSTER = 1000, 42
B_DATE, SEED_DATE = 500, 7
BLOCK_DAYS = 10


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def _calib_fast(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    lp = _logit(p)
    X = np.column_stack([np.ones(len(p)), lp])
    beta = np.zeros(2)
    for _ in range(60):
        mu = np.clip(1.0 / (1.0 + np.exp(-(X @ beta))), EPS, 1.0 - EPS)
        w = mu * (1.0 - mu)
        XWX = X.T @ (X * w[:, None])
        try:
            step = np.linalg.solve(XWX, X.T @ (y - mu))
        except np.linalg.LinAlgError:
            return (float("nan"), float("nan"))
        beta += step
        if np.max(np.abs(step)) < 1e-9:
            break
    return float(beta[0]), float(beta[1])


def _stats(p: np.ndarray, y: np.ndarray, p_ref: float) -> dict:
    n = len(p)
    brier = float(np.mean((p - y) ** 2))
    brier_ref = float(np.mean((p_ref - y) ** 2))
    bss = 1.0 - brier / brier_ref if brier_ref > 0 else float("nan")
    a0, a1 = _calib_fast(p, y)
    return {
        "n": n,
        "O_over_E": round(float(y.mean() / p.mean()), 3) if p.mean() > 0 else None,
        "brier": brier,
        "bss": bss,
        "intercept": a0,
        "slope": a1,
    }


def _ci(values: list[float]) -> list[float]:
    arr = np.asarray(values)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [float("nan"), float("nan")]
    return [round(float(np.percentile(arr, 2.5)), 4),
            round(float(np.percentile(arr, 97.5)), 4)]


def _cluster_ci(p, y, code, p_ref, b, seed):
    codes = np.unique(code)
    rng = np.random.default_rng(seed)
    out = {k: [] for k in ("oe", "brier", "bss", "intercept", "slope")}
    for _ in range(b):
        pick = rng.choice(codes, size=len(codes), replace=True)
        idx = np.concatenate([np.where(code == c)[0] for c in pick])
        if len(idx) == 0:
            continue
        s = _stats(p[idx], y[idx], p_ref)
        out["oe"].append(s["O_over_E"] if s["O_over_E"] is not None else float("nan"))
        out["brier"].append(s["brier"])
        out["bss"].append(s["bss"])
        out["intercept"].append(s["intercept"])
        out["slope"].append(s["slope"])
    return {k: _ci(v) for k, v in out.items()}


def _dateblock_ci(p, y, date, p_ref, b, seed):
    dates = np.unique(date)
    rng = np.random.default_rng(seed)
    # blok tanggal kontigu 10 hari kalender
    blocks = []
    start = dates[0]
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).astype(int) > BLOCK_DAYS:
            blocks.append((start, dates[i - 1]))
            start = dates[i]
    blocks.append((start, dates[-1]))
    out = {k: [] for k in ("oe", "brier", "bss", "intercept", "slope")}
    for _ in range(b):
        pick = [blocks[j] for j in rng.integers(0, len(blocks), size=len(blocks))]
        mask = np.zeros(len(p), dtype=bool)
        for lo, hi in pick:
            mask |= (date >= lo) & (date <= hi)
        if mask.sum() == 0:
            continue
        s = _stats(p[mask], y[mask], p_ref)
        out["oe"].append(s["O_over_E"] if s["O_over_E"] is not None else float("nan"))
        out["brier"].append(s["brier"])
        out["bss"].append(s["bss"])
        out["intercept"].append(s["intercept"])
        out["slope"].append(s["slope"])
    return {k: _ci(v) for k, v in out.items()}


def main() -> None:
    data = D.load()
    result = {"phase": "P4.5 — Uncertainty (bootstrap CI)",
              "primary": f"stock-cluster B={B_CLUSTER} seed={SEED_CLUSTER} (tanpa refit)",
              "sensitivity": f"date-block B={B_DATE} seed={SEED_DATE} block={BLOCK_DAYS}d",
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
            for sp, mask in (("dev", dev), ("validation", val)):
                m = mask & np.isfinite(blk["y"])
                p, y = blk["p"][m], blk["y"][m]
                ht.setdefault(str(h), {})[sp] = {
                    "point": _stats(p, y, p_ref),
                    "ci_cluster": _cluster_ci(p, y, blk["code"][m], p_ref,
                                              B_CLUSTER, SEED_CLUSTER),
                    "ci_dateblock": _dateblock_ci(p, y, blk["date"][m], p_ref,
                                                  B_DATE, SEED_DATE),
                }
        result["targets"][tgt] = ht
    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(r"data\phase4_p45_uncertainty.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
    print("[ok] data/phase4_p45_uncertainty.json", file=sys.stderr)

    print("=== P4.5 CI (cluster [primary] | dateblock) — O/E, BSS, intercept, slope ===",
          file=sys.stderr)
    for tgt, ht in result["targets"].items():
        for h in HORIZONS:
            if str(h) not in ht:
                continue
            for sp in ("dev", "validation"):
                blk = ht[str(h)][sp]
                cc, dc = blk["ci_cluster"], blk["ci_dateblock"]
                print(f"{tgt:14s} h={h:>2} {sp:10s} n={blk['point']['n']:>7} "
                      f"O/E={blk['point']['O_over_E']} [{cc['oe'][0]},{cc['oe'][1]}] "
                      f"BSS={blk['point']['bss']} [{cc['bss'][0]},{cc['bss'][1]}] "
                      f"int={blk['point']['intercept']} [{cc['intercept'][0]},{cc['intercept'][1]}] "
                      f"slope={blk['point']['slope']} [{cc['slope'][0]},{cc['slope'][1]}] | "
                      f"db O/E [{dc['oe'][0]},{dc['oe'][1]}] db BSS [{dc['bss'][0]},{dc['bss'][1]}]",
                      file=sys.stderr)


if __name__ == "__main__":
    main()