from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import config


@dataclass(frozen=True)
class RegimeProfile:
    name: str
    weights: dict[str, float]
    buy_threshold: int | None
    sell_threshold: int
    position_pct: float
    multiplier: float = 1.0


_REGIME_PROFILES = {
    "bull": RegimeProfile(
        name="bull",
        weights={"trend": 0.35, "momentum": 0.25, "volume": 0.15, "price_action": 0.25},
        buy_threshold=72,
        sell_threshold=config.SWING_SELL_THRESHOLD,
        position_pct=1.0,
        multiplier=config.REGIME_MULTIPLIER_BULL,
    ),
    "sideways": RegimeProfile(
        name="sideways",
        weights={"trend": 0.15, "momentum": 0.15, "volume": 0.25, "price_action": 0.45},
        buy_threshold=68,
        sell_threshold=config.SWING_SELL_THRESHOLD,
        position_pct=0.5,
        multiplier=config.REGIME_MULTIPLIER_SIDEWAYS,
    ),
    "bear": RegimeProfile(
        name="bear",
        weights={"trend": 0.20, "momentum": 0.30, "volume": 0.25, "price_action": 0.25},
        buy_threshold=70,
        sell_threshold=config.SWING_SELL_THRESHOLD,
        position_pct=0.25,
        multiplier=config.REGIME_MULTIPLIER_BEAR,
    ),
}


def get_regime_profile(regime: str) -> RegimeProfile:
    return _REGIME_PROFILES.get(regime, _REGIME_PROFILES["sideways"])


def detect_regime(
    close: np.ndarray,
    adx: np.ndarray,
    sma_period: int | None = None,
    sideways_cutoff: float | None = None,
) -> str:
    sma_period = sma_period or config.REGIME_SMA_PERIOD
    sideways_cutoff = sideways_cutoff or config.REGIME_ADX_SIDEWAYS_CUTOFF

    if close.size == 0 or adx.size == 0:
        return "sideways"

    latest_close = close[-1]
    latest_adx = adx[-1]
    if np.isnan(latest_close) or np.isnan(latest_adx):
        return "sideways"

    if latest_adx < sideways_cutoff:
        return "sideways"

    window = close[-min(sma_period, close.size):]
    sma = float(np.nanmean(window)) if np.any(np.isfinite(window)) else np.nan
    if np.isnan(sma):
        return "sideways"

    return "bull" if latest_close > sma else "bear"


def regime_series(
    close: np.ndarray,
    adx: np.ndarray,
    sma_period: int | None = None,
    sideways_cutoff: float | None = None,
) -> np.ndarray:
    sma_period = sma_period or config.REGIME_SMA_PERIOD
    sideways_cutoff = sideways_cutoff or config.REGIME_ADX_SIDEWAYS_CUTOFF

    n = len(close)
    labels = np.full(n, "sideways", dtype=object)
    for i in range(n):
        latest_close = close[i]
        latest_adx = adx[i]
        if np.isnan(latest_close) or np.isnan(latest_adx):
            continue
        if latest_adx < sideways_cutoff:
            continue
        start = max(0, i + 1 - sma_period)
        window = close[start : i + 1]
        sma = float(np.nanmean(window)) if np.any(np.isfinite(window)) else np.nan
        if not np.isnan(sma):
            labels[i] = "bull" if latest_close > sma else "bear"
    return labels
