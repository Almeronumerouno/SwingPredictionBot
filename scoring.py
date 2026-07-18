"""
scoring.py — Fase 2: Swing Score + Gating Logic.

Input: array indikator dari indicators.py (numpy, index sejajar).
Output: dict dengan Swing Score, komponen individual, rekomendasi, confidence.

4 komponen SwingScore (equal-weight, configurable via config.SCORE_WEIGHTS):
  - Trend    (EMA spread + ADX gating)
  - Momentum (RSI + MFI, ADX gated)
  - Volume   (RVOL + arah harga)
  - Price Action (S/R distance + Donchian breakout gated RVOL)

ATR TIDAK masuk SwingScore — dipindah ke risk.py (Fase 3) untuk SL/TP sizing.
"""
from __future__ import annotations

import numpy as np
import config


def _gate_adx(adx: np.ndarray) -> np.ndarray:
    """Gate factor dari ADX: naik linear 0→1 dari ADX=0 sampai ADX_GATE_CEILING.
    Begitu ADX nyentuh 25 (tren kuat Wilder), gate=1.0.
    """
    return np.minimum(adx / config.ADX_GATE_CEILING, 1.0)


def _clip(v: np.ndarray, lo: float = 0.0, hi: float = 1.0) -> np.ndarray:
    return np.clip(v, lo, hi)


# Step 2 — Normalisasi dasar
def _norm_rsi(rsi: np.ndarray) -> np.ndarray:
    return rsi / 100.0


def _norm_mfi(mfi: np.ndarray) -> np.ndarray:
    return mfi / 100.0


# Step 3 — EMA norm
def _ema_norm(ema_fast: np.ndarray, ema_slow: np.ndarray,
              atr: np.ndarray) -> np.ndarray:
    spread_atr = (ema_fast - ema_slow) / np.where(atr > 0, atr, np.nan)
    return _clip((spread_atr + 3.0) / 6.0, 0.0, 1.0)


# Step 4 — Trend Score
def _trend_score(ema_fast: np.ndarray, ema_slow: np.ndarray,
                 atr: np.ndarray, adx: np.ndarray) -> np.ndarray:
    en = _ema_norm(ema_fast, ema_slow, atr)
    gate = _gate_adx(adx)
    return 0.5 + (en - 0.5) * gate


# Step 5 — Momentum Score
def _momentum_score(rsi: np.ndarray, mfi: np.ndarray,
                    adx: np.ndarray) -> np.ndarray:
    raw = (_norm_rsi(rsi) + _norm_mfi(mfi)) / 2.0
    gate = _gate_adx(adx)
    return 0.5 + (raw - 0.5) * gate


# Step 6 — Volume Score
def _volume_score(rvol: np.ndarray, close: np.ndarray) -> np.ndarray:
    sign = np.where(close > np.roll(close, 1), 1.0, -1.0)
    sign[0] = 0.0
    clamped = _clip(rvol - 1.0, 0.0, 1.0)
    return 0.5 + sign * clamped * 0.5


# Step 7 — Price Action Score
def _price_action_score(
    close: np.ndarray,
    support: list,
    resistance: list,
    donchian_upper: np.ndarray,
    donchian_lower: np.ndarray,
    rvol: np.ndarray,
) -> np.ndarray:
    n = len(close)
    pa = np.full(n, np.nan)

    for i in range(n):
        if np.isnan(close[i]):
            continue

        # resistance level terdekat di atas harga
        sup = _nearest_level(close[i], support, below=True)
        res = _nearest_level(close[i], resistance, below=False)

        if sup is not None and res is not None and res > sup:
            base = _clip((close[i] - sup) / (res - sup), 0.0, 1.0)
        else:
            base = 0.5

        rvol_i = rvol[i] if not np.isnan(rvol[i]) else 0.0
        donch_upper = donchian_upper[i]
        donch_lower = donchian_lower[i]

        if not np.isnan(donch_upper) and close[i] > donch_upper and rvol_i >= config.RVOL_BREAKOUT_CONFIRM:
            pa[i] = 1.0
        elif not np.isnan(donch_lower) and close[i] < donch_lower and rvol_i >= config.RVOL_BREAKOUT_CONFIRM:
            pa[i] = 0.0
        else:
            pa[i] = base

    return pa


def _nearest_level(
    price: float, levels: list, below: bool = True
) -> float | None:
    """
    Cari level S/R terdekat: `below=True` → level <= price,
    `below=False` → level > price.
    """
    filtered = [l["level"] for l in levels if l.get("level") is not None]
    if not filtered:
        return None
    if below:
        candidates = [v for v in filtered if v <= price]
        return max(candidates) if candidates else None
    else:
        candidates = [v for v in filtered if v > price]
        return min(candidates) if candidates else None


# Step 10 — Confidence (two-factor: agreement + strength of evidence)
def _confidence(scores: dict, swing_score: float,
                gate: float, rvol: float) -> str:
    """
    confidence = agreement_score * strength_factor

    agreement_score: fraksi komponen yang searah majority swing.
    strength_factor: rata-rata gate (ADX-based) & rvol_strength.
    """
    values = [scores[k] for k in ("trend", "momentum", "volume", "price_action")]
    majority = 1.0 if swing_score > 50.0 else -1.0
    aligned = sum(1 for v in values if (v > 0.5) == (majority > 0))
    agreement_score = aligned / len(values)

    rvol_strength = _clip(rvol / config.RVOL_BREAKOUT_CONFIRM, 0.0, 1.0)
    strength_factor = (gate + rvol_strength) / 2.0

    raw = agreement_score * strength_factor
    if raw >= config.CONFIDENCE_HIGH_CUTOFF:
        return "tinggi"
    elif raw >= config.CONFIDENCE_LOW_CUTOFF:
        return "sedang"
    return "rendah"


# Step 10 — Risk Level
def _risk_level(atr: np.ndarray) -> str:
    """
    Risk level dari ATR ratio: atr[-1] / mean(atr[-RISK_ATR_LOOKBACK:]).
    Cutoff 0.8/1.5 adalah heuristik — perlu dikalibrasi di backtest.
    """
    lookback = config.RISK_ATR_LOOKBACK
    if len(atr) < lookback + 1:
        return "sedang"
    latest = atr[-1]
    baseline = np.nanmean(atr[-lookback:])
    if np.isnan(latest) or np.isnan(baseline) or baseline == 0:
        return "sedang"
    ratio = latest / baseline
    if ratio > config.RISK_HIGH_CUTOFF:
        return "tinggi"
    elif ratio < config.RISK_LOW_CUTOFF:
        return "rendah"
    return "sedang"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

ScoreInput = dict
"""
Dictionary input untuk compute_score, berisi array numpy (index sejajar) dan
scalar (index terakhir / hari ini):
  Wajib:
    - close (np.ndarray)
    - rsi (np.ndarray)
    - atr (np.ndarray)
    - adx (np.ndarray)
    - plus_di (np.ndarray)
    - minus_di (np.ndarray)
    - ema_fast (np.ndarray)
    - ema_slow (np.ndarray)
    - mfi (np.ndarray)
    - rvol (np.ndarray)
    - donchian_upper (np.ndarray)
    - donchian_lower (np.ndarray)
    - support (list[dict])  # dari support_resistance_levels["support"]
    - resistance (list[dict])  # dari support_resistance_levels["resistance"]
"""


def compute_score(data: ScoreInput) -> dict:
    """
    Hitung Swing Score lengkap dan return rekomendasi.

    Args:
        data: dict sesuai ScoreInput.

    Returns:
        dict dengan keys:
          - valid (bool): False kalau ada komponen NaN
          - swing_score (float): 0-100, None kalau valid=False
          - components (dict): skor tiap komponen (0-1)
          - recommendation (str): "BUY" / "SELL" / "HOLD", None kalau valid=False
          - confidence (str): "tinggi" / "sedang" / "rendah"
          - risk_level (str): "rendah" / "sedang" / "tinggi"
          - prob_continuation (None): placeholder — butuh backtest
          - prob_reversal (None): placeholder — butuh backtest
    """
    w = config.SCORE_WEIGHTS

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

    trend_scores = _trend_score(ema_fast, ema_slow, atr_arr, adx_arr)
    momentum_scores = _momentum_score(rsi, mfi_arr, adx_arr)
    volume_scores = _volume_score(rvol_arr, close)
    pa_scores = _price_action_score(
        close, support, resistance, donch_upper, donch_lower, rvol_arr
    )

    # Ambil index terakhir (hari ini)
    i = -1
    is_valid = not (
        np.isnan(trend_scores[i])
        or np.isnan(momentum_scores[i])
        or np.isnan(volume_scores[i])
        or np.isnan(pa_scores[i])
    )
    if not is_valid:
        return {
            "valid": False,
            "swing_score": None,
            "components": {},
            "recommendation": None,
            "confidence": None,
            "risk_level": None,
            "prob_continuation": None,
            "prob_reversal": None,
        }

    components = {
        "trend": float(trend_scores[i]),
        "momentum": float(momentum_scores[i]),
        "volume": float(volume_scores[i]),
        "price_action": float(pa_scores[i]),
    }

    swing_score = 100.0 * (
        w["trend"] * components["trend"]
        + w["momentum"] * components["momentum"]
        + w["volume"] * components["volume"]
        + w["price_action"] * components["price_action"]
    )

    # Step 9 — Threshold → Rekomendasi
    if swing_score >= config.SWING_BUY_THRESHOLD:
        rec = "BUY"
    elif swing_score <= config.SWING_SELL_THRESHOLD:
        rec = "SELL"
    else:
        rec = "HOLD"

    # Step 10 — Confidence & Risk
    gate = float(_gate_adx(adx_arr)[i])
    rvol_today = float(rvol_arr[i]) if not np.isnan(rvol_arr[i]) else 0.0
    confidence = _confidence(components, swing_score, gate, rvol_today)
    risk_level = _risk_level(atr_arr)

    return {
        "valid": True,
        "swing_score": round(swing_score, 1),
        "components": components,
        "recommendation": rec,
        "confidence": confidence,
        "risk_level": risk_level,
        "prob_continuation": None,
        "prob_reversal": None,
    }


if __name__ == "__main__":
    print("scoring.py — gunakan test_real_data.py untuk smoke test")
