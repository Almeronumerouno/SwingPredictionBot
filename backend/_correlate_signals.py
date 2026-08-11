"""
_correlate_signals.py — Ukur overlap & korelasi antar sinyal bot.

Pertanyaan: apakah sinyal swing (BUY) dan sinyal recovery (POTENTIAL/WATCH)
muncul di saham & hari yang sama? Kalau dua sistem memberi sinyal pada
waktu bersamaan, "sinyal gabungan" bisa lebih kuat (atau redundant).

Metode (point-in-time, anti look-ahead):
  - Untuk tiap saham & tiap bar i (>= warmup): bangun analisis recovery dari
    bars[:i+1] (hanya data sampai hari i), dan sinyal swing dari indikator
    yang seluruhnya dihitung sampai hari i (compute_signals dari backtest,
    yang memakai array penuh tapi bar i sebagai bar terakhir).
  - Swing aktif  : recommendation == "BUY" pada hari i
  - Recovery aktif: signal in {POTENTIAL, WATCH} pada hari i
  - Overlap      : hari di mana keduanya aktif bersamaan (juga window
                   t..t+lag_days: recovery di t, swing menyusul)

Output:
  - Tabel per saham: n hari aktif, overlap, phi coefficient (korelasi biner),
    contoh tanggal overlap pertama.
  - Agregat semua saham.

Usage:
    python _correlate_signals.py --codes BBCA BMRI BBRI ASII TLKM ADRO
    python _correlate_signals.py --codes BBCA --lag 3 --json
    python _correlate_signals.py --top 10        # 10 saham paling likuid di universe
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np

import config as CFG
import indicators as ind
from backtest import compute_signals, BacktestConfig
from recovery import build_recovery_analysis

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
NPZ_PATH = os.path.join(BACKEND_DIR, "data", "universe_ohlcv.npz")


def _make_bar(i: int, rows, n_fields: int) -> SimpleNamespace:
    """Bangun objek mirip DailyBar dari baris npz (index relatif ke awal)."""
    r = rows[i]
    # kolom: [open, high, low, close, adj_close, volume]
    return SimpleNamespace(
        date=date(2020, 1, 1) + timedelta(days=i),  # sintetis, urut saja
        previous=float(r[3 - 1]) if i > 0 else float(r[2]),
        open_price=float(r[0]),
        high=float(r[1]),
        low=float(r[2]),
        close=float(r[3]),
        raw_close=float(r[3]),
        adj_close=float(r[4]) if n_fields > 4 else float(r[3]),
        volume=float(r[5]) if n_fields > 5 else 0.0,
        approx_value=0.0,
        frequency="1d",
        bid=0.0,
        offer=0.0,
        foreign_buy=0.0,
        foreign_sell=0.0,
    )


def _indicator_data(bars: list) -> dict:
    close = np.array([b.close for b in bars], dtype=float)
    open_ = np.array([b.open_price for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    low = np.array([b.low for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)
    atr_val = ind.atr(high, low, close)
    adx_val = ind.adx(high, low, close)
    rvol_val = ind.rvol(volume, period=CFG.RVOL_WINDOW)
    return {
        "close": close, "high": high, "low": low,
        "rsi": ind.rsi(close),
        "atr": atr_val,
        "adx": adx_val["adx"],
        "plus_di": adx_val["plus_di"],
        "minus_di": adx_val["minus_di"],
        "ema_fast": ind.ema_trend(close)["ema_fast"],
        "ema_slow": ind.ema_trend(close)["ema_slow"],
        "mfi": ind.mfi(high, low, close, volume),
        "rvol": rvol_val,
        "donchian_upper": ind.donchian_channel(high, low)["upper"],
        "donchian_lower": ind.donchian_channel(high, low)["lower"],
    }


def correlate_stock(
    code: str,
    rows: np.ndarray,
    m: int,
    n_fields: int,
    bt_cfg: BacktestConfig,
    lag: int = 3,
) -> dict:
    """Korelasi sinyal swing vs recovery untuk satu saham (point-in-time)."""
    sw_active: list[bool] = []
    rec_active: list[bool] = []
    samples: list[tuple[int, str, str]] = []  # (idx, swing_label, recovery_label)

    # Sinyal swing: hitung sekali untuk seri penuh (compute_signals bar i =
    # kondisi pada hari i, tanpa lookahead). Recovery: panggil per bar.
    bars_all = [_make_bar(j, rows, n_fields) for j in range(m)]
    data = _indicator_data(bars_all)
    signals = compute_signals(data, bt_cfg)
    recs = signals["recommendations"]
    swing_scores = signals["swing_scores"]

    warmup = 0
    valid = np.where(~np.isnan(swing_scores))[0]
    if len(valid):
        warmup = int(valid[0])

    for i in range(warmup, m):
        # --- swing pada hari i ---
        lab_sw = str(recs[i]) if i < len(recs) else "HOLD"
        # --- recovery pada hari i (hanya data sampai i) ---
        try:
            a = build_recovery_analysis(
                code, code, bars_all[: i + 1],
                drop_pct=CFG.RECOVERY_DROP_DEFAULT,
                last_updated=bars_all[i].date,
            )
            lab_rec = str(a.get("signal", "NO_SETUP"))
        except Exception:
            lab_rec = "NO_SETUP"
        sw = lab_sw == "BUY"
        rec = lab_rec in ("POTENTIAL", "WATCH")
        sw_active.append(sw)
        rec_active.append(rec)
        if sw or rec:
            samples.append((i, lab_sw, lab_rec))

    sw_arr = np.array(sw_active, dtype=float)
    rec_arr = np.array(rec_active, dtype=float)

    phi = 0.0
    if sw_arr.sum() > 0 and rec_arr.sum() > 0 and sw_arr.sum() < len(sw_arr):
        p00 = np.mean((sw_arr == 0) & (rec_arr == 0))
        p01 = np.mean((sw_arr == 0) & (rec_arr == 1))
        p10 = np.mean((sw_arr == 1) & (rec_arr == 0))
        p11 = np.mean((sw_arr == 1) & (rec_arr == 1))
        denom = (p10 + p11) * (p00 + p01) * (p11 + p01) * (p00 + p10)
        phi = (p11 * p00 - p10 * p01) / np.sqrt(denom) if denom > 0 else 0.0

    # overlap langsung & overlap ber-lag (recovery hari t, swing dalam t..t+lag)
    overlap_same = int(np.sum(sw_arr & rec_arr))
    overlap_lag = 0
    first_overlap = None
    for i in range(len(rec_arr)):
        if rec_arr[i]:
            window = sw_arr[i : i + lag + 1]
            if window.sum() > 0:
                overlap_lag += 1
                if first_overlap is None:
                    first_overlap = i
    if overlap_same and first_overlap is None:
        first_overlap = int(np.argmax(sw_arr & rec_arr))

    return {
        "code": code,
        "bars": m,
        "swing_buy_days": int(np.sum(sw_arr)),
        "recovery_days": int(np.sum(rec_arr)),
        "overlap_same_day": overlap_same,
        "overlap_lag_window": overlap_lag,
        "phi": round(float(phi), 3),
        "first_overlap_idx": first_overlap,
        "first_overlap": None if first_overlap is None else str(bars_all[first_overlap].date),
        "samples": [
            {"i": i, "swing": s, "recovery": r} for i, s, r in samples[:12]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Korelasi sinyal swing vs recovery")
    parser.add_argument("--codes", nargs="*", default=None)
    parser.add_argument("--top", type=int, default=None,
                        help="N saham pertama (paling likuid di universe)")
    parser.add_argument("--npz", default=NPZ_PATH)
    parser.add_argument("--lag", type=int, default=3,
                        help="Window hari utk overlap recovery->swing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.npz):
        print(f"[ERROR] dataset tidak ada: {args.npz}", file=sys.stderr)
        sys.exit(1)

    d = np.load(args.npz)
    rows, lens = d["rows"], d["lens"]
    codes_all = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    n_fields = rows.shape[2]

    if args.codes:
        sel = args.codes
        idx = {c: i for i, c in enumerate(codes_all)}
        missing = [c for c in sel if c not in idx]
        if missing:
            print(f"[ERROR] kode tidak ditemukan di dataset: {missing}", file=sys.stderr)
            sys.exit(1)
        sel_idx = [idx[c] for c in sel]
    elif args.top:
        sel_idx = list(range(min(args.top, len(codes_all))))
        sel = [codes_all[i] for i in sel_idx]
    else:
        print("[ERROR] beri --codes atau --top", file=sys.stderr)
        sys.exit(1)

    bt_cfg = BacktestConfig(swing_buy_threshold=CFG.SWING_BUY_THRESHOLD,
                            adx_gate_ceiling=CFG.ADX_GATE_CEILING)
    results = []
    for c_i, code in zip(sel_idx, sel):
        m = int(lens[c_i])
        if m < 100:
            print(f"  {code}: SKIP (hanya {m} bar)")
            continue
        r = correlate_stock(code, rows[c_i], m, n_fields, bt_cfg, args.lag)
        results.append(r)
        print(f"  {code}: swingBUY={r['swing_buy_days']:>4} "
              f"recovery={r['recovery_days']:>4} overlap_same={r['overlap_same_day']:>3} "
              f"overlap_lag{args.lag}={r['overlap_lag_window']:>3} phi={r['phi']:+.3f}"
              f"{(' first=' + r['first_overlap']) if r['first_overlap'] else ''}")

    if not results:
        print("[ERROR] tidak ada saham yang diproses", file=sys.stderr)
        sys.exit(1)

    s = sum(r["swing_buy_days"] for r in results)
    r_ = sum(r["recovery_days"] for r in results)
    o_same = sum(r["overlap_same_day"] for r in results)
    o_lag = sum(r["overlap_lag_window"] for r in results)
    jours = sum(r["bars"] for r in results)
    phis = [r["phi"] for r in results if r["phi"] != 0.0]

    print()
    print("=" * 88)
    print(f"  AGREGAT ({len(results)} saham, {jours} bar-hari)")
    print("-" * 88)
    print(f"  Hari swing-BUY                : {s} ({s/jours*100:.2f}% dari bar-hari)")
    print(f"  Hari recovery aktif           : {r_} ({r_/jours*100:.2f}%)")
    print(f"  Overlap same-day              : {o_same} "
          f"({o_same/s*100:.1f}% hari swing diikuti recovery, {o_same/r_*100:.1f}% hari recovery bersamaan swing)")
    print(f"  Overlap dalam {args.lag} hari setelah recovery : {o_lag} "
          f"({o_lag/(r_ or 1)*100:.1f}% recovery diikuti swing <= {args.lag} hari)")
    if phis:
        print(f"  Phi (korelasi biner, rata2 saham dgn kedua sinyal): {np.mean(phis):+.3f}")
    print("=" * 88)
    print("  Catatan: recovery aktif = POTENTIAL/WATCH (drawdown point-in-time),")
    print("  swing = rekomendasi BUY hari itu. Phi ~0 = independen; + = bersama.")
    print()

    if args.json:
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()