from __future__ import annotations

import numpy as np

import config
from regime import detect_regime, get_regime_profile


def _clip(v: np.ndarray, lo: float = 0.0, hi: float = 1.0) -> np.ndarray:
    return np.clip(v, lo, hi)


def _gate_adx(adx: np.ndarray) -> np.ndarray:
    return np.minimum(adx / config.ADX_GATE_CEILING, 1.0)


def _trend_score(ema_fast: np.ndarray, ema_slow: np.ndarray, atr: np.ndarray, adx: np.ndarray) -> np.ndarray:
    spread_atr = (ema_fast - ema_slow) / np.where(atr > 0, atr, np.nan)
    en = _clip((spread_atr + 3.0) / 6.0, 0.0, 1.0)
    gate = _gate_adx(adx)
    return 0.5 + (en - 0.5) * gate


def _momentum_score(rsi: np.ndarray, mfi: np.ndarray, adx: np.ndarray) -> np.ndarray:
    raw = ((rsi / 100.0) + (mfi / 100.0)) / 2.0
    gate = _gate_adx(adx)
    return 0.5 + (raw - 0.5) * gate


def _volume_score(rvol: np.ndarray, close: np.ndarray) -> np.ndarray:
    sign = np.where(close > np.roll(close, 1), 1.0, -1.0)
    sign[0] = 0.0
    clamped = _clip(rvol - 1.0, 0.0, 1.0)
    return 0.5 + sign * clamped * 0.5


def _nearest_level(price: float, levels: list, below: bool = True) -> float | None:
    filtered = [l["level"] for l in levels if l.get("level") is not None]
    if not filtered:
        return None
    if below:
        candidates = [v for v in filtered if v <= price]
        return max(candidates) if candidates else None
    candidates = [v for v in filtered if v > price]
    return min(candidates) if candidates else None


def _price_action_score(close, support, resistance, donchian_upper, donchian_lower, rvol):
    n = len(close)
    pa = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(close[i]):
            continue
        sup = _nearest_level(close[i], support, below=True)
        res = _nearest_level(close[i], resistance, below=False)
        if sup is not None and res is not None and res > sup:
            base = _clip((close[i] - sup) / (res - sup), 0.0, 1.0)
        else:
            base = 0.5

        rvol_i = rvol[i] if not np.isnan(rvol[i]) else 0.0
        prev_upper = donchian_upper[i - 1] if i > 0 else np.nan
        prev_lower = donchian_lower[i - 1] if i > 0 else np.nan
        if not np.isnan(prev_upper) and close[i] > prev_upper and rvol_i >= config.RVOL_BREAKOUT_CONFIRM:
            pa[i] = 1.0
        elif not np.isnan(prev_lower) and close[i] < prev_lower and rvol_i >= config.RVOL_BREAKOUT_CONFIRM:
            pa[i] = 0.0
        else:
            pa[i] = base
    return pa


# Fallback buy threshold — selalu sama dengan config (audit #15: konstanta
# duplikat `BUY_THRESHOLD=70` lama yang beda nilai sudah dihapus).
BUY_THRESHOLD = config.SWING_BUY_THRESHOLD


def risk_level_from_atr(atr: np.ndarray, i: int = -1) -> str:
    """
    Risk level berdasar rasio ATR bar ke-i vs baseline ATR `RISK_ATR_LOOKBACK`
    hari SEBELUMNYA (single source of truth — dipakai live & backtest).

    ratio > RISK_HIGH_CUTOFF (1.5x) -> "tinggi"   (SL diketatkan 0.8x)
    ratio < RISK_LOW_CUTOFF  (0.8x) -> "rendah"
    selain itu                       -> "sedang"
    """
    if i < 0:
        i = len(atr) + i
    if i < config.RISK_ATR_LOOKBACK:
        return "sedang"
    latest = atr[i]
    baseline = float(np.nanmean(atr[i - config.RISK_ATR_LOOKBACK:i]))
    if np.isnan(latest) or np.isnan(baseline) or baseline == 0:
        return "sedang"
    ratio = float(latest) / baseline
    if ratio > config.RISK_HIGH_CUTOFF:
        return "tinggi"
    elif ratio < config.RISK_LOW_CUTOFF:
        return "rendah"
    return "sedang"


def confidence_from_score(
    components: dict,
    swing_score: float,
    gate: float,
    rvol: float,
    recommendation: str | None = None,
    rvol_breakout_confirm: float = config.RVOL_BREAKOUT_CONFIRM,
) -> str:
    """
    Confidence berdasar agreement antar komponen skor + ADX gate + RVOL.
    Identik dengan logika `_confidence()` lama di backtest.py (audit: pindah
    ke sini agar live API & backtest memakai logika yang sama).
    """
    values = list(components.values())
    majority = 1.0 if swing_score > 50.0 else -1.0
    aligned = sum(1 for v in values if (v > 0.5) == (majority > 0))
    agreement_score = aligned / len(values) if values else 0.0
    rvol_strength = min(rvol / rvol_breakout_confirm, 1.0) if rvol > 0 else 0.0
    strength_factor = (gate + rvol_strength) / 2.0
    raw = agreement_score * strength_factor
    if raw >= config.CONFIDENCE_HIGH_CUTOFF:
        tier = "tinggi"
    elif raw >= config.CONFIDENCE_LOW_CUTOFF:
        tier = "sedang"
    else:
        tier = "rendah"
    if recommendation == "BUY":
        tier = {"tinggi": "sedang", "sedang": "rendah", "rendah": "rendah"}[tier]
    return tier


def _price_stagnation_gate(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> bool:
    n = len(close)
    if n < config.STAGNATION_LOOKBACK:
        return False
    recent_high = float(np.nanmax(high[-config.STAGNATION_LOOKBACK:]))
    recent_low = float(np.nanmin(low[-config.STAGNATION_LOOKBACK:]))
    if recent_high == recent_low or close[-1] == 0:
        return True
    range_pct = (recent_high - recent_low) / close[-1]
    return range_pct < config.STAGNATION_RANGE_PCT


def compute_score(data: dict) -> dict:
    close = data["close"]
    rsi = data["rsi"]
    atr_arr = data["atr"]
    adx_arr = data["adx"]
    mfi_arr = data["mfi"]
    rvol_arr = data["rvol"]
    ema_fast = data["ema_fast"]
    ema_slow = data["ema_slow"]
    donch_upper = data["donchian_upper"]
    donch_lower = data["donchian_lower"]
    support = data.get("support", [])
    resistance = data.get("resistance", [])
    high_arr = data.get("high")
    low_arr = data.get("low")

    regime = detect_regime(close, adx_arr)
    profile = get_regime_profile(regime)
    w = profile.weights

    trend_scores = _trend_score(ema_fast, ema_slow, atr_arr, adx_arr)
    momentum_scores = _momentum_score(rsi, mfi_arr, adx_arr)
    volume_scores = _volume_score(rvol_arr, close)
    pa_scores = _price_action_score(close, support, resistance, donch_upper, donch_lower, rvol_arr)

    i = -1
    if any(np.isnan(x[i]) for x in (trend_scores, momentum_scores, volume_scores, pa_scores)):
        return {"valid": False, "swing_score": None, "components": None, "recommendation": None, "confidence": None, "risk_level": None, "prob_continuation": None, "prob_reversal": None, "regime": regime}

    components = {
        "trend": float(trend_scores[i]),
        "momentum": float(momentum_scores[i]),
        "volume": float(volume_scores[i]),
        "price_action": float(pa_scores[i]),
    }

    raw_score = 100.0 * (
        w["trend"] * components["trend"]
        + w["momentum"] * components["momentum"]
        + w["volume"] * components["volume"]
        + w["price_action"] * components["price_action"]
    )

    effective_score = raw_score * profile.multiplier
    swing_score = round(effective_score, 1)

    buy_thr = profile.buy_threshold if profile.buy_threshold is not None else BUY_THRESHOLD
    if swing_score >= buy_thr:
        rec = "BUY"
    elif swing_score <= profile.sell_threshold:
        rec = "SELL"
    else:
        rec = "HOLD"

    is_stagnant = high_arr is not None and low_arr is not None and _price_stagnation_gate(high_arr, low_arr, close)
    if is_stagnant and rec != "HOLD":
        rec = "HOLD"
        swing_score = min(swing_score, 50.0)

    # risk_level & confidence DINAMIS (audit #6): dulu hardcoded "sedang" sehingga
    # cabang tighten-SL di risk.py tidak pernah aktif di jalur live. Sekarang
    # memakai fungsi yang sama dengan backtest (single source of truth).
    risk_level = risk_level_from_atr(atr_arr, -1)
    gate_i = float(_gate_adx(adx_arr)[-1]) if not np.isnan(adx_arr[-1]) else 0.0
    rvol_i = float(rvol_arr[-1]) if not np.isnan(rvol_arr[-1]) else 0.0
    confidence = confidence_from_score(
        components, swing_score, gate_i, rvol_i, recommendation=rec
    )

    return {
        "valid": True,
        "swing_score": swing_score,
        "components": components,
        "recommendation": rec,
        "confidence": confidence,
        "risk_level": risk_level,
        "prob_continuation": None,
        "prob_reversal": None,
        "regime": regime,
    }
