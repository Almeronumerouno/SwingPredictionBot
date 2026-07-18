"""
indicators.py — Fase 1: Layer Indikator (modul murni, tanpa dependensi ke
scraper/bot). Input: array harga historis (OHLCV numpy array, urut lama ->
baru). Output: array nilai indikator, index sejajar dengan input (bar yang
belum cukup data historis diisi np.nan).

Semua rumus mengikuti riset (Riset_Mendalam_Sistem_Trading_Swing_Saham) dan
sudah dicek-silang ke sumber sekunder (pandas-ta, Wilder "New Concepts in
Technical Trading Systems", ChartSchool StockCharts) buat mastiin gak ada
kesalahan umum yang sering kejadian di implementasi lain (lihat catatan di
tiap fungsi).

Dependensi: numpy saja (sudah ada di requirements.txt).
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Building blocks: EMA & Wilder's Smoothing (RMA)
# ---------------------------------------------------------------------------

def ema(values: np.ndarray, period: int) -> np.ndarray:
    """
    Exponential Moving Average standar. alpha = 2/(period+1).
    Seed awal = SMA dari `period` nilai pertama (sesuai riset: "Inisialisasi
    EMA awal (misal SMA periode pertama)"), bukan langsung dari nilai
    pertama saja -- ini bikin hasil lebih stabil & sesuai konvensi standar.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    alpha = 2.0 / (period + 1)
    seed = np.mean(values[:period])
    out[period - 1] = seed
    for i in range(period, n):
        out[i] = values[i] * alpha + out[i - 1] * (1 - alpha)
    return out


def wilder_rma(values: np.ndarray, period: int) -> np.ndarray:
    """
    Wilder's Smoothed Moving Average (dipakai internal oleh RSI, ATR, ADX).

    PENTING: ini BUKAN EMA biasa. alpha = 1/period (bukan 2/(period+1)).
    Ini kesalahan paling umum yang bikin implementasi RSI/ATR/ADX "generic"
    beda dari versi asli Wilder -- termasuk indikator built-in MetaTrader 4
    yang justru salah (dikonfirmasi dari riset forum trader).

    Rumus resmi (New Concepts in Technical Trading Systems, 1978):
        seed          = SMA(values[0:period])
        smoothed[i]   = (smoothed[i-1] * (period - 1) + values[i]) / period
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    seed = np.mean(values[:period])
    out[period - 1] = seed
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


# ---------------------------------------------------------------------------
# Trend: EMA(10, 25)
# ---------------------------------------------------------------------------

def ema_trend(close: np.ndarray, fast: int = 10, slow: int = 25) -> dict:
    """EMA cepat & lambat sesuai pilihan riset (EMA 10 & 25 buat filter tren)."""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    return {"ema_fast": ema_fast, "ema_slow": ema_slow}


# ---------------------------------------------------------------------------
# Volatility: ATR(14, Wilder)
# ---------------------------------------------------------------------------

def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """TR = max(H-L, |H-Cprev|, |L-Cprev|). Bar pertama: TR = H-L (no prev close)."""
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(high)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev_close = close[:-1]
    hl = high[1:] - low[1:]
    hc = np.abs(high[1:] - prev_close)
    lc = np.abs(low[1:] - prev_close)
    tr[1:] = np.maximum(hl, np.maximum(hc, lc))
    return tr


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """ATR(14) Wilder = wilder_rma(TR, 14)."""
    tr = true_range(high, low, close)
    return wilder_rma(tr, period)


# ---------------------------------------------------------------------------
# Momentum: RSI(14, Wilder)
# ---------------------------------------------------------------------------

def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    RSI Wilder. RS = avg_gain/avg_loss (Wilder-smoothed), RSI = 100 - 100/(1+RS).
    Edge case: avg_loss == 0 dan avg_gain > 0 -> RSI = 100 (bukan div-by-zero).
    avg_loss == 0 dan avg_gain == 0 (harga flat total) -> RSI = 50 (netral).
    """
    close = np.asarray(close, dtype=float)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # bar pertama tidak ada delta valid, buang dari perhitungan seed
    gain[0] = 0.0
    loss[0] = 0.0

    avg_gain = wilder_rma(gain, period)
    avg_loss = wilder_rma(loss, period)

    out = np.full(len(close), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi_val = 100 - (100 / (1 + rs))

    valid = ~np.isnan(avg_gain)
    out[valid] = rsi_val[valid]
    out[valid & (avg_loss == 0) & (avg_gain > 0)] = 100.0
    out[valid & (avg_loss == 0) & (avg_gain == 0)] = 50.0
    return out


# ---------------------------------------------------------------------------
# Trend Strength: ADX(14) lengkap +DI/-DI/DX
# ---------------------------------------------------------------------------

def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> dict:
    """
    Directional Movement System (Wilder). Return dict berisi plus_di,
    minus_di, dx, dan adx -- semua array sejajar index dengan input.

    Catatan warm-up: ADX baru punya nilai valid mulai index ~2*period-1
    (DX butuh `period` bar buat matang, ADX butuh `period` bar lagi buat
    nge-smooth DX). Practitioner Wilder menyarankan minimal ~150 bar data
    biar ADX benar-benar stabil -- makanya HISTORY_LOOKBACK_DAYS di config
    perlu cukup panjang kalau mau ADX yang reliable, bukan cuma pas-pasan
    2x period.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(high)

    up_move = np.zeros(n)
    down_move = np.zeros(n)
    up_move[1:] = high[1:] - high[:-1]
    down_move[1:] = low[:-1] - low[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = true_range(high, low, close)
    atr14 = wilder_rma(tr, period)
    plus_dm_smoothed = wilder_rma(plus_dm, period)
    minus_dm_smoothed = wilder_rma(minus_dm, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100 * (plus_dm_smoothed / atr14)
        minus_di = 100 * (minus_dm_smoothed / atr14)
        di_sum = plus_di + minus_di
        dx = 100 * np.abs(plus_di - minus_di) / di_sum
    dx = np.where(di_sum == 0, 0.0, dx)
    dx[np.isnan(plus_di) | np.isnan(minus_di)] = np.nan

    adx_val = wilder_rma(dx[~np.isnan(dx)], period) if np.any(~np.isnan(dx)) else np.array([])
    # Selaraskan lagi ke panjang & index asli (karena wilder_rma tadi jalan
    # di atas array yang sudah dibuang NaN-nya)
    adx_out = np.full(n, np.nan)
    valid_idx = np.where(~np.isnan(dx))[0]
    if len(valid_idx) >= period:
        adx_out[valid_idx] = adx_val

    return {
        "plus_di": plus_di,
        "minus_di": minus_di,
        "dx": dx,
        "adx": adx_out,
    }


# ---------------------------------------------------------------------------
# Volume-Momentum: MFI(14) -- rolling sum biasa, BUKAN Wilder smoothing
# ---------------------------------------------------------------------------

def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray,
        period: int = 14) -> np.ndarray:
    """
    Money Flow Index. Sesuai riset: pakai rolling SUM biasa atas Positive/
    Negative Money Flow selama N hari -- BUKAN exponential/Wilder smoothing
    kayak RSI. Ini beda penting yang sering ketuker karena MFI sering
    disebut "RSI + volume", padahal mekanisme averaging-nya beda.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    volume = np.asarray(volume, dtype=float)
    n = len(close)

    typical_price = (high + low + close) / 3.0
    raw_money_flow = typical_price * volume

    tp_delta = np.diff(typical_price, prepend=typical_price[0])
    positive_flow = np.where(tp_delta > 0, raw_money_flow, 0.0)
    negative_flow = np.where(tp_delta < 0, raw_money_flow, 0.0)
    positive_flow[0] = 0.0
    negative_flow[0] = 0.0

    out = np.full(n, np.nan)
    for i in range(period, n):
        pos_sum = positive_flow[i - period + 1: i + 1].sum()
        neg_sum = negative_flow[i - period + 1: i + 1].sum()
        if neg_sum == 0:
            out[i] = 100.0 if pos_sum > 0 else 50.0
        else:
            money_ratio = pos_sum / neg_sum
            out[i] = 100 - (100 / (1 + money_ratio))
    return out


# ---------------------------------------------------------------------------
# Volume: RVOL
# ---------------------------------------------------------------------------

def rvol(volume: np.ndarray, period: int = 20) -> np.ndarray:
    """
    Relative Volume = volume hari ini / rata-rata volume `period` hari
    SEBELUMNYA (tidak termasuk hari ini sendiri, biar gak bias/self-referencing).
    RVOL > 1 = volume di atas rata-rata (minat pasar tinggi).
    """
    volume = np.asarray(volume, dtype=float)
    n = len(volume)
    out = np.full(n, np.nan)
    for i in range(period, n):
        avg_prev = volume[i - period:i].mean()  # tidak termasuk index i
        out[i] = volume[i] / avg_prev if avg_prev > 0 else np.nan
    return out


# ---------------------------------------------------------------------------
# Price Action: Donchian Channel(20)
# ---------------------------------------------------------------------------

def donchian_channel(high: np.ndarray, low: np.ndarray, period: int = 20) -> dict:
    """Upper = highest high N hari (termasuk hari ini), Lower = lowest low N hari."""
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(high)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    for i in range(period - 1, n):
        upper[i] = high[i - period + 1: i + 1].max()
        lower[i] = low[i - period + 1: i + 1].min()
    mid = (upper + lower) / 2.0
    return {"upper": upper, "lower": lower, "mid": mid}


# ---------------------------------------------------------------------------
# Price Action: Swing High / Swing Low (fractal N-bar)
# ---------------------------------------------------------------------------

def swing_points(high: np.ndarray, low: np.ndarray, window: int = 2) -> dict:
    """
    Deteksi swing high/low pakai metode fractal: bar ke-i dianggap swing
    high kalau high[i] adalah nilai TERTINGGI dibanding `window` bar di kiri
    DAN `window` bar di kanan (default window=2 -> fractal 5-bar ala Bill
    Williams). Swing low sebaliknya (nilai TERENDAH).

    CATATAN PENTING (lagging by design): swing point di bar ke-i baru bisa
    DIKONFIRMASI setelah `window` bar berikutnya selesai terbentuk -- jadi
    ini bukan sinyal real-time, melainkan konfirmasi mundur. Index terakhir
    (`window` bar paling akhir) otomatis belum bisa dikonfirmasi = False.

    Return: dict {"swing_high": bool array, "swing_low": bool array}
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(high)
    swing_high = np.zeros(n, dtype=bool)
    swing_low = np.zeros(n, dtype=bool)
    for i in range(window, n - window):
        left_h = high[i - window:i]
        right_h = high[i + 1:i + window + 1]
        if high[i] > left_h.max() and high[i] > right_h.max():
            swing_high[i] = True
        left_l = low[i - window:i]
        right_l = low[i + 1:i + window + 1]
        if low[i] < left_l.min() and low[i] < right_l.min():
            swing_low[i] = True
    return {"swing_high": swing_high, "swing_low": swing_low}


# ---------------------------------------------------------------------------
# Price Action: Support / Resistance level (clustering swing points)
# ---------------------------------------------------------------------------

def support_resistance_levels(high: np.ndarray, low: np.ndarray, window: int = 2,
                               tolerance_pct: float = 1.0) -> dict:
    """
    Kelompokkan swing high & swing low yang berdekatan (dalam toleransi %
    tertentu) jadi level S/R, lalu urutkan berdasar jumlah "sentuhan"
    (semakin sering harga mantul di situ, semakin kuat levelnya).

    Ini implementasi dasar/heuristik -- riset menyatakan S/R secara
    prinsip kualitatif (gak ada rumus matematis baku), jadi algoritma
    clustering ini adalah salah satu cara paling umum buat mengkuantifikasi.
    """
    points = swing_points(high, low, window=window)
    resistance_prices = high[points["swing_high"]]
    support_prices = low[points["swing_low"]]

    def _cluster(prices: np.ndarray) -> list[dict]:
        if len(prices) == 0:
            return []
        sorted_prices = np.sort(prices)
        clusters: list[list[float]] = [[sorted_prices[0]]]
        for p in sorted_prices[1:]:
            last_cluster_mean = np.mean(clusters[-1])
            if abs(p - last_cluster_mean) / last_cluster_mean * 100 <= tolerance_pct:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        result = [{"level": float(np.mean(c)), "touches": len(c)} for c in clusters]
        result.sort(key=lambda x: x["touches"], reverse=True)
        return result

    return {
        "resistance": _cluster(resistance_prices),
        "support": _cluster(support_prices),
    }


# ---------------------------------------------------------------------------
# Price Action: Fibonacci Retracement
# ---------------------------------------------------------------------------

def fibonacci_retracement(swing_high: float, swing_low: float) -> dict:
    """
    Level retracement standar dari swing_high ke swing_low (uptrend leg).
    Kalau leg-nya downtrend (swing_low terjadi SETELAH swing_high), tinggal
    swap urutan argumen pas manggil fungsi ini.
    """
    diff = swing_high - swing_low
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    return {f"{r * 100:.1f}%": swing_high - diff * r for r in ratios}


def fibonacci_extension(swing_low_a: float, swing_high_b: float) -> dict:
    """Target extension setelah breakout swing high (leg A->B lanjut naik)."""
    diff = swing_high_b - swing_low_a
    ratios = [1.0, 1.272, 1.618, 2.0, 2.618]
    return {f"{r * 100:.1f}%": swing_high_b + diff * (r - 1.0) for r in ratios}


# ---------------------------------------------------------------------------
# Price Action: Candlestick Patterns (Hammer, Engulfing, Doji)
# ---------------------------------------------------------------------------

def candlestick_patterns(open_: np.ndarray, high: np.ndarray, low: np.ndarray,
                          close: np.ndarray, doji_body_pct: float = 0.10,
                          hammer_shadow_ratio: float = 2.0) -> dict:
    """
    Deteksi pola dasar per-bar. Threshold berdasar konvensi umum
    (StockCharts ChartSchool, TradingView pattern scanners):
      - Doji: body <= 10% dari total range (high-low)
      - Hammer: lower shadow >= 2x body, upper shadow kecil, body di bagian
        atas range (bullish reversal candidate -- konteks tren tetap perlu
        dicek di layer scoring, ini cuma deteksi bentuk candle-nya doang)
      - Bullish/Bearish Engulfing: body candle sekarang membungkus penuh
        body candle sebelumnya DAN warnanya berlawanan

    Return dict of boolean arrays, index sejajar dengan input.
    """
    open_ = np.asarray(open_, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(close)

    body = np.abs(close - open_)
    full_range = high - low
    full_range_safe = np.where(full_range == 0, np.nan, full_range)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    doji = np.zeros(n, dtype=bool)
    valid_range = full_range > 0
    doji[valid_range] = (body[valid_range] / full_range[valid_range]) <= doji_body_pct

    hammer = np.zeros(n, dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        hammer_cond = (
            (body > 0)
            & (lower_shadow >= hammer_shadow_ratio * body)
            & (upper_shadow <= body)
        )
    hammer[:] = hammer_cond

    bullish_engulfing = np.zeros(n, dtype=bool)
    bearish_engulfing = np.zeros(n, dtype=bool)
    for i in range(1, n):
        prev_bullish = close[i - 1] > open_[i - 1]
        prev_bearish = close[i - 1] < open_[i - 1]
        cur_bullish = close[i] > open_[i]
        cur_bearish = close[i] < open_[i]
        prev_body_low = min(open_[i - 1], close[i - 1])
        prev_body_high = max(open_[i - 1], close[i - 1])
        cur_body_low = min(open_[i], close[i])
        cur_body_high = max(open_[i], close[i])

        if prev_bearish and cur_bullish:
            if cur_body_low <= prev_body_low and cur_body_high >= prev_body_high:
                bullish_engulfing[i] = True
        if prev_bullish and cur_bearish:
            if cur_body_low <= prev_body_low and cur_body_high >= prev_body_high:
                bearish_engulfing[i] = True

    return {
        "doji": doji,
        "hammer": hammer,
        "bullish_engulfing": bullish_engulfing,
        "bearish_engulfing": bearish_engulfing,
    }


# ---------------------------------------------------------------------------
# Self-test manual (bisa dijalankan terpisah: python -m indicators)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Data dummy 40 hari buat smoke-test tiap fungsi (bukan data real saham)
    rng = np.random.default_rng(42)
    n = 40
    base = 1000 + np.cumsum(rng.normal(0, 10, n))
    close = base
    open_ = close + rng.normal(0, 3, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 5, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 5, n))
    volume = rng.integers(100_000, 5_000_000, n).astype(float)

    print("EMA(10,25):", {k: round(v[-1], 2) for k, v in ema_trend(close).items()})
    print("ATR(14):", round(atr(high, low, close)[-1], 2))
    print("RSI(14):", round(rsi(close)[-1], 2))
    adx_result = adx(high, low, close)
    print("ADX(14):", round(adx_result["adx"][-1], 2),
          "| +DI:", round(adx_result["plus_di"][-1], 2),
          "| -DI:", round(adx_result["minus_di"][-1], 2))
    print("MFI(14):", round(mfi(high, low, close, volume)[-1], 2))
    print("RVOL(20):", round(rvol(volume)[-1], 2))
    donch = donchian_channel(high, low)
    print("Donchian(20):", round(donch["upper"][-1], 2), "/", round(donch["lower"][-1], 2))
    sw = swing_points(high, low)
    print("Swing highs terdeteksi:", sw["swing_high"].sum(),
          "| Swing lows:", sw["swing_low"].sum())
    sr = support_resistance_levels(high, low)
    print("Resistance levels:", sr["resistance"][:3])
    print("Support levels:", sr["support"][:3])
    print("Fibonacci retracement (contoh):",
          {k: round(v, 1) for k, v in fibonacci_retracement(high.max(), low.min()).items()})
    patterns = candlestick_patterns(open_, high, low, close)
    print("Pola candlestick terdeteksi:",
          {k: int(v.sum()) for k, v in patterns.items()})
