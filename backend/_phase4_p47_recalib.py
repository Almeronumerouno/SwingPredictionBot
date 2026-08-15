"""
_phase4_p47_recalib.py — P4.7: Conditional recalibration (hanya bila material).

Material miscalibration terkonfirmasi (P4.1–P4.6): previous_close BSS negatif
robust; prior_peak overestimate validation + deviasi antar regime.

Calibration window : 126 hari TRADING terakhir dari DEV (purged per horizon)
Order             : M0 frozen production (referensi) -> M1 logistic
                    intercept-only -> M2 intercept+slope -> M3 regime-
                    conditional intercept (slope=1) ; M4 isotonic (SENSITIVITY
                    only, bukan kandidat produksi).
Evaluasi          : VALIDATION (bukan holdout). Holdout final TIDAK dipakai
                    utk seleksi.
Keputusan         : pilih transformasi yang menurunkan Brier/ECE & membawa
                    O/E mendekati 1 di validation; rekomendasi per target x h.

Output: data/phase4_p47_recalib.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.isotonic import IsotonicRegression

import _phase4_data as D
from _calibrate_recovery_model import HORIZONS

CUTOFF_DT = np.datetime64("2026-01-23")
EMBARGO_DT = np.datetime64("2026-04-23")
EPS = 1e-6
CAL_DAYS = 126
N_BIN = 10


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


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


def _fit_intercept_only(lp: np.ndarray, y: np.ndarray) -> float:
    c = 0.0
    for _ in range(100):
        mu = np.clip(1.0 / (1.0 + np.exp(-(c + lp))), EPS, 1.0 - EPS)
        w = mu * (1.0 - mu)
        grad = np.sum(y - mu)
        hess = -np.sum(w)
        step = -grad / hess if hess < 0 else 0.0
        c += step
        if abs(step) < 1e-9:
            break
    return float(c)


def _fit_slope_intercept(lp: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    X = np.column_stack([np.ones(len(y)), lp])
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


def _eval(p: np.ndarray, y: np.ndarray, p_ref: float) -> dict:
    n = len(p)
    brier = float(np.mean((p - y) ** 2))
    brier_ref = float(np.mean((p_ref - y) ** 2))
    bss = 1.0 - brier / brier_ref if brier_ref > 0 else None
    return {
        "n": n,
        "O_over_E": round(float(y.mean() / p.mean()), 3) if p.mean() > 0 else None,
        "brier": round(brier, 5),
        "bss": round(bss, 4) if bss is not None else None,
        "ece10": _ece(p, y, N_BIN),
        "mean_p": round(float(p.mean()), 4),
        "rate": round(float(y.mean()), 4),
    }


def main() -> None:
    data = D.load()
    result = {"phase": "P4.7 — Conditional recalibration",
              "cal_window": f"{CAL_DAYS} trading days terakhir DEV (purged)",
              "order": "M0 frozen -> M1 intercept-only -> M2 intercept+slope -> "
                       "M3 regime-conditional intercept (slope=1) | M4 isotonic (sensitivity)",
              "eval": "VALIDATION (holdout final TIDAK dipakai untuk seleksi)",
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
            m_dev = dev & np.isfinite(blk["y"])
            m_val = val & np.isfinite(blk["y"])
            p_dev, y_dev = blk["p"][m_dev], blk["y"][m_dev]
            p_val, y_val = blk["p"][m_val], blk["y"][m_val]
            if len(p_dev) == 0 or len(p_val) == 0:
                continue
            p_ref = float(y_dev.mean())
            # calibration window: 126 hari trading terakhir dev
            dates_dev = np.unique(blk["date"][m_dev])
            cal_cut = dates_dev[-CAL_DAYS] if len(dates_dev) >= CAL_DAYS else dates_dev[0]
            m_cal = m_dev & (blk["date"] >= cal_cut)
            p_cal, y_cal = blk["p"][m_cal], blk["y"][m_cal]
            lp_cal, lp_val = _logit(p_cal), _logit(p_val)
            evals = {}
            evals["M0_frozen"] = _eval(p_val, y_val, p_ref)
            c1 = _fit_intercept_only(lp_cal, y_cal)
            evals["M1_intercept"] = {
                **_eval(1.0 / (1.0 + np.exp(-(c1 + lp_val))), y_val, p_ref),
                "params": {"c": round(c1, 4)}}
            a0, a1 = _fit_slope_intercept(lp_cal, y_cal)
            evals["M2_intercept_slope"] = {
                **_eval(1.0 / (1.0 + np.exp(-(a0 + a1 * lp_val))), y_val, p_ref),
                "params": {"a0": round(a0, 4), "a1": round(a1, 4)}}
            # M3: intercept per regime (slope=1)
            c_by_reg = {}
            p_m3 = np.empty_like(p_val)
            for rg in (0, 1, 2):
                m_r = m_cal & (blk["regime"] == rg)
                p_r, y_r = blk["p"][m_r], blk["y"][m_r]
                c_r = _fit_intercept_only(_logit(p_r), y_r) if len(p_r) > 50 else 0.0
                c_by_reg[rg] = round(c_r, 4)
                m_vr = blk["regime"][m_val] == rg
                p_m3[m_vr] = 1.0 / (1.0 + np.exp(-(c_r + lp_val[m_vr])))
            evals["M3_regime_intercept"] = {
                **_eval(p_m3, y_val, p_ref),
                "params": {str(k): v for k, v in c_by_reg.items()}}
            # M4: isotonic (sensitivity only)
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            iso.fit(p_cal, y_cal)
            evals["M4_isotonic"] = _eval(iso.predict(p_val), y_val, p_ref)
            # pilih: Brier terendah di validation (bukan holdout)
            best = min(evals, key=lambda k: evals[k]["brier"])
            rec = f"{best}: brier={evals[best]['brier']} O/E={evals[best]['O_over_E']}"
            ht[str(h)] = {
                "n_cal": int(len(p_cal)), "n_val": int(len(p_val)),
                "cal_window_start": str(cal_cut),
                "p_ref_dev_climatology": round(p_ref, 4),
                "models": evals, "selected_on_validation": best,
                "recommendation": rec,
            }
        result["targets"][tgt] = ht
    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(r"data\phase4_p47_recalib.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
    print("[ok] data/phase4_p47_recalib.json", file=sys.stderr)

    print("=== P4.7 validation — Brier (O/E) [ECE] per transformasi ===", file=sys.stderr)
    for tgt, ht in result["targets"].items():
        for h in HORIZONS:
            if str(h) not in ht:
                continue
            blk = ht[str(h)]
            row = f"{tgt:14s} h={h:>2} n_cal={blk['n_cal']:>6} |"
            for k in ("M0_frozen", "M1_intercept", "M2_intercept_slope",
                      "M3_regime_intercept", "M4_isotonic"):
                r = blk["models"].get(k)
                if not r:
                    continue
                row += f" {k.split('_')[0]}: B={r['brier']} O/E={r['O_over_E']} "
                row += f"[{r['ece10']}] |"
            print(row + f" -> pilih {blk['selected_on_validation']}", file=sys.stderr)


if __name__ == "__main__":
    main()