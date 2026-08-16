"""
_p77_survivorship_extra.py — P7.7: Survivorship / Historical Universe
Integrity — audit tambahan di luar P6.5.

P6.5 (sudah ada, dijalankan ulang): recovery model pd saham delisted —
overpred h21 +0.054, h63 +0.144; refit delta b max 0.0013; 0 saham
delisted punya bar di window OOS (>= 2025-11-24).

Di sini:
  1. RTF (detect_accumulation) khusus saham DELISTED: berapa yg bisa
     menghasilkan sinyal valid & berapa episode ARA (event pemicu).
  2. SUSPENDED: bar volume=0 (indikasi suspensi) di universe & delisted;
     episode drawdown yg overlap run zero-volume panjang (close flat ->
     dd menanjak tanpa volume — bias kecil pd model recovery).
  3. IPO entry dates: distribusi first-date universe (data availability
     != listing date; keterbatasan didokumentasikan).

Output: data/phase7_p77_survivorship.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
OUT_JSON = os.path.join(DATA_DIR, "phase7_p77_survivorship.json")
ZERO_VOL_RUN = 20       # run volume=0 panjang -> indikasi suspensi
ZERO_VOL_IN_EP = 5      # bar zero-vol minimal di dalam episode utk dihitung


def _bars_from_rows(rows, lens, dates, i: int) -> list:
    m = int(lens[i])
    out = []
    for j in range(m):
        r = rows[i, j]
        out.append(SimpleNamespace(
            date=str(dates[i][j])[:10],
            open_price=float(r[0]), high=float(r[1]), low=float(r[2]),
            close=float(r[3]), raw_close=float(r[3]),
            adj_close=float(r[4]) if np.isfinite(r[4]) and r[4] > 0 else float(r[3]),
            volume=float(r[5]),
        ))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    import config
    import recovery

    uni = np.load(os.path.join(DATA_DIR, "universe_ohlcv.npz"), allow_pickle=True)
    codes_u = [c.decode() if isinstance(c, bytes) else str(c) for c in uni["codes"]]
    rows_u, lens_u, dates_u = uni["rows"], uni["lens"], uni["dates"]

    deli = np.load(os.path.join(DATA_DIR, "delisted_ohlcv.npz"), allow_pickle=True)
    codes_d = [c.decode() if isinstance(c, bytes) else str(c) for c in deli["codes"]]
    rows_d, lens_d, dates_d = deli["rows"], deli["lens"], deli["dates"]

    # ── 1. RTF khusus delisted ───────────────────────────────────────────
    rtf = {"n_stocks": 0, "n_with_min_bars": 0, "n_valid_signal": 0,
           "n_ara_episodes": 0, "reasons": {}}
    for i, code in enumerate(codes_d):
        m = int(lens_d[i])
        if m < config.RECOVERY_MIN_BARS:
            continue
        bars = _bars_from_rows(rows_d, lens_d, dates_d, i)
        rtf["n_with_min_bars"] += 1
        res = recovery.detect_accumulation(bars)
        if res.get("valid"):
            rtf["n_valid_signal"] += 1
        else:
            r = res.get("reason") or "unknown"
            rtf["reasons"][r] = rtf["reasons"].get(r, 0) + 1
        close = np.array([b.close for b in bars])
        n_ara = int((close[1:] >= close[:-1] * (1 + config.ACCUM_ARA_RISE_PCT / 100.0)).sum())
        rtf["n_ara_episodes"] += n_ara
    rtf["n_stocks"] = len(codes_d)
    print(f"RTF delisted: {rtf['n_valid_signal']} sinyal valid dari "
          f"{rtf['n_with_min_bars']} saham dgn >= {config.RECOVERY_MIN_BARS} bar "
          f"| ARA episodes total {rtf['n_ara_episodes']}")

    # ── 2. Suspensi (bar volume=0) ───────────────────────────────────────
    susp = {"universe": {"stocks_with_zero_vol": 0, "zero_vol_bars": 0,
                         "stocks_long_suspend": 0},
            "delisted": {"stocks_with_zero_vol": 0, "zero_vol_bars": 0,
                         "stocks_long_suspend": 0},
            "dd_episodes_overlap_zero_vol": 0,
            "dd_episodes_total": 0,
            "universe_dd_episodes_overlap_zero_vol": 0,
            "universe_dd_episodes_total": 0,
            "n_stocks_skip_model_data_short": 0}
    for tag, rows, lens, dates, codes in (("universe", rows_u, lens_u, dates_u, codes_u),
                                          ("delisted", rows_d, lens_d, dates_d, codes_d)):
        s = susp[tag]
        for i, code in enumerate(codes):
            m = int(lens[i])
            if tag == "universe" and m < 260:
                susp["n_stocks_skip_model_data_short"] += 1
            if m < 260:
                continue
            vol = rows[i, :m, 5]
            close = rows[i, :m, 3]
            zv = vol == 0
            if zv.any():
                s["stocks_with_zero_vol"] += 1
                s["zero_vol_bars"] += int(zv.sum())
                # run zero-vol panjang (>= ZERO_VOL_RUN)
                pos = np.flatnonzero(zv)
                if len(pos):
                    rb = np.flatnonzero(np.diff(pos) != 1)
                    runs = np.split(pos, rb + 1)
                    if any(len(run) >= ZERO_VOL_RUN for run in runs):
                        s["stocks_long_suspend"] += 1
            # episode drawdown overlap zero-vol
            peak = np.full(m, np.nan)
            if m >= 252:
                from numpy.lib.stride_tricks import sliding_window_view
                peak[251:] = sliding_window_view(close, 252).max(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                dd = np.clip(1.0 - close / peak, 0.0, 0.85)
            valid = np.isfinite(dd) & (dd > 0)
            if not valid.any():
                continue
            pos = np.flatnonzero(valid)
            rb = np.flatnonzero(np.diff(pos) != 1)
            for run in np.split(pos, rb + 1):
                key = "dd_episodes_total" if tag == "delisted" else "universe_dd_episodes_total"
                susp[key] += 1
                if (zv[run[0]:run[-1] + 1].sum() >= ZERO_VOL_IN_EP):
                    key2 = ("dd_episodes_overlap_zero_vol" if tag == "delisted"
                            else "universe_dd_episodes_overlap_zero_vol")
                    susp[key2] += 1
    print(f"Suspensi: universe zero-vol bars {susp['universe']['zero_vol_bars']:,} "
          f"({susp['universe']['stocks_with_zero_vol']} saham; "
          f"{susp['universe']['stocks_long_suspend']} suspensi panjang >= {ZERO_VOL_RUN} bar) "
          f"| delisted: {susp['delisted']['zero_vol_bars']:,} bars, "
          f"{susp['delisted']['stocks_long_suspend']} panjang")
    print(f"Episode dd overlap zero-vol (delisted): "
          f"{susp['dd_episodes_overlap_zero_vol']} dari {susp['dd_episodes_total']} "
          f"({susp['dd_episodes_overlap_zero_vol']/max(1, susp['dd_episodes_total'])*100:.1f}%)")
    print(f"Episode dd overlap zero-vol (universe): "
          f"{susp['universe_dd_episodes_overlap_zero_vol']} dari "
          f"{susp['universe_dd_episodes_total']} "
          f"({susp['universe_dd_episodes_overlap_zero_vol']/max(1, susp['universe_dd_episodes_total'])*100:.1f}%)")
    print(f"Saham universe dgn data pendek (<260 bar, di-skip model): "
          f"{susp['n_stocks_skip_model_data_short']}")

    # ── 3. IPO entry dates (data availability) ───────────────────────────
    first_dates = []
    g_first = None
    for i, code in enumerate(codes_u):
        m = int(lens_u[i])
        if m == 0 or dates_u[i] is None or len(dates_u[i]) == 0:
            continue
        f = str(dates_u[i][0])[:10]
        first_dates.append(f)
    g_first = min(first_dates)
    buckets = {"<2016": 0, "2016-2017": 0, "2018-2019": 0, "2020-2021": 0,
               "2022-2023": 0, "2024+": 0}
    for f in first_dates:
        y = int(f[:4])
        if y < 2016:
            buckets["<2016"] += 1
        elif y < 2018:
            buckets["2016-2017"] += 1
        elif y < 2020:
            buckets["2018-2019"] += 1
        elif y < 2022:
            buckets["2020-2021"] += 1
        elif y < 2024:
            buckets["2022-2023"] += 1
        else:
            buckets["2024+"] += 1
    n_at_start = sum(1 for f in first_dates if f == g_first)
    print(f"IPO/data-availability: global first {g_first}; {n_at_start} saham "
          f"mulai dari awal data; distribusi: {buckets}")

    out = {
        "method": "P7.7 survivorship/universe integrity — audit tambahan",
        "rtf_delisted": rtf,
        "suspension": susp,
        "zero_vol_run_min_bars": ZERO_VOL_RUN,
        "ipo_availability": {
            "global_first_date": g_first,
            "n_stocks_at_start": n_at_start,
            "first_date_buckets": buckets,
            "limitation": ("first_date = ketersediaan data (bukan tanggal IPO "
                           "resmi; IDX API resmi tidak dapat diakses). Saham "
                           "listing belakangan punya histori lebih pendek."),
        },
        "limitations": [
            "delisted coverage parsial: 31 seeds (16 dgn data) dari SahamOK/"
            "IDXChannel/CNBC — IDX API resmi tidak dapat diakses (Cloudflare).",
            "missing delisting return: bar terakhir Yahoo bisa > 45 hari sebelum "
            "delisting resmi (gap_ok=False; suspensi panjang / data tidak lengkap).",
            "saham suspended: bar volume=0 tetap dipakai di state recovery "
            "(close flat -> dd menanjak tanpa volume) — dampak kecil, "
            "didokumentasikan sebagai limitation.",
            "klaim universe-wide performance TIDAK unbiased (survivorship-limited); "
            "label di config & phase6_survivorship.json.",
        ],
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not args.no_save:
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nTersimpan: {OUT_JSON}")
    else:
        print("\n(no-save)")


if __name__ == "__main__":
    sys.exit(main())