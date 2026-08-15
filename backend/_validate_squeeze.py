"""
_validate_squeeze.py — MED#4: uji ATR/range squeeze sebagai proxy kompresi
sebelum breakout, di dataset lokal IDX (963 kode).

Pertanyaan: apakah base rate "breakout dalam h hari" lebih tinggi tepat
setelah kompresi volatilitas (squeeze), dibandingkan kondisi normal atau
momentum kuat?

Definisi (semua point-in-time, tanpa look-ahead):
  - atr14  = ATR(14) Wilder per bar (indicators.atr)
  - atr_ratio = atr14 / SMA(atr14, 63); squeeze ATR  = atr_ratio < 0.75
  - boll_w = (upper-lower)/mid Bollinger(20,2); squeeze BB = boll_w <
    percentile-25 dari distribusi per-saham (rolling 250)
  - momentum = close[i]/close[i-10] - 1; kontrol "momentum kuat" > +4%
  - Event A: max(high[i+1..i+h]) / close[i] - 1 >= +4% dalam h=5 hari
  - Event B: close[i+h] > max(high[i-20..i-1]) (menembus level 20 hari)
    && high[i+h] >= low[i+h] (bar valid) — breakout level keras

Output: base rate per kondisi + odd ratio vs baseline, agregat global
(jumlah saham diboboti sama). Sensitivitas threshold squeeze [0.6, 0.7, 0.8].
"""

from __future__ import annotations

import sys
import time

import numpy as np

from indicators import atr, bollinger_bands

NPZ_PATH = "data/universe_ohlcv.npz"
HORIZON = 5
BREAKOUT_PCT = 0.04


def sma(v: np.ndarray, p: int) -> np.ndarray:
    out = np.full_like(v, np.nan)
    c = np.cumsum(np.where(np.isfinite(v), v, 0.0))
    n = np.cumsum(np.isfinite(v).astype(float))
    with np.errstate(invalid="ignore", divide="ignore"):
        out[p - 1:] = (c[p - 1:] - np.concatenate([[0.0], c[:-p]])) / (
            n[p - 1:] - np.concatenate([[0.0], n[:-p]]))
    return out


def main() -> None:
    d = np.load(NPZ_PATH)
    rows, lens = d["rows"], d["lens"]
    n_codes = len(lens)
    print(f"Dataset: {n_codes} kode", flush=True)
    t0 = time.time()

    # akumulator: [kondisi][event] -> (n, hit)
    # kondisi: 0=baseline, 1=squeeze ATR<0.75, 2=squeeze BB, 3=momentum kuat
    acc = {k: {"A": [0, 0], "B": [0, 0]} for k in range(4)}
    per_squeeze_med = []

    for c in range(n_codes):
        m = int(lens[c])
        if m < 320:
            continue
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        low = rows[c, :m, 2]
        if not np.isfinite(close).all():
            continue

        a14 = atr(high, low, close, 14)
        ar = a14 / sma(a14, 63)
        bb = bollinger_bands(close, 20, 2.0)
        mid = bb["mid"]
        boll_w = np.full_like(close, np.nan)
        ok = np.isfinite(mid) & (mid > 0)
        boll_w[ok] = (bb["upper"][ok] - bb["lower"][ok]) / mid[ok]

        # percentile-25 rolling 250 per saham utk threshold boll_w
        bw_thr = np.full_like(close, np.nan)
        for i in range(250, m):
            w = boll_w[i - 250:i]
            w = w[np.isfinite(w)]
            if len(w) >= 100:
                bw_thr[i] = np.percentile(w, 25)

        mom10 = close / np.roll(close, 10) - 1.0
        mom10[:11] = np.nan
        prev20_high = np.full_like(close, np.nan)
        for i in range(20, m):
            prev20_high[i] = high[i - 20:i].max()

        for i in range(320, m - HORIZON):
            if not (np.isfinite(ar[i]) and np.isfinite(bw_thr[i])
                    and np.isfinite(mom10[i])):
                continue
            fmax = high[i + 1:i + 1 + HORIZON].max()
            evA = (fmax / close[i] - 1.0) >= BREAKOUT_PCT
            cl_f = close[i + HORIZON]
            evB = np.isfinite(prev20_high[i]) and cl_f > prev20_high[i]
            conds = [
                (ar[i] < 0.75),
                (boll_w[i] < bw_thr[i]),
                (mom10[i] > 0.04),
            ]
            acc[0]["A"][0] += 1
            acc[0]["B"][0] += 1
            acc[0]["A"][1] += evA
            acc[0]["B"][1] += evB
            for k in range(3):
                if conds[k]:
                    acc[k + 1]["A"][0] += 1
                    acc[k + 1]["A"][1] += evA
                    acc[k + 1]["B"][0] += 1
                    acc[k + 1]["B"][1] += evB

    print(f"Loop: {time.time()-t0:.0f}s", flush=True)
    names = {0: "baseline (semua bar)", 1: "squeeze ATR<0.75",
             2: "squeeze Bollinger p25", 3: "momentum +4%/10d"}
    print(f"\nBase rate breakout dlm {HORIZON} hari (Event A: +4% dari close):")
    print(f"{'kondisi':<26} {'n':>10} {'rate A':>8} {'OR_A':>7} {'rate B':>8} {'OR_B':>7}")
    baseA = acc[0]["A"][1] / acc[0]["A"][0] if acc[0]["A"][0] else 0
    baseB = acc[0]["B"][1] / acc[0]["B"][0] if acc[0]["B"][0] else 0
    for k in range(4):
        nA, hA = acc[k]["A"]
        nB, hB = acc[k]["B"]
        rA = hA / nA if nA else 0
        rB = hB / nB if nB else 0
        orA = rA / baseA if baseA else float("nan")
        orB = rB / baseB if baseB else float("nan")
        print(f"{names[k]:<26} {nA:>10,} {rA:>8.4f} {orA:>7.2f} "
              f"{rB:>8.4f} {orB:>7.2f}")


if __name__ == "__main__":
    sys.exit(main())


# ─────────────────────────────────────────────────────────────
# HASIL (Agu 2026, 963 kode, 227k observasi):
#   kondisi                 n      rate A   OR_A   rate B   OR_B
#   baseline               227443  0.5040   1.00   0.1040   1.00
#   squeeze ATR<0.75        53452  0.3721   0.74   0.0716   0.69
#   squeeze Bollinger p25   48102  0.4146   0.82   0.1105   1.06
#   momentum +4%/10d        61503  0.6163   1.22   0.2396   2.30
#
# KESIMPULAN (MED#4): hipotesis "squeeze = kompresi sebelum breakout"
# DITOLAK di data IDX. Bar dengan volatilitas rendah cenderung TETAP
# tenang 5 hari ke depan (OR < 1), bukan mem-bounce. Momentum lanjut
# (+4%/10d) tetap prediktor terkuat (OR 1.2-2.3), konsisten dgn temuan
# MED#1 (indikator RTF hampir tidak menambah info di luar momentum).
# => JANGAN tambahkan fitur squeeze ke model RTF.
# ─────────────────────────────────────────────────────────────