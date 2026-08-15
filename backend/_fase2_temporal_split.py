"""
_fase2_temporal_split.py — F2.1: Kalibrasi recovery dgn CHRONOLOGICAL SPLIT
global + PURGE + EMBARGO (leakage-aware validation, López de Prado).

Masalah yang diperbaiki:
  _calibrate_recovery_model.py memakai split "70% baris pertama vs 30%
  sisanya" pada observasi yang GABUNGAN semua saham — posisi baris tidak
  sama dengan waktu kejadian (saham mulai berbeda), dan label horizon dari
  observasi train dapat menembus periode test (label leakage). Audit v2
  §5 menilai ini CRITICAL.

Desain F2.1:
  - Cutoff global: quantile TRAIN_FRAC (default 0.70) dari SELURUH tanggal
    baris dataset (satu tanggal, berlaku utk semua saham & semua horizon).
  - PURGE (per observasi, per horizon): label obs train berakhir di bar
    pos+h → tanggal aktual dates[kode][pos+h]; obs dengan date_end > cutoff
    DIBUANG dari train (label-nya menembus test).
  - EMBARGO (hari kalender, default 90 ~= max horizon 63 hari trading):
    test hanya berisi obs dengan start_date > cutoff + embargo; obs di
    antara (purge..embargo) dibuang (gap utk serial dependence di boundary).
  - Evaluasi:
      A. Refit logistic di train(purged) → eval OOS di test(embargoed):
         AUC/Brier/kalibrasi bucket. Menjawab "model masih bagus kalau
         dilatih masa lalu & diuji masa depan?"
      B. Model PRODUKSI (recovery_model_params.json, tanpa refit) dievaluasi
         pada test temporal yg sama: kalibrasi bucket test & overprediction.
         Menjawab "param produksi yg dipakai live masih kalibrasi di masa
         depan?" — kalau overpredict, rekalibrasi diperlukan.

OUTPUT: data/recovery_temporal_eval.json (TIDAK menimpa recovery_model_params.json)
Usage:
    python _fase2_temporal_split.py [--cutoff YYYY-MM-DD] [--embargo-days 90]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

from _calibrate_recovery_model import (DD_BUCKETS, DD_CLAMP_MAX, HORIZONS,
                                       TRAIN_FRAC, _collect_rows)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
PARAMS_JSON = os.path.join(DATA_DIR, "recovery_model_params.json")
OUT_JSON = os.path.join(DATA_DIR, "recovery_temporal_eval.json")

DEFAULT_EMBARGO_DAYS = 90  # ~max horizon (63 hari trading) dalam kalender


def _load_npz(path: str):
    d = np.load(path, allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    rows, lens = d["rows"], d["lens"].astype(int)
    dates = [list(dl) if dl is not None else [] for dl in d["dates"]]
    return codes, rows, lens, dates


def _global_cutoff(dates: list[list[str]], frac: float) -> np.datetime64:
    """Quantile frac dari seluruh tanggal baris (global, bukan per saham)."""
    all_dt = np.concatenate([
        np.array(dl, dtype="datetime64[D]") for dl in dates if len(dl)
    ])
    q = np.quantile(all_dt.astype("int64"), frac)
    return np.datetime64(int(q), "D")


def _purge_embargo_masks(dd, code, date_s, date_e, cutoff: np.datetime64,
                         embargo_days: int, h: int):
    """Mask train/test dgn purge + embargo.

    - TRAIN: start <= cutoff DAN date_end <= cutoff (label tidak menembus).
    - TEST : start > cutoff + embargo (buffer serial dependence).
    - PURGED: start <= cutoff tapi date_end > cutoff (label menembus test).
    - GAP  : cutoff < start <= cutoff + embargo (dibuang).
    """
    emb = cutoff + np.timedelta64(embargo_days, "D")
    train = (date_s <= cutoff) & (date_e <= cutoff)
    test = date_s > emb
    purged = (date_s <= cutoff) & (date_e > cutoff)
    gap = (date_s > cutoff) & (date_s <= emb)
    return train, test, purged, gap


def _fit_and_eval(dd_tr, y_tr, dd_te, y_te, h: int) -> dict:
    """Refit logistic di train → eval AUC/Brier/kalibrasi di test."""
    if len(dd_tr) < 50 or len(np.unique(y_tr)) < 2 or len(dd_te) == 0:
        return {"horizon_days": h, "fitted": False}
    clf = LogisticRegression(penalty=None, max_iter=5000)
    clf.fit(dd_tr.reshape(-1, 1), y_tr)
    a, b = float(clf.intercept_[0]), float(clf.coef_[0][0])

    def _probs(x):
        return 1.0 / (1.0 + np.exp(-(a + b * x)))

    p_te = _probs(dd_te)
    auc_te = roc_auc_score(y_te, p_te) if len(np.unique(y_te)) > 1 else None
    brier_te = float(brier_score_loss(y_te, p_te))
    cal = []
    for lo, hi in DD_BUCKETS:
        m = (dd_te >= lo) & (dd_te < hi)
        if m.sum() < 30:
            continue
        cal.append({
            "bucket": f"{lo:.2f}-{hi:.2f}",
            "n": int(m.sum()),
            "pred": round(float(p_te[m].mean()), 4),
            "actual": round(float(y_te[m].mean()), 4),
            "dev": round(float(y_te[m].mean() - p_te[m].mean()), 4),
        })
    return {
        "horizon_days": h, "fitted": True,
        "a": round(a, 5), "b": round(b, 5),
        "n_train": int(len(dd_tr)), "n_test": int(len(dd_te)),
        "n_pos_test": int(y_te.sum()),
        "rec_test": round(float(y_te.mean()), 4),
        "mean_dd_test": round(float(dd_te.mean()), 4),
        "auc_test": round(auc_te, 4) if auc_te is not None else None,
        "brier_test": round(brier_te, 5),
        "calibration": cal,
    }


def _prod_on_test(params: dict, dd_te, y_te, h: int) -> dict:
    """Model produksi (param json) TANPA refit, dievaluasi di test temporal."""
    hp = params.get("horizons", {}).get(str(h), {})
    if not hp.get("fitted"):
        return {"horizon_days": h, "fitted": False}
    a, b = float(hp["a"]), float(hp["b"])
    p = 1.0 / (1.0 + np.exp(-(a + b * np.clip(dd_te, 0.0, DD_CLAMP_MAX))))
    auc = roc_auc_score(y_te, p) if len(np.unique(y_te)) > 1 else None
    cal = []
    for lo, hi in DD_BUCKETS:
        m = (dd_te >= lo) & (dd_te < hi)
        if m.sum() < 30:
            continue
        cal.append({
            "bucket": f"{lo:.2f}-{hi:.2f}",
            "n": int(m.sum()),
            "pred": round(float(p[m].mean()), 4),
            "actual": round(float(y_te[m].mean()), 4),
            "dev": round(float(y_te[m].mean() - p[m].mean()), 4),
        })
    return {
        "horizon_days": h, "fitted": True,
        "auc_test": round(auc, 4) if auc is not None else None,
        "brier_test": round(float(brier_score_loss(y_te, p)), 5),
        "rec_test": round(float(y_te.mean()), 4),
        "mean_pred": round(float(p.mean()), 4),
        "overpred": round(float(p.mean() - y_te.mean()), 4),
        "calibration": cal,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--cutoff", default=None,
                    help="YYYY-MM-DD; default = quantile TRAIN_FRAC tanggal baris")
    ap.add_argument("--peak-lookback", type=int, default=252)
    ap.add_argument("--embargo-days", type=int, default=DEFAULT_EMBARGO_DAYS)
    args = ap.parse_args()

    codes, rows, lens, dates = _load_npz(args.npz)
    print(f"Dataset: {len(codes)} kode, peak-lookback={args.peak_lookback}, "
          f"embargo={args.embargo_days} hari kalender", flush=True)

    cutoff = (np.datetime64(args.cutoff, "D") if args.cutoff
              else _global_cutoff(dates, TRAIN_FRAC))
    print(f"Cutoff global      : {cutoff}", flush=True)
    print(f"Rentang tanggal    : {_global_cutoff(dates, 0.0)} s/d "
          f"{_global_cutoff(dates, 1.0)}", flush=True)

    t0 = time.time()
    collected = _collect_rows(rows, lens, args.peak_lookback, dates_list=dates)
    print(f"collect rows: {time.time()-t0:.0f}s", flush=True)

    with open(PARAMS_JSON, encoding="utf-8") as f:
        params = json.load(f)

    print("\n" + "=" * 118)
    print(f"{'h':>4} | {'n_tr':>8} {'n_te':>8} {'rec_te':>7} | "
          f"{'AUC_refit':>9} {'Br_refit':>9} | {'AUC_prod':>9} {'Br_prod':>9} "
          f"{'ovr_prod':>8} | {'n_purged':>8} {'n_gap':>8}")
    print("-" * 118)
    report = {"cutoff": str(cutoff), "embargo_days": args.embargo_days,
              "refit": {}, "production": {}, "n_purged": {}, "n_gap": {}}
    for h in HORIZONS:
        dd = collected[h]["dd"]
        y = collected[h]["y"]
        code = collected[h]["code"]
        d_s = collected[h]["date_s"]
        d_e = collected[h]["date_e"]
        if len(dd) == 0:
            continue
        tr, te, purged, gap = _purge_embargo_masks(
            dd, code, d_s, d_e, cutoff, args.embargo_days, h)
        n_purged = int(purged.sum())
        n_gap = int(gap.sum())
        r = _fit_and_eval(dd[tr], y[tr], dd[te], y[te], h)
        p = _prod_on_test(params, dd[te], y[te], h)
        report["refit"][str(h)] = r
        report["production"][str(h)] = p
        report["n_purged"][str(h)] = n_purged
        report["n_gap"][str(h)] = n_gap
        if r.get("fitted"):
            print(f"{h:>4} | {r['n_train']:>8,} {r['n_test']:>8,} "
                  f"{r['rec_test']*100:>6.1f}% | {str(r['auc_test']):>9} "
                  f"{r['brier_test']:>9.4f} | {str(p.get('auc_test')):>9} "
                  f"{p.get('brier_test', '-'):>9} {p.get('overpred', 0):>+8.1%} | "
                  f"{n_purged:>8,} {n_gap:>8,}")
        else:
            print(f"{h:>4} | (tidak cukup data) | n_purged={n_purged:,} "
                  f"n_gap={n_gap:,}")
    print("=" * 118)
    print("AUC_refit = logistic DILATIH ulang di train(purged), diuji di test(embargoed)")
    print("AUC_prod  = param produksi recovery_model_params.json TANPA refit, diuji di test")
    print("ovr_prod  = mean_pred - rec_test (positif = produksi overpredict di masa depan)")
    print("n_gap     = observasi antara cutoff & cutoff+embargo (dibuang)")

    print("\nKalibrasi bucket PRODUKSI di test temporal (h=21):")
    c21 = report["production"].get("21", {})
    for c in c21.get("calibration", []):
        print(f"  dd {c['bucket']:12s} n={c['n']:>7,} pred={c['pred']:.3f} "
              f"actual={c['actual']:.3f} dev={c['dev']:+.3f}")

    q = cutoff
    report.update({
        "model": "logistic_drawdown",
        "split": "chronological_global + purge(label end <= cutoff) + "
                 f"embargo({args.embargo_days}d)",
        "train_frac": TRAIN_FRAC,
        "range": [str(_global_cutoff(dates, 0.0)), str(_global_cutoff(dates, 1.0))],
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {OUT_JSON} (produksi TIDAK ditimpa)")


if __name__ == "__main__":
    sys.exit(main())