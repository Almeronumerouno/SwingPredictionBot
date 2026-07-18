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


def _position_shares(capital: float, entry: float, stop_loss: float) -> tuple[int, str | None]:
    """
    Hitung posisi berdasarkan alokasi 25% modal per posisi.
    Jika hasilnya < 1 lot, coba sampai 50% capital.

    Returns (shares, note):
      - shares: jumlah lembar (kelipatan LOT_SIZE), 0 jika tidak mampu 1 lot
      - note: peringatan jika risiko > 1%, None jika aman
    """
    per_share_risk = abs(entry - stop_loss)
    if per_share_risk <= 0:
        return 0, None

    cost_per_lot = entry * LOT_SIZE

    for deploy_pct in (0.25, 0.50):
        max_lots = int((capital * deploy_pct) // cost_per_lot)
        if max_lots >= 1:
            shares = max_lots * LOT_SIZE
            risk_pct = (per_share_risk * shares) / capital
            note = None
            if risk_pct > config.RISK_PER_TRADE_PCT:
                note = f"Risiko aktual {risk_pct*100:.1f}%"
            return shares, note

    return 0, None


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

    size, note = _position_shares(capital, entry_price, sl)
    if size == 0:
        cost_1lot = entry_price * LOT_SIZE
        return {
            "direction": direction,
            "entry": entry_price,
            "stop_loss": round(sl, 0),
            "take_profit": round(tp, 0),
            "shares": 0,
            "lots": 0,
            "risk_reward_ratio": None,
            "note": (
                f"Butuh minimal Rp {int(cost_1lot):,} "
                f"untuk 1 lot ({LOT_SIZE} lbr @ Rp {int(entry_price):,})"
            ),
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


if __name__ == "__main__":
    print("risk.py — isi TODO sudah diimplementasi")
