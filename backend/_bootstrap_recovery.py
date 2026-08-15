"""
_bootstrap_recovery.py — MED#6 + VALID#7: bootstrap stability & stress
bull/bear utk model recovery (logistic drawdown, h=21).

1. Bootstrap stability: resample SAHAM (bukan bar) B kali, fit ulang
   logistic, distribusi (a, b, P(dd=0.30)). Bandingkan CI bootstrap vs
   SE delta-method (a_se/b_se) yang dipakai produksi (ROMBAK#3) — kalau
   cocok, CI produksi valid.
2. Stress regime: split temporal paruh-1 vs paruh-2 (per saham), fit di
   satu paruh, evaluasi di paruh lain (AUC + kalibrasi bucket). Kalau
   transferabilitas rendah => pertimbangkan parameter terpisah per regime.
"""

from __future__ import annotations

import sys
import time

import numpy as np

from _calibrate_recovery_model import _collect_rows, NPZ_PATH

PEAK_LOOKBACK = 252
H = 21
B = 40
SEED = 42
TRAIN_FRAC = 0.7


def _logistic(dd, y):
    """Fit logistic, return (a, b). None kalau gak fit."""
    from sklearn.linear_model import LogisticRegression
    if len(dd) < 50 or len(np.unique(y)) < 2:
        return None
    clf = LogisticRegression(penalty=None, max_iter=5000)
    clf.fit(dd.reshape(-1, 1), y)
    return float(clf.intercept_[0]), float(clf.coef_[0][0])


def _auc(y, p):
    from sklearn.metrics import roc_auc_score
    try:
        return roc_auc_score(y, p)
    except ValueError:
        return None


def main() -> None:
    d = np.load(NPZ_PATH)
    rows, lens = d["rows"], d["lens"]
    print(f"Dataset: {len(lens)} kode", flush=True)

    t0 = time.time()
    collected = _collect_rows(rows, lens, PEAK_LOOKBACK)
    dd = collected[H]["dd"]
    y = collected[H]["y"]
    pos = collected[H]["pos"]
    print(f"Koleksi observasi h={H}: n={len(dd):,} pos={y.sum():,} "
          f"({time.time()-t0:.0f}s)", flush=True)

    # ---- bootstrap per saham ----
    # petakan pos -> kode (pos adalah indeks bar global; lens utk mapping)
    code_of_pos = np.empty(len(pos), dtype=int)
    base = 0
    n_codes = len(lens)
    for c in range(n_codes):
        m = int(lens[c])
        code_of_pos[base:base + m] = c
        base += m

    rng = np.random.default_rng(SEED)
    boot_a, boot_b, boot_p3 = [], [], []
    codes = np.arange(n_codes)
    for b in range(B):
        pick = rng.choice(codes, size=n_codes, replace=True)
        mask = np.isin(code_of_pos, pick)
        ab = _logistic(dd[mask], y[mask])
        if ab is None:
            continue
        a, bb = ab
        boot_a.append(a)
        boot_b.append(bb)
        boot_p3.append(1.0 / (1.0 + np.exp(-(a + bb * 0.30))))
    boot_a = np.array(boot_a)
    boot_b = np.array(boot_b)
    boot_p3 = np.array(boot_p3)

    print(f"\nBootstrap {len(boot_a)}/{B} fit valid (resample saham):")
    for name, arr in (("a", boot_a), ("b", boot_b), ("P(dd=0.30)", boot_p3)):
        lo, hi = np.percentile(arr, 5), np.percentile(arr, 95)
        print(f"  {name:<10} mean={arr.mean():.4f}  CI90 bootstrap=({lo:.4f}, {hi:.4f})  "
              f"range={hi-lo:.4f}")

    # bandingkan dgn SE delta method dari produksi (json)
    import json, os
    jp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "data", "recovery_model_params.json")
    with open(jp, encoding="utf-8") as f:
        params = json.load(f)
    r21 = params["horizons"][str(H)]
    print(f"\nBanding SE delta-method produksi (a_se={r21['a_se']}, "
          f"b_se={r21['b_se']}) vs SD bootstrap "
          f"(a={boot_a.std():.4f}, b={boot_b.std():.4f}):")
    print("  delta SD / bootstrap SD -> a:", r21["a_se"] / boot_a.std(),
          " b:", r21["b_se"] / boot_b.std())

    # ---- stress bull/bear: paruh-1 vs paruh-2 per saham ----
    # observasi dikelompokkan per saham, paruh berdasarkan posisi bar
    half = np.empty(len(dd), dtype=int)
    base = 0
    for c in range(n_codes):
        m = int(lens[c])
        mid = base + m // 2
        half[base:base + m] = np.where(pos[base:base + m] < mid, 0, 1)
        base += m

    print(f"\nStress regime (split paruh waktu per saham):")
    print(f"{'fit':<10}{'eval':<10}{'n':>9}{'n_pos':>8}{'rec%':>7}{'AUC':>8} "
          f"{'P(0.3)':>8}  kalibrasi bucket 0.15-0.25 / 0.40-0.60")
    for fit_h, ev_h in ((0, 1), (1, 0)):
        mfit = half == fit_h
        mev = half == ev_h
        ab = _logistic(dd[mfit], y[mfit])
        if ab is None:
            continue
        a, bb = ab
        p_ev = 1.0 / (1.0 + np.exp(-(a + bb * dd[mev])))
        auc = _auc(y[mev], p_ev)
        rate = y[mev].mean()
        p3 = 1.0 / (1.0 + np.exp(-(a + bb * 0.30)))
        cal = []
        for lo, hi in ((0.15, 0.25), (0.40, 0.60)):
            mm = (dd[mev] >= lo) & (dd[mev] < hi)
            if mm.sum() >= 100:
                cal.append(f"{y[mev][mm].mean():.3f}/{p_ev[mm].mean():.3f}")
            else:
                cal.append("-")
        print(f"{'P1' if fit_h==0 else 'P2':<10}{'P2' if ev_h==1 else 'P1':<10}"
              f"{int(mev.sum()):>9,}{int(y[mev].sum()):>8,}{rate*100:>6.1f}%"
              f"{str(round(auc,4) if auc else None):>8}{p3:>8.3f}   {cal[0]}  {cal[1]}")


if __name__ == "__main__":
    sys.exit(main())


# ─────────────────────────────────────────────────────────────
# HASIL (Agu 2026, 963 kode, h=21, bootstrap saham B=40):
#   a:     mean 0.7348,  CI90 (0.6582, 0.8182),  SD 0.0499
#   b:     mean -9.651,  CI90 (-10.03, -9.248),  SD 0.2312
#   P(0.3):mean 0.1034,  CI90 (0.0974, 0.1088)   <- stabil, sempit
#
#   1. CI delta-method bar-level (a_se=0.0128, b_se=0.0638) = 3.6-3.9x
#      TERLALU SEMPIT vs bootstrap saham (bar per saham berkorelasi,
#      n_eff jauh < n_bar). => faktor skala ci_bootstrap scale_a/scale_b
#      (3.89 / 3.62) sudah diterapkan di recovery_model_probs().
#
# Stress regime (paruh waktu per saham; P1 = paruh awal, P2 = paruh akhir):
#   fit P1 -> eval P2: n=398, rec 32.9%, AUC 0.803  (P2 sedikit observasi
#                       krn window 252 memakan paruh saham pendek)
#   fit P2 -> eval P1: n=256k, rec 19.2%, AUC 0.827, P(0.3)=0.015
#      kalibrasi bucket P1 (aktual/pred): 0.15-0.25 -> 0.200/0.089,
#      0.40-0.60 -> 0.030/0.001  (UNDER-prediksi besar)
#
#   => 1) Model global condong ke regime terbaru (dataset 3.5 th: awal
#         bearish, akhir lebih bull) — P(recover) paruh awal di-under-
#         prediksi hingga ~10-30x di bucket dalam. JANGAN interpretasi
#         P sebagai probabilitas abadi; utk keputusan besar, bandingkan
#         base-rate per saham (empirical_base_rates) yg point-in-time.
#      2) AUC transfer antar paruh 0.80-0.83 = ranking stabil; kalibrasi
#         level yang beda. (VALID#7: dijawab — ranking OK, level regime-
#         sensitive; bobot terpisah per regime belum layak utk sekarang.)
# ─────────────────────────────────────────────────────────────