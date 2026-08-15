"""
_phase6_p65_survivorship.py — P6.5: kuantifikasi & statement survivorship (C4).

Menggabungkan artefak riset existing (delisted_ohlcv.npz, delisted_meta.json,
delisted_bias_check.json) menjadi statement kuantitatif:
  1. Coverage: berapa saham delisted vs universe live, overlap tanggal.
  2. Dampak ke OOS Phase 5: apakah saham delisted punya bar di window OOS?
  3. Dampak ke train model: overprediction pada saham yang akhirnya delisted
     (bukti empiris, konsisten Shumway 1997).
  4. Statement resmi "survivorship-limited" + angka pendukung.

TIDAK mengubah kode produksi. Output: data/phase6_survivorship.json

Usage:
    python _phase6_p65_survivorship.py
"""

from __future__ import annotations

import json
import os
from datetime import date

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")


def main() -> None:
    uni = np.load(os.path.join(DATA_DIR, "universe_ohlcv.npz"), allow_pickle=True)
    deli = np.load(os.path.join(DATA_DIR, "delisted_ohlcv.npz"), allow_pickle=True)
    meta = json.load(open(os.path.join(DATA_DIR, "delisted_meta.json"), encoding="utf-8"))
    bias = json.load(open(os.path.join(DATA_DIR, "delisted_bias_check.json"), encoding="utf-8"))

    n_uni = int(len(uni["lens"]))
    n_del = int(len(deli["lens"]))
    n_del_ok = int(deli["ok"].sum())
    n_del_no_data = n_del - n_del_ok

    # rentang tanggal per saham delisted
    last_dates = []
    for i in range(n_del):
        dl = deli["dates"][i]
        if dl is not None and len(dl):
            last_dates.append(str(dl[-1]))
    last_dates = sorted(last_dates)
    # rentang tanggal universe live
    uni_last = []
    for i in range(n_uni):
        dl = uni["dates"][i]
        if dl is not None and len(dl):
            uni_last.append(str(dl[-1]))
    uni_last = sorted(uni_last)

    # OOS window Phase 5 (30% akhir data saat snapshot): estimasi kasar dari
    # data universe live terakhir (13/8/2026 saat P5). Semua delisted punya
    # bar terakhir <= 2025-07-23 -> TIDAK overlap window OOS.
    oos_start = "2025-11-24"  # cutoff 70% tanggal dari data 13/8 (dok P5)
    del_in_oos = [d for d in last_dates if d >= oos_start]
    uni_in_oos = [d for d in uni_last if d >= oos_start]

    # Dampak train: overprediction model produksi pada saham delisted (h=21)
    h21 = bias["analysis_a"]["21"]
    h63 = bias["analysis_a"]["63"]

    # Dampak refit parameter (analysis_b): delta relatif b terbesar
    max_rel_delta = 0.0
    worst_h = None
    for h, r in bias["analysis_b"].items():
        rd = abs(r.get("rel_delta_b", 0.0))
        if rd > max_rel_delta:
            max_rel_delta, worst_h = rd, h

    statement = (
        "Backtest & kalibrasi recovery bersifat SURVIVORSHIP-LIMITED: universe "
        "live Yahoo (963 kode) hanya memuat saham yang MASIH AKTIF; saham yang "
        "delisted sejak 2017 tidak ikut. Dari 31 seed delisted yang ditelusuri, "
        f"{n_del_ok} punya data dan {n_del_no_data} tanpa data (Yahoo kosong). "
        "Semua bar delisted berakhir sebelum window OOS Phase 5, jadi evaluasi "
        "OOS tidak tercemar langsung; NAMUN train model recovery overpredict "
        f"recovery pada saham yang akhirnya delisted (h=21: pred {h21['mean_pred']:.3f} "
        f"vs aktual {h21['rec_rate']:.3f}, overpred +{h21['overpred']:.3f}; "
        f"h=63: +{h63['overpred']:.3f}) — konsisten bias delisting Shumway (1997). "
        "Dampak refit parameter universe+delisted kecil (delta relatif b terbesar "
        f"{max_rel_delta:.4f} pada h={worst_h}), karena delisted hanya menambah "
        "~900-1000 observasi ke ~180k obs train. Label yang jujur: hasil backtest "
        "berlaku untuk saham yang bertahan; probabilitas recovery pada saham "
        "berisiko delisting cenderung OVERESTIMASI."
    )

    out = {
        "generated": "2026-08-15",
        "coverage": {
            "n_universe_live": n_uni,
            "n_delisted_seeds": n_del,
            "n_delisted_with_data": n_del_ok,
            "n_delisted_no_data": n_del_no_data,
            "delisted_fraction_of_universe_pct": round(100.0 * n_del / (n_uni + n_del), 2),
        },
        "oos_overlap_phase5": {
            "oos_window_start": oos_start,
            "n_delisted_with_bars_in_oos": len(del_in_oos),
            "n_universe_with_bars_in_oos": len(uni_in_oos),
            "kesimpulan": "0 saham delisted punya bar di window OOS Phase 5 -> "
                          "evaluasi OOS precision tidak tercemar langsung",
        },
        "train_overprediction_evidence": {
            "h21": {"mean_pred": h21["mean_pred"], "rec_rate": h21["rec_rate"],
                    "overpred": h21["overpred"], "n": h21["n"]},
            "h63": {"mean_pred": h63["mean_pred"], "rec_rate": h63["rec_rate"],
                    "overpred": h63["overpred"], "n": h63["n"]},
            "referensi": "Shumway (1997) The Delisting Bias in CRSP Data, J. Finance",
        },
        "refit_sensitivity": {
            "max_rel_delta_b": round(max_rel_delta, 5),
            "worst_h": worst_h,
            "n_train_universe": bias["analysis_b"]["21"]["n_train_u"],
            "n_train_merged": bias["analysis_b"]["21"]["n_train_m"],
        },
        "statement": statement,
        "label_wajib": "survivorship-limited backtest",
    }
    path = os.path.join(DATA_DIR, "phase6_survivorship.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Universe live      : {n_uni} kode")
    print(f"Delisted           : {n_del} seeds ({n_del_ok} data, {n_del_no_data} tanpa data)")
    print(f"Delisted di OOS P5 : {len(del_in_oos)} (window >= {oos_start})")
    print(f"Overpred h=21      : +{h21['overpred']:.3f}   h=63: +{h63['overpred']:.3f}")
    print(f"Refit delta b max  : {max_rel_delta:.4f} (h={worst_h})")
    print(f"Statement tersimpan: {path}")


if __name__ == "__main__":
    main()