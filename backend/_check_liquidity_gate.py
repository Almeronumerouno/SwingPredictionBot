"""Check dampak gate likuiditas ADV20 (rombak TODO, Agu 2026).

Pertanyaan: gate likuiditas (ADV20 >= 1jt lbr & >= Rp1M, tanpa hari ARA)
memfilter 50% sinyal akumulasi di universe 963 saham. Apakah saham yg
terfilter memang punya outcome lebih buruk (gate berguna) atau setara
(gate terlalu ketat)?

Desain (sama dgn _baseline_compare):
- per saham, bar evaluasi tiap stride 5
- klasifikasi per bar via detect_accumulation (point-in-time penuh)
- kumpulkan bar yg lolos SEMUA gate kecuali liquidity -> split 2 grup:
  Lolos gate likuiditas vs Terfilter (gate likuiditas gagal)
- label B10: max(high[t+1..t+10]) >= close[t] * 1.10
- label Up5: close[t+5] >= close[t] * 1.04
- base rate per grup + delta CI (normal approx)

Hasil (12-Agu-2026, universe_ohlcv.npz 963 saham, stride 5):
  - sinyal lolos semua gate kecuali likuiditas: 1.693 bar
    PRIMA (>=1jt lbr & >=Rp1M):       n=825  B10=0.3176  Up5=0.2376
    FLOOR (>=500rb lbr & >=Rp250jt):  n=375  B10=0.3040  Up5=0.2507
    TERFILTER (<500rb lbr & <Rp250jt):n=493  B10=0.3063  Up5=0.2312
  - delta B10 prima-terfilter +0.0113 (z=0.43); Up5 +0.0063 (z=0.26);
    floor-terfilter -0.0023 -> SEMUA tidak signifikan (z < 1).
  - juga: hanya bar terakhir per saham -> 11/22 sinyal RTF terfilter gate 1jt.
Keputusan: likuiditas TIDAK prediktif -> gate = floor operasional BEI
  (500rb lbr & Rp250jt/hari) utk eksekusi swing, "prima" (1jt/Rp1M) jadi
  flag display. Config: ACCUM_MIN_ADV_* = floor, ACCUM_PRIMA_ADV_* = flag.
"""
from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, r"C:\CodeKuliah\SwingPredictionBot\backend")

import config  # noqa: E402
import recovery  # noqa: E402


def main() -> None:
    d = np.load(r"C:\CodeKuliah\SwingPredictionBot\backend\data\universe_ohlcv.npz",
                allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c)
             for c in d["codes"]]
    rows, lens = d["rows"], d["lens"]

    N, COL_O, COL_H, COL_L, COL_C, COL_V = 5, 0, 1, 2, 3, 5

    passed = []   # (code) lolos semua gate + likuiditas PRIMA (1jt lbr / Rp1M)
    floor = []    # lolos semua gate + floor BEI (500rb lbr / Rp250jt) tapi bukan prima
    filtered = []  # lolos semua gate KECUALI likuiditas (di bawah floor)
    t0 = time.time()

    for c, code in enumerate(codes):
        m = int(lens[c])
        if m < 40:
            continue
        r = rows[c]

        def bar(j: int) -> SimpleNamespace:
            return SimpleNamespace(
                date=str(int(r[j, COL_C]))[:10],  # dummy, tak dipakai
                open_price=float(r[j, COL_O]), high=float(r[j, COL_H]),
                low=float(r[j, COL_L]), close=float(r[j, COL_C]),
                volume=float(r[j, COL_V]),
            )

        for t in range(30, m - N, N):
            bars = [bar(j) for j in range(t + 1)]
            acc = recovery.detect_accumulation(bars)
            g = acc.get("gates", {})
            all_but_liq = (g.get("below") and g.get("density")
                           and g.get("min_heavy") and g.get("above_ma"))
            if not all_but_liq:
                continue
            cls = r[:, COL_C]
            b10 = float(np.max(cls[t + 1:t + 1 + 10]) >= cls[t] * 1.10)
            up5 = float(cls[t + 5] >= cls[t] * 1.04)
            rec = (code, b10, up5)
            av = acc.get("adv_vol_20") or 0.0
            avv = acc.get("adv_val_20") or 0.0
            liq_prima = av >= 1_000_000 and avv >= 1_000_000_000
            liq_floor = av >= 500_000 and avv >= 250_000_000
            if liq_prima:
                passed.append(rec)
            elif liq_floor:
                floor.append(rec)
            else:
                filtered.append(rec)

    def report(name: str, recs: list) -> None:
        if not recs:
            print(f"{name}: (0 bar)")
            return
        b10 = np.mean([x[1] for x in recs])
        up5 = np.mean([x[2] for x in recs])
        n = len(recs)
        se_b10 = np.sqrt(b10 * (1 - b10) / n)
        print(f"{name}: n={n:6d}  B10={b10:.4f} (+-1.96se {1.96*se_b10:.4f})  Up5={up5:.4f}")

    report("LOKAL  PRIMA  (>=1jt lbr & Rp1M)", passed)
    report("LOKAL  FLOOR  (>=500rb lbr & Rp250jt)", floor)
    report("LOKAL  TERFILTER (di bawah floor)   ", filtered)
    print(f"elapsed {time.time() - t0:.1f}s")

    if passed and filtered:
        p, f = passed, filtered
        bp, bf = np.mean([x[1] for x in p]), np.mean([x[1] for x in f])
        se = np.sqrt(bp * (1 - bp) / len(p) + bf * (1 - bf) / len(f))
        print(f"delta B10 (prima - terfilter) = {bp - bf:+.4f}  z={(bp-bf)/se:+.2f}")
        up_p, up_f = np.mean([x[2] for x in p]), np.mean([x[2] for x in f])
        se_u = np.sqrt(up_p * (1 - up_p) / len(p) + up_f * (1 - up_f) / len(f))
        print(f"delta Up5 (prima - terfilter) = {up_p - up_f:+.4f}  z={(up_p-up_f)/se_u:+.2f}")
    if floor and filtered and passed:
        bp, _, bf = (np.mean([x[1] for x in passed]),
                     None, np.mean([x[1] for x in filtered]))
        print(f"delta B10 (floor - terfilter) = {np.mean([x[1] for x in floor]) - bf:+.4f}")


if __name__ == "__main__":
    main()