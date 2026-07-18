"""
Test indikator dengan data saham asli (BBCA).
Jalanin: python test_real_data.py
Bandingin hasil RSI/ADX terakhir sama TradingView.
"""
import numpy as np
from data_source.yahoo_client import fetch_trading_info
import config
import indicators as ind

KODE = "BBCA"
HARI = config.HISTORY_LOOKBACK_DAYS  # 150

print(f"Fetch {KODE} {HARI} hari kalender...")
bars = fetch_trading_info(KODE, length=HARI)
print(f"Dapat {len(bars)} hari data\n")

close = np.array([b.close for b in bars])
open_ = np.array([b.open_price for b in bars])
high = np.array([b.high for b in bars])
low = np.array([b.low for b in bars])
volume = np.array([b.volume for b in bars])

# --- RSI, ADX, EMA, ATR ---
rsi_val = ind.rsi(close)
atr_val = ind.atr(high, low, close)
ema_trend = ind.ema_trend(close)
adx_result = ind.adx(high, low, close)
mfi_val = ind.mfi(high, low, close, volume)
donch = ind.donchian_channel(high, low)
patterns = ind.candlestick_patterns(open_, high, low, close)
sr = ind.support_resistance_levels(high, low)

# Print 3 bar terakhir
print(f"{'Tanggal':>12} {'Close':>8} {'RSI':>6} {'ADX':>6} {'+DI':>6} {'-DI':>6} {'ATR':>6} {'MFI':>6} {'EMA10':>8} {'EMA25':>8}")
print("-" * 80)
for b, r, a, mf, emf, ems in zip(
    bars[-5:],
    rsi_val[-5:],
    atr_val[-5:],
    mfi_val[-5:],
    ema_trend["ema_fast"][-5:],
    ema_trend["ema_slow"][-5:],
):
    idx = bars.index(b)
    adx_row = adx_result
    plus_di = adx_row["plus_di"][idx]
    minus_di = adx_row["minus_di"][idx]
    adx_v = adx_row["adx"][idx]
    print(f"{b.date:>12} {b.close:>8.0f} {r:>6.1f} {adx_v:>6.1f} {plus_di:>6.1f} {minus_di:>6.1f} {a:>6.1f} {mf:>6.1f} {emf:>8.0f} {ems:>8.0f}")

print("\n--- Donchian(20) ---")
print(f"  Upper: {donch['upper'][-1]:.0f}  Mid: {donch['mid'][-1]:.0f}  Lower: {donch['lower'][-1]:.0f}")

sw = ind.swing_points(high, low)
print(f"\n--- Swing Points ---")
print(f"  Swing high: {sw['swing_high'].sum()} pts  Swing low: {sw['swing_low'].sum()} pts")

print(f"\n--- Support/Resistance ---")
res_str = ", ".join(f"{l['level']:.0f}({l['touches']}x)" for l in sr['resistance'][:5])
sup_str = ", ".join(f"{l['level']:.0f}({l['touches']}x)" for l in sr['support'][:5])
print(f"  Resistance: [{res_str}]")
print(f"  Support:    [{sup_str}]")

fib_high = high.max()
fib_low = low.min()
fib = ind.fibonacci_retracement(fib_high, fib_low)
print(f"\n--- Fibonacci (high={fib_high:.0f}, low={fib_low:.0f}) ---")
print(f"  {', '.join(f'{k}: {v:.0f}' for k, v in fib.items())}")

print(f"\n--- Candlestick (5 bar terakhir) ---")
for b, d, h, be, bu in zip(bars[-5:], patterns['doji'][-5:], patterns['hammer'][-5:], patterns['bearish_engulfing'][-5:], patterns['bullish_engulfing'][-5:]):
    tags = []
    if d: tags.append("DOJI")
    if h: tags.append("HAMMER")
    if be: tags.append("BEAR_ENGULF")
    if bu: tags.append("BULL_ENGULF")
    print(f"  {b.date}: {', '.join(tags) if tags else '-'}")

print(f"\nData valid: {len(bars)} bars, RSI valid sejak bar ke-{np.where(~np.isnan(rsi_val))[0][0]}")
print(f"ADX valid sejak bar ke-{np.where(~np.isnan(adx_result['adx']))[0][0]}")
print(f"Sekarang bandingin RSI={rsi_val[-1]:.1f} & ADX={adx_result['adx'][-1]:.1f} dengan TradingView!")
