"""
_baseline_compare.py — LOW#1: baseline comparison model RTF (akumulasi
post-ARA) vs strategi simpel di dataset lokal IDX.

Strategi yang dibandingkan (semua point-in-time, evaluasi sama):
  - RTF/Accumulation: detect_accumulation(bars[:i+1]) valid == True
  - Momentum keras:   bar i naik +5%..+9.9% (menjelang ARA)
  - Momentum 10d:     close[i]/close[i-10] - 1 >= +10%
  - Deep drawdown:    dd_fraction(i) >= 0.25 (model recovery: P naik)
  - Random baseline:  semua bar

Event target (mirip recovery target):
  - B10: max(high[i+1..i+10]) / close[i] - 1 >= +10% (bounce 10% dlm 10 hr)
  - Up5d: return 5d ke depan > +4%

Sampling: utk tiap saham, evaluasi bar i = kelipatan 5 (stride 5) dari
bar 320..m-15 utk batasi beban komputasi, semua strategi dievaluasi di
bar yg sama (perbandingan fair). Panggil detect_accumulation hanya utk
bar dgn harga di bawah ARA terakhir (skip cepat kalau tidak ada ARA).
"""

from __future__ import annotations

import sys
import time

import numpy as np

from data_source import local_dataset
from recovery import detect_accumulation, dd_fraction

NPZ_PATH = "data/universe_ohlcv.npz"
STRIDE = 5


def main() -> None:
    d = np.load(NPZ_PATH)
    rows, lens = d["rows"], d["lens"]
    n_codes = len(lens)
    print(f"Dataset: {n_codes} kode", flush=True)
    t0 = time.time()

    # akumulator per strategi: {label: {"b10": [n, hit], "up5": [n, hit]}}
    S = {
        "random": {"b10": [0, 0], "up5": [0, 0]},
        "momentum_hard": {"b10": [0, 0], "up5": [0, 0]},
        "momentum_10d": {"b10": [0, 0], "up5": [0, 0]},
        "deep_dd": {"b10": [0, 0], "up5": [0, 0]},
        "rtf_accum": {"b10": [0, 0], "up5": [0, 0]},
    }

    n_accum_calls = 0
    for c in range(n_codes):
        m = int(lens[c])
        if m < 320:
            continue
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        if not np.isfinite(close).all() or (close <= 0).any():
            continue

        ret1 = np.full(m, np.nan)
        ret1[1:] = close[1:] / close[:-1] - 1.0
        ret10 = np.full(m, np.nan)
        ret10[10:] = close[10:] / close[:-10] - 1.0
        # ada tidaknya ARA di history saham (skip cepat)
        ara_ever = bool(np.any(close[1:] >= close[:-1] * 1.10))

        for i in range(320, m - 15, STRIDE):
            # ---- target ----
            fmax10 = high[i + 1:i + 11].max()
            b10 = (fmax10 / close[i] - 1.0) >= 0.10
            up5 = (close[i + 5] / close[i] - 1.0) > 0.04
            r1 = ret1[i]
            r10 = ret10[i]

            # ---- strategi flags ----
            mom_hard = np.isfinite(r1) and 0.05 <= r1 < 0.10
            mom_10d = np.isfinite(r10) and r10 >= 0.10
            ddf, _ = dd_fraction(close[:i + 1])
            deep = ddf is not None and ddf >= 0.25
            rtf = False
            if ara_ever:
                bars = [local_dataset.make_local_bar(j, rows[c], rows.shape[2])
                        for j in range(i + 1)]
                try:
                    acc = detect_accumulation(bars)
                    n_accum_calls += 1
                    rtf = bool(acc.get("valid"))
                except Exception:
                    rtf = False

            for lbl, flag in (
                ("random", True),
                ("momentum_hard", mom_hard),
                ("momentum_10d", mom_10d),
                ("deep_dd", deep),
                ("rtf_accum", rtf),
            ):
                if flag:
                    S[lbl]["b10"][0] += 1
                    S[lbl]["b10"][1] += b10
                    S[lbl]["up5"][0] += 1
                    S[lbl]["up5"][1] += up5

    print(f"Loop: {time.time()-t0:.0f}s, detect_accumulation calls: "
          f"{n_accum_calls:,}", flush=True)

    print(f"\nBaseline comparison (semua di bar sama, stride={STRIDE}):")
    print(f"{'strategi':<16}{'n':>9}{'B10 rate':>10}{'OR_B10':>8}"
          f"{'Up5 rate':>10}{'OR_Up5':>8}")
    base_b10 = S["random"]["b10"][1] / S["random"]["b10"][0]
    base_up5 = S["random"]["up5"][1] / S["random"]["up5"][0]
    for lbl in S:
        n_b, h_b = S[lbl]["b10"]
        n_u, h_u = S[lbl]["up5"]
        r_b = h_b / n_b if n_b else 0.0
        r_u = h_u / n_u if n_u else 0.0
        print(f"{lbl:<16}{n_b:>9,}{r_b:>10.4f}{r_b/base_b10:>8.2f}"
              f"{r_u:>10.4f}{r_u/base_up5:>8.2f}")


if __name__ == "__main__":
    sys.exit(main())


# ─────────────────────────────────────────────────────────────
# HASIL (Agu 2026, 963 kode, stride 5, n=44k bar, panggilan RTF 40k):
#   strategi        n       B10 rate   OR_B10   Up5 rate  OR_Up5
#   random          44149   0.3654     1.00     0.2106    1.00
#   momentum_hard    2780   0.5770     1.58     0.3813    1.81
#   momentum_10d     6641   0.5562     1.52     0.3231    1.53
#   deep_dd         22447   0.4054     1.11     0.2254    1.07
#   rtf_accum        910   0.5385     1.47     0.2319    1.10
#
# KESIMPULAN (LOW#1):
#   1. Model RTF (akumulasi post-ARA) WORTH IT utk target bounce 10d/10%:
#      edge 1.47x vs random — sebanding momentum 10d (1.52x), dan muncul
#      di jalur sinyal BEDA (pasca-ARA), bukan sekadar momentum ulang.
#      Untuk up-trend 5 hari edge nya marginal (1.10x, n kecil) — pakai
#      utk entry swing, bukan scalping.
#   2. Momentum murni (keras +5-10%/hari atau +10%/10d) tetap baseline
#      terkuat di semua target — konsisten MED#1/MED#4/MED#5.
#   3. Beli deep drawdown tanpa model hampir tanpa edge (1.07-1.11x):
#      model recovery P(recover) memberi nilai sebagai RANKING antar
#      saham, bukan sebagai level absolut (lihat juga _bootstrap_recovery:
#      kalibrasi level under-prediksi di regime bearish).
# ─────────────────────────────────────────────────────────────