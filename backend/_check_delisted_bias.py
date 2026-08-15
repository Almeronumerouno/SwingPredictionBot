"""
_check_delisted_bias.py — Cek survivorship bias model recovery menggunakan
data saham yang sudah DELISTED (delisted_ohlcv.npz hasil _fetch_delisted.py).

Pertanyaan:
  1. Apakah model produksi (recovery_model_params.json) overpredict recovery
     pada saham yang NASIBNYA BURUK (kemudian delisted)?
  2. Seberapa jauh parameter logistic bergeser bila universe diperluas
     dengan saham delisted?

Analisis A — model produksi TETAP (tanpa refit) di-evaluasi pada baris
  drawdown dari saham delisted saja: per-horizon AUC, Brier, rec_rate vs
  mean prediksi, kalibrasi per bucket dd. mean(pred) - rec_rate > 0 =
  overpredict.

Analisis B — refit logistic di universe saja (baseline, harus ~mirip
  produksi) vs universe+delisted: delta a, delta b, delta AUC test,
  delta Brier. Material bila |delta b| relatif besar atau AUC test turun.

Catatan metodologi (baca sebelum menafsirkan):
  - Baris delisted hanya ada dari data Yahoo yang tersisa (coverage
    parsial ~60-75%); saham yang bangkrut parah sering tidak punya data
    sama sekali (survivorship pada data itu sendiri).
  - Jendela waktu baris delisted 2017-2018 tidak overlap dengan jendela
    universe (2023-2026). Bandingkan dengan bijak.
  - Horizon label memakai high mendatang sampai batas bar; untuk saham
    yang datanya berhenti tepat di delisting, label = sampai bar terakhir
    (censored dibuang oleh _collect_rows: end <= m-1).

Usage:
    python _check_delisted_bias.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss

from _calibrate_recovery_model import (DD_BUCKETS, DD_CLAMP_MAX, HORIZONS,
                                       TRAIN_FRAC, _collect_rows, _fit_horizon)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
UNIVERSE_NPZ = os.path.join(DATA_DIR, "universe_ohlcv.npz")
DELISTED_NPZ = os.path.join(DATA_DIR, "delisted_ohlcv.npz")
PARAMS_JSON = os.path.join(DATA_DIR, "recovery_model_params.json")

PEAK_LOOKBACK = 252
MIN_BUCKET_N = 10   # sampel delisted kecil — threshold bucket diturunkan


def _load(npz_path: str) -> tuple[np.ndarray, np.ndarray]:
    d = np.load(npz_path)
    return d["rows"], d["lens"].astype(int)


def _logit_probs(dd: np.ndarray, a: float, b: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(a + b * np.clip(dd, 0.0, DD_CLAMP_MAX))))


def _bucket_calibration(dd: np.ndarray, y: np.ndarray, p: np.ndarray,
                        min_n: int = MIN_BUCKET_N) -> list[dict]:
    out = []
    for lo, hi in DD_BUCKETS:
        m = (dd >= lo) & (dd < hi)
        if m.sum() < min_n:
            continue
        out.append({
            "bucket": f"{lo:.2f}-{hi:.2f}",
            "n": int(m.sum()),
            "pred": round(float(p[m].mean()), 4),
            "actual": round(float(y[m].mean()), 4),
            "dev": round(float(y[m].mean() - p[m].mean()), 4),
        })
    return out


def analysis_a(params: dict, rows: np.ndarray, lens: np.ndarray) -> dict:
    """Model produksi tetap → baris delisted saja."""
    print("\n" + "=" * 100)
    print("ANALISIS A — Model produksi (param json) dievaluasi pada saham DELISTED saja")
    print("=" * 100)
    print(f"{'h':>4} {'n':>8} {'n_pos':>7} {'rec%':>7} {'mean_p%':>8} "
          f"{'ovr%':>7} {'AUC':>7} {'Brier':>8}")
    print("-" * 100)
    t0 = time.time()
    collected = _collect_rows(rows, lens, PEAK_LOOKBACK)
    print(f"collect rows: {time.time()-t0:.0f}s", flush=True)
    out = {}
    for h in HORIZONS:
        dd = collected[h]["dd"]
        y = collected[h]["y"]
        if len(dd) == 0:
            print(f"{h:>4} (tidak ada baris)")
            continue
        hp = params["horizons"].get(str(h), {})
        if not hp.get("fitted", False):
            print(f"{h:>4} (model produksi tidak fitted)")
            continue
        p = _logit_probs(dd, float(hp["a"]), float(hp["b"]))
        rec = float(y.mean())
        mean_p = float(p.mean())
        auc = roc_auc_score(y, p) if len(np.unique(y)) > 1 else None
        brier = float(brier_score_loss(y, p))
        out[h] = {
            "n": int(len(dd)),
            "n_pos": int(y.sum()),
            "rec_rate": round(rec, 4),
            "mean_pred": round(mean_p, 4),
            "overpred": round(mean_p - rec, 4),
            "auc": round(auc, 4) if auc is not None else None,
            "brier": round(brier, 5),
            "calibration": _bucket_calibration(dd, y, p),
        }
        print(f"{h:>4} {len(dd):>8,} {int(y.sum()):>7,} {rec*100:>6.1f}% "
              f"{mean_p*100:>7.1f}% {mean_p-rec:>+7.1%} "
              f"{str(auc):>7} {brier:>8.4f}")
    print("-" * 100)
    print("ovr% = mean_pred - rec_rate (positif = overpredict recovery)")
    print("Kalibrasi bucket (h=21, delisted saja):")
    if 21 in out:
        for c in out[21]["calibration"]:
            print(f"  dd {c['bucket']:12s} n={c['n']:>5,} pred={c['pred']:.3f} "
                  f"actual={c['actual']:.3f} dev={c['dev']:+.3f}")
    return out


def analysis_b(rows_u: np.ndarray, lens_u: np.ndarray,
               rows_m: np.ndarray, lens_m: np.ndarray) -> dict:
    """Refit universe vs universe+delisted: geseran param & performa."""
    print("\n" + "=" * 100)
    print("ANALISIS B — Refit logistic: universe saja vs universe + delisted")
    print("=" * 100)
    print(f"{'h':>4} {'a_U':>9} {'a_M':>9} {'da':>8} {'b_U':>9} {'b_M':>9} "
          f"{'db':>8} {'AUC_U':>7} {'AUC_M':>7} {'Br_U':>7} {'Br_M':>7}")
    print("-" * 100)
    t0 = time.time()
    cu = _collect_rows(rows_u, lens_u, PEAK_LOOKBACK)
    cm = _collect_rows(rows_m, lens_m, PEAK_LOOKBACK)
    print(f"collect rows: {time.time()-t0:.0f}s", flush=True)
    out = {}
    for h in HORIZONS:
        ru = _fit_horizon(cu[h]["dd"], cu[h]["y"], cu[h]["pos"], h, TRAIN_FRAC)
        rm = _fit_horizon(cm[h]["dd"], cm[h]["y"], cm[h]["pos"], h, TRAIN_FRAC)
        if not (ru.get("fitted") and rm.get("fitted")):
            print(f"{h:>4} (tidak cukup data)")
            continue
        da = float(rm["a"]) - float(ru["a"])
        db = float(rm["b"]) - float(ru["b"])
        rel_db = db / abs(float(ru["b"])) if ru["b"] else None
        out[h] = {
            "a_universe": ru["a"], "a_merged": rm["a"],
            "b_universe": ru["b"], "b_merged": rm["b"],
            "delta_a": round(da, 5), "delta_b": round(db, 5),
            "rel_delta_b": round(rel_db, 4) if rel_db is not None else None,
            "auc_test_universe": ru["auc_test"], "auc_test_merged": rm["auc_test"],
            "brier_universe": ru["brier_test"], "brier_merged": rm["brier_test"],
            "n_train_u": ru["n_train"], "n_train_m": rm["n_train"],
            "n_test_u": ru["n_test"], "n_test_m": rm["n_test"],
        }
        print(f"{h:>4} {ru['a']:>9.4f} {rm['a']:>9.4f} {da:>+8.4f} "
              f"{ru['b']:>9.4f} {rm['b']:>9.4f} {db:>+8.4f} "
              f"{str(ru['auc_test']):>7} {str(rm['auc_test']):>7} "
              f"{ru['brier_test']:>7.4f} {rm['brier_test']:>7.4f}")
    print("-" * 100)
    print(f"n_train universe={ru.get('n_train')} → merged={rm.get('n_train')} "
          f"(h=21); rel_delta_b = delta_b/|b_universe|")
    return out


def main() -> None:
    if not os.path.exists(DELISTED_NPZ):
        print(f"{DELISTED_NPZ} tidak ada — jalankan _fetch_delisted.py dulu")
        return 1
    with open(PARAMS_JSON, encoding="utf-8") as f:
        params = json.load(f)

    rows_u, lens_u = _load(UNIVERSE_NPZ)
    rows_d, lens_d = _load(DELISTED_NPZ)
    n_d_ok = int((lens_d > 0).sum())
    print(f"Universe: {len(lens_u)} kode | Delisted: {len(lens_d)} "
          f"({n_d_ok} ada baris)", flush=True)

    res_a = analysis_a(params, rows_d, lens_d)

    rows_m = np.concatenate([rows_u, rows_d], axis=0)
    lens_m = np.concatenate([lens_u, lens_d])
    res_b = analysis_b(rows_u, lens_u, rows_m, lens_m)

    print("\n" + "=" * 100)
    print("RINGKASAN KEPUTUSAN (diisi manual setelah baca output):")
    print("  A: overpred = mean_pred - rec_rate pada saham delisted")
    print("  B: rel_delta_b material bila > ~5-10% (geseran slope logistic)")
    print("=" * 100)

    report = {
        "analysis_a": res_a,
        "analysis_b": res_b,
        "catatan": "Evaluasi model produksi pada saham delisted; "
                   "refit universe vs universe+delisted.",
    }
    with open(os.path.join(DATA_DIR, "delisted_bias_check.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\nTersimpan: data/delisted_bias_check.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
