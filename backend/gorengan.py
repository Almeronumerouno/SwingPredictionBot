"""
gorengan.py — Gorengan Detection Engine.

Menghitung Gorengan Risk Score (0-100) yang memperkirakan probabilitas
sebuah saham menunjukkan karakteristik pump-and-dump ("saham gorengan").

Ini BUKAN sinyal buy/sell. Ini adalah risk assessment layer yang
memperingatkan user ketika price action menyerupai perilaku gorengan.

7 komponen:
  1. Historical P&D Profile (15%) — rekam jejak pump & dump di masa lalu
  2. Liquidity Risk       (15%) — saham tidak likuid (structural)
  3. Market Cap           (10%) — ukuran perusahaan (data shares)
  4. Active Pump          (30%) — short-term: RVOL spike + momentum 5d/10d + ATR expansion
  5. Mid Momentum (20d)   (10%) — return searah 20 hari (Z-score)
  6. Distribution Risk    (10%) — pola distribusi (dump)
  7. Turnover + Gaps      (10%) — turnover ratio + gap-up beruntun
  + Pemantauan Khusus    (+10 bonus)

Active Pump pake raw thresholds (bukan time-series Z-score) biar gak kalah
sama saham yang baseline-nya udah tinggi duluan (BHAT, NEST — UMA sejak Juni).
Deteksi peak RVOL 14 hari, momentum 5d + 10d, dan ATR expansion 5d vs 14d.
Level threshold: EXTREME >65, HIGH >45, MEDIUM >20.

Validated against 45 BEI UMA stocks (Jun-Jul 2026): 48.9% HIGH+, 95.6% MEDIUM+.
Z-score only: 2.9% HIGH+, 70.6% MEDIUM+.

Dependensi: numpy saja.
"""

from __future__ import annotations

import numpy as np

import config as CFG


# ---------------------------------------------------------------------------
# Helper: Z-score
# ---------------------------------------------------------------------------

def _zscore(arr: np.ndarray, lookback: int = 60) -> float:
    """
    Z-score observasi TERAKHIR terhadap baseline `lookback` observasi
    SEBELUMNYA (audit #12: konsisten dengan konvensi `indicators.rvol()`
    yang mengecualikan hari berjalan — menghindari self-referencing di mana
    nilai ekstrem menarik mean/std baseline ke arah dirinya sendiri dan
    meredam skor anomali).
    """
    valid = arr[~np.isnan(arr)]
    if len(valid) < 11:
        return 0.0
    baseline = valid[-lookback:-1] if len(valid) > lookback else valid[:-1]
    if len(baseline) < 10:
        return 0.0
    mu = np.mean(baseline)
    sigma = np.std(baseline, ddof=1)
    if sigma == 0:
        return 0.0
    return float((valid[-1] - mu) / sigma)


def _zscore_to_score(z: float) -> float:
    if z > CFG.GORENGAN_ZSCORE_HIGH:
        return 100.0
    elif z > CFG.GORENGAN_ZSCORE_MED:
        return 60.0
    elif z > CFG.GORENGAN_ZSCORE_LOW:
        return 25.0
    return 0.0


def _volume_anomaly(rvol_arr: np.ndarray) -> tuple[float, str | None]:
    """Volume anomaly via Z-score RVOL, dengan persistensi (≥2 dari 3 hari terakhir)."""
    n = len(rvol_arr)
    if n < 2:
        return 0.0, None

    recent = rvol_arr[-min(3, n):]
    recent = recent[~np.isnan(recent)]
    if len(recent) == 0:
        return 0.0, None

    persist = sum(1 for v in recent if v > 0)  # at least positive
    if persist < 2 and len(recent) >= 2:
        return 0.0, None

    z = _zscore(rvol_arr)
    score = _zscore_to_score(z)
    val = float(np.max(recent))

    warning = None
    if score > 50:
        warning = f"Volume melonjak {val:.1f}x dari rata-rata (Z={z:.1f}) — kemungkinan akumulasi/distribusi tidak wajar"
    return score, warning


# ---------------------------------------------------------------------------
# 1. Volume Anomaly (10%)
# ---------------------------------------------------------------------------

def _volatility(atr_arr: np.ndarray) -> tuple[float, str | None]:
    """Volatility anomaly via Z-score ATR."""
    z = _zscore(atr_arr)

    if z > 0:
        score = _zscore_to_score(z)
    else:
        score = 0.0

    warning = None
    if score > 50:
        valid = atr_arr[~np.isnan(atr_arr)]
        ratio = valid[-1] / np.mean(valid[-min(60, len(valid)):]) if len(valid) >= 2 else 0
        warning = f"Volatilitas meledak (Z={z:.1f}) — pergerakan harga sangat tidak stabil"
    return score, warning


# ---------------------------------------------------------------------------
# 2. Volatility (Z-score) (10%)
# ---------------------------------------------------------------------------

def _momentum(close: np.ndarray, n: int = 20) -> tuple[float, str | None]:
    """Momentum = (close[-1] - close[-1-n]) / close[-1-n] * 100, di-Z-score."""
    if len(close) <= n + 1:
        return 0.0, None
    returns = np.diff(close) / close[:-1] * 100
    z = _zscore(returns, lookback=n)

    score = _zscore_to_score(z) if z > 0 else 0.0

    mom_val = (close[-1] - close[-1 - n]) / close[-1 - n] * 100
    warning = None
    if score > 50:
        warning = f"Momentum tajam {mom_val:+.1f}% dalam {n} hari (Z={z:.1f}) — akselerasi harga tidak wajar"
    return score, warning


# ---------------------------------------------------------------------------
# 3. Momentum (Z-score) (10%)
# ---------------------------------------------------------------------------

def _liquidity_risk(close: np.ndarray, volume: np.ndarray) -> tuple[float, str | None]:
    """Deteksi saham tidak likuid berdasarkan median daily value 60 hari.
    Kita pakai median agar lonjakan transaksi saat 'digoreng' tidak menutupi fakta 
    bahwa saham ini biasanya sangat sepi (tidak likuid)."""
    lookback = min(60, len(close))
    daily_value = close[-lookback:] * volume[-lookback:]
    median_value = np.median(daily_value)

    if median_value > CFG.GORENGAN_LIQ_HIGH:
        score = 0.0
    elif median_value > CFG.GORENGAN_LIQ_MED:
        score = 25.0
    elif median_value > CFG.GORENGAN_LIQ_LOW:
        score = 60.0
    elif median_value > CFG.GORENGAN_LIQ_MIN:
        score = 80.0
    else:
        score = 100.0

    warning = None
    if score > 50:
        med_million = median_value / 1e6
        warning = f"Saham pada dasarnya sepi/tidak likuid (median transaksi normal: Rp{med_million:,.0f}jt) — sangat mudah disetir bandar"
    return score, warning


# ---------------------------------------------------------------------------
# 4. Liquidity Risk (20%)
# ---------------------------------------------------------------------------

def _market_cap_risk(shares: float | None, close_price: float) -> tuple[float, str | None]:
    """Ukur risiko berdasarkan market cap. Data shares dari securities_list.json."""
    if shares is None or shares <= 0:
        return 0.0, None

    mcap = shares * close_price

    if mcap < CFG.GORENGAN_MCAP_HIGH:
        score = 100.0
    elif mcap < CFG.GORENGAN_MCAP_MED:
        score = 60.0
    elif mcap < CFG.GORENGAN_MCAP_LOW:
        score = 25.0
    else:
        score = 0.0

    warning = None
    if score > 50:
        mcap_b = mcap / 1e12
        warning = f"Market cap kecil (Rp{mcap_b:.2f}T) — saham dengan ukuran ini sangat mudah disetir bandar"
    return score, warning


# ---------------------------------------------------------------------------
# 6. Turnover + Pump-phase Gaps (10%)
# ---------------------------------------------------------------------------

def _turnover_risk(volume: np.ndarray, shares: float | None) -> tuple[float, str | None]:
    """Turnover = volume / shares_outstanding. Berapa % float berputar dalam sehari."""
    if shares is None or shares <= 0 or len(volume) < 1:
        return 0.0, None

    turnover = volume[-1] / shares

    if turnover > CFG.GORENGAN_TURNOVER_HIGH:
        score = 100.0
    elif turnover > CFG.GORENGAN_TURNOVER_MED:
        score = 60.0
    elif turnover > CFG.GORENGAN_TURNOVER_LOW:
        score = 25.0
    else:
        score = 0.0

    warning = None
    if score > 50:
        warning = f"Turnover {turnover*100:.1f}% float dalam sehari — porsi besar saham berpindah tangan"
    return score, warning


def _consecutive_gaps(
    open_: np.ndarray, close: np.ndarray,
) -> tuple[float, str | None]:
    """Pump-phase: gap-up beruntun dalam 5 hari terakhir."""
    n = len(close)
    if n < 3:
        return 0.0, None

    gaps = 0
    lookback = min(5, n)
    for i in range(-lookback + 1, 0):
        if open_[i] > close[i - 1] * (1 + CFG.GORENGAN_GAP_PCT / 100):
            gaps += 1

    score = min(100, gaps / CFG.GORENGAN_GAP_COUNT * 100) if CFG.GORENGAN_GAP_COUNT > 0 else 0

    warning = None
    if score > 50:
        warning = f"{gaps}x gap-up dalam {lookback} hari — fase pump klasik sebelum potensi dump"
    return score, warning


# ---------------------------------------------------------------------------
# 7. Distribution Risk (10%)
# ---------------------------------------------------------------------------

def _distribution_risk(
    close: np.ndarray, open_: np.ndarray,
    high: np.ndarray, low: np.ndarray,
    volume: np.ndarray,
) -> tuple[float, str | None]:
    """Deteksi pola distribusi klasik (dump behavior)."""
    n = len(close)
    if n < 5:
        return 0.0, None

    conditions_met = 0

    # Price near 20D high
    lookback = min(20, n)
    high_20d = np.max(high[-lookback:])
    if close[-1] >= 0.95 * high_20d:
        conditions_met += 1

    # Volume increasing
    vol_avg_5 = np.mean(volume[-min(5, n):])
    if volume[-1] > vol_avg_5:
        conditions_met += 1

    # Close near low of the day (bearish candle body position)
    day_range = high[-1] - low[-1]
    if day_range > 0:
        close_position = (close[-1] - low[-1]) / day_range
        if close_position < 0.3:
            conditions_met += 1

    # Long upper wick
    body = abs(close[-1] - open_[-1])
    upper_wick = high[-1] - max(open_[-1], close[-1])
    if body > 0 and upper_wick > 2 * body:
        conditions_met += 1

    # Score: 0, 1, 2, 3, 4 conditions => 0, 25, 50, 80, 100
    score_map = {0: 0, 1: 25, 2: 50, 3: 80, 4: 100}
    score = float(score_map.get(conditions_met, 100))

    warning = None
    if score > 50:
        warning = "Distribusi terdeteksi: harga di dekat tertinggi tapi close di dekat terendah — kemungkinan bandar sedang jual"
    return score, warning


# ---------------------------------------------------------------------------
# 8. Historical Pump & Dump Profile (20%)
# ---------------------------------------------------------------------------

def _historical_pump_and_dump_profile(
    high: np.ndarray, low: np.ndarray, close: np.ndarray
) -> tuple[float, str | None]:
    """Mendeteksi riwayat (1 tahun terakhir) dari kejadian Pump & Dump."""
    n = len(close)
    if n < 60:  # Butuh minimal histori cukup untuk mendeteksi siklus
        return 0.0, None

    # Algoritma pencarian puncak ekstrem
    pump_dump_count = 0
    max_pump_severity = 0.0

    i = 40  # Mulai dari hari ke-40 agar punya ruang untuk cek masa lalu dan masa depan
    while i < n - 10:
        # Puncak lokal di sekitar area ini?
        local_high_idx = i - 10 + np.argmax(high[i-10:i+10])
        peak_price = high[local_high_idx]
        
        # Cek harga terendah SEBELUM puncak (maksimal 30 hari sebelumnya)
        start_idx = max(0, local_high_idx - 30)
        base_low = np.min(low[start_idx:local_high_idx]) if local_high_idx > start_idx else peak_price
        
        # Cek harga terendah SESUDAH puncak (maksimal 40 hari sesudahnya)
        end_idx = min(n, local_high_idx + 40)
        crash_low = np.min(low[local_high_idx+1:end_idx]) if end_idx > local_high_idx+1 else peak_price
        
        if base_low > 0 and peak_price > 0:
            pump_pct = (peak_price - base_low) / base_low * 100
            dump_pct = (peak_price - crash_low) / peak_price * 100
            
            # Kriteria P&D: Naik drastis, lalu dibanting dalam waktu singkat
            if pump_pct > CFG.GORENGAN_PUMP_PCT and dump_pct > CFG.GORENGAN_DUMP_PCT:
                pump_dump_count += 1
                if pump_pct > max_pump_severity:
                    max_pump_severity = pump_pct
                # Lompat ke depan untuk menghindari mendeteksi gunung yang sama dua kali
                i = local_high_idx + 40
                continue
        i += 10
        
    if pump_dump_count >= 2:
        score = 100.0
    elif pump_dump_count == 1:
        if max_pump_severity > CFG.GORENGAN_SWING_EXTREME:
            score = 80.0
        else:
            score = 50.0
    else:
        score = 0.0

    warning = None
    if score > 80:
        warning = f"Riwayat Kriminal: Saham ini terdeteksi sebagai serial gorengan ({pump_dump_count}x siklus Pump & Dump tajam dalam setahun)"
    elif score > 40:
        warning = f"Riwayat Pump & Dump: Pernah ditarik naik {max_pump_severity:.0f}% lalu dibanting dalam setahun terakhir"
        
    return score, warning


# ---------------------------------------------------------------------------
# Active Pump — short-term raw-threshold detection
# ---------------------------------------------------------------------------

def _active_pump(
    rvol_arr: np.ndarray,
    close: np.ndarray,
    atr_arr: np.ndarray,
) -> tuple[float, str | None]:
    """
    Deteksi pump aktif via raw thresholds (bukan Z-score).

    Kebalikan dari Z-score yang gampang kalah sama saham dengan baseline
    volatile tinggi (BHAT, NEST, dll yang UMA sejak Juni).

    Logic:
      1. RVOL latest + RVOL max dalam 14 hari (catch stock yg baru spike)
      2. 5d momentum + 10d momentum (raw return)
      3. 5d ATR expansion vs 14d baseline

    Ambil MAX dari semuanya.
    """
    scores = []

    # 1. Raw RVOL spike — latest bar + max dalam 14 hari terakhir
    rv = rvol_arr[~np.isnan(rvol_arr)]
    if len(rv) > 0:
        rv_last = float(rv[-1])
        if rv_last > CFG.GORENGAN_RVOL_EXTREME:
            scores.append(100)
        elif rv_last > CFG.GORENGAN_RVOL_HIGH:
            scores.append(70)
        elif rv_last > CFG.GORENGAN_RVOL_MODERATE:
            scores.append(30)

        # Peak RVOL dalam 14 hari — catch yg udah settle tapi masih residual
        recent_rv = rv[-min(14, len(rv)):]
        peak_rv = float(np.max(recent_rv))
        if peak_rv > rv_last:
            if peak_rv > CFG.GORENGAN_RVOL_EXTREME:
                scores.append(70)
            elif peak_rv > CFG.GORENGAN_RVOL_HIGH:
                scores.append(50)

    # 2. Short momentum (5-day return %) + mid (10-day)
    for lookback, thresholds in [
        (5, (CFG.GORENGAN_MOMENTUM_EXTREME, CFG.GORENGAN_MOMENTUM_HIGH,
             CFG.GORENGAN_MOMENTUM_MODERATE, CFG.GORENGAN_MOMENTUM_LOW)),
        (10, (CFG.GORENGAN_MOMENTUM_10D_EXTREME, CFG.GORENGAN_MOMENTUM_10D_HIGH,
              CFG.GORENGAN_MOMENTUM_10D_MODERATE, CFG.GORENGAN_MOMENTUM_10D_LOW)),
    ]:
        if len(close) > lookback:
            ret = (close[-1] - close[-1 - lookback]) / close[-1 - lookback] * 100
            if ret > thresholds[0]:
                scores.append(100)
            elif ret > thresholds[1]:
                scores.append(70)
            elif ret > thresholds[2]:
                scores.append(40)
            elif ret > thresholds[3]:
                scores.append(20)

    # 3. Short ATR expansion ratio
    valid_atr = atr_arr[~np.isnan(atr_arr)]
    if len(valid_atr) >= 10:
        recent = np.mean(valid_atr[-5:])
        baseline = np.mean(valid_atr[-14:-5])
        if baseline > 0:
            ratio = recent / baseline
            if ratio > CFG.GORENGAN_VOLA_EXTREME:
                scores.append(100)
            elif ratio > CFG.GORENGAN_VOLA_HIGH:
                scores.append(70)
            elif ratio > CFG.GORENGAN_VOLA_MODERATE:
                scores.append(40)

    score = float(max(scores)) if scores else 0.0
    warning = None
    if score > 50:
        warning = (
            "Aktivitas pump terdeteksi: volume melonjak +/atau "
            "momentum tajam dalam 5 hari terakhir"
        )
    return score, warning


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_gorengan(
    close: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    atr_arr: np.ndarray,
    adx_arr: np.ndarray,
    rvol_arr: np.ndarray,
    shares: float | None = None,
    listing_board: str | None = None,
) -> dict:
    """
    Hitung Gorengan Risk Score untuk satu saham.

    Args:
        shares: Total shares outstanding (dari securities_list.json).
        listing_board: Pencatatan BEI (Utama / Pengembangan / Pemantauan Khusus).

    Returns:
        dict dengan keys:
          - score (float): 0-100
          - level (str): LOW / MEDIUM / HIGH / EXTREME
          - factors (dict): skor tiap komponen (0-100)
          - warnings (list[str]): peringatan spesifik
          - explanation (str): penjelasan human-readable
    """
    liq_score, liq_warn = _liquidity_risk(close, volume)

    close_price = float(close[-1]) if len(close) > 0 else 0
    mcap_score, mcap_warn = _market_cap_risk(shares, close_price)

    mom_score, mom_warn = _momentum(close)
    active_score, active_warn = _active_pump(rvol_arr, close, atr_arr)

    to_score, to_warn = _turnover_risk(volume, shares)
    gap_score, gap_warn = _consecutive_gaps(open_, close)
    turnover_gaps_score = max(to_score, gap_score)
    turnover_gaps_warn = to_warn or gap_warn

    dist_score, dist_warn = _distribution_risk(close, open_, high, low, volume)
    hist_score, hist_warn = _historical_pump_and_dump_profile(high, low, close)

    # Listing board bonus → warning only (no weight)
    has_board_flag = listing_board == "Pemantauan Khusus"

    # Weighted sum (total 100%)
    weights = {
        "hist": 0.15,
        "liq": 0.15,
        "mcap": 0.10,
        "active": 0.30,
        "mom": 0.10,
        "dist": 0.10,
        "turnover_gaps": 0.10,
    }
    raw_score = (
        weights["hist"] * hist_score
        + weights["liq"] * liq_score
        + weights["mcap"] * mcap_score
        + weights["active"] * active_score
        + weights["mom"] * mom_score
        + weights["dist"] * dist_score
        + weights["turnover_gaps"] * turnover_gaps_score
    )
    # Board flag: flat +10 if Pemantauan Khusus
    if has_board_flag:
        raw_score += 10.0
    final_score = float(np.clip(raw_score, 0, 100))

    # Level classification — lowered thresholds
    if final_score > CFG.GORENGAN_LEVEL_EXTREME:
        level = "EXTREME"
    elif final_score > CFG.GORENGAN_LEVEL_HIGH:
        level = "HIGH"
    elif final_score > CFG.GORENGAN_LEVEL_MEDIUM:
        level = "MEDIUM"
    else:
        level = "LOW"

    # Collect warnings
    warnings = [w for w in [
        hist_warn, liq_warn, active_warn, mom_warn,
        mcap_warn, to_warn, gap_warn, dist_warn,
    ] if w is not None]

    if has_board_flag:
        warnings.append("Saham di papan Pemantauan Khusus BEI — sinyal risiko dari regulator")

    # Explanation
    if level == "EXTREME":
        explanation = (
            f"Skor gorengan {final_score:.0f}/100 — EXTREME. "
            "Saham ini menunjukkan karakteristik pump-and-dump yang sangat kuat. "
            "Harga kemungkinan besar sedang digoreng. Trading dengan sangat hati-hati "
            "atau hindari sepenuhnya."
        )
    elif level == "HIGH":
        explanation = (
            f"Skor gorengan {final_score:.0f}/100 — HIGH. "
            "Beberapa indikator menunjukkan kemungkinan manipulasi harga. "
            "Pertimbangkan risiko dengan matang sebelum masuk posisi."
        )
    elif level == "MEDIUM":
        explanation = (
            f"Skor gorengan {final_score:.0f}/100 — MEDIUM. "
            "Ada beberapa tanda spekulatif, namun belum mencapai level berbahaya. "
            "Tetap waspada dan gunakan stop loss ketat."
        )
    else:
        explanation = (
            f"Skor gorengan {final_score:.0f}/100 — LOW. "
            "Saham ini menunjukkan perilaku harga yang relatif normal dan wajar."
        )

    factors = {
        "historical_pump_dump_risk": round(hist_score, 1),
        "liquidity_risk": round(liq_score, 1),
        "market_cap_risk": round(mcap_score, 1),
        "active_pump": round(active_score, 1),
        "mid_momentum": round(mom_score, 1),
        "distribution_risk": round(dist_score, 1),
        "turnover_gaps": round(turnover_gaps_score, 1),
    }

    return {
        "score": round(final_score, 1),
        "level": level,
        "factors": factors,
        "warnings": warnings,
        "explanation": explanation,
    }
