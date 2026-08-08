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

    AUDIT #9 (seeding bias): versi lama memakai `np.diff(close, prepend=close[0])`
    yang menyisipkan delta[0]=0 PALSU, lalu seed wilder_rma menghitung
    mean(values[0:period]) — berarti seed hanya dari (period-1) delta asli
    + 1 nol. Sekarang delta dihitung TANPA padding (panjang n-1, semua asli),
    seed wilder_rma berisi `period` delta asli (baris bar ke-i = delta[i-1]).
    Bar RSI pertama yang benar secara konvensi Wilder = index `period`
    (butuh 14 delta = 15 bar harga).
    """
    close = np.asarray(close, dtype=float)
    n = len(close)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out

    delta = np.diff(close)  # n-1 delta ASLI, tanpa padding nol
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    avg_gain = wilder_rma(gain, period)
    avg_loss = wilder_rma(loss, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi_val = 100 - (100 / (1 + rs))

    valid = ~np.isnan(avg_gain)
    rsi_val[valid & (avg_loss == 0) & (avg_gain > 0)] = 100.0
    rsi_val[valid & (avg_loss == 0) & (avg_gain == 0)] = 50.0

    # Bar harga ke-i memakai delta ke-(i-1) -> geser output 1 index.
    # Bar pertama (i=0) tidak punya delta -> NaN. Bar valid pertama = index `period`.
    out[1:] = rsi_val
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


def bollinger_bands(close: np.ndarray, period: int = 20, std_mult: float = 2.0) -> dict:
    sma = np.full_like(close, np.nan)
    upper = np.full_like(close, np.nan)
    lower = np.full_like(close, np.nan)
    for i in range(period - 1, len(close)):
        window = close[i - period + 1 : i + 1]
        m = float(np.nanmean(window))
        sd = float(np.nanstd(window, ddof=1))
        sma[i] = m
        upper[i] = m + std_mult * sd
        lower[i] = m - std_mult * sd
    return {"upper": upper, "lower": lower, "mid": sma}


def drawdown_from_high(high: np.ndarray, close: np.ndarray, period: int = 20) -> np.ndarray:
    dd = np.full_like(close, np.nan)
    for i in range(period - 1, len(close)):
        recent_high = float(np.nanmax(high[i - period + 1 : i + 1]))
        if recent_high > 0:
            dd[i] = 1.0 - close[i] / recent_high
    return dd


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
# Price Action: Candlestick Patterns (Single, Double, Triple)
# ---------------------------------------------------------------------------

def _trend_direction(close: np.ndarray, lookback: int = 10) -> np.ndarray:
    close = np.asarray(close, dtype=float)
    n = len(close)
    trend = np.full(n, "neutral", dtype=object)
    for i in range(lookback, n):
        sma = np.mean(close[i - lookback:i])
        if close[i] > sma:
            trend[i] = "up"
        elif close[i] < sma:
            trend[i] = "down"
    return trend


def candlestick_patterns(open_: np.ndarray, high: np.ndarray, low: np.ndarray,
                          close: np.ndarray, doji_body_pct: float = 0.10,
                          shadow_ratio: float = 2.0) -> dict:
    """
    Deteksi Single, Double, dan Triple candlestick patterns.
    Threshold mengikuti konvensi umum StockCharts / TradingView.

    Return dict of boolean arrays (index sejajar input) untuk tiap pola.
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
    is_bullish = close > open_
    is_bearish = close < open_
    valid_range = full_range > 0

    trend = _trend_direction(close)

    out: dict[str, np.ndarray] = {}

    # ── helpers ──
    def _bool_arr() -> np.ndarray:
        return np.zeros(n, dtype=bool)

    def _range_pct(i: int) -> float:
        return body[i] / full_range[i] if full_range[i] > 0 else 1.0

    # ─────────────────────────────────
    #  SINGLE-CANDLE PATTERNS
    # ─────────────────────────────────

    # Doji
    doji = _bool_arr()
    doji[valid_range] = (body[valid_range] / full_range[valid_range]) <= doji_body_pct
    out["doji"] = doji

    # Dragonfly Doji
    dfly = _bool_arr()
    dfly[valid_range] = (
        doji[valid_range]
        & (upper_shadow[valid_range] <= 0.1 * full_range[valid_range])
        & (lower_shadow[valid_range] >= 0.6 * full_range[valid_range])
    )
    out["dragonfly_doji"] = dfly

    # Gravestone Doji
    gstone = _bool_arr()
    gstone[valid_range] = (
        doji[valid_range]
        & (lower_shadow[valid_range] <= 0.1 * full_range[valid_range])
        & (upper_shadow[valid_range] >= 0.6 * full_range[valid_range])
    )
    out["gravestone_doji"] = gstone

    # Long-Legged Doji
    ll_doji = _bool_arr()
    ll_doji[valid_range] = (
        doji[valid_range]
        & (upper_shadow[valid_range] >= 0.3 * full_range[valid_range])
        & (lower_shadow[valid_range] >= 0.3 * full_range[valid_range])
    )
    out["long_legged_doji"] = ll_doji

    # Hammer (downtrend) / Hanging Man (uptrend)
    hammer_shape = _bool_arr()
    with np.errstate(divide="ignore", invalid="ignore"):
        hammer_shape[valid_range] = (
            (body[valid_range] > 0)
            & (lower_shadow[valid_range] >= shadow_ratio * body[valid_range])
            & (upper_shadow[valid_range] <= body[valid_range] * 0.5)
        )
    hammer = _bool_arr()
    hanging_man = _bool_arr()
    for i in range(n):
        if hammer_shape[i]:
            if trend[i] == "down":
                hammer[i] = True
            elif trend[i] == "up":
                hanging_man[i] = True
    out["hammer"] = hammer
    out["hanging_man"] = hanging_man

    # Inverted Hammer (downtrend) / Shooting Star (uptrend)
    inv_shape = _bool_arr()
    with np.errstate(divide="ignore", invalid="ignore"):
        inv_shape[valid_range] = (
            (body[valid_range] > 0)
            & (upper_shadow[valid_range] >= shadow_ratio * body[valid_range])
            & (lower_shadow[valid_range] <= body[valid_range] * 0.5)
        )
    inv_hammer = _bool_arr()
    shooting_star = _bool_arr()
    for i in range(n):
        if inv_shape[i]:
            if trend[i] == "down":
                inv_hammer[i] = True
            elif trend[i] == "up":
                shooting_star[i] = True
    out["inverted_hammer"] = inv_hammer
    out["shooting_star"] = shooting_star

    # Marubozu
    marubozu = _bool_arr()
    marubozu[valid_range] = (body[valid_range] >= 0.95 * full_range[valid_range])
    out["marubozu"] = marubozu

    # Belt Hold
    belt_hold_bullish = _bool_arr()
    belt_hold_bearish = _bool_arr()
    for i in range(n):
        if not valid_range[i] or body[i] == 0:
            continue
        if is_bullish[i] and lower_shadow[i] <= 0.05 * full_range[i] and upper_shadow[i] <= 0.3 * body[i]:
            belt_hold_bullish[i] = True
        if is_bearish[i] and upper_shadow[i] <= 0.05 * full_range[i] and lower_shadow[i] <= 0.3 * body[i]:
            belt_hold_bearish[i] = True
    out["belt_hold_bullish"] = belt_hold_bullish
    out["belt_hold_bearish"] = belt_hold_bearish

    # Spinning Top
    spinning_top = _bool_arr()
    for i in range(n):
        if not valid_range[i]:
            continue
        rp = _range_pct(i)
        if 0.1 < rp <= 0.3:
            us_pct = upper_shadow[i] / full_range[i] if full_range[i] > 0 else 0
            ls_pct = lower_shadow[i] / full_range[i] if full_range[i] > 0 else 0
            if abs(us_pct - ls_pct) <= 0.15:
                spinning_top[i] = True
    out["spinning_top"] = spinning_top

    # ─────────────────────────────────
    #  TWO-CANDLE PATTERNS
    # ─────────────────────────────────

    bullish_engulfing = _bool_arr()
    bearish_engulfing = _bool_arr()
    bullish_harami = _bool_arr()
    bearish_harami = _bool_arr()
    harami_cross = _bool_arr()
    piercing = _bool_arr()
    dark_cloud = _bool_arr()
    tweezer_top = _bool_arr()
    tweezer_bottom = _bool_arr()
    on_neck = _bool_arr()
    in_neck = _bool_arr()
    kicker_bullish = _bool_arr()
    kicker_bearish = _bool_arr()

    for i in range(1, n):
        p_open, p_high, p_low, p_close = open_[i - 1], high[i - 1], low[i - 1], close[i - 1]
        c_open, c_high, c_low, c_close = open_[i], high[i], low[i], close[i]

        p_body_low = min(p_open, p_close)
        p_body_high = max(p_open, p_close)
        c_body_low = min(c_open, c_close)
        c_body_high = max(c_open, c_close)
        p_bull = p_close > p_open
        p_bear = p_close < p_open
        c_bull = c_close > c_open
        c_bear = c_close < c_open

        # Engulfing (STRICT: current body must FULLY contain previous body)
        if p_bear and c_bull:
            if c_body_low < p_body_low and c_body_high > p_body_high:
                bullish_engulfing[i] = True
        if p_bull and c_bear:
            if c_body_low < p_body_low and c_body_high > p_body_high:
                bearish_engulfing[i] = True

        # Harami
        if p_bear and c_bull:
            if c_body_low > p_body_low and c_body_high < p_body_high:
                bullish_harami[i] = True
        if p_bull and c_bear:
            if c_body_low > p_body_low and c_body_high < p_body_high:
                bearish_harami[i] = True

        # Harami Cross
        if (p_bear and c_bull) or (p_bull and c_bear):
            if c_body_low > p_body_low and c_body_high < p_body_high:
                c_range = c_high - c_low
                if c_range > 0 and (abs(c_close - c_open) / c_range) <= doji_body_pct:
                    harami_cross[i] = True

        # Piercing Line
        if p_bear and c_bull:
            midpoint = (p_open + p_close) / 2.0
            if c_open < p_low and c_close > midpoint and c_close < p_open:
                piercing[i] = True

        # Dark Cloud Cover
        if p_bull and c_bear:
            midpoint = (p_open + p_close) / 2.0
            if c_open > p_high and c_close < midpoint and c_close > p_open:
                dark_cloud[i] = True

        # Tweezer Top (previous bullish, current bearish, same high)
        if p_bull and c_bear:
            if abs(c_high - p_high) / max(c_high, p_high) <= 0.01:
                tweezer_top[i] = True

        # Tweezer Bottom (previous bearish, current bullish, same low)
        if p_bear and c_bull:
            if abs(c_low - p_low) / max(c_low, p_low) <= 0.01:
                tweezer_bottom[i] = True

        # On-Neck Line
        if p_bear and c_bull:
            if abs(c_close - p_low) / max(c_close, p_low) <= 0.01:
                on_neck[i] = True

        # In-Neck Line
        if p_bear and c_bull:
            c_range = c_high - c_low
            if c_range > 0 and 0.01 < abs(c_close - p_low) / max(c_close, p_low) <= 0.03:
                in_neck[i] = True

        # Kicker Bullish
        if p_bear and c_bull:
            if c_low > p_high:
                kicker_bullish[i] = True

        # Kicker Bearish
        if p_bull and c_bear:
            if c_high < p_low:
                kicker_bearish[i] = True

    out["bullish_engulfing"] = bullish_engulfing
    out["bearish_engulfing"] = bearish_engulfing
    out["bullish_harami"] = bullish_harami
    out["bearish_harami"] = bearish_harami
    out["harami_cross"] = harami_cross
    out["piercing"] = piercing
    out["dark_cloud_cover"] = dark_cloud
    out["tweezer_top"] = tweezer_top
    out["tweezer_bottom"] = tweezer_bottom
    out["on_neck"] = on_neck
    out["in_neck"] = in_neck
    out["kicker_bullish"] = kicker_bullish
    out["kicker_bearish"] = kicker_bearish

    # ─────────────────────────────────
    #  THREE-CANDLE PATTERNS
    # ─────────────────────────────────

    morning_star = _bool_arr()
    evening_star = _bool_arr()
    abandoned_baby_bullish = _bool_arr()
    abandoned_baby_bearish = _bool_arr()
    three_white_soldiers = _bool_arr()
    three_black_crows = _bool_arr()
    three_inside_up = _bool_arr()
    three_inside_down = _bool_arr()
    three_outside_up = _bool_arr()
    three_outside_down = _bool_arr()
    rising_three = _bool_arr()
    falling_three = _bool_arr()

    def _body_pct(i: int) -> float:
        return body[i] / full_range[i] if full_range[i] > 0 else 0.5

    for i in range(2, n):
        c1, c2, c3 = i - 2, i - 1, i
        o1, h1, l1, c1_c = open_[c1], high[c1], low[c1], close[c1]
        o2, h2, l2, c2_c = open_[c2], high[c2], low[c2], close[c2]
        o3, h3, l3, c3_c = open_[c3], high[c3], low[c3], close[c3]

        b1_bull = c1_c > o1
        b1_bear = c1_c < o1
        b2_bull = c2_c > o2
        b2_bear = c2_c < o2
        b3_bull = c3_c > o3
        b3_bear = c3_c < o3

        b1_body = abs(c1_c - o1)
        b2_body = abs(c2_c - o2)
        b3_body = abs(c3_c - o3)
        b1_hi = max(o1, c1_c)
        b1_lo = min(o1, c1_c)
        b3_hi = max(o3, c3_c)
        b3_lo = min(o3, c3_c)

        # Morning Star — second candle gaps below first body (h2 < b1_hi)
        if b1_bear and b3_bull:
            c2_small = full_range[c2] > 0 and (_body_pct(c2) <= 0.3 or b2_body < b1_body * 0.3)
            if c2_small and h2 < b1_hi and c3_c > (o1 + c1_c) / 2.0:
                morning_star[c3] = True

        # Evening Star — second candle gaps above first body (l2 > b1_lo)
        if b1_bull and b3_bear:
            c2_small = full_range[c2] > 0 and (_body_pct(c2) <= 0.3 or b2_body < b1_body * 0.3)
            if c2_small and l2 > b1_lo and c3_c < (o1 + c1_c) / 2.0:
                evening_star[c3] = True

        # Abandoned Baby Bullish
        if morning_star[c3] and full_range[c2] > 0:
            if h2 < l1 and h2 < l3:
                abandoned_baby_bullish[c3] = True

        # Abandoned Baby Bearish
        if evening_star[c3] and full_range[c2] > 0:
            if l2 > h1 and l2 > h3:
                abandoned_baby_bearish[c3] = True

        # Three White Soldiers
        if b1_bull and b2_bull and b3_bull:
            if (c2_c > c1_c and c3_c > c2_c
                    and _body_pct(c1) >= 0.4 and _body_pct(c2) >= 0.4 and _body_pct(c3) >= 0.4):
                three_white_soldiers[c3] = True

        # Three Black Crows
        if b1_bear and b2_bear and b3_bear:
            if (c2_c < c1_c and c3_c < c2_c
                    and _body_pct(c1) >= 0.4 and _body_pct(c2) >= 0.4 and _body_pct(c3) >= 0.4):
                three_black_crows[c3] = True

        # Three Inside Up
        if b1_bear and b2_bull:
            if l2 > l1 and h2 < h1 and b3_bull and c3_c > h1:
                three_inside_up[c3] = True

        # Three Inside Down
        if b1_bull and b2_bear:
            if l2 > l1 and h2 < h1 and b3_bear and c3_c < l1:
                three_inside_down[c3] = True

        # Three Outside Up
        if b1_bear and b2_bull and h2 > h1 and l2 < l1:
            if b3_bull and c3_c > c2_c:
                three_outside_up[c3] = True

        # Three Outside Down
        if b1_bull and b2_bear and h2 > h1 and l2 < l1:
            if b3_bear and c3_c < c2_c:
                three_outside_down[c3] = True

    # ─────────────────────────────────
    #  FIVE-CANDLE PATTERNS (separate loop)
    # ─────────────────────────────────

    for i in range(4, n):
        p_open, p_high, p_low, p_close = open_[i - 4], high[i - 4], low[i - 4], close[i - 4]
        c_open, c_high, c_low, c_close = open_[i], high[i], low[i], close[i]

        p_body_hi = max(p_open, p_close)
        p_body_lo = min(p_open, p_close)
        p_bull = p_close > p_open
        p_bear = p_close < p_open
        c_bull = c_close > c_open
        c_bear = c_close < c_open

        # Rising Three Methods
        # 1: long bullish, 2-4: small bearish inside 1's range, 5: bullish > 1's close
        if p_bull and c_bull:
            p_body_pct = abs(p_close - p_open) / (p_high - p_low) if (p_high - p_low) > 0 else 0.5
            c_body_pct = abs(c_close - c_open) / (c_high - c_low) if (c_high - c_low) > 0 else 0.5
            if p_body_pct < 0.4 or c_body_pct < 0.4:
                continue
            inside = True
            for inner in [i - 3, i - 2, i - 1]:
                if not (p_body_lo <= min(open_[inner], close[inner])
                        and max(open_[inner], close[inner]) <= p_body_hi
                        and close[inner] < open_[inner]):
                    inside = False
                    break
            if inside and c_close > p_close:
                rising_three[i] = True

        # Falling Three Methods
        # 1: long bearish, 2-4: small bullish inside 1's range, 5: bearish < 1's close
        if p_bear and c_bear:
            p_body_pct = abs(p_close - p_open) / (p_high - p_low) if (p_high - p_low) > 0 else 0.5
            c_body_pct = abs(c_close - c_open) / (c_high - c_low) if (c_high - c_low) > 0 else 0.5
            if p_body_pct < 0.4 or c_body_pct < 0.4:
                continue
            inside = True
            for inner in [i - 3, i - 2, i - 1]:
                if not (p_body_lo <= min(open_[inner], close[inner])
                        and max(open_[inner], close[inner]) <= p_body_hi
                        and close[inner] > open_[inner]):
                    inside = False
                    break
            if inside and c_close < p_close:
                falling_three[i] = True

    out["morning_star"] = morning_star
    out["evening_star"] = evening_star
    out["abandoned_baby_bullish"] = abandoned_baby_bullish
    out["abandoned_baby_bearish"] = abandoned_baby_bearish
    out["three_white_soldiers"] = three_white_soldiers
    out["three_black_crows"] = three_black_crows
    out["three_inside_up"] = three_inside_up
    out["three_inside_down"] = three_inside_down
    out["three_outside_up"] = three_outside_up
    out["three_outside_down"] = three_outside_down
    out["rising_three_methods"] = rising_three
    out["falling_three_methods"] = falling_three

    return out


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
