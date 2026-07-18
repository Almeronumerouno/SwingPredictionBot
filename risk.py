"""risk.py — Fase 3: Risk & Trade Plan (SL/TP sizing dari ATR)."""

from __future__ import annotations

import config

LOT_SIZE = 100


def _stop_loss(entry: float, atr: float, direction: str, risk_level: str) -> float:
    mult = config.ATR_SL_MULTIPLIER
    if risk_level == "tinggi":
        mult *= 0.8
    if direction == "BUY":
        return entry - mult * atr
    else:
        return entry + mult * atr


def _take_profit(entry: float, atr: float, direction: str) -> float:
    mult = config.ATR_TP_MULTIPLIER
    if direction == "BUY":
        return entry + mult * atr
    else:
        return entry - mult * atr


def _position_size(capital: float, entry: float, stop_loss: float) -> int:
    risk_amount = capital * config.RISK_PER_TRADE_PCT
    per_share_risk = abs(entry - stop_loss)
    if per_share_risk <= 0:
        return 0
    raw_shares = risk_amount / per_share_risk
    shares = int(raw_shares // LOT_SIZE) * LOT_SIZE
    if shares < LOT_SIZE:
        return 0
    return shares


def build_trade_plan(score_result: dict, entry_price: float, atr: float, capital: float) -> dict | None:
    """
    Return trade plan dict atau None kalau HOLD / invalid / ATR gak valid.

    Return keys:
      - direction (str): "BUY" / "SELL"
      - entry (float): entry price
      - stop_loss (float)
      - take_profit (float)
      - shares (int): jumlah lembar saham (bukan lot)
      - lots (int): konversi ke lot IDX (100 lembar)
      - risk_reward_ratio (float)
      - note (str, opsional): pesan kalau capital kurang
    """
    if not score_result.get("valid") or score_result["recommendation"] == "HOLD":
        return None
    if atr is None or atr <= 0:
        return None

    direction = score_result["recommendation"]
    risk_level = score_result["risk_level"]

    sl = _stop_loss(entry_price, atr, direction, risk_level)
    tp = _take_profit(entry_price, atr, direction)
    size = _position_size(capital, entry_price, sl)

    risk = abs(entry_price - sl)
    reward = abs(tp - entry_price)
    rr_ratio = round(reward / risk, 2) if risk > 0 else None

    plan = {
        "direction": direction,
        "entry": entry_price,
        "stop_loss": round(sl, 0),
        "take_profit": round(tp, 0),
        "shares": size,
        "lots": size // LOT_SIZE,
        "risk_reward_ratio": rr_ratio,
    }

    if size == 0:
        cost_1lot = entry_price * LOT_SIZE
        if capital >= cost_1lot:
            plan["shares"] = LOT_SIZE
            plan["lots"] = 1
            plan["note"] = (
                f"Hanya mampu 1 lot. Risiko aktual > {config.RISK_PER_TRADE_PCT*100:.0f}% "
                f"modal karena jarak SL melebihi batas aman untuk modal Rp {int(capital):,}. "
                f"Saran: tambah modal atau cari saham dengan harga lebih rendah."
            )
        else:
            plan["note"] = (
                f"Butuh minimal Rp {int(cost_1lot):,} "
                f"untuk 1 lot ({LOT_SIZE} lbr @ Rp {int(entry_price):,})"
            )

    return plan


if __name__ == "__main__":
    print("risk.py — isi TODO sudah diimplementasi")
