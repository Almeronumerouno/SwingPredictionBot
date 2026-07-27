"""
backtest.py — Fase 6: Backtest Engine untuk SwingPredictionBot.

Mensimulasikan strategi Swing Score (BUY/SELL/HOLD) + SL/TP ATR-based
pada data historis. Zero modification ke kode existing (Fase 1-5).

Pendekatan:
  1. Compute ALL indicators 1x → full numpy arrays
  2. Compute ALL component scores 1x → full arrays
  3. Walk bars: sinyal → entry → SL/TP check → exit → metrics

Parameter tuning via BacktestConfig tanpa sentuh config.py.
"""

from __future__ import annotations

import sys
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np

import config as CFG
import indicators as ind
from data_source.yahoo_client import fetch_trading_info


# ──────────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────────

@dataclass
class BacktestConfig:
    """Override parameter untuk calibration. Default = config.py values."""
    adx_gate_ceiling: int = CFG.ADX_GATE_CEILING
    swing_buy_threshold: int = CFG.SWING_BUY_THRESHOLD   # experimental — not validated
    swing_sell_threshold: int = CFG.SWING_SELL_THRESHOLD  # validated edge (58% WR)
    atr_sl_multiplier: float = CFG.ATR_SL_MULTIPLIER
    atr_tp_multiplier: float = CFG.ATR_TP_MULTIPLIER
    rvol_breakout_confirm: float = CFG.RVOL_BREAKOUT_CONFIRM
    rvol_window: int = CFG.RVOL_WINDOW
    position_pct: float = 0.25
    fee_pct: float = 0.25
    long_only: bool = False


# ──────────────────────────────────────────────
#  Trade & Metrics Records
# ──────────────────────────────────────────────

class ExitReason(Enum):
    SL_HIT = "SL_HIT"
    TP_HIT = "TP_HIT"
    REVERSAL = "REVERSAL"
    END_OF_DATA = "END_OF_DATA"

    def __str__(self):
        return self.value


@dataclass
class BacktestTrade:
    entry_date: str
    exit_date: str
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    return_pct: float
    holding_days: int
    exit_reason: ExitReason
    entry_score: float = 0.0
    confidence: str = ""
    risk_level: str = ""


@dataclass
class BacktestMetrics:
    code: str
    period_start: str
    period_end: str
    total_calendar_days: int
    total_trading_days: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return_pct: float
    buy_hold_return_pct: float
    alpha_pct: float
    avg_return_per_trade: float
    avg_holding_days: float
    max_drawdown_pct: float
    avg_rr: float
    sharpe: float
    total_fees: float
    trades: list[BacktestTrade] = field(default_factory=list)


# ──────────────────────────────────────────────
#  Lot / IDX Constants
# ──────────────────────────────────────────────

_LOT_SIZE = 100


# ──────────────────────────────────────────────
#  Helpers (replicated from scoring.py + risk.py
#  dengan parameter override via BacktestConfig)
# ──────────────────────────────────────────────

def _nearest_level(price: float, levels: list, below: bool = True) -> float | None:
    filtered = [l["level"] for l in levels if l.get("level") is not None]
    if not filtered:
        return None
    if below:
        candidates = [v for v in filtered if v <= price]
        return max(candidates) if candidates else None
    else:
        candidates = [v for v in filtered if v > price]
        return min(candidates) if candidates else None


def _calc_sl(entry: float, atr: float, direction: str, risk_level: str, cfg: BacktestConfig) -> float:
    mult = cfg.atr_sl_multiplier
    if risk_level == "tinggi":
        mult *= 0.8
    if direction == "BUY":
        return entry - mult * atr
    return entry + mult * atr


def _calc_tp(entry: float, atr: float, direction: str, cfg: BacktestConfig) -> float:
    mult = cfg.atr_tp_multiplier
    if direction == "BUY":
        return entry + mult * atr
    return entry - mult * atr


def _calc_shares(allocated: float, entry_price: float) -> int:
    lot_cost = entry_price * _LOT_SIZE
    if lot_cost <= 0:
        return 0
    lots = int(allocated // lot_cost)
    if lots < 1:
        return 0
    return lots * _LOT_SIZE


def _risk_level(atr: np.ndarray, i: int) -> str:
    if i < CFG.RISK_ATR_LOOKBACK:
        return "sedang"
    latest = atr[i]
    baseline = np.nanmean(atr[i - CFG.RISK_ATR_LOOKBACK:i])
    if np.isnan(latest) or np.isnan(baseline) or baseline == 0:
        return "sedang"
    ratio = latest / baseline
    if ratio > CFG.RISK_HIGH_CUTOFF:
        return "tinggi"
    elif ratio < CFG.RISK_LOW_CUTOFF:
        return "rendah"
    return "sedang"


def _confidence(components: dict, swing_score: float, gate: float, rvol: float, cfg: BacktestConfig,
                 recommendation: str | None = None) -> str:
    values = list(components.values())
    majority = 1.0 if swing_score > 50.0 else -1.0
    aligned = sum(1 for v in values if (v > 0.5) == (majority > 0))
    agreement_score = aligned / len(values) if values else 0.0
    rvol_strength = min(rvol / cfg.rvol_breakout_confirm, 1.0) if rvol > 0 else 0.0
    strength_factor = (gate + rvol_strength) / 2.0
    raw = agreement_score * strength_factor
    if raw >= CFG.CONFIDENCE_HIGH_CUTOFF:
        tier = "tinggi"
    elif raw >= CFG.CONFIDENCE_LOW_CUTOFF:
        tier = "sedang"
    else:
        tier = "rendah"
    if recommendation == "BUY":
        tier = {"tinggi": "sedang", "sedang": "rendah", "rendah": "rendah"}[tier]
    return tier


# ──────────────────────────────────────────────
#  Signal Computation (full arrays)
# ──────────────────────────────────────────────

def compute_signals(data: dict, cfg: BacktestConfig) -> dict:
    """
    Compute swing_score dan recommendation untuk SETIAP bar (bukan cuma
    index terakhir). Semua parameter scoring diambil dari cfg, bukan config
    module — biar kalibrasi bisa override lewat BacktestConfig.

    Returns dict dengan key:
      swing_scores (np.ndarray), recommendations (np.ndarray of str),
      trend/momentum/volume/price_action (np.ndarray), gate (np.ndarray)
    """
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
    high = data.get("high")
    low = data.get("low")

    w = CFG.SCORE_WEIGHTS
    n = len(close)

    # ── ADX Gate (full array) ──
    gate = np.minimum(adx_arr / cfg.adx_gate_ceiling, 1.0)

    # ── Trend Score ──
    spread_atr = (ema_fast - ema_slow) / np.where(atr_arr > 0, atr_arr, np.nan)
    en = np.clip((spread_atr + 3.0) / 6.0, 0.0, 1.0)
    trend_scores = 0.5 + (en - 0.5) * gate

    # ── Momentum Score ──
    raw_mom = (rsi / 100.0 + mfi_arr / 100.0) / 2.0
    momentum_scores = 0.5 + (raw_mom - 0.5) * gate

    # ── Volume Score ──
    sign = np.where(close > np.roll(close, 1), 1.0, -1.0)
    sign[0] = 0.0
    clamped = np.clip(rvol_arr - 1.0, 0.0, 1.0)
    volume_scores = 0.5 + sign * clamped * 0.5

    # ── Price Action Score (loop — PIT S/R per bar) ──
    pa_scores = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(close[i]):
            continue

        if high is not None and low is not None and i >= 30:
            sr = ind.support_resistance_levels(high[:i+1], low[:i+1])
            sup_list = sr["support"]
            res_list = sr["resistance"]
        else:
            sup_list = []
            res_list = []

        sup = _nearest_level(close[i], sup_list, below=True)
        res = _nearest_level(close[i], res_list, below=False)
        if sup is not None and res is not None and res > sup:
            base = np.clip((close[i] - sup) / (res - sup), 0.0, 1.0)
        else:
            base = 0.5
        rv = rvol_arr[i] if not np.isnan(rvol_arr[i]) else 0.0
        if not np.isnan(donch_upper[i]) and close[i] > donch_upper[i] and rv >= cfg.rvol_breakout_confirm:
            pa_scores[i] = 1.0
        elif not np.isnan(donch_lower[i]) and close[i] < donch_lower[i] and rv >= cfg.rvol_breakout_confirm:
            pa_scores[i] = 0.0
        else:
            pa_scores[i] = base

    # ── Swing Score ──
    swing_scores = 100.0 * (
        w["trend"] * trend_scores
        + w["momentum"] * momentum_scores
        + w["volume"] * volume_scores
        + w["price_action"] * pa_scores
    )

    # ── Recommendation ──
    recs = np.full(n, "HOLD", dtype=object)
    buy_mask = swing_scores >= cfg.swing_buy_threshold
    sell_mask = swing_scores <= cfg.swing_sell_threshold
    recs[buy_mask] = "BUY"
    recs[sell_mask] = "SELL"

    return {
        "swing_scores": swing_scores,
        "recommendations": recs,
        "trend": trend_scores,
        "momentum": momentum_scores,
        "volume": volume_scores,
        "price_action": pa_scores,
        "gate": gate,
    }


# ──────────────────────────────────────────────
#  Core Backtest Engine
# ──────────────────────────────────────────────

def _find_warmup(swing_scores: np.ndarray) -> int:
    """First bar where swing_score is not NaN."""
    valid = np.where(~np.isnan(swing_scores))[0]
    return int(valid[0]) if len(valid) > 0 else 0


def run_backtest(
    code: str,
    capital: float = 10_000_000,
    bt_config: Optional[BacktestConfig] = None,
    length: int = CFG.HISTORY_LOOKBACK_DAYS,
    target_date: str | None = None,
    sim_start_idx: int = 0,
    sim_end_idx: Optional[int] = None,
) -> BacktestMetrics:
    """
    Run full backtest untuk satu kode saham.

    Args:
        code: Kode saham IDX (misal "BBCA")
        capital: Modal awal dalam IDR
        bt_config: Parameter override (default = BacktestConfig())
        length: Hari kalender historis
        target_date: Format YYYY-MM-DD, batas akhir data
        sim_start_idx: Index pertama walk simulation (buat walk-forward)
        sim_end_idx: Index terakhir+1 walk simulation (None = sampai akhir)

    Returns:
        BacktestMetrics dengan semua metrik + daftar trade
    """
    if bt_config is None:
        bt_config = BacktestConfig()

    # ── 1. Fetch data ──
    bars = fetch_trading_info(code, length=length, target_date=target_date)
    if len(bars) < CFG.MIN_TRADING_DAYS:
        raise ValueError(
            f"Data {code} tidak cukup: {len(bars)} hari < {CFG.MIN_TRADING_DAYS} minimum"
        )

    close = np.array([b.close for b in bars], dtype=float)
    open_ = np.array([b.open_price for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    low = np.array([b.low for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)
    dates = [b.date for b in bars]
    n = len(close)

    # ── 2. Compute ALL indicators (1x) ──
    rsi_val = ind.rsi(close)
    atr_val = ind.atr(high, low, close)
    ema_val = ind.ema_trend(close)
    adx_val = ind.adx(high, low, close)
    mfi_val = ind.mfi(high, low, close, volume)
    rvol_val = ind.rvol(volume, period=bt_config.rvol_window)
    donch = ind.donchian_channel(high, low)

    data = {
        "close": close,
        "high": high,
        "low": low,
        "rsi": rsi_val,
        "atr": atr_val,
        "adx": adx_val["adx"],
        "plus_di": adx_val["plus_di"],
        "minus_di": adx_val["minus_di"],
        "ema_fast": ema_val["ema_fast"],
        "ema_slow": ema_val["ema_slow"],
        "mfi": mfi_val,
        "rvol": rvol_val,
        "donchian_upper": donch["upper"],
        "donchian_lower": donch["lower"],
    }

    # ── 3. Compute signal arrays ──
    signals = compute_signals(data, bt_config)
    swing_scores = signals["swing_scores"]
    recs = signals["recommendations"]

    warmup = max(_find_warmup(swing_scores), sim_start_idx)
    sim_end = n if sim_end_idx is None else min(sim_end_idx, n)
    last_idx = sim_end - 1
    if warmup >= last_idx:
        return BacktestMetrics(
            code=code,
            period_start=dates[0] if dates else "",
            period_end=dates[-1] if dates else "",
            total_calendar_days=0,
            total_trading_days=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_return_pct=0.0,
            buy_hold_return_pct=0.0,
            alpha_pct=0.0,
            avg_return_per_trade=0.0,
            avg_holding_days=0.0,
            max_drawdown_pct=0.0,
            avg_rr=0.0,
            sharpe=0.0,
            total_fees=0.0,
        )

    # ── 4. Walk simulation ──
    trades: list[BacktestTrade] = []
    equity = capital
    peak = capital
    max_dd = 0.0

    in_position = False
    pos: dict = {}
    total_fees = 0.0
    equity_curve = []

    for i in range(warmup, sim_end):
        # ── Mark-to-market equity ──
        if in_position:
            ret_mtm = (close[i] / pos["entry_price"] - 1)
            if pos["direction"] == "SELL":
                ret_mtm = -ret_mtm
            current_equity = pos["entry_equity"] * (1 + ret_mtm * bt_config.position_pct)
        else:
            current_equity = equity

        equity_curve.append(current_equity)
        peak = max(peak, current_equity)
        dd = (peak - current_equity) / peak * 100
        if dd > max_dd:
            max_dd = dd

        # ── Enter (lagged: signal from bar i-1, execute at bar i) ──
        if not in_position:
            if i <= warmup or recs[i-1] not in ("BUY", "SELL"):
                continue

            atr_i = atr_val[i]
            if np.isnan(atr_i) or atr_i <= 0:
                continue

            direction = recs[i-1]
            if bt_config.long_only and direction == "SELL":
                continue

            entry_price = close[i]

            allocated = current_equity * bt_config.position_pct
            shares = _calc_shares(allocated, entry_price)
            if shares < _LOT_SIZE:
                continue

            risk_lvl = _risk_level(atr_val, i)

            sl = _calc_sl(entry_price, atr_i, direction, risk_lvl, bt_config)
            tp = _calc_tp(entry_price, atr_i, direction, bt_config)

            fee_entry = entry_price * shares * bt_config.fee_pct / 100
            total_fees += fee_entry

            gate_i = float(signals["gate"][i])
            rvol_i = float(rvol_val[i]) if not np.isnan(rvol_val[i]) else 0.0
            conf = _confidence(
                {
                    "trend": float(signals["trend"][i]),
                    "momentum": float(signals["momentum"][i]),
                    "volume": float(signals["volume"][i]),
                    "price_action": float(signals["price_action"][i]),
                },
                float(swing_scores[i]),
                gate_i,
                rvol_i,
                bt_config,
                recommendation=direction,
            )

            in_position = True
            pos = {
                "direction": direction,
                "entry_price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "shares": shares,
                "entry_idx": i,
                "entry_date": dates[i],
                "entry_score": float(swing_scores[i]),
                "entry_equity": current_equity,
                "confidence": conf,
                "risk_level": risk_lvl,
            }

        # ── Exit check ──
        else:
            direction = pos["direction"]
            exit_reason = None
            exit_price_candidate = None

            if direction == "BUY":
                if low[i] <= pos["stop_loss"]:
                    exit_reason = ExitReason.SL_HIT
                    exit_price_candidate = min(pos["stop_loss"], open_[i])
                elif high[i] >= pos["take_profit"]:
                    exit_reason = ExitReason.TP_HIT
                    exit_price_candidate = max(pos["take_profit"], open_[i])
                elif recs[i] == "SELL" and i > pos["entry_idx"]:
                    exit_reason = ExitReason.REVERSAL
                    exit_price_candidate = close[i]
            else:
                if high[i] >= pos["stop_loss"]:
                    exit_reason = ExitReason.SL_HIT
                    exit_price_candidate = max(pos["stop_loss"], open_[i])
                elif low[i] <= pos["take_profit"]:
                    exit_reason = ExitReason.TP_HIT
                    exit_price_candidate = min(pos["take_profit"], open_[i])
                elif recs[i] == "BUY" and i > pos["entry_idx"]:
                    exit_reason = ExitReason.REVERSAL
                    exit_price_candidate = close[i]

            if exit_reason is not None:
                holding = i - pos["entry_idx"]
                ret = (exit_price_candidate - pos["entry_price"]) / pos["entry_price"]
                if direction == "SELL":
                    ret = -ret

                fee_exit = exit_price_candidate * pos["shares"] * bt_config.fee_pct / 100
                total_fees += fee_exit

                fee_rate = bt_config.fee_pct / 100
                net_ret = ret - fee_rate * (1 + exit_price_candidate / pos["entry_price"])

                trade = BacktestTrade(
                    entry_date=pos["entry_date"],
                    exit_date=dates[i],
                    direction=direction,
                    entry_price=pos["entry_price"],
                    exit_price=exit_price_candidate,
                    stop_loss=pos["stop_loss"],
                    take_profit=pos["take_profit"],
                    return_pct=round(net_ret * 100, 2),
                    holding_days=holding,
                    exit_reason=exit_reason,
                    entry_score=pos["entry_score"],
                    confidence=pos["confidence"],
                    risk_level=pos["risk_level"],
                )
                trades.append(trade)

                pnl = pos["entry_equity"] * bt_config.position_pct * ret
                pnl -= (fee_entry + fee_exit)
                equity = pos["entry_equity"] + pnl
                in_position = False
                pos = {}

    # ── Close any open position at end of window ──
    if in_position:
        holding = last_idx - pos["entry_idx"]
        ret = (close[last_idx] - pos["entry_price"]) / pos["entry_price"]
        if pos["direction"] == "SELL":
            ret = -ret

        fee_exit = close[last_idx] * pos["shares"] * bt_config.fee_pct / 100
        total_fees += fee_exit
        fee_rate = bt_config.fee_pct / 100
        net_ret = ret - fee_rate * (1 + close[last_idx] / pos["entry_price"])

        trade = BacktestTrade(
            entry_date=pos["entry_date"],
            exit_date=dates[last_idx],
            direction=pos["direction"],
            entry_price=pos["entry_price"],
            exit_price=close[last_idx],
            stop_loss=pos["stop_loss"],
            take_profit=pos["take_profit"],
            return_pct=round(net_ret * 100, 2),
            holding_days=holding,
            exit_reason=ExitReason.END_OF_DATA,
            entry_score=pos["entry_score"],
            confidence=pos["confidence"],
            risk_level=pos["risk_level"],
        )
        trades.append(trade)
        pnl = pos["entry_equity"] * bt_config.position_pct * ret
        pnl -= (fee_entry + fee_exit)
        equity = pos["entry_equity"] + pnl

    # ──────────────────────────────────────────
    #  5. Compute Metrics
    # ──────────────────────────────────────────

    total_return = (equity / capital - 1) * 100

    buy_start = close[warmup]
    buy_end = close[last_idx]
    buy_hold_ret = (buy_end - buy_start) / buy_start * 100

    winning = [t for t in trades if t.return_pct > 0]
    losing = [t for t in trades if t.return_pct <= 0]
    total_trades = len(trades)
    win_rate = len(winning) / total_trades * 100 if total_trades else 0.0

    avg_ret = float(np.mean([t.return_pct for t in trades])) if trades else 0.0
    avg_hold = float(np.mean([t.holding_days for t in trades])) if trades else 0.0
    avg_rr = float(
        np.mean([
            abs(t.take_profit - t.entry_price) / abs(t.stop_loss - t.entry_price)
            for t in trades
            if abs(t.stop_loss - t.entry_price) > 0
        ])
    ) if trades else 0.0

    rets_arr = np.array([t.return_pct / 100 for t in trades])
    if len(rets_arr) > 1 and rets_arr.std() > 0:
        annualization_factor = math.sqrt(252 / avg_hold) if avg_hold > 0 else 1.0
        sharpe = float(rets_arr.mean() / rets_arr.std() * annualization_factor)
    else:
        sharpe = 0.0

    # Daily Sharpe from equity curve
    eq_arr = np.array(equity_curve)
    daily_rets = (eq_arr[1:] - eq_arr[:-1]) / eq_arr[:-1]
    valid = daily_rets[~np.isnan(daily_rets)]
    if len(valid) > 1 and valid.std() > 0:
        sharpe = float(valid.mean() / valid.std() * math.sqrt(252))
    else:
        sharpe = 0.0

    total_calendar = (datetime.strptime(dates[last_idx], "%Y-%m-%d") - datetime.strptime(dates[warmup], "%Y-%m-%d")).days if dates else 0

    return BacktestMetrics(
        code=code,
        period_start=dates[warmup],
        period_end=dates[last_idx],
        total_calendar_days=total_calendar,
        total_trading_days=sim_end - warmup,
        total_trades=total_trades,
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=round(win_rate, 1),
        total_return_pct=round(total_return, 2),
        buy_hold_return_pct=round(buy_hold_ret, 2),
        alpha_pct=round(total_return - buy_hold_ret, 2),
        avg_return_per_trade=round(avg_ret, 2),
        avg_holding_days=round(avg_hold, 1),
        max_drawdown_pct=round(max_dd, 2),
        avg_rr=round(avg_rr, 2),
        sharpe=round(sharpe, 2),
        total_fees=round(total_fees, 0),
        trades=trades,
    )


# ──────────────────────────────────────────────
#  Report Printing
# ──────────────────────────────────────────────

def _color(val: float, good_high: bool = True) -> str:
    """Return ANSI color string for terminal output."""
    if good_high:
        if val > 0:
            return "\033[32m"  # green
        elif val < 0:
            return "\033[31m"  # red
    else:
        if val < 0:
            return "\033[32m"  # green
        elif val > 0:
            return "\033[31m"  # red
    return "\033[0m"


def _reset() -> str:
    return "\033[0m"


def _pct(val: float) -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def print_report(metrics: BacktestMetrics, verbose: bool = False) -> None:
    """Print formatted backtest report to terminal."""
    sep = "=" * 60
    sub = "-" * 60

    print()
    print(sep)
    print(f"  Backtest: {metrics.code}")
    print(f"  Periode:  {metrics.period_start} -> {metrics.period_end} ({metrics.total_calendar_days} hari kalender, {metrics.total_trading_days} trading day)")
    print(sep)
    print()
    print(f"  {'Total Trades:':<25} {metrics.total_trades:<8}", end="")
    print(f"{'Win Rate:':<25} {_color(metrics.win_rate, True)}{metrics.win_rate:.1f}%{_reset()}")
    print(f"  {'Winning Trades:':<25} {metrics.winning_trades:<8}", end="")
    print(f"{'Losing Trades:':<25} {metrics.losing_trades}")
    print()

    print(f"  {'Total Return:':<25} {_color(metrics.total_return_pct, True)}{_pct(metrics.total_return_pct):>8}{_reset()}", end="")
    print(f" {'Buy & Hold:':<25} {_color(metrics.buy_hold_return_pct, True)}{_pct(metrics.buy_hold_return_pct):>8}{_reset()}")
    print(f"  {'Alpha vs B&H:':<25} {_color(metrics.alpha_pct, True)}{_pct(metrics.alpha_pct):>8}{_reset()}", end="")
    print(f" {'Max Drawdown:':<25} {_color(-metrics.max_drawdown_pct, False)}{_pct(-metrics.max_drawdown_pct):>8}{_reset()}")
    print()

    print(f"  {'Avg Return/Trade:':<25} {_color(metrics.avg_return_per_trade, True)}{_pct(metrics.avg_return_per_trade)}{_reset()}", end="")
    print(f" {'Avg Holding:':<25} {metrics.avg_holding_days} hari")
    print(f"  {'Avg R:R Ratio:':<25} {metrics.avg_rr:<8}", end="")
    print(f" {'Sharpe Ratio:':<25} {_color(metrics.sharpe, True)}{metrics.sharpe}{_reset()}")
    print(f"  {'Total Fees:':<25} Rp {metrics.total_fees:,.0f}")
    print()

    if verbose and metrics.trades:
        print(sub)
        print(f"  {'#':>3} {'Entry':>10} {'Exit':>10} {'Dir':>4} {'EntryPx':>10} {'ExitPx':>10} {'Return':>8} {'Days':>4} {'Reason':>12}")
        print(sub)
        for idx, t in enumerate(metrics.trades, 1):
            print(
                f"  {idx:>3} {t.entry_date:>10} {t.exit_date:>10} {t.direction:>4} "
                f"{t.entry_price:>10.0f} {t.exit_price:>10.0f} "
                f"{_color(t.return_pct, True)}{t.return_pct:>7.1f}%{_reset()} "
                f"{t.holding_days:>4} {t.exit_reason.value:>12}"
            )
        print(sub)
        print()


# ──────────────────────────────────────────────
#  CLI Entry Point
# ──────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Backtest SwingPredictionBot — Fase 6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python backtest.py BBCA BMRI ASII
  python backtest.py BBCA --capital 50000000 --verbose
  python backtest.py BBCA BMRI --adx-ceiling 20 --rvol-breakout 1.5
        """,
    )
    parser.add_argument("codes", nargs="+", help="Kode saham IDX (pisah spasi)")
    parser.add_argument("--capital", type=float, default=10_000_000, help="Modal awal (default: 10.000.000)")
    parser.add_argument("--length", type=int, default=CFG.HISTORY_LOOKBACK_DAYS, help="Hari kalender historis")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--verbose", "-v", action="store_true", help="Tampilkan detail tiap trade")
    parser.add_argument("--json", action="store_true", help="Output JSON (stdout)")

    # Calibration overrides
    parser.add_argument("--adx-ceiling", type=int, default=None)
    parser.add_argument("--buy-threshold", type=int, default=None)
    parser.add_argument("--sell-threshold", type=int, default=None)
    parser.add_argument("--sl-multiplier", type=float, default=None)
    parser.add_argument("--tp-multiplier", type=float, default=None)
    parser.add_argument("--rvol-breakout", type=float, default=None)
    parser.add_argument("--rvol-window", type=int, default=None)
    parser.add_argument("--position-pct", type=float, default=None)
    parser.add_argument("--fee-pct", type=float, default=None)
    parser.add_argument("--long-only", action="store_true",
                        help="Nonaktifkan short entry (SELL cuma jadi exit signal)")

    args = parser.parse_args()

    bt_config = BacktestConfig()
    if args.adx_ceiling is not None:
        bt_config.adx_gate_ceiling = args.adx_ceiling
    if args.buy_threshold is not None:
        bt_config.swing_buy_threshold = args.buy_threshold
    if args.sell_threshold is not None:
        bt_config.swing_sell_threshold = args.sell_threshold
    if args.sl_multiplier is not None:
        bt_config.atr_sl_multiplier = args.sl_multiplier
    if args.tp_multiplier is not None:
        bt_config.atr_tp_multiplier = args.tp_multiplier
    if args.rvol_breakout is not None:
        bt_config.rvol_breakout_confirm = args.rvol_breakout
    if args.rvol_window is not None:
        bt_config.rvol_window = args.rvol_window
    if args.position_pct is not None:
        bt_config.position_pct = args.position_pct
    if args.fee_pct is not None:
        bt_config.fee_pct = args.fee_pct
    if args.long_only:
        bt_config.long_only = True

    results: list[BacktestMetrics] = []
    for code in args.codes:
        try:
            metrics = run_backtest(code, capital=args.capital, bt_config=bt_config,
                                   length=args.length, target_date=args.date)
            results.append(metrics)
            if not args.json:
                print_report(metrics, verbose=args.verbose)
        except (ValueError, Exception) as e:
            if args.json:
                results.append(None)
            else:
                print(f"\n  [ERROR] {code}: {e}\n")

    # Summary across all codes
    if len(results) > 1 and not args.json:
        print("=" * 60)
        print("  AGGREGATE SUMMARY (rata-rata semua saham)")
        print("=" * 60)
        valid = [r for r in results if r is not None and r.total_trades > 0]
        if valid:
            print(f"  {'Avg Win Rate:':<25} {np.mean([r.win_rate for r in valid]):.1f}%")
            print(f"  {'Avg Total Return:':<25} {np.mean([r.total_return_pct for r in valid]):.2f}%")
            print(f"  {'Avg B&H Return:':<25} {np.mean([r.buy_hold_return_pct for r in valid]):.2f}%")
            print(f"  {'Avg Alpha:':<25} {np.mean([r.alpha_pct for r in valid]):.2f}%")
            print(f"  {'Avg Max DD:':<25} {np.mean([r.max_drawdown_pct for r in valid]):.2f}%")
            print(f"  {'Avg Sharpe:':<25} {np.mean([r.sharpe for r in valid]):.2f}")
            print(f"  {'Total Trades (all):':<25} {sum(r.total_trades for r in valid)}")
            print()

    if args.json:
        import json as _json
        output = []
        for r in results:
            if r is None:
                output.append(None)
            else:
                d = asdict(r)
                d["trades"] = [asdict(t) for t in r.trades]
                output.append(d)
        print(_json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
