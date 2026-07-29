from __future__ import annotations

import config
from regime import get_regime_profile

LOT_SIZE = 100


def _stop_loss(entry: float, atr: float, direction: str, risk_level: str) -> float:
    mult = config.ATR_SL_MULTIPLIER
    if risk_level == "tinggi":
        mult *= 0.8
    return entry - mult * atr if direction == "BUY" else entry + mult * atr


def _take_profit(entry: float, atr: float, direction: str) -> float:
    mult = config.ATR_TP_MULTIPLIER
    return entry + mult * atr if direction == "BUY" else entry - mult * atr


def _position_shares(capital: float, entry: float, stop_loss: float, position_pct: float = config.DEFAULT_POSITION_PCT):
    per_share_risk = abs(entry - stop_loss)
    if per_share_risk <= 0:
        return 0, None

    deploy_pct = max(0.0, min(position_pct, 1.0))
    cost_per_lot = entry * LOT_SIZE
    max_lots = int((capital * deploy_pct) // cost_per_lot)
    if max_lots < 1:
        return 0, None

    shares = max_lots * LOT_SIZE
    risk_pct = (per_share_risk * shares) / capital if capital > 0 else 0.0
    note = None
    if risk_pct > config.RISK_PER_TRADE_PCT:
        risk_amt = int(per_share_risk * shares)
        note = f"Risiko jika kena SL: Rp {risk_amt:,} ({risk_pct*100:.1f}% dari modal)"
    return shares, note


def build_trade_plan(score_result: dict, entry_price: float, atr: float, capital: float, position_pct: float | None = None):
    if not score_result.get("valid") or score_result.get("recommendation") == "HOLD":
        return None
    if atr is None or atr <= 0:
        return None

    direction = score_result["recommendation"]
    if config.LONG_ONLY_MODE and direction == "SELL":
        return None

    regime = score_result.get("regime", "sideways")
    profile = get_regime_profile(regime)
    effective_position_pct = position_pct if position_pct is not None else profile.position_pct

    sl = _stop_loss(entry_price, atr, direction, score_result["risk_level"])
    tp = _take_profit(entry_price, atr, direction)
    size, note = _position_shares(capital, entry_price, sl, effective_position_pct)

    if size == 0:
        return {
            "direction": direction,
            "entry": entry_price,
            "stop_loss": round(sl, 0),
            "take_profit": round(tp, 0),
            "shares": 0,
            "lots": 0,
            "risk_reward_ratio": None,
            "note": f"Butuh minimal Rp {int(entry_price * LOT_SIZE):,} untuk 1 lot",
        }

    risk = abs(entry_price - sl)
    reward = abs(tp - entry_price)
    rr_ratio = round(reward / risk, 2) if risk > 0 else None

    return {
        "direction": direction,
        "entry": entry_price,
        "stop_loss": round(sl, 0),
        "take_profit": round(tp, 0),
        "shares": size,
        "lots": size // LOT_SIZE,
        "risk_reward_ratio": rr_ratio,
        "note": note,
    }
