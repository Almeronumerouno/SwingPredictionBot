"""
_calibrate_recovery_model.py — Kalibrasi model recovery EMPIRIS pengganti GBM.

!!! LEGACY / NOT FOR PRODUCTION (P7.4, 16-08-2026) !!!
Script ini adalah kalibrator LAMA (methodology pre-P6). Production params
(data/recovery_model_params.json) HANYA boleh ditulis oleh calibrator yang
telah disetujui: _phase6_p61_calibrate.py (protocol frozen P6: split global
kronologis cutoff 70% tanggal + purge label-overlap + embargo 5 hari
kalender; provenance wajib).
Untuk mencegah overwrite tidak sengaja: script ini MENOLAK menulis ke
recovery_model_params.json kecuali dijalankan dgn --allow-prod-write
(tidak disarankan; hanya untuk audit/rollback eksplisit oleh lead).

Model:
    P_recover(dd_fraction, t) = 1 / (1 + exp(a_t + b_t * dd_fraction))
    dd_fraction = 1 - (harga_trough / prior_peak)

Definisi (keputusan desain — terdokumentasi di config.py & README):
  - Target recovery  : prior high ("par") = max(close) trailing
                        RECOVERY_PEAK_LOOKBACK_DAYS (252) hari trading.
  - Horizon          : per-horizon terpisah [1,3,5,10,21,42,63] hari trading —
                        tidak ada "tanpa batas waktu" (bias ke 1).
  - Event per hari   : SETIAP hari yang sedang dalam drawdown (close < peak)
                        adalah satu observasi (point-in-time, tanpa lookahead).
  - Outcome          : max(high[i+1..i+h]) >= peak[i] (disentuh, konsisten
                        definisi first-passage). Censored bila window tidak penuh.
  - Split temporal   : 70% tanggal awal = train, 30% akhir = test (OOS).
  - Basis harga      : close/high MENTAH (konsisten jalur produksi recovery.py
                        yang memakai b.close raw). Varian adjusted dilaporkan
                        sebagai robustness check.

Output:
  data/recovery_model_params.json — param a_t, b_t per horizon + base-rate table
  Laporan stdout                  — n, recovery rate, AUC/Brier OOS per horizon,
                                    tabel base-rate per bucket dd.

Usage:
    python _calibrate_recovery_model.py                     # laporan SAJA (menolak tulis prod)
    python _calibrate_recovery_model.py --out <path>        # simpan ke path lain
    python _calibrate_recovery_model.py --allow-prod-write  # TIDAK disarankan
    python _calibrate_recovery_model.py --peak-lookback 126  # sensitivitas window
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from scipy.stats import norm

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
PARAMS_PATH = os.path.join(DATA_DIR, "recovery_model_params.json")

HORIZONS = (1, 3, 5, 10, 21, 42, 63)          # hari trading
DD_BUCKETS = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.15),
              (0.15, 0.25), (0.25, 0.40), (0.40, 0.60), (0.60, 0.85)]
DD_CLAMP_MAX = 0.85
TRAIN_FRAC = 0.70


def _trailing_peak(close: np.ndarray, window: int) -> np.ndarray:
    """peak[i] = max(close[i-window+1 .. i]); NaN untuk i < window-1."""
    n = len(close)
    out = np.full(n, np.nan)
    if n < window:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    sw = sliding_window_view(close, window)          # (n-window+1, window)
    peak = sw.max(axis=1)
    out[window - 1:] = peak
    return out


def _collect_rows(rows: np.ndarray, lens: np.ndarray,
                  window: int,
                  dates_list: np.ndarray | None = None) -> dict[int, dict]:
    """Per-horizon: kumpulkan (dd_fraction, y) semua saham, point-in-time.

    Menggunakan seri RAW (kolom 3 = close_raw, kolom 1 = high).
    Hasil: {h: {"dd", "y", "pos", "code", "date_s", "date_e"}}
      pos     = indeks bar observasi (split berbasis posisi, kompatibel lama)
      code    = indeks kode utk tiap observasi
      date_s  = tanggal bar observasi (start event), datetime64[D]
      date_e  = tanggal bar POS + h (bar terakhir label), datetime64[D]
    date_s/date_e hanya terisi bila dates_list diberikan (len==lens), dipakai
    utk purge/embargo temporal (F2.1). Tanpa dates_list -> array kosong.
    """
    n_codes = len(lens)
    out: dict[int, dict] = {h: {"dd": [], "y": [], "pos": [], "code": [],
                                "date_s": [], "date_e": []} for h in HORIZONS}
    for c in range(n_codes):
        m = int(lens[c])
        if m < window + max(HORIZONS) + 5:
            continue
        dt = None
        if dates_list is not None and c < len(dates_list):
            dl = dates_list[c]
            if dl is not None and len(dl) == m:
                dt = np.asarray(dl, dtype="datetime64[D]")
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        peak = _trailing_peak(close, window)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.clip(1.0 - close / peak, 0.0, DD_CLAMP_MAX)
        valid = np.isfinite(dd) & (dd > 0.0)
        idx = np.where(valid)[0]
        if len(idx) == 0:
            continue
        for h in HORIZONS:
            end = idx + 1 + h
            ok_h = end <= m - 1
            i_h = idx[ok_h]
            if len(i_h) == 0:
                continue
            # max(high[i+1 .. i+h]) per observasi — loop numpy murah per saham
            fmax_h = np.zeros(len(i_h))
            for j, i0 in enumerate(i_h):
                fmax_h[j] = high[i0 + 1:i0 + h + 1].max()
            y = (fmax_h >= peak[i_h]).astype(float)
            out[h]["dd"].append(dd[i_h])
            out[h]["y"].append(y)
            out[h]["pos"].append(i_h)
            out[h]["code"].append(np.full(len(i_h), c, dtype=np.int32))
            if dt is not None:
                out[h]["date_s"].append(dt[i_h])
                out[h]["date_e"].append(dt[i_h + h])  # bar terakhir label
    for h in HORIZONS:
        for k in ("dd", "y", "pos"):
            out[h][k] = np.concatenate(out[h][k]) if out[h][k] else np.array([])
        out[h]["code"] = (np.concatenate(out[h]["code"]) if out[h]["code"]
                          else np.array([], dtype=np.int32))
        if out[h]["date_s"]:
            out[h]["date_s"] = np.concatenate(out[h]["date_s"])
            out[h]["date_e"] = np.concatenate(out[h]["date_e"])
        else:
            out[h]["date_s"] = np.array([], dtype="datetime64[D]")
            out[h]["date_e"] = np.array([], dtype="datetime64[D]")
    return out


def _fit_horizon(dd: np.ndarray, y: np.ndarray, pos: np.ndarray,
                 h: int, split_frac: float) -> dict:
    """Fit logistic per horizon dengan split temporal berbasis posisi bar."""
    # threshold posisi: pakai posisi RELATIF per saham tidak tersimpan → pakai
    # split global berdasarkan urutan observasi (sudah per-saham time-ordered).
    n = len(dd)
    n_train = int(n * split_frac)
    dd_t, y_t = dd[:n_train], y[:n_train]
    dd_v, y_v = dd[n_train:], y[n_train:]

    def _fit(x, yy):
        if len(x) < 50 or len(np.unique(yy)) < 2:
            return None
        clf = LogisticRegression(penalty=None, max_iter=5000)
        clf.fit(x.reshape(-1, 1), yy)
        return clf

    clf = _fit(dd_t, y_t)
    if clf is None:
        return {"horizon_days": h, "fitted": False}

    a = float(clf.intercept_[0])
    b = float(clf.coef_[0][0])

    # SE parameter via Hessian logistic: cov = inv(X'WX), W = p(1-p).
    # Dipakai utk confidence interval P(recover) (delta method, ROMBAK#3).
    def _param_se(x, yy):
        p = 1.0 / (1.0 + np.exp(-(a + b * x)))
        W = p * (1.0 - p)
        Xd = np.column_stack([np.ones_like(x), x])
        try:
            cov = np.linalg.inv((Xd.T * W) @ Xd)
            return (float(np.sqrt(cov[0, 0])), float(np.sqrt(cov[1, 1])),
                    float(cov[0, 1]))
        except np.linalg.LinAlgError:
            return (None, None, None)

    a_se, b_se, cov_ab = _param_se(dd_t, y_t)

    def _probs(x):
        return 1.0 / (1.0 + np.exp(-(a + b * x)))

    auc_train = roc_auc_score(y_t, _probs(dd_t)) if len(np.unique(y_t)) > 1 else None
    auc_test = roc_auc_score(y_v, _probs(dd_v)) if len(np.unique(y_v)) > 1 else None
    brier_test = float(brier_score_loss(y_v, _probs(dd_v)))

    # kalibrasi bucket (prediksi rata vs aktual) — OOS
    cal = []
    for lo, hi in DD_BUCKETS:
        m = (dd_v >= lo) & (dd_v < hi)
        if m.sum() < 30:
            continue
        cal.append({
            "bucket": f"{lo:.2f}-{hi:.2f}",
            "n": int(m.sum()),
            "pred": round(float(_probs(dd_v[m]).mean()), 4),
            "actual": round(float(y_v[m].mean()), 4),
        })

    return {
        "horizon_days": h,
        "fitted": True,
        "a": round(a, 5),
        "b": round(b, 5),
        "a_se": round(a_se, 5) if a_se is not None else None,
        "b_se": round(b_se, 5) if b_se is not None else None,
        "cov_ab": round(cov_ab, 6) if cov_ab is not None else None,
        "ci_method": "delta method pada skala logit (90%)",
        "n_train": int(n_train),
        "n_test": int(n - n_train),
        "n_pos": int(y.sum()),
        "rec_rate": round(float(y.mean()), 4),
        "mean_dd": round(float(dd.mean()), 4),
        "auc_train": round(auc_train, 4) if auc_train is not None else None,
        "auc_test": round(auc_test, 4) if auc_test is not None else None,
        "brier_test": round(brier_test, 5),
        "calibration": cal,
    }


def build_base_rate_table(rows, lens, window: int) -> dict:
    """Base-rate EMPIRIS per bucket dd x horizon (tanpa model) — Exhibit-4 style."""
    tbl: dict[str, dict[int, dict]] = {}
    for lo, hi in DD_BUCKETS:
        key = f"{lo:.2f}-{hi:.2f}"
        tbl[key] = {h: {"n": 0, "recovered": 0} for h in HORIZONS}
    n_codes = len(lens)
    for c in range(n_codes):
        m = int(lens[c])
        if m < window + max(HORIZONS) + 5:
            continue
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        peak = _trailing_peak(close, window)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.clip(1.0 - close / peak, 0.0, DD_CLAMP_MAX)
        valid = np.isfinite(dd) & (dd > 0.0)
        idx = np.where(valid)[0]
        for i0 in idx:
            b = None
            for lo, hi in DD_BUCKETS:
                if lo <= dd[i0] < hi:
                    b = f"{lo:.2f}-{hi:.2f}"
                    break
            if b is None:
                continue
            for h in HORIZONS:
                if i0 + 1 + h > m - 1:
                    continue
                tbl[b][h]["n"] += 1
                if high[i0 + 1:i0 + h + 1].max() >= peak[i0]:
                    tbl[b][h]["recovered"] += 1
    out = {}
    for b, horizons in tbl.items():
        out[b] = {}
        for h, v in horizons.items():
            rate = v["recovered"] / v["n"] if v["n"] else None
            out[b][str(h)] = {
                "n": v["n"],
                "rate": round(rate, 4) if rate is not None else None,
            }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--out", default=PARAMS_PATH)
    ap.add_argument("--peak-lookback", type=int, default=252)
    ap.add_argument("--no-save", action="store_true", help="hanya laporan, tanpa simpan")
    ap.add_argument(
        "--allow-prod-write", action="store_true",
        help="P7.4: izinkan menulis ke recovery_model_params.json PRODUKSI "
             "(TIDAK disarankan — jalur legacy; production hanya via "
             "_phase6_p61_calibrate.py)",
    )
    args = ap.parse_args()

    # P7.4: hard guard — script legacy tidak boleh menimpa production params
    # tanpa flag eksplisit (mencegah overwrite metodologi lama ke produksi).
    out_path = os.path.abspath(args.out)
    prod_path = os.path.abspath(PARAMS_PATH)
    if out_path == prod_path and not args.allow_prod_write:
        print(
            "REFUSED (P7.4): _calibrate_recovery_model.py adalah LEGACY. "
            "Menulis ke recovery_model_params.json dilarang tanpa "
            "--allow-prod-write. Gunakan --out <path lain> utk menyimpan "
            "hasil, atau _phase6_p61_calibrate.py utk kalibrasi produksi.",
            file=sys.stderr,
        )
        return 1

    d = np.load(args.npz)
    rows, lens = d["rows"], d["lens"]
    print(f"Dataset: {len(lens)} kode, peak-lookback={args.peak_lookback}, "
          f"horizons={HORIZONS}", flush=True)

    t0 = time.time()
    collected = _collect_rows(rows, lens, args.peak_lookback)
    print(f"Kumpulkan observasi: {time.time()-t0:.0f}s", flush=True)

    fitted = []
    print("\n" + "=" * 100)
    print(f"{'h':>4} {'n_train':>9} {'n_test':>8} {'n_pos':>8} {'rec%':>7} "
          f"{'mean_dd':>8} {'a':>10} {'b':>10} {'AUC_tr':>8} {'AUC_te':>8} {'Brier_te':>9}")
    print("-" * 100)
    for h in HORIZONS:
        r = _fit_horizon(collected[h]["dd"], collected[h]["y"],
                         collected[h]["pos"], h, TRAIN_FRAC)
        fitted.append(r)
        if r["fitted"]:
            print(f"{h:>4} {r['n_train']:>9,} {r['n_test']:>8,} {r['n_pos']:>8,} "
                  f"{r['rec_rate']*100:>6.1f}% {r['mean_dd']:>8.3f} "
                  f"{r['a']:>10.4f} {r['b']:>10.4f} {str(r['auc_train']):>8} "
                  f"{str(r['auc_test']):>8} {r['brier_test']:>9.4f}")
        else:
            print(f"{h:>4} (tidak cukup data)")
    print("=" * 100)

    print("\nTabel Base-Rate Empiris (P(hit prior peak dalam h hari) per bucket dd):")
    tbl = build_base_rate_table(rows, lens, args.peak_lookback)
    hdr = "bucket      " + "".join(f"{h:>8}" for h in HORIZONS)
    print(hdr)
    for b in DD_BUCKETS:
        key = f"{b[0]:.2f}-{b[1]:.2f}"
        line = f"{key:12s}"
        for h in HORIZONS:
            v = tbl[key].get(str(h), {})
            line += f"{(str(v.get('rate')) if v.get('rate') is not None else '-')[:7]:>8}"
        line += f"   (n={tbl[key]['21']['n']:,} utk h=21)"
        print(line)

    # kalibrasi OOS per horizon — ringkasan
    print("\nKalibrasi OOS (prediksi vs aktual per bucket, h=21):")
    for r in fitted:
        if r["fitted"] and r["horizon_days"] == 21:
            for c in r["calibration"]:
                print(f"  dd {c['bucket']:12s} n={c['n']:>7,} "
                      f"pred={c['pred']:.3f} actual={c['actual']:.3f} "
                      f"dev={c['actual']-c['pred']:+.3f}")

    if args.no_save:
        return

    params = {
        "model": "logistic_drawdown",
        "target": "prior_peak",
        "target_definition": "max(close) trailing peak_lookback hari trading",
        "peak_lookback_days": args.peak_lookback,
        "dd_fraction": "1 - close/peak, clamp [0, 0.85]",
        "basis_harga": "raw close/high (konsisten jalur produksi)",
        "horizons": {str(r["horizon_days"]): r for r in fitted},
        "base_rate_table": tbl,
        "train_frac": TRAIN_FRAC,
        "split": "temporal (70% awal = train, 30% akhir = test)",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": os.path.basename(args.npz),
        "n_codes": int(len(lens)),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {args.out}")


if __name__ == "__main__":
    sys.exit(main())
