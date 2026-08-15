"""
_phase6_p69_recalib.py — P6.9: Re-freeze Probability Quality Candidate (pasca-switch params P6).

Konteks (keputusan user, 15-08-2026):
  - params produksi recovery_model_params.json DI-SWITCH ke params P6 (split
    global kronologis + purge + embargo; lama = position-based/leaky).
  - M1 candidate lama (P4.7, di-freeze 15-08) diturunkan dari probability
    layer pre-P6 -> TIDAK valid utk P6. Harus di-re-evaluate di atas layer baru.
  - Holdout P4.8 TIDAK dibuka; ini re-freeze methodology SEBELUM holdout.

Desain (konsisten dgn P4.7, tapi dgn kerangka P6):
  - DEV  = observasi dgn date_s + ceil(h*1.5) + embargo(5 hari kalender) <= cutoff
           (rule ketat ala P6.1; margin 1.5x = hari kalender per h bar, konservatif)
  - VAL  = test bersih P6: date_s >= cutoff (2025-11-24) — window yang TIDAK
           dipakai utk fit params (evaluation set, bukan holdout).
  - Calibration window = 126 hari trading terakhir DEV (purged) — sama P4.7.
  - Transformasi: M0 raw -> M1 intercept-only (slope=1) -> M2 slope+intercept
    (sensitivity, BUKAN kandidat produksi; konsisten P4.7).
  - BSS ref = frozen_base_rate_reference di phase4_holdout_config.json
    (DILARANG memakai prevalence VAL sebagai reference — aturan P4.8).
  - Diagnostic Case A/B/C (per user):
      Case A: slope_val ~ 1 & intercept_val ~ 0  -> M0 P6 raw acceptable
      Case B: intercept_val != 0                  -> uji M1 intercept-only
      Case C: recalibration membuat p_min 0.68 jenuh (saturation) -> jangan promote
  - Keputusan rekomendasi: pilih M1 HANYA bila Brier_M1 < Brier_M0 di VAL dan
    O/E_M1 lebih dekat ke 1; laporkan Case C (fraction p>=0.68) utk transparansi.

Output: data/phase6_p69_recalib.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

import _phase4_data as D
from _calibrate_recovery_model import HORIZONS

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HOLDOUT_CFG = os.path.join(DATA_DIR, "phase4_holdout_config.json")
OUT_PATH = os.path.join(DATA_DIR, "phase6_p69_recalib.json")

CUTOFF_DT = np.datetime64("2025-11-24")   # cutoff P6.1 (params P6)
EMBARGO_DAYS = 5                          # hari kalender, sama dgn P6.1
EPS = 1e-6
CAL_DAYS = 126                            # sama dgn P4.7
N_BIN = 10
P_MIN = 0.68                              # gate produksi (frozen)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def _fit_intercept_only(lp: np.ndarray, y: np.ndarray) -> float:
    """IRLS: logit(p) = c + 1*lp (slope FIXED = 1)."""
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
    """IRLS penuh: logit(p) = a0 + a1*lp."""
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


def _metrics(p: np.ndarray, y: np.ndarray, p_ref: float) -> dict:
    n = len(p)
    brier = float(np.mean((p - y) ** 2))
    brier_ref = float(np.mean((p_ref - y) ** 2))
    bss = 1.0 - brier / brier_ref if brier_ref > 0 else None
    pc = np.clip(p, EPS, 1.0 - EPS)
    logloss = float(-np.mean(y * np.log(pc) + (1.0 - y) * np.log(1.0 - pc)))
    return {
        "n": int(n),
        "O_over_E": round(float(y.mean() / p.mean()), 4) if p.mean() > 0 else None,
        "brier": round(brier, 5),
        "bss": round(bss, 4) if bss is not None else None,
        "logloss": round(logloss, 5),
        "ece10": _ece(p, y, N_BIN),
        "mean_p": round(float(p.mean()), 5),
        "rate": round(float(y.mean()), 5),
        "sat68": round(float(np.mean(p >= P_MIN)), 5),  # Case C: saturation p_min
    }


def _dev_mask(date: np.ndarray, h: int) -> np.ndarray:
    """Rule P6.1 ketat (konservatif): date_s + ceil(h*1.5) + embargo <= cutoff.
    h bar ~ 1.45-1.5 hari kalender/bar -> margin anti-leak utk label window."""
    span = int(np.ceil(h * 1.5)) + EMBARGO_DAYS
    return date + np.timedelta64(span, "D") <= CUTOFF_DT


def main() -> None:
    data = D.load()
    with open(HOLDOUT_CFG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    refs = cfg["frozen_base_rate_reference"]

    result = {
        "phase": "P6.9 - re-freeze probability quality candidate (pasca-switch params P6)",
        "params_source": "recovery_model_params.json = params P6 (hash baru, lihat holdout config)",
        "split": {
            "cutoff": str(CUTOFF_DT),
            "dev_rule": "date_s + ceil(h*1.5) + 5 hari kalender <= cutoff (rule P6.1, konservatif)",
            "val": "date_s >= cutoff (test bersih P6 - evaluation set, BUKAN holdout)",
            "cal_window": f"{CAL_DAYS} hari trading terakhir DEV (purged)",
        },
        "bss_ref": "frozen_base_rate_reference (phase4_holdout_config.json) - bukan prevalence VAL",
        "case_def": {
            "A": "slope_val~1 & intercept_val~0 -> M0 raw acceptable",
            "B": "intercept_val != 0 -> uji M1 intercept-only",
            "C": "recalibration jenuhkan p_min 0.68 -> jangan promote",
        },
        "targets": {},
    }

    for tgt in ("previous_close", "prior_peak"):
        ht = {}
        for h in HORIZONS:
            try:
                blk = D.get(tgt, h, data)
            except KeyError:
                continue
            p_all = np.asarray(blk["p"], dtype=float)
            y_all = np.asarray(blk["y"], dtype=float)
            date = np.asarray(blk["date"], dtype="datetime64[D]")
            m_ok = np.isfinite(y_all) & (date != np.datetime64("NaT"))
            p_all, y_all, date = p_all[m_ok], y_all[m_ok], date[m_ok]
            if len(p_all) == 0:
                continue

            dev = _dev_mask(date, h)
            val = date >= CUTOFF_DT
            # pastikan DEV dan VAL TIDAK overlap (purge sisa)
            p_dev, y_dev, d_dev = p_all[dev], y_all[dev], date[dev]
            p_val, y_val, d_val = p_all[val], y_all[val], date[val]
            if len(p_dev) == 0 or len(p_val) == 0:
                continue
            p_ref = float(refs.get(tgt, {}).get(str(h), float(y_dev.mean())))

            # calibration window: 126 hari trading terakhir DEV
            dates_dev = np.unique(d_dev)
            cal_cut = dates_dev[-CAL_DAYS] if len(dates_dev) >= CAL_DAYS else dates_dev[0]
            m_cal = dev & (date >= cal_cut)
            p_cal, y_cal = p_all[m_cal], y_all[m_cal]
            lp_cal, lp_val = _logit(p_cal), _logit(p_val)

            evals = {"M0_raw": _metrics(p_val, y_val, p_ref)}
            c1 = _fit_intercept_only(lp_cal, y_cal)
            p_m1 = 1.0 / (1.0 + np.exp(-(c1 + lp_val)))
            evals["M1_intercept"] = {
                **_metrics(p_m1, y_val, p_ref),
                "params": {"c": round(c1, 4)},
            }
            a0, a1 = _fit_slope_intercept(lp_cal, y_cal)
            p_m2 = 1.0 / (1.0 + np.exp(-(a0 + a1 * lp_val)))
            evals["M2_intercept_slope"] = {
                **_metrics(p_m2, y_val, p_ref),
                "params": {"a0": round(a0, 4), "a1": round(a1, 4)},
            }

            # Diagnostic di VAL (BUKAN utk seleksi - hanya klasifikasi Case)
            a0_v, a1_v = _fit_slope_intercept(lp_val, y_val)

            # Case logic
            cases = []
            if abs(a0_v) < 0.1 and abs(a1_v - 1.0) < 0.1:
                cases.append("A")
            if abs(a0_v) >= 0.1:
                cases.append("B")
            cases.append("C-check")
            sat_m0 = evals["M0_raw"]["sat68"]
            sat_m1 = evals["M1_intercept"]["sat68"]
            case_c = bool(sat_m1 > sat_m0 + 0.01 and sat_m1 > 0.05)

            # rekomendasi freeze: M1 hanya bila Brier turun & O/E lebih dekat 1
            b0, b1 = evals["M0_raw"]["brier"], evals["M1_intercept"]["brier"]
            oe0, oe1 = evals["M0_raw"]["O_over_E"], evals["M1_intercept"]["O_over_E"]
            oe_dist0 = abs(1.0 - oe0) if oe0 is not None else 1e9
            oe_dist1 = abs(1.0 - oe1) if oe1 is not None else 1e9
            m1_justified = (b1 < b0) and (oe_dist1 < oe_dist0) and not case_c
            rec = "M1 (intercept-only, c baru)" if m1_justified else "M0 raw (P6)"

            ht[str(h)] = {
                "n_dev": int(len(p_dev)), "n_cal": int(len(p_cal)),
                "n_val": int(len(p_val)),
                "cal_window_start": str(cal_cut),
                "p_ref_frozen": round(p_ref, 4),
                "models": evals,
                "diag_val": {"a0": round(a0_v, 4), "a1": round(a1_v, 4)},
                "cases": cases,
                "case_C_saturation_flagged": case_c,
                "m1_justified": bool(m1_justified),
                "recommendation": rec,
            }
        result["targets"][tgt] = ht

    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(f"[ok] {OUT_PATH}")

    print("\n=== P6.9 VAL (test bersih P6) — Brier (O/E) [ECE10] sat68 ===")
    print(f"{'target':<14s} {'h':>3} {'n_val':>8} | {'M0':>10} {'M1':>10} "
          f"{'M2(sens)':>10} | diag a0/a1 | case | freeze")
    for tgt, ht in result["targets"].items():
        for h in HORIZONS:
            if str(h) not in ht:
                continue
            blk = ht[str(h)]
            m0, m1, m2 = blk["models"]["M0_raw"], blk["models"]["M1_intercept"], \
                blk["models"]["M2_intercept_slope"]
            a0v, a1v = blk["diag_val"]["a0"], blk["diag_val"]["a1"]
            print(f"{tgt:<14s} h={h:>2} {blk['n_val']:>8,} | "
                  f"{m0['brier']:.4f}/{m0['O_over_E']:.2f} "
                  f"{m1['brier']:.4f}/{m1['O_over_E']:.2f} "
                  f"{m2['brier']:.4f}/{m2['O_over_E']:.2f} | "
                  f"{a0v:+.2f}/{a1v:.2f} | {','.join(blk['cases'])} | {blk['recommendation']}")


if __name__ == "__main__":
    sys.exit(main())