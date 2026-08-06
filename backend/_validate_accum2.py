"""
_validate_accum2.py — [v2 — DIDIGANTI v3] Validasi pola "akumulasi" versi user (SOLA Jul 30 -> Aug 6).

CATATAN: Konfig resmi di config.py TIDAK lagi memakai lookback=5/min-heavy=3/RVOL>=2.0.
Versi produksi sekarang = _validate_accum3.py (versi bandar): jendela dinamis sejak ARA
(+10% harian) + kepadatan >= 40% (min 2 hari heavy) + close >= SMA20. File ini dipertahankan
sebagai rekam jejak v2 yang aslinya membuktikan pola "banyak hari RVOL tinggi + belum breakout".

HASIL (24-27 saham IDX, drop >=5%, RVOL>=2.0):
  hari-heavy  n    b5      b10     up1
  0 (ktrl)   1517  13.4%    4.4%   21.2%
  2          136  14.7%    5.9%   38.2%
  3           55  16.4%   10.9%   41.8%
  4           12  50.0%   33.3%   83.3%
=> pola akumulasi TERKONFIRMASI (naik monoton, tidak overfit ).
   Konfig resmi (ACCUM_* di config.py): lookback=5, min-heavy=3, RVOL>=2.0.

User / desain revisi:
  Akumulasi BUKAN 1 hari RVOL tinggi, tapi:
    - beberapa hari (>= mindays) volume TINGGI dalam jendela lookback hari terakhir,
    - tapi harga MASIH DI BAWAH level (belum breakout / masih merah),
    - lalu BOOM (naik besar).
  Konsep SOLA: 30 Jul (10.9M), 31 Jul (19.3M), 3 Ags (19.4M), 5 Ags (25M)
  sambil harga turun 104->88, baru 6 Ags shot +14.5% dengan 114M.

Anti look-ahead: di hari t hanya pakai data <= t.
Reference = close[t - lookback] (level beberapa hari lalu yang belum dilewati).
Outcome h = 5 hari ke depan:
  rec5 : max(high[t+1..t+5]) >= ref           balik ke level
  b5   : max(high[t+1..t+5]) >= ref * 1.05    breakout +5%
  b10  : max(high[t+1..t+5]) >= ref * 1.10    "boom" +10%
  up1  : ada 1 hari close >= close[t] * 1.05  (pump dalam 5 hari)

Usage:
    python _validate_accum2.py SOLA [--lookback 5] [--mindays 3] [--heavy 2.0] [--length 800] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

import config as CFG
import indicators as ind
from data_source.yahoo_client import fetch_trading_info


def _events_for_code(code: str, length: int, lookback: int, mindays: int, heavy_mult: float) -> dict:
    bars = fetch_trading_info(code, length=length)
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)

    if len(close) < CFG.RECOVERY_MIN_BARS:
        return {"code": code, "error": f"data cuma {len(close)} bar"}

    rv = ind.rvol(volume, 20)
    heavy = rv >= heavy_mult

    n = len(close)
    buckets: dict[int, list[dict]] = {}

    for t in range(25, n):
        lo = max(t - lookback + 1, 0)
        k = int(heavy[lo: t + 1].sum())
        if close[t] >= close[t - lookback]:
            # sudah breakout di atas level lookback-lalu -> bukan "masih di bawah"
            continue

        ref = close[t - lookback]
        fwd_n = min(5, n - 1 - t)
        if fwd_n < 1:
            continue
        fwd_high = high[t + 1: t + 1 + fwd_n]
        fwd_close = close[t + 1: t + 1 + fwd_n]
        mxh = float(np.nanmax(fwd_high))
        rec5 = 1.0 if mxh >= ref else 0.0
        b5 = 1.0 if mxh >= ref * 1.05 else 0.0
        b10 = 1.0 if mxh >= ref * 1.10 else 0.0
        up1 = 1.0 if float(np.nanmax(fwd_close / close[t])) >= 1.05 else 0.0

        buckets.setdefault(k, []).append({
            "rec5": rec5, "b5": b5, "b10": b10, "up1": up1,
            "pos_vs_ref": round(float(close[t] / ref), 3),
        })

    return {"code": code, "buckets": buckets}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validasi pola akumulasi (banyak hari RVOL tinggi, harga belum breakout)")
    parser.add_argument("codes", nargs="+")
    parser.add_argument("--lookback", type=int, default=5)
    parser.add_argument("--mindays", type=int, default=3)
    parser.add_argument("--heavy", type=float, default=2.0)
    parser.add_argument("--length", type=int, default=800)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    all_buckets: dict[int, list[dict]] = {}
    for code in args.codes:
        try:
            res = _events_for_code(code, args.length, args.lookback, args.mindays, args.heavy)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {code}: {e}", file=sys.stderr)
            continue
        if "error" in res:
            print(f"[WARN] {code}: {res['error']}", file=sys.stderr)
            continue
        for k, rows in res["buckets"].items():
            all_buckets.setdefault(k, []).extend(rows)

    summary = {}
    for k in sorted(all_buckets):
        rows = all_buckets[k]
        summary[k] = {
            "n": len(rows),
            **{m: round(float(np.mean([r[m] for r in rows])), 3)
               for m in ("rec5", "b5", "b10", "up1")},
        }

    if args.json:
        print(json.dumps({"codes": args.codes, "lookback": args.lookback,
                          "min_days": args.mindays, "heavy_mult": args.heavy,
                          "buckets": summary}, indent=2))
        return

    print()
    print("=" * 84)
    print("  VALIDASI AKUMULASI v2 (pola SOLA) — banyak hari RVOL tinggi sambil harga belum breakout")
    print(f"  Codes: {', '.join(args.codes)} | lookback {args.lookback}d | min {args.mindays} hari heavy | RVOL>={args.heavy}")
    print("  ref = close 5 hari lalu | rec5=balik | b5=+5% | b10=+10% (boom) | up1=pump 5% dalam 5d")
    print("=" * 84)
    print(f"  {'hari-heavy':>10} {'n':>5} {'rec5':>6} {'b5':>6} {'b10':>6} {'up1':>6}   keterangan")
    print("  " + "-" * 74)
    for k in sorted(all_buckets):
        a = summary[k]
        tag = " <== pola user (akumulasi)" if k >= args.mindays else ""
        print(f"  {k:>10} {a['n']:>5} {a['rec5']:>6.3f} {a['b5']:>6.3f} {a['b10']:>6.3f} {a['up1']:>6.3f}   {tag}")
    print()

    ctrl = summary.get(0, {})
    if ctrl:
        print("  Kontrol (0 hari heavy, masih di bawah): n=%d rec5=%.3f b5=%.3f b10=%.3f up1=%.3f" % (
            ctrl["n"], ctrl["rec5"], ctrl["b5"], ctrl["b10"], ctrl["up1"]))
        for k in sorted(all_buckets):
            if k >= args.mindays and k in summary:
                a = summary[k]
                print(f"  PATTERN k={k}: n={a['n']} rec5={a['rec5']:.3f}(ctrl {ctrl['rec5']:.3f}) "
                      f"b5={a['b5']:.3f}({ctrl['b5']:.3f}) b10={a['b10']:.3f}({ctrl['b10']:.3f}) "
                      f"up1={a['up1']:.3f}({ctrl['up1']:.3f})")
    print()


if __name__ == "__main__":
    main()