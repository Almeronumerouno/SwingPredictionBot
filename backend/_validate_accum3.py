"""
_validate_accum3.py — [v3] Validasi pola "akumulasi post-ARA" + konfirmasi SMA20 (versi bandar).

Konsep baru (user, 2026):
  - ARA (+10% flat harian) = hari melesat = puncak distribusi/dump.
  - Setelah ARA, window akumulasi = SEMUA hari sejak ARA (bukan jendela tetap 5 hari).
  - "Siap terbang" = banyak hari volume tinggi (RVOL >= heavy, biasanya 2.0x vs avg 20
    hari sebelumnya) DI DALAM window itu (kepadatan >= density), dan harga MASIH DI
    BAWAH level ARA (belum breakout), ditambah konfirmasi -- versi bandar:
    harga menembus / berada DI ATAS SMA(MA_DAYS) = konfirmasi terbang.
  - Dibandingkan 3 arm (semua: window sejak ARA terakhir):
      A : density>=thr && heavy>=mindays && close >= SMA(20)   (model bandar)
      B : density>=thr && heavy>=mindays                        (model tanpa MA20)
      kontrol: density < thr                                    (volume biasa-biasa)
  Dievaluasi walk-forward anti look-ahead (di hari t hanya pakai data <= t).

Outcome 5 hari ke depan (sama metrik v2 biar sebanding):
  rec5 : max(high[t+1..t+5]) >= ref_ara          balik ke level ARA
  b5   : max(high[t+1..t+5]) >= ref_ara * 1.05   breakout +5% di atas ARA
  b10  : max(high[t+1..t+5]) >= ref_ara * 1.10   "boom" +10%
  up1  : ada 1 hari close >= close[t] * 1.05     (pump dalam 5 hari)

Usage:
    python _validate_accum3.py                          # scan semua universe (cache)
    python _validate_accum3.py SOLA NSSS AKPI           # hanya codes tertentu
    python _validate_accum3.py --ara-pct 10 --density 0.40 --mindays 2 --ma 20
    python _validate_accum3.py --length 800 --workers 8 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

import config as CFG
import indicators as ind
from data_source.gainers import get_or_fetch_securities_list
from data_source.yahoo_client import fetch_trading_info


def _events_for_code(code: str, length: int, ara_pct: float, min_heavy: int,
                     density_thr: float, heavy_mult: float, ma_days: int) -> dict:
    bars = fetch_trading_info(code, length=length)
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)

    n = len(close)
    if n < CFG.RECOVERY_MIN_BARS:
        return {"code": code, "error": f"data cuma {n} bar"}

    rv = ind.rvol(volume, 20)
    heavy = rv >= heavy_mult

    # rolling SMA tanpa look-ahead: sma[i] = mean(close[i-ma_days+1..i])
    sma = np.full(n, np.nan)
    if ma_days > 0 and n >= ma_days:
        cs = np.cumsum(np.concatenate(([0.0], close)))
        sma[ma_days - 1:] = (cs[ma_days:] - cs[:-ma_days]) / ma_days

    rows: list[dict] = []
    last_ara: int | None = None  # indeks ARA terbaru yang sudah terlihat (di <= i)
    heavy_anchor: int | None = None  # anchor yang dipakai utk heavy terakhir

    for i in range(1, n):
        if close[i - 1] > 0 and close[i] >= close[i - 1] * (1.0 + ara_pct / 100.0):
            last_ara = i

        # butuh rvol valid (>=20), sma valid (>=ma), dan 5 bar forward
        if i < 24 or n - 1 - i < 5:
            continue
        if last_ara is None:
            continue  # belum pernah ARA -> tidak ada ref

        a = last_ara
        if a >= i:
            continue
        window = i - a  # hari trading SETELAH ARA .. i (tanpa hari ARA itu sendiri)

        # Baseline volume "normal" DI-ANCHOR ke 20 hari SEBELUM ARA (sama dengan
        # recovery.detect_accumulation): volume hari ARA tidak boleh ikut menaikkan
        # baseline, kalau tidak heavy post-ARA ~20 hari pertama tidak pernah ke-detect.
        if a != heavy_anchor:
            base_start = max(0, a - 20)
            pre_ara_avg = float(volume[base_start:a].mean()) if a > base_start else float("nan")
            if np.isfinite(pre_ara_avg) and pre_ara_avg > 0:
                heavy = volume >= heavy_mult * pre_ara_avg
            else:
                heavy = rv >= heavy_mult
            heavy_anchor = a
        heavy_cnt = int(heavy[a + 1: i + 1].sum())
        density = heavy_cnt / window

        ref = close[a]
        if not (ref > 0 and np.isfinite(ref)):
            continue

        above_ma = bool(np.isfinite(sma[i]) and close[i] >= sma[i])

        # "fresh cross": di atas SMA20 sekarang, dan salah satu dari 2 bar sebelumnya di bawah
        cross2 = False
        if above_ma:
            cross2 = (
                (i - 1 >= 0 and np.isfinite(sma[i - 1]) and close[i - 1] < sma[i - 1])
                or (i - 2 >= 0 and np.isfinite(sma[i - 2]) and close[i - 2] < sma[i - 2])
            )

        fwd = high[i + 1: i + 6]
        fwd_c = close[i + 1: i + 6]
        if fwd.size == 0:
            continue
        mxh = float(np.nanmax(fwd))
        rec5 = 1.0 if mxh >= ref else 0.0
        b5 = 1.0 if mxh >= ref * 1.05 else 0.0
        b10 = 1.0 if mxh >= ref * 1.10 else 0.0
        up1 = 1.0 if float(np.nanmax(fwd_c)) >= close[i] * 1.05 else 0.0

        rows.append({
            "density": round(density, 3),
            "heavy": heavy_cnt,
            "window": window,
            "above_ma": 1.0 if above_ma else 0.0,
            "cross2": 1.0 if cross2 else 0.0,
            "rec5": rec5, "b5": b5, "b10": b10, "up1": up1,
            "pos_vs_ara": round(float(close[i] / ref), 3),
        })

    return {"code": code, "rows": rows}


def _agg(name: str, rows: list[dict]) -> dict:
    n = len(rows)
    out = {
        "arm": name,
        "n": n,
        "density_avg": round(float(np.mean([r["density"] for r in rows])), 3) if n else None,
        "pct_above_ma": round(100.0 * float(np.mean([r["above_ma"] for r in rows])), 1) if n else None,
        "pct_cross2": round(100.0 * float(np.mean([r["cross2"] for r in rows])), 1) if n else None,
    }
    for m in ("rec5", "b5", "b10", "up1"):
        out[m] = round(float(np.mean([r[m] for r in rows])), 3) if n else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Validasi akumulasi post-ARA + konfirmasi SMA20 (bandar)")
    parser.add_argument("codes", nargs="*")
    parser.add_argument("--ara-pct", type=float, default=10.0)
    parser.add_argument("--density", type=float, default=0.40)
    parser.add_argument("--mindays", type=int, default=2)
    parser.add_argument("--heavy", type=float, default=2.0)
    parser.add_argument("--ma", type=int, default=20)
    parser.add_argument("--length", type=int, default=800)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.codes:
        codes = args.codes
    else:
        securities = get_or_fetch_securities_list()
        if not securities:
            print("Daftar sekuritas kosong.", file=sys.stderr)
            return
        codes = [s.code for s in securities]

    print(f"Scan {len(codes)} saham (ARA +{args.ara_pct:.0f}%, density>={args.density:.2f}, "
          f"min-heavy {args.mindays}, RVOL>={args.heavy:.1f}x, SMA{args.ma}, "
          f"length {args.length}, {args.workers} worker)…", file=sys.stderr)

    arm_a: list[dict] = []
    arm_b: list[dict] = []
    ctrl: list[dict] = []

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(_events_for_code, c, args.length, args.ara_pct, args.mindays,
                      args.density, args.heavy, args.ma): c
            for c in codes
        }
        for fut in as_completed(futures):
            code = futures[fut]
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f"  …{done}/{len(futures)}", file=sys.stderr)
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"[ERROR] {code}: {e}", file=sys.stderr)
                continue
            if "error" in res:
                print(f"[WARN] {code}: {res['error']}", file=sys.stderr)
                continue
            for r in res["rows"]:
                if r["density"] >= args.density and r["heavy"] >= args.mindays:
                    arm_b.append(r)
                    if r["above_ma"]:
                        arm_a.append(r)
                else:
                    ctrl.append(r)

    summary = [_agg("A: akumulasi+SMA20", arm_a),
               _agg("B: akumulasi (tanpa MA20)", arm_b),
               _agg("kontrol (density<)", ctrl)]

    # split Arm A: masih di bawah level ARA vs sudah di atas (recovery/distribusi)
    a_below = [r for r in arm_a if r["pos_vs_ara"] < 1.0]
    a_above = [r for r in arm_a if r["pos_vs_ara"] >= 1.0]
    summary += [_agg("A split: masih di bawah ARA", a_below),
                _agg("A split: sudah di atas ARA", a_above)]

    # kontrol juga di-split supaya perbandingan adil (kontrol di bawah vs di atas ARA)
    ctrl_below = [r for r in ctrl if r["pos_vs_ara"] < 1.0]
    ctrl_above = [r for r in ctrl if r["pos_vs_ara"] >= 1.0]
    summary += [_agg("kontrol split: masih di bawah ARA", ctrl_below),
                _agg("kontrol split: sudah di atas ARA", ctrl_above)]

    # split Arm A: baru cross SMA20 (2 bar) vs sudah lama di atas
    a_cross = [r for r in arm_a if r["cross2"]]
    a_stay = [r for r in arm_a if not r["cross2"]]
    summary += [_agg("A split: cross SMA20<=2d", a_cross),
                _agg("A split: di atas >2d", a_stay)]
    if args.json:
        print(json.dumps({"codes": len(codes), "ara_pct": args.ara_pct,
                          "density_thr": args.density, "min_heavy": args.mindays,
                          "heavy": args.heavy, "ma_days": args.ma,
                          "arms": summary}, indent=2))
        return

    print()
    print("=" * 96)
    print("  VALIDASI v3 — akumulasi post-ARA (jendela dinamis) + konfirmasi SMA20")
    print(f"  ARA +{args.ara_pct:.0f}% | density>={args.density:.2f} | min-heavy {args.mindays} | "
          f"RVOL>={args.heavy:.1f}x | SMA{args.ma} | outcome 5d ke depan")
    print("=" * 96)
    print(f"  {'arm':<28}{'n':>6}{'density':>9}{'MA+%':>7}{'rec5':>7}{'b5':>7}{'b10':>7}{'up1':>7}")
    print("  " + "-" * 88)
    for a in summary:
        n = a["n"]
        if n == 0:
            print(f"  {a['arm']:<28}{0:>6}{'—':>9}{'—':>7}{'—':>7}{'—':>7}{'—':>7}{'—':>7}")
            continue
        d = f"{a['density_avg']:.2f}" if a["density_avg"] is not None else "—"
        ma = f"{a['pct_above_ma']:.0f}%" if a["pct_above_ma"] is not None else "—"
        print(f"  {a['arm']:<28}{n:>6}{d:>9}{ma:>7}"
              f"{a['rec5']:>7.3f}{a['b5']:>7.3f}{a['b10']:>7.3f}{a['up1']:>7.3f}")
        if a.get("pct_cross2") is not None and a["arm"].startswith("A"):
            print(f"  {'':<58}  (baru cross SMA20: {a['pct_cross2']:.0f}% dari arm ini)")
    print("=" * 96)

    ctrl_a = summary[2]
    if ctrl_a["n"]:
        print("  Delta vs kontrol:")
        for a in summary[:2]:
            if a["n"] == 0:
                continue
            print(f"    {a['arm']}: b10 {a['b10']:+.3f}  up1 {a['up1']:+.3f}  "
                  f"rec5 {a['rec5']:+.3f}  (kontrol b10={ctrl_a['b10']:.3f} up1={ctrl_a['up1']:.3f})")
    print()


if __name__ == "__main__":
    main()
