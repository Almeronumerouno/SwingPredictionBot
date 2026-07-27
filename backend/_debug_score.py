import config
import numpy as np
import indicators as ind
import scoring
from data_source.yahoo_client import fetch_trading_info

for code in ["KOKA", "KBLV", "BBYB"]:
    try:
        bars = fetch_trading_info(code, length=config.HISTORY_LOOKBACK_DAYS)
        print(f"{code} bars: {len(bars)}")
        if len(bars) < config.MIN_TRADING_DAYS:
            print(f"  SKIP: only {len(bars)} bars")
            continue

        close = np.array([b.close for b in bars])
        high = np.array([b.high for b in bars])
        low = np.array([b.low for b in bars])
        volume = np.array([b.volume for b in bars])

        rsi_val = ind.rsi(close)
        atr_val = ind.atr(high, low, close)
        ema_val = ind.ema_trend(close)
        adx_val = ind.adx(high, low, close)
        mfi_val = ind.mfi(high, low, close, volume)
        rvol_val = ind.rvol(volume)
        donch = ind.donchian_channel(high, low)
        sr = ind.support_resistance_levels(high, low)

        score_result = scoring.compute_score({
            "close": close, "rsi": rsi_val, "atr": atr_val,
            "adx": adx_val["adx"], "plus_di": adx_val["plus_di"],
            "minus_di": adx_val["minus_di"], "ema_fast": ema_val["ema_fast"],
            "ema_slow": ema_val["ema_slow"], "mfi": mfi_val, "rvol": rvol_val,
            "donchian_upper": donch["upper"], "donchian_lower": donch["lower"],
            "support": sr["support"], "resistance": sr["resistance"],
        })
        print(f"  valid={score_result['valid']} score={score_result['swing_score']} rec={score_result['recommendation']}")
    except Exception as e:
        print(f"  ERROR: {e}")
