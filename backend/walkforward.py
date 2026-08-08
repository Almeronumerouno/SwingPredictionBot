"""
walkforward.py — Walk-Forward Validation Harness.

Split data per saham ke N rolling window (train → test dengan purge + embargo).
Setiap window optimasi di train, test di OOS.
Output: concat equity curve dari seluruh (saham × window).
"""

from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass, field, asdict
import json

import numpy as np

import config as CFG
from backtest import BacktestConfig, run_backtest


# ──────────────────────────────────────────────
#  Walk-Forward Window
# ──────────────────────────────────────────────

@dataclass
class WalkForwardWindow:
    id: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def build_windows(
    n_bars: int,
    train_days: int = CFG.WF_TRAIN_DAYS,
    test_days: int = CFG.WF_TEST_DAYS,
    purge_days: int = CFG.WF_PURGE_DAYS,
    embargo_days: int = CFG.WF_EMBARGO_DAYS,
) -> list[WalkForwardWindow]:
    windows = []
    start = 0
    window_id = 1
    while True:
        train_start = start
        train_end = train_start + train_days
        test_start = train_end + purge_days + embargo_days
        test_end = test_start + test_days
        if test_end > n_bars:
            break
        windows.append(WalkForwardWindow(window_id, train_start, train_end, test_start, test_end))
        window_id += 1
        start += test_days
    return windows


# ──────────────────────────────────────────────
#  Parameter Candidates
# ──────────────────────────────────────────────

# audit fix #4: kandidat dibangun dari OPTIMIZATION GRID (CFG.WF_OPT_GRID),
# bukan daftar hardcode 2 set. Grid ini dioptimalkan pada data TRAIN window;
# kombinasi yang menang diverifikasi di data TEST (OOS).
GRID_FIXED_PARAMS = {
    "swing_sell_threshold": CFG.SWING_SELL_THRESHOLD,
    "atr_tp_multiplier": CFG.ATR_TP_MULTIPLIER,
    "rvol_window": CFG.RVOL_WINDOW,
    "risk_per_trade_pct": CFG.RISK_PER_TRADE_PCT,
    "long_only": CFG.LONG_ONLY_MODE,
    "breakeven_trigger": CFG.BREAKEVEN_TRIGGER,
}


def build_candidates(grid: dict | None = None) -> list[dict]:
    """Flatten grid parameter → daftar kandidat BacktestConfig."""
    grid = grid if grid is not None else CFG.WF_OPT_GRID
    keys = list(grid.keys())
    combos = list(itertools.product(*grid.values()))
    candidates = []
    for combo in combos:
        params = dict(zip(keys, combo))
        candidates.append(params)
    return candidates


DEFAULT_CANDIDATES = build_candidates()


# ──────────────────────────────────────────────
#  Walk-Forward Runner
# ──────────────────────────────────────────────

@dataclass
class WFResult:
    code: str
    window_id: int
    params: dict            # parameter PEMENANG (dipilih dari data train)
    oos_trades: list
    oos_win_rate: float
    oos_total_return: float
    oos_sharpe: float
    oos_max_dd: float
    train_sharpe: float = 0.0      # metrik train dari pemenang (transparansi)
    train_trades: int = 0


def run_walk_forward(
    code: str,
    capital: float = 10_000_000,
    candidates: list[dict] | None = None,
    length: int = 365,
) -> list[WFResult]:
    """
    Run walk-forward validation untuk satu kode saham.

    ALUR (audit fix #4 — dulu train window dihitung tapi TIDAK dipakai):
      per window (train → purge/embargo → test):
       1. semua kandidat grid di-backtest di data TRAIN window
       2. kandidat dengan trade >= WF_OPT_MIN_TRADES (filter) dan metrik
          WF_OPT_METRIC (default sharpe) terbaik -> PEMENANG
       3. HANYA pemenang yang di-backtest di data TEST (OOS)
      hasil OOS tiap window dikumpulkan -> gabungan equity curve OOS.

    Default length=365 agar cukup untuk beberapa window.
    """
    if candidates is None:
        candidates = DEFAULT_CANDIDATES

    from data_source.yahoo_client import fetch_trading_info
    bars = fetch_trading_info(code, length=length)
    if len(bars) < CFG.MIN_TRADING_DAYS:
        raise ValueError(f"Data {code} tidak cukup: {len(bars)} hari")

    n_bars = len(bars)
    windows = build_windows(n_bars)

    results: list[WFResult] = []

    for win in windows:
        # ── 1) Optimasi di TRAIN ──
        train_metrics = []
        for params in candidates:
            cfg = BacktestConfig(**{**GRID_FIXED_PARAMS, **params})
            try:
                metrics = run_backtest(
                    code,
                    capital=capital,
                    bt_config=cfg,
                    length=length,
                    sim_start_idx=win.train_start,
                    sim_end_idx=win.train_end,
                )
            except Exception:
                continue
            train_metrics.append((params, metrics))

        if not train_metrics:
            continue

        # Filter jumlah trade minimal di train → metrik pemenang
        qualified = [
            (p, m) for p, m in train_metrics
            if m.total_trades >= CFG.WF_OPT_MIN_TRADES
        ]
        pool = qualified if qualified else []  # kalau semuanya gugur → window skip
        if not pool:
            continue

        best_params, best_train = max(
            pool,
            key=lambda pm: (
                getattr(pm[1], CFG.WF_OPT_METRIC, 0.0),
                pm[1].total_trades,
            ),
        )

        # ── 2) Evaluasi OOS (test window) dengan pemenang ──
        oos_cfg = BacktestConfig(**{**GRID_FIXED_PARAMS, **best_params})
        try:
            oos = run_backtest(
                code,
                capital=capital,
                bt_config=oos_cfg,
                length=length,
                sim_start_idx=win.test_start,
                sim_end_idx=win.test_end,
            )
        except Exception:
            continue

        oos_trades = [asdict(t) for t in oos.trades]
        results.append(WFResult(
            code=code,
            window_id=win.id,
            params=best_params,
            oos_trades=oos_trades,
            oos_win_rate=oos.win_rate,
            oos_total_return=oos.total_return_pct,
            oos_sharpe=oos.sharpe,
            oos_max_dd=oos.max_drawdown_pct,
            train_sharpe=getattr(best_train, CFG.WF_OPT_METRIC, 0.0),
            train_trades=best_train.total_trades,
        ))

    return results


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Walk-Forward Validation")
    parser.add_argument("codes", nargs="+", help="Kode saham IDX")
    parser.add_argument("--capital", type=float, default=10_000_000)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    all_oos_trades = []
    all_results = []

    for code in args.codes:
        try:
            results = run_walk_forward(code, capital=args.capital)
            all_results.extend(results)
            for r in results:
                all_oos_trades.extend(r.oos_trades)
        except Exception as e:
            print(f"[ERROR] {code}: {e}", file=sys.stderr)

    # Audit fix #5: sharpe OOS TIDAK lagi dihitung dari return per-trade yang
    # di-annualisasi pakai √252 (salah secara metodologis). Dipakai sharpe
    # dari tiap window (sudah daily-equity-based di backtest.py).
    oos_rets = [t["return_pct"] / 100 for t in all_oos_trades]
    n = len(oos_rets)
    win_rate = sum(1 for r in oos_rets if r > 0) / n * 100 if n else 0.0
    total_ret = sum(oos_rets) * 100 if n else 0.0
    sharpe = float(np.mean([r.oos_sharpe for r in all_results])) if all_results else 0.0
    max_dd = 0.0
    eq = 1.0
    peak = 1.0
    for r in oos_rets:
        eq *= (1 + r)
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    report = {
        "codes": args.codes,
        "windows": len(set(r.window_id for r in all_results)),
        "param_sets": len(DEFAULT_CANDIDATES),
        "oos_trades": n,
        "oos_win_rate": round(win_rate, 1),
        "oos_total_return": round(total_ret, 2),
        "oos_sharpe": round(sharpe, 2),
        "oos_max_dd": round(max_dd, 2),
        "results": [asdict(r) for r in all_results],
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print()
        print("=" * 60)
        print("  WALK-FORWARD VALIDATION")
        print("=" * 60)
        print(f"  Codes:        {', '.join(args.codes)}")
        print(f"  Windows:      {report['windows']}")
        print(f"  Param sets:   {report['param_sets']}")
        print(f"  OOS Trades:   {report['oos_trades']}")
        print(f"  OOS Win Rate: {report['oos_win_rate']}%")
        print(f"  OOS Return:   {report['oos_total_return']}%")
        print(f"  OOS Sharpe:   {report['oos_sharpe']}")
        print(f"  OOS Max DD:   {report['oos_max_dd']}%")
        print()


if __name__ == "__main__":
    main()
