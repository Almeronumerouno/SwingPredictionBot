"""
_validate_post_ara.py — MED#5: statistik return setelah hari ARA.

Pertanyaan: seberapa buruk return 1-10 hari setelah ARA (auto-reject
blanket) dibanding momentum lanjut biasa? Dan berapa lama "efek post-ARA"
bertahan (kapan base rate kembali ke baseline)?

Definisi (point-in-time, konsisten jalur produksi recovery.py):
  - ARA day: close[i] >= close[i-1] * 1.10 (config ACCUM_ARA_RISE_PCT)
  - Kontrol momentum lanjut: return 1 hari +5% s/d +9.9% (menjelang ARA,
    bukan < 0.1% di bawah ARA suppression)
  - Kontrol momentum 10d: close[i]/close[i-10]-1 >= +10% (rukun momentum
    kuat, bandingkan lain kali)
  - Return k-hari = close[i+k]/close[i] - 1; mean, median, % negatif
  - P(fut 5d > 0) per jarak d hari setelah ARA (d = 1..15) — kapan efeknya
    hilang vs baseline.
"""

from __future__ import annotations

import sys
import time

import numpy as np

NPZ_PATH = "data/universe_ohlcv.npz"
ARA_RISE = 0.10


def main() -> None:
    d = np.load(NPZ_PATH)
    rows, lens = d["rows"], d["lens"]
    n_codes = len(lens)
    print(f"Dataset: {n_codes} kode", flush=True)
    t0 = time.time()

    H = [1, 2, 3, 5, 10]
    # statistik: dict k -> {label: {"rets": [], "neg": 0, "n": 0}}
    stats = {}
    for label in ("post_ara", "momentum_5_10", "baseline"):
        stats[label] = {h: {"rets": [], "neg": 0, "n": 0} for h in H}

    # P(fut5>0) per jarak sejak ARA
    dist_pos = np.zeros(16)
    dist_n = np.zeros(16)
    baseline_pos = 0
    baseline_n = 0

    for c in range(n_codes):
        m = int(lens[c])
        if m < 320:
            continue
        close = rows[c, :m, 3]
        if not np.isfinite(close).all() or (close <= 0).any():
            continue
        ret1 = np.full(m, np.nan)
        ret1[1:] = close[1:] / close[:-1] - 1.0
        ret10 = np.full(m, np.nan)
        ret10[10:] = close[10:] / close[:-10] - 1.0

        ara = np.zeros(m, dtype=bool)
        ara[1:] = close[1:] >= close[:-1] * (1.0 + ARA_RISE)
        # ara = hari ARA (indeks i merujuk hari ARA itu sendiri)

        for i in range(15, m - 10):
            # baseline: semua bar (skema sama seperti loop)
            # avoid ARA day itu sendiri sbg baseline? baseline semua bar biasa
            is_ara = ara[i]
            is_mom = (not is_ara) and ret1[i] >= 0.05 and ret1[i] < 0.10
            is_base = not is_ara

            for h in H:
                if i + h >= m:
                    continue
                r = close[i + h] / close[i] - 1.0
                if is_ara:
                    tgt = stats["post_ara"][h]
                elif is_mom:
                    tgt = stats["momentum_5_10"][h]
                elif is_base:
                    tgt = stats["baseline"][h]
                else:
                    continue
                tgt["rets"].append(r)
                tgt["n"] += 1
                tgt["neg"] += r < 0.0

            # P(fut5 > 0) per jarak sejak ARA
            if is_ara:
                for dd in range(1, 16):
                    if i + dd + 5 >= m:
                        continue
                    dist_n[dd] += 1
                    dist_pos[dd] += close[i + dd + 5] / close[i + dd] - 1.0 > 0.0
            if is_base and i + 5 < m:
                baseline_n += 1
                baseline_pos += close[i + 5] / close[i] - 1.0 > 0.0

    print(f"Loop: {time.time()-t0:.0f}s", flush=True)

    print("\nReturn k-hari ke depan (mean / median / %neg) — ARA vs kontrol:")
    print(f"{'label':<18}{'n':>10}" + "".join(f"{'h=' + str(h):>20}" for h in H))
    for label in stats:
        nn = stats[label][1]["n"]
        line = f"{label:<18}{nn:>10,}"
        for h in H:
            s = stats[label][h]
            if s["n"]:
                a = np.array(s["rets"])
                line += f"  {a.mean()*100:5.2f}%/{np.median(a)*100:5.2f}%/{s['neg']/s['n']*100:4.1f}%neg"
            else:
                line += f"  {'-':>20}"
        print(line)

    print("\nP(return 5d > 0) per jarak d hari setelah ARA (vs baseline):")
    base = baseline_pos / baseline_n if baseline_n else 0.0
    print(f"  baseline: {base:.4f} (n={baseline_n:,})")
    for dd in range(1, 16):
        if dist_n[dd]:
            r = dist_pos[dd] / dist_n[dd]
            print(f"  d={dd:>2}  {r:.4f}  (n={int(dist_n[dd]):>8,})  "
                  f"vsBaseline={r/base:.2f}")


if __name__ == "__main__":
    sys.exit(main())


# ─────────────────────────────────────────────────────────────
# HASIL (Agu 2026, 963 kode):
#   return k-hari: mean / median / %neg
#   post_ara (h1..h10): +0.44% / +1.09% / +1.65% / +2.68% / +4.03% mean,
#                       %neg 49.7 / 51.4 / 52.0 / 52.6 / 53.6
#   momentum_5_10:      +1.28% / +2.25% / +3.04% / +4.34% / +6.49%,
#                       %neg 41.5 / 44.6 / 46.4 / 47.8 / 49.6
#   baseline:           +0.04% / +0.10% / +0.19% / +0.40% / +1.13%,
#                       %neg 37.7 / 41.1 / 42.7 / 44.3 / 46.0
#   P(fut5d>0) sejak ARA: d1=0.404 d2=0.406 d3=0.400 d4=0.394 d5=0.389
#         d6..d10 ~0.383-0.393, d11-15 ~0.40 (baseline 0.390)
#
# KESIMPULAN (MED#5):
#   1. Saat ARA DILARANG blanket-forever: efek negatif hanya nyata pada
#      hari pertama (h1 %neg 49.7 vs baseline 37.7); sejak d=1-2 base rate
#      FUT5 malah >= baseline (1.04x) dan kembali netral di d>=5.
#   2. Yang jauh membedakan: momentum moderat (+5-10%/hari) vs post-ARA —
#      %neg lebih rendah (41.5 vs 49.7) konsisten di semua horizon.
#   3. Rekomendasi implementasi (bukan blanket-negative): kalau mau
#      filter, pakai penalti MELURUH berbasis "jarak sejak ARA", mis.
#      weight = exp(-d/3), atau skip hanya utk bar ARA itu sendiri.
#      Dan pastikan harga belum di atas level ARA (sudah dilakukan
#      recovery.py via gate below-ARA). Tidak perlu penalti permanen.
# ─────────────────────────────────────────────────────────────