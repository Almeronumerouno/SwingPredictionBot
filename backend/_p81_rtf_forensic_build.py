"""
_p81_rtf_forensic_build.py — Bangun dataset forensik sinyal RTF (1 Jul - 14 Agu 2026).

Utk SETIAP sinyal RTF valid (detect_accumulation(bars[:k+1])["valid"]), ekstrak:
  - fitur internal RTF   : k_heavy, window_days, density_pct, rvol, max_rvol,
                           net_dist, net_dist_heavy, sma_gap_pct, acc_density,
                           post_ara_decay, distance_pct, double_ara,
                           days_since_prev_ara, adv_vol_20, adv_val_20,
                           liquidity_prima, state_ma20
  - fitur price-action    : ret1/5/10/20, sma20_slope, atr14_pct, hi_lo_pct,
                           range_window_pct (kompresi), cv_close_window,
                           dd60, hi250_ratio, z_vol, vol_conc_3d,
                           cum_vol_ratio (vs pre-event avg)
  - fitur timing/persist  : streak (hari berturut-turut sinyal), n_sig_same_total,
                           window_days (usia sinyal), days_since_prev_ara
  - fitur market regime   : mkt_ret_today, breadth_today, mkt_ret5, mkt_vol_today
  - label                 : hit_b10 (b10: max high[+1..+10]/close0-1 >= 0.10),
                           days_to_hit (1..10 atau -1), max_gap_pct,
                           hit_close_b10 (referensi close-based, utk audit saja)

Semua fitur point-in-time (hanya data <= hari sinyal). Simpan: data/phase8_rtf_forensic.jsonl
"""

from __future__ import annotations

import json
import sys
import time
from types import SimpleNamespace

import numpy as np

from recovery import detect_accumulation

NPZ_PATH = "data/universe_ohlcv.npz"
# CLI: python _p81_rtf_forensic_build.py [START] [END] [OUT]
START = sys.argv[1] if len(sys.argv) > 1 else "2026-07-01"
END = sys.argv[2] if len(sys.argv) > 2 else "2026-08-16"
OUT = sys.argv[3] if len(sys.argv) > 3 else "data/phase8_rtf_forensic.jsonl"

ATR_N = 14


def wilder_atr_pct(high, low, close, n=ATR_N):
    """ATR Wilder point-in-time sampai index terakhir; return (atr_pct, atr_series)."""
    m = len(close)
    if m < n + 2:
        return None, None
    tr = np.zeros(m)
    tr[0] = high[0] - low[0]
    for i in range(1, m):
        pc = close[i - 1]
        tr[i] = max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc))
    atr = np.zeros(m)
    atr[n - 1] = tr[:n].mean()
    for i in range(n, m):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr, tr


def make_bars(rows, dates, c: int, m: int) -> list:
    bars = []
    cl = rows[c, :m, 3]
    for i in range(m):
        r = rows[c, i]
        prev = float(cl[i - 1]) if i > 0 else float(r[3])
        bars.append(SimpleNamespace(
            date=dates[i], previous=prev,
            open_price=float(r[0]), high=float(r[1]), low=float(r[2]),
            close=float(r[3]), raw_close=float(r[3]),
            adj_close=float(r[4]) if len(r) > 4 else float(r[3]),
            volume=float(r[5]) if len(r) > 5 else 0.0,
            approx_value=0.0, frequency="1d",
            bid=0.0, offer=0.0, foreign_buy=0.0, foreign_sell=0.0,
        ))
    return bars


def main() -> None:
    d = np.load(NPZ_PATH, allow_pickle=True)
    rows, lens = d["rows"], d["lens"]
    raw_dates = d["dates"]
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    n_codes = len(codes)
    start_dt = np.datetime64(START)
    end_dt = np.datetime64(END)

    # ---- regime market per tanggal (point-in-time, dari seluruh universe) ----
    mkt = {}  # iso -> [ret_today, breadth, ret5, vol_today]
    all_dates = sorted({str(x)[:10] for dc in raw_dates if dc is not None for x in dc})
    for iso in all_dates:
        if not (start_dt <= np.datetime64(iso) <= end_dt):
            continue
        r1s, r5s = [], []
        dtv = np.datetime64(iso)
        for c in range(n_codes):
            m = int(lens[c])
            if m < 30:
                continue
            dsc = np.asarray(raw_dates[c], dtype="datetime64[D]")
            k = int(np.searchsorted(dsc, dtv))
            if k >= m or dsc[k] != dtv:
                continue
            close = rows[c, :m, 3]
            if k >= 1 and np.isfinite(close[k]) and close[k - 1] > 0 and close[k] > 0:
                r1s.append(close[k] / close[k - 1] - 1.0)
            if k >= 5 and close[k] > 0 and close[k - 5] > 0:
                r5s.append(close[k] / close[k - 5] - 1.0)
        if r1s:
            r1 = np.array(r1s)
            mkt[iso] = [float(r1.mean()), float((r1 > 0).mean()),
                        float(np.mean(r5s)) if r5s else None,
                        float(r1.std())]

    # ---- loop saham ----
    out_rows = []
    t0 = time.time()
    n_sig = 0
    for c in range(n_codes):
        m = int(lens[c])
        if m < 60:
            continue
        if raw_dates[c] is None:
            continue
        dsc = np.asarray(raw_dates[c], dtype="datetime64[D]")
        if len(dsc) < m:
            continue
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        low = rows[c, :m, 2]
        vol = rows[c, :m, 5]
        idxs = [k for k in range(m) if start_dt <= dsc[k] <= end_dt]
        if not idxs:
            continue
        if not np.isfinite(close[: idxs[-1] + 1]).all() or (close[: idxs[-1] + 1] <= 0).any():
            continue
        bars = make_bars(rows, [str(x)[:10] for x in dsc], c, m)

        # rolling SMA20
        sma20 = np.full(m, np.nan)
        if m >= 20:
            cs = np.cumsum(np.concatenate(([0.0], close)))
            sma20[19:] = (cs[20:] - cs[:-20]) / 20.0
        atr, _ = wilder_atr_pct(high, low, close)
        ret1 = np.full(m, np.nan)
        ret1[1:] = close[1:] / close[:-1] - 1.0

        streak = 0
        n_same = 0
        for k in idxs:
            r = detect_accumulation(bars[: k + 1])
            if not r.get("valid"):
                streak = 0
                continue
            streak += 1
            n_same += 1
            n_sig += 1
            close0 = float(close[k])
            if close0 <= 0:
                continue
            iso = str(bars[k].date)[:10]

            # ---- label b10 ----
            hit_iso = None
            days_to_hit = -1
            max_gap = None
            for j in range(k + 1, min(k + 10, m - 1) + 1):
                g = high[j] / close0 - 1.0
                if max_gap is None or g > max_gap:
                    max_gap = g
                if hit_iso is None and g >= 0.10:
                    hit_iso = str(dsc[j])[:10]
                    days_to_hit = j - k
            horizon = min(10, m - 1 - k)
            hit_b10 = hit_iso is not None
            # referensi close-based (audit saja)
            hit_close = False
            for j in range(k + 1, min(k + 10, m - 1) + 1):
                if close[j] / close0 - 1.0 >= 0.10:
                    hit_close = True
                    break

            # ---- fitur price-action point-in-time ----
            r5 = close[k] / close[k - 5] - 1.0 if k >= 5 and close[k - 5] > 0 else None
            r10 = close[k] / close[k - 10] - 1.0 if k >= 10 and close[k - 10] > 0 else None
            r20 = close[k] / close[k - 20] - 1.0 if k >= 20 and close[k - 20] > 0 else None
            sma_slope = None
            if np.isfinite(sma20[k]) and k >= 5 and np.isfinite(sma20[k - 5]) and sma20[k - 5] > 0:
                sma_slope = (sma20[k] / sma20[k - 5] - 1.0) * 100.0
            atr_pct = (atr[k] / close0 * 100.0) if atr is not None and np.isfinite(atr[k]) else None
            hi_lo = (high[k] - low[k]) / close0 * 100.0
            # kompresi window post-event
            anchor = k - int(r.get("window_days") or 0)
            anchor = max(0, anchor)
            if anchor < k:
                w_hi = high[anchor + 1: k + 1].max()
                w_lo = low[anchor + 1: k + 1].min()
                range_win = (w_hi - w_lo) / close0 * 100.0
                cv_close = float(np.std(close[anchor + 1: k + 1]) / max(np.mean(close[anchor + 1: k + 1]), 1e-9))
            else:
                range_win, cv_close = None, None
            # drawdown & jarak ke high 250d
            dd60 = None
            hi250 = None
            if k >= 5:
                pk60 = close[max(0, k - 60): k + 1].max()
                dd60 = (1.0 - close0 / pk60) * 100.0 if pk60 > 0 else None
            if k >= 30:
                pk250 = close[max(0, k - 250): k + 1].max()
                hi250 = close0 / pk250 if pk250 > 0 else None
            # volume
            v20 = vol[max(0, k - 20): k + 1]
            z_vol = None
            if len(v20) >= 6 and v20.std() > 0:
                z_vol = (vol[k] - v20.mean()) / v20.std()
            # cum vol ratio vs pre-event avg (21 hari sebelum anchor)
            cum_vol_ratio = None
            pre_avg = None
            if anchor >= 21:
                pre_avg = vol[anchor - 21: anchor].mean()
            elif anchor > 0:
                pre_avg = vol[:anchor].mean()
            if pre_avg and pre_avg > 0:
                cum_vol_ratio = vol[anchor + 1: k + 1].sum() / (pre_avg * max(int(r.get("window_days") or 1), 1))
            # konsentrasi volume 3 hari terakhir
            vol_conc = None
            if anchor < k and pre_avg and pre_avg > 0:
                v3 = vol[max(anchor + 1, k - 2): k + 1].sum()
                vt = vol[anchor + 1: k + 1].sum()
                vol_conc = v3 / vt if vt > 0 else None
            # volume vs ADV20 post-event (fitur yg sama dgn gate likuiditas)
            # fitur internal RTF
            feat = {
                "code": codes[c], "date": iso, "close0": round(close0, 2),
                "k_heavy": r.get("k_heavy"), "window_days": r.get("window_days"),
                "density_pct": r.get("density_pct"), "rvol": r.get("rvol"),
                "max_rvol": r.get("max_rvol"), "net_dist": r.get("net_dist"),
                "net_dist_heavy": r.get("net_dist_heavy"),
                "sma_gap_pct": r.get("sma_gap_pct"),
                "acc_density": r.get("acc_density"),
                "post_ara_decay": r.get("post_ara_decay"),
                "distance_pct": r.get("distance_pct"),
                "double_ara": r.get("double_ara"),
                "days_since_prev_ara": r.get("days_since_prev_ara"),
                "adv_vol_20": r.get("adv_vol_20"), "adv_val_20": r.get("adv_val_20"),
                "liquidity_prima": r.get("liquidity_prima"),
                "state_ma20": r.get("state_ma20"),
                "ret1": round(ret1[k] * 100, 4) if np.isfinite(ret1[k]) else None,
                "ret5": round(r5 * 100, 4) if r5 is not None else None,
                "ret10": round(r10 * 100, 4) if r10 is not None else None,
                "ret20": round(r20 * 100, 4) if r20 is not None else None,
                "sma_slope_pct": round(sma_slope, 4) if sma_slope is not None else None,
                "atr14_pct": round(atr_pct, 4) if atr_pct is not None else None,
                "hi_lo_pct": round(hi_lo, 4),
                "range_window_pct": round(range_win, 4) if range_win is not None else None,
                "cv_close_window": round(cv_close, 5) if cv_close is not None else None,
                "dd60_pct": round(dd60, 4) if dd60 is not None else None,
                "hi250_ratio": round(hi250, 5) if hi250 is not None else None,
                "z_vol": round(z_vol, 4) if z_vol is not None else None,
                "cum_vol_ratio": round(cum_vol_ratio, 4) if cum_vol_ratio is not None else None,
                "vol_conc_3d": round(vol_conc, 4) if vol_conc is not None else None,
                "streak": streak, "n_sig_same": n_same,
                "mk": mkt.get(iso, [None, None, None, None]),
                "horizon": horizon,
                "hit": hit_b10, "days_to_hit": days_to_hit,
                "hit_date": hit_iso, "max_gap_pct": round(max_gap * 100, 4) if max_gap is not None else None,
                "hit_close_b10": hit_close,
            }
            out_rows.append(feat)

    with open(OUT, "w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row) + "\n")
    n_hit = sum(1 for r in out_rows if r["hit"])
    print(f"sinyal: {n_sig}, tersimpan: {len(out_rows)}, HIT: {n_hit} "
          f"({n_hit / max(len(out_rows), 1) * 100:.1f}%) — {time.time() - t0:.1f}s")
    print(f"saved: {OUT}")


if __name__ == "__main__":
    sys.exit(main())