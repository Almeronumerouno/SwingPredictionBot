"""
Cek 5 saham yang beneran dump: harga pump vs harga dump.
"""
import config
import numpy as np
from data_source.yahoo_client import fetch_trading_info

STOCKS = [
    ("COCO", "2026-07-01"),
    ("TRUS", "2026-07-02"),
    ("BAPA", "2026-07-14"),
    ("RONY", "2026-07-16"),
    ("KBLV", "2026-07-16"),
]

def find_date_idx(bars, target_date):
    for i, b in enumerate(bars):
        if b.date > target_date:
            return i
    return len(bars)

def max_drawdown_detail(prices):
    peak = prices[0]
    peak_idx = 0
    max_dd = 0.0
    max_dd_idx = 0
    for i, p in enumerate(prices):
        if p > peak:
            peak = p
            peak_idx = i
        dd = (p - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd
            max_dd_idx = i
    return max_dd, peak, float(prices[max_dd_idx]), peak_idx, max_dd_idx

for code, date in STOCKS:
    bars = fetch_trading_info(code, length=400)
    split = find_date_idx(bars, date)
    
    # Price ON the screening date (entry)
    entry_bar = bars[split - 1]
    entry_price = entry_bar.close
    
    # Future prices
    future = bars[split:]
    future_close = np.array([b.close for b in future])
    
    dd, peak_price, trough_price, peak_idx, trough_idx = max_drawdown_detail(future_close)
    peak_date = future[peak_idx].date if peak_idx < len(future) else "N/A"
    trough_date = future[trough_idx].date if trough_idx < len(future) else "N/A"
    
    print(f"\n{'='*60}")
    print(f"{code} — masuk daftar gainer tgl {date}")
    print(f"{'='*60}")
    print(f"  Harga masuk (tgl {date}):              Rp{entry_price:,.0f}")
    print(f"  Harga tertinggi setelahnya ({peak_date}): Rp{peak_price:,.0f}")
    print(f"  Harga terendah setelahnya ({trough_date}): Rp{trough_price:,.0f}")
    print(f"  Naik dari entry ke peak:               {(peak_price-entry_price)/entry_price*100:+.1f}%")
    print(f"  Turun dari peak ke trough:              {(trough_price-peak_price)/peak_price*100:.1f}%")
    print(f"  Total dari entry ke trough:             {(trough_price-entry_price)/entry_price*100:.1f}%")
