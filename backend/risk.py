from __future__ import annotations

import numpy as np

import config
from regime import get_regime_profile

LOT_SIZE = 100


def _stop_loss(entry: float, atr: float, direction: str, risk_level: str) -> float:
    mult = config.ATR_SL_MULTIPLIER
    # audit fix #6: cabang "tinggi" ini dulu dead code di jalur live karena
    # scoring.py selalu mengirim risk_level="sedang". Sekarang risk_level
    # dinamis (scoring.risk_level_from_atr, single source of truth dgn
    # backtest._risk_level) — SL diketatkan 0.8x saat ATR > 1.5x baseline.
    if risk_level == "tinggi":
        mult *= 0.8
    return entry - mult * atr if direction == "BUY" else entry + mult * atr


def _take_profit(entry: float, atr: float, direction: str) -> float:
    mult = config.ATR_TP_MULTIPLIER
    return entry + mult * atr if direction == "BUY" else entry - mult * atr


def _position_shares(
    capital: float,
    entry: float,
    stop_loss: float,
    risk_pct: float = config.RISK_PER_TRADE_PCT,
    regime_mult: float = 1.0,
) -> tuple[int, str | None]:
    """All-in sizing (POSITION_SIZING_MODE="all_in"): seluruh modal
    dialokasikan ke satu saham, dalam kelipatan LOT_SIZE.

    keputusan produk: sistem ini untuk all-in per saham, bukan membagi
    modal secara risk-budget (risk_pct x regime_mult TIDAK dipakai lagi
    untuk menghitung lot; hanya untuk pelaporan).
    Output: kelipatan LOT_SIZE; 0 jika < 1 lot atau modal tidak cukup.
    """
    if capital is None or np.isnan(capital) or capital <= 0:
        return 0, None
    if entry is None or np.isnan(entry) or entry <= 0:
        return 0, None
    if stop_loss is None or np.isnan(stop_loss):
        return 0, None

    per_share_risk = abs(entry - stop_loss)
    if np.isnan(per_share_risk) or per_share_risk <= 0:
        return 0, None

    lots = int(capital / entry) // LOT_SIZE
    shares = lots * LOT_SIZE

    if shares < LOT_SIZE:
        return 0, None

    risk_amt = per_share_risk * shares
    if np.isnan(risk_amt) or np.isnan(per_share_risk):
        return 0, None

    risk_pct_actual = risk_amt / capital if capital > 0 else 0.0
    note = (
        f"All-in: Rp {shares * entry:,.0f} ({shares * entry / capital * 100:.2f}% modal)"
        f" · risiko bila kena SL: Rp {risk_amt:,.0f} ({risk_pct_actual*100:.2f}% modal)"
    )
    return shares, note


def build_trade_plan(score_result: dict, entry_price: float, atr: float, capital: float, position_pct: float | None = None):
    if not score_result or not score_result.get("valid") or score_result.get("recommendation") == "HOLD":
        return None
    if atr is None or np.isnan(atr) or atr <= 0:
        return None
    if entry_price is None or np.isnan(entry_price) or entry_price <= 0:
        return None
    if capital is None or np.isnan(capital) or capital <= 0:
        return None

    direction = score_result.get("recommendation")
    if config.LONG_ONLY_MODE and direction == "SELL":
        return None

    regime = score_result.get("regime", "sideways")
    profile = get_regime_profile(regime)
    regime_mult = profile.position_pct if position_pct is None else max(0.0, position_pct)

    sl = _stop_loss(entry_price, atr, direction, score_result.get("risk_level", "sedang"))
    tp = _take_profit(entry_price, atr, direction)
    size, note = _position_shares(
        capital, entry_price, sl,
        risk_pct=config.RISK_PER_TRADE_PCT,
        regime_mult=regime_mult,
    )

    if size == 0:
        min_capital_note = (
            f"Butuh minimal Rp {int(entry_price * LOT_SIZE):,} untuk 1 lot"
            if entry_price is not None and not np.isnan(entry_price)
            else "Modal tidak cukup untuk 1 lot"
        )
        return {
            "direction": direction,
            "entry": entry_price,
            "stop_loss": round(sl, 0) if not np.isnan(sl) else None,
            "take_profit": round(tp, 0) if not np.isnan(tp) else None,
            "shares": 0,
            "lots": 0,
            "risk_reward_ratio": None,
            "risk_per_trade_pct": None,
            "note": min_capital_note,
        }

    risk = abs(entry_price - sl)
    reward = abs(tp - entry_price)
    rr_ratio = round(reward / risk, 2) if risk > 0 else None
    risk_actual_pct = (risk * size / capital * 100) if capital > 0 else None

    return {
        "direction": direction,
        "entry": entry_price,
        "stop_loss": round(sl, 0),
        "take_profit": round(tp, 0),
        "shares": size,
        "lots": size // LOT_SIZE,
        "risk_reward_ratio": rr_ratio,
        "risk_per_trade_pct": round(risk_actual_pct, 2) if risk_actual_pct is not None else None,
        "note": note,
    }
