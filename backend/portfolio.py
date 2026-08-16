"""
portfolio.py — Portfolio-Level Aggregation (P7.2, audit READY-TO-FLY v2).

Prinsip (P7.2):
- Semua portfolio metric (return, Sharpe, Sortino, max DD, CAGR, turnover,
  total cost) dihitung dari SATU chronological equity/cash/position series.
- DILARANG: sum(trade_return_pct) sebagai portfolio return;
  mean(window_sharpe) sebagai portfolio Sharpe.
- Window identity: kombinasi (code, window_id) — window_id per saham tidak
  unik global (walkforward.build_windows memulai dari 1 untuk tiap saham).

Model eksekusi (sederhana, deterministic, jujur):
- Kapital K dialokasikan per posisi: notional max = K / max_positions.
  (Dengan max_positions posisi paralel, exposure ≤ ~100%.)
- Entry: shares = floor(notional / entry_price / 100) * 100 (lot IDX 100),
  cash -= shares*entry_price*(1 + fee_buy_pct/100).
- Exit: cash += shares*exit_price*(1 - fee_sell_pct/100).
- Short (direction=-1) didukung dengan gross collateral (proceeds masuk cash,
  posisi shares negatif, tanpa margin call) — model sederhana, eksplisit.
- Slippage SUDAH tercermin di entry_price/exit_price (diterapkan backtest
  pada harga eksekusi; fee dihitung terpisah oleh engine ini).
- Mark-to-market harian pakai close per saham; harga tidak tersedia → forward
  fill (harga terakhir diketahui).

Series output: [{date, cash, equity, exposure, n_positions}] + daily returns.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np


@dataclass
class PortfolioEvent:
    """Satu trade OOS dari satu (code, window_id)."""
    code: str
    window_id: int
    direction: int          # +1 long (short tidak didukung; long_only mode)
    entry_date: str         # ISO "YYYY-MM-DD"
    exit_date: str
    entry_price: float      # sudah net slippage (harga eksekusi backtest)
    exit_price: float       # sudah net slippage


@dataclass
class PortfolioPoint:
    date: str
    cash: float
    equity: float
    exposure: float         # notional aktif / equity (0..~1)
    n_positions: int


@dataclass
class PortfolioResult:
    series: list[PortfolioPoint]
    daily_returns: list[float]      # sejajar dgn series[1:]; None/[] bila <2 titik
    # metrics portfolio-level (dari SATU series):
    sharpe: Optional[float]
    sortino: Optional[float]
    max_drawdown_pct: float
    cagr_pct: Optional[float]
    total_return_pct: float
    turnover: float                 # total notional (entry+exit) / avg equity
    total_cost: float               # total fee (buy+sell) dalam rupiah
    n_days: int
    avg_exposure: float
    peak_positions: int
    skipped_events: int             # exit tanpa posisi (entry di-skip krn modal)


def build_portfolio_series(
    events: list[PortfolioEvent],
    prices: dict[str, dict[str, float]],        # code -> {date_iso: close}
    capital: float = 10_000_000,
    max_positions: int = 3,
    fee_buy_pct: float = 0.0,
    fee_sell_pct: float = 0.0,
    lot_size: int = 100,
) -> PortfolioResult:
    """Bangun satu chronological equity/cash/position series dari semua event.

    prices: harga close harian per saham untuk mark-to-market. Tanggal ISO.
    """
    if max_positions < 1:
        raise ValueError("max_positions harus >= 1")

    # ── precompute harga per code: sorted (date, close) utk forward-fill ──
    code_dates: dict[str, list[str]] = {}
    code_closes: dict[str, list[float]] = {}
    for code, m in prices.items():
        items = sorted(m.items())
        code_dates[code] = [d for d, _ in items]
        code_closes[code] = [c for _, c in items]

    def price_at(code: str, date: str, fallback: float) -> float:
        ds = code_dates.get(code)
        if not ds:
            return fallback
        idx = bisect_right(ds, date) - 1
        if idx >= 0:
            return code_closes[code][idx]
        return fallback

    # ── timeline = union entry/exit dates + semua bar dates ──
    all_dates = set()
    for ev in events:
        all_dates.add(ev.entry_date)
        all_dates.add(ev.exit_date)
    for ds in code_dates.values():
        all_dates.update(ds)
    timeline = sorted(all_dates)

    # index events per tanggal
    exits_at: dict[str, list[PortfolioEvent]] = {}
    entries_at: dict[str, list[PortfolioEvent]] = {}
    for ev in events:
        exits_at.setdefault(ev.exit_date, []).append(ev)
        entries_at.setdefault(ev.entry_date, []).append(ev)

    cash = capital
    positions: dict[str, dict] = {}     # code -> {shares, entry_price}
    equity = capital
    series: list[PortfolioPoint] = []
    total_notional = 0.0
    total_cost = 0.0
    peak_pos = 0
    skipped_events = 0
    per_pos_notional = capital / max_positions

    for day in timeline:
        # 1) exit dulu (hari yang sama: exit sebelum entry — deterministic)
        for ev in exits_at.get(day, []):
            pos = positions.pop(ev.code, None)
            if pos is None:
                # trade tidak pernah terbuka (entry di-skip krn modal tidak
                # cukup utk 1 lot / harga > notional cap) — catat, jangan crash
                skipped_events += 1
                continue
            shares = pos["shares"]
            if shares > 0:  # close long
                proceeds = shares * ev.exit_price * (1 - fee_sell_pct / 100)
                cash += proceeds
                total_cost += shares * ev.exit_price * fee_sell_pct / 100
            else:           # close short (buy back)
                cost = abs(shares) * ev.exit_price * (1 + fee_buy_pct / 100)
                cash -= cost
                total_cost += abs(shares) * ev.exit_price * fee_buy_pct / 100
            total_notional += abs(shares) * ev.exit_price
        # 2) entry
        for ev in entries_at.get(day, []):
            notional = min(cash, per_pos_notional)
            if ev.direction == 1:  # long: cost (price+fee) harus <= cash
                n_shares = int(
                    min(notional, cash / (1 + fee_buy_pct / 100))
                    / ev.entry_price / lot_size
                ) * lot_size
                if n_shares <= 0:
                    continue
                cost = n_shares * ev.entry_price * (1 + fee_buy_pct / 100)
                cash -= cost
                total_cost += n_shares * ev.entry_price * fee_buy_pct / 100
                positions[ev.code] = {"shares": n_shares, "entry_price": ev.entry_price}
            else:                  # short (gross collateral, tanpa margin call)
                n_shares = int(notional / ev.entry_price / lot_size) * lot_size
                if n_shares <= 0:
                    continue
                proceeds = n_shares * ev.entry_price * (1 - fee_sell_pct / 100)
                cash += proceeds
                total_cost += n_shares * ev.entry_price * fee_sell_pct / 100
                positions[ev.code] = {"shares": -n_shares, "entry_price": ev.entry_price}
            total_notional += n_shares * ev.entry_price
        # 3) mark-to-market (shares bertanda: negatif utk short)
        mtm = cash
        for code, pos in positions.items():
            px = price_at(code, day, pos["entry_price"])
            mtm += pos["shares"] * px
        equity = mtm
        notional_active = sum(
            abs(pos["shares"]) * price_at(code, day, pos["entry_price"])
            for code, pos in positions.items()
        )
        exposure = notional_active / equity if equity > 0 else 0.0
        peak_pos = max(peak_pos, len(positions))
        series.append(PortfolioPoint(
            date=day, cash=cash, equity=equity,
            exposure=round(exposure, 4), n_positions=len(positions),
        ))

    # ── daily returns dari satu series ──
    eq = [p.equity for p in series]
    daily = []
    for i in range(1, len(eq)):
        prev = eq[i - 1]
        if prev > 0:
            daily.append(eq[i] / prev - 1.0)
    daily_arr = np.asarray(daily, dtype=float)

    def _sharpe() -> Optional[float]:
        if len(daily_arr) < 2 or float(np.std(daily_arr)) == 0.0:
            return None
        return float(np.mean(daily_arr) / np.std(daily_arr, ddof=1) * np.sqrt(252))

    def _sortino() -> Optional[float]:
        downside = daily_arr[daily_arr < 0]
        if len(daily_arr) < 2 or len(downside) == 0 or float(np.std(downside)) == 0.0:
            return None
        return float(np.mean(daily_arr) / np.std(downside, ddof=1) * np.sqrt(252))

    # max DD kronologis
    max_dd = 0.0
    peak_eq = eq[0] if eq else 0.0
    for e in eq:
        peak_eq = max(peak_eq, e)
        if peak_eq > 0:
            max_dd = max(max_dd, (peak_eq - e) / peak_eq * 100)

    total_ret = (eq[-1] / eq[0] - 1) * 100 if eq and eq[0] > 0 else 0.0
    n_days = len(eq)
    cagr = None
    if n_days >= 2 and eq[0] > 0 and eq[-1] > 0:
        cagr = (float(eq[-1] / eq[0]) ** (252 / n_days) - 1) * 100
    avg_eq = float(np.mean(eq)) if eq else 1.0
    avg_exposure = float(np.mean([p.exposure for p in series])) if series else 0.0

    return PortfolioResult(
        series=series,
        daily_returns=[round(r, 8) for r in daily],
        sharpe=round(_sharpe(), 2) if _sharpe() is not None else None,
        sortino=round(_sortino(), 2) if _sortino() is not None else None,
        max_drawdown_pct=round(max_dd, 2),
        cagr_pct=round(cagr, 2) if cagr is not None else None,
        total_return_pct=round(total_ret, 2),
        turnover=round(total_notional / avg_eq, 3) if avg_eq > 0 else 0.0,
        total_cost=round(total_cost, 0),
        n_days=n_days,
        avg_exposure=round(avg_exposure, 4),
        peak_positions=peak_pos,
        skipped_events=skipped_events,
    )


def events_from_wf_results(results: list) -> list[PortfolioEvent]:
    """Konversi WFResult (walkforward.py) -> PortfolioEvent.

    results: iterable WFResult dgn atribut code, window_id, oos_trades
    (list of dict hasil asdict(BacktestTrade)).
    """
    events = []
    for r in results:
        for t in r.oos_trades:
            d = t["direction"]
            if isinstance(d, str):
                direction = 1 if d.upper() == "BUY" else -1
            else:
                direction = int(d)
            events.append(PortfolioEvent(
                code=r.code,
                window_id=r.window_id,
                direction=direction,
                entry_date=str(t["entry_date"]),
                exit_date=str(t["exit_date"]),
                entry_price=float(t["entry_price"]),
                exit_price=float(t["exit_price"]),
            ))
    return events