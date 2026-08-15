"""Evaluasi precision@K ranking Ready-To-Fly (rombak TODO, Agu 2026).

Pertanyaan: apakah skor "strength" (kepadatan x DirNet x decay kesegaran)
yang kini mengurutkan tab Ready To Fly benar-benar memeringkat sinyal
lebih baik daripada alternatif sederhana?

Metodologi (riset s2: precision@K + clustering/block bootstrap):
- Unit query = TANGGAL (kalender IDX). Kandidat = semua saham yg
  ready_to_fly pada tanggal itu (lintas saham, sama dgn produksi).
- Label relevan (2 definisi):
    up5>=4%  : close[t+5] >= close[t] * 1.04   (target Up5)
    up5>0    : close[t+5] >  close[t]           (profit apapun)
- P@K(q) = mean label di top-K. Agregat = mean per query.
- AP@K(q) = rank-aware precision; MAP@K = mean per query (query >=1 relevan).
- CI: BLOCK bootstrap berurutan atas query (block length = H=5 hari,
  karena label overlap antar hari; B=1000) -- lebih cocok drpd iid.
- Pembanding ranking: strength (produksi), density saja, density x dirnet
  (tanpa decay), random.

Hasil (12-Agu-2026, universe_ohlcv.npz 963 saham, stride 10):
  n_signal=528, query_hari=69, avg 7.7 kandidat/hari.
  Label up5>=4% (target):
    K=5 : strength 0.305 | density 0.257 | no-decay 0.257 | random 0.239
    K=10: strength 0.273 | density 0.246 | no-decay 0.250 | random 0.239
  Label up5>0 (profit apapun): semua ~base rate (0.37-0.41) -> tanpa edge
    (konsisten MED#5: sinyal akumulasi netral utk profit, positif utk +4%).
  MAP@K (strength): K5 0.243 / K10 0.181 (up5>=4%).
Kesimpulan: (1) strength (density x dirnet x decay) KONSISTEN unggul ~+20%
  drpd density/no-decay di target Up5>=4% utk K=5-10 -> ranking strength
  dipertahankan; (2) bukti lemah (n query kecil: K5=42, K10=22, CI lebar),
  bukan perbedaan signifikan ketat; (3) base rate tinggi (0.24) krn semua
  sinyal momentum naik -> P@K bukan pemisah kuat, ranking hanya fine-grained;
  (4) sinyal langka (7.7/hari) -> K<=10 yang relevan utk produksi.
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, r"C:\CodeKuliah\SwingPredictionBot\backend")

import recovery  # noqa: E402

STRIDE = 10
H = 5
X_REL = 0.04
KS = (5, 10, 20)
B = 1000
BLOCK = H
RNG = np.random.default_rng(20260812)


def main() -> None:
    d = np.load(r"C:\CodeKuliah\SwingPredictionBot\backend\data\universe_ohlcv.npz",
                allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c)
             for c in d["codes"]]
    rows, lens = d["rows"], d["lens"]
    dates_all = d["dates"]
    COL_O, COL_H, COL_L, COL_C, COL_V = 0, 1, 2, 3, 5

    # tanggal -> list (strength, density, nodecay, up5_rel, up5_pos)
    by_date: dict[str, list] = defaultdict(list)
    n_sig = 0
    t0 = time.time()

    for c, code in enumerate(codes):
        m = int(lens[c])
        if m < 40 + H:
            continue
        rr = rows[c]
        cls = rr[:, COL_C]
        dts = dates_all[c]

        def bar(j: int) -> SimpleNamespace:
            return SimpleNamespace(
                date=str(dts[j]),
                open_price=float(rr[j, COL_O]), high=float(rr[j, COL_H]),
                low=float(rr[j, COL_L]), close=float(rr[j, COL_C]),
                volume=float(rr[j, COL_V]),
            )

        for t in range(30, m - H, STRIDE):
            if t >= len(dts):
                continue
            acc = recovery.detect_accumulation([bar(j) for j in range(t + 1)])
            if not acc.get("ready_to_fly"):
                continue
            n_sig += 1
            by_date[str(dts[t])].append((
                acc.get("strength") or 0.0,
                acc.get("density_pct") or 0.0,
                (acc.get("density_pct") or 0.0) / 100.0
                * (acc.get("net_dist_heavy") or 0.5),
                float(cls[t + H] >= cls[t] * (1.0 + X_REL)),
                float(cls[t + H] > cls[t]),
            ))

    days = sorted(by_date.keys())
    print(f"n_signal={n_sig}  query_hari={len(days)}  "
          f"avg_kandidat/hari={n_sig / len(days):.1f}  elapsed={time.time()-t0:.1f}s")

    # matriks per hari: kolom 0..4; simpan array 2D utk semua hari
    arrs = [np.asarray(by_date[k], dtype=float) for k in days]

    def boot_ci(vals: np.ndarray) -> tuple:
        # block bootstrap berurutan (block length = BLOCK)
        n = len(vals)
        boots = []
        nb = int(np.ceil(n / BLOCK))
        for _ in range(B):
            idx = np.concatenate([
                np.arange(int(s), min(int(s) + BLOCK, n))
                for s in RNG.integers(0, n, nb)
            ])
            boots.append(vals[idx].mean())
        boots = np.sort(boots)
        return float(vals.mean()), float(boots[25]), float(boots[975])

    for lbl_i, lbl_name in ((3, "up5>=4%"), (4, "up5>0")):
        print(f"\n== Label relevan: {lbl_name} ==")
        for k in KS:
            print(f" -- K={k}: P@K mean + block-bootstrap CI95 --")
            schemes = (("strength   ", 0), ("density    ", 1),
                       ("no-decay   ", 2))
            for name, col in schemes:
                pks = np.array([float(
                    a[np.argsort(-a[:, col])[:k]][:, lbl_i].mean()
                ) if len(a) >= k else np.nan for a in arrs])
                pks = pks[np.isfinite(pks)]
                if len(pks) == 0:
                    continue
                mean, lo, hi = boot_ci(pks)
                print(f"   {name}: {mean:.4f}  CI95 [{lo:.4f}, {hi:.4f}]  (query={len(pks)})")
            # random = base rate label di query yg punya >= k kandidat
            base = np.mean([a[:, lbl_i].mean() for a in arrs if len(a) >= k])
            print(f"   random   : {base:.4f}  (base rate, query>=K={k})")
        # MAP@K
        print(" -- MAP@K (rank-aware, strength) --")
        for k in KS:
            maps = []
            for a in arrs:
                if len(a) < k or a[:, lbl_i].sum() == 0:
                    continue
                order = np.argsort(-a[:, 0])
                hits = 0
                s = 0.0
                for r_i, idx in enumerate(order[:k]):
                    if a[idx, lbl_i]:
                        hits += 1
                        s += hits / (r_i + 1)
                maps.append(s / k)
            if maps:
                maps = np.array(maps)
                mean, lo, hi = boot_ci(maps)
                print(f"   K={k}: MAP {mean:.4f}  CI95 [{lo:.4f}, {hi:.4f}]  (query={len(maps)})")


if __name__ == "__main__":
    main()