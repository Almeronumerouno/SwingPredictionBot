"""
backtest_calibrate.py — Multi-parameter calibration untuk SwingPredictionBot.

Mencoba berbagai kombinasi parameter, menjalankan backtest pada beberapa
saham IDX, dan menampilkan perbandingan metrik untuk menemukan parameter
optimal.

Strategi:
  1. Define parameter grid (nilai-nilai yang mau dicoba)
  2. Untuk tiap kombinasi → run backtest di beberapa saham
  3. Aggregate metrics
  4. Rank kombinasi berdasarkan metrik pilihan (default: Sharpe)
  5. Cetak leaderboard

Usage:
  python backtest_calibrate.py                          # default grid
  python backtest_calibrate.py --codes BBCA BMRI ASII   # custom stocks
  python backtest_calibrate.py --metric win_rate        # rank by win rate
  python backtest_calibrate.py --output results.json    # export ke JSON
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any, Optional

import numpy as np

from backtest import BacktestConfig, BacktestMetrics, run_backtest, print_report


# ──────────────────────────────────────────────
#  Default Parameter Grid
# ──────────────────────────────────────────────

DEFAULT_PARAM_GRID: dict[str, list[Any]] = {
    "adx_gate_ceiling": [15, 20, 25, 30],
    "swing_buy_threshold": [55, 60, 65, 70, 75],
    "atr_sl_multiplier": [1.5, 2.0, 3.0, 4.0],
    "rvol_window": [5, 10, 20, 30],
    "rvol_breakout_confirm": [1.2, 1.5, 2.0, 3.0],
}

DEFAULT_CODES = ["BBCA", "BMRI", "ASII", "TLKM", "ADRO"]

DEFAULT_METRIC = "sharpe"


# ──────────────────────────────────────────────
#  Calibration Runner
# ──────────────────────────────────────────────

@dataclass
class CalibrationResult:
    params: dict[str, Any]
    aggregate: dict[str, float]
    per_stock: dict[str, BacktestMetrics]


def run_calibration(
    codes: list[str],
    param_grid: dict[str, list[Any]],
    capital: float = 100_000_000,
    length: int = 365,
    target_date: str | None = None,
    fixed_params: Optional[dict] = None,
) -> list[CalibrationResult]:
    """
    Iterate all parameter combinations, run backtest for each stock,
    aggregate metrics, return ranked results.

    Args:
        codes: List kode saham IDX
        param_grid: Dict {param_name: [values_to_try]}
        capital: Modal untuk backtest
        length: Hari kalender historis
        target_date: Optional YYYY-MM-DD
        fixed_params: Parameter yang tetap (not in grid)

    Returns:
        List CalibrationResult sorted by aggregate[metric] descending
    """
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(itertools.product(*param_values))

    if fixed_params is None:
        fixed_params = {}

    results: list[CalibrationResult] = []
    total = len(combinations)
    metric_names = [
        "total_return_pct", "buy_hold_return_pct", "alpha_pct",
        "win_rate", "sharpe", "avg_rr", "max_drawdown_pct",
        "total_trades", "avg_return_per_trade", "avg_holding_days",
    ]

    for idx, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        merged = {**fixed_params, **params}

        # Build BacktestConfig
        cfg = BacktestConfig()
        for k, v in merged.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

        sys.stdout.write(f"\r  Calibrating [{idx}/{total}] {params}... ")
        sys.stdout.flush()

        per_stock: dict[str, BacktestMetrics] = {}
        aggregate: dict[str, float] = {m: 0.0 for m in metric_names}

        valid_count = 0
        for code in codes:
            try:
                metrics = run_backtest(
                    code, capital=capital, bt_config=cfg,
                    length=length, target_date=target_date,
                )
                per_stock[code] = metrics
                if metrics.total_trades > 0:
                    for m in metric_names:
                        aggregate[m] += getattr(metrics, m, 0.0)
                    valid_count += 1
            except (ValueError, Exception) as e:
                sys.stdout.write(f"[{code}:{e}] ")

        if valid_count > 0:
            for m in metric_names:
                aggregate[m] /= valid_count

        results.append(CalibrationResult(
            params=params,
            aggregate=aggregate,
            per_stock=per_stock,
        ))

        # Small delay to avoid rate limiting
        time.sleep(0.1)

    print()
    return results


# ──────────────────────────────────────────────
#  Report
# ──────────────────────────────────────────────

def print_leaderboard(
    results: list[CalibrationResult],
    metric: str = "sharpe",
    top_n: int = 10,
) -> None:
    """Print top-N parameter combinations ranked by metric."""
    sorted_results = sorted(
        results,
        key=lambda r: r.aggregate.get(metric, 0.0),
        reverse=True,
    )

    sep = "=" * 80
    header = (
        f"  {'Rank':>4}  {'WinRate':>7}  {'TotRet':>8}  {'Alpha':>8}  "
        f"{'Sharpe':>7}  {'MaxDD':>7}  {'AvgR:R':>7}  {'Trades':>6}  "
        f"{'Params'}"
    )

    print()
    print(sep)
    print(f"  CALIBRATION LEADERBOARD — ranked by {metric}")
    print(sep)
    print(header)
    print("-" * 80)

    for rank, r in enumerate(sorted_results[:top_n], 1):
        a = r.aggregate
        param_str = " ".join(f"{k}={v}" for k, v in r.params.items())
        print(
            f"  {rank:>4}  "
            f"{a.get('win_rate', 0):>6.1f}%  "
            f"{a.get('total_return_pct', 0):>+7.2f}%  "
            f"{a.get('alpha_pct', 0):>+7.2f}%  "
            f"{a.get('sharpe', 0):>7.3f}  "
            f"{a.get('max_drawdown_pct', 0):>6.2f}%  "
            f"{a.get('avg_rr', 0):>7.2f}  "
            f"{int(a.get('total_trades', 0)):>6}  "
            f"{param_str}"
        )

    print("-" * 80)

    # Best params
    best = sorted_results[0]
    print()
    print("  RECOMMENDED PARAMETERS:")
    print(f"    {best.params}")
    print(f"    Expected Sharpe: {best.aggregate.get('sharpe', 0):.3f}")
    print(f"    Expected Win Rate: {best.aggregate.get('win_rate', 0):.1f}%")
    print(f"    Expected Alpha: {best.aggregate.get('alpha_pct', 0):+.2f}%")
    print()


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Calibrate SwingPredictionBot parameters — Fase 6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python backtest_calibrate.py
  python backtest_calibrate.py --codes BBCA BMRI --metric sharpe
  python backtest_calibrate.py --param adx_gate_ceiling 20 25 30 --param rvol_window 10 20
  python backtest_calibrate.py --top 5 --output best.json
        """,
    )
    parser.add_argument("--codes", nargs="+", default=DEFAULT_CODES,
                        help=f"Kode saham (default: {' '.join(DEFAULT_CODES)})")
    parser.add_argument("--capital", type=float, default=100_000_000)
    parser.add_argument("--length", type=int, default=365)
    parser.add_argument("--metric", default=DEFAULT_METRIC,
                        help=f"Metrik ranking (default: {DEFAULT_METRIC})")
    parser.add_argument("--top", type=int, default=10, help="Top N ditampilkan")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output JSON file untuk hasil lengkap")
    parser.add_argument("--param", action="append", nargs="+", default=None,
                        help="Custom param grid: --param adx_gate_ceiling 20 25 30")
    parser.add_argument("--no-default-params", action="store_true",
                        help="Jangan pakai default grid (harus --param manual)")

    args = parser.parse_args()

    # Build param grid
    param_grid: dict[str, list[Any]] = {}
    if not args.no_default_params:
        param_grid = dict(DEFAULT_PARAM_GRID)

    if args.param:
        for p in args.param:
            if len(p) < 2:
                print(f"[WARN] Skip --param: butuh minimal 1 nama + 1 value, dapat {p}")
                continue
            name = p[0]
            values = []
            for v in p[1:]:
                try:
                    values.append(int(v) if "." not in v else float(v))
                except ValueError:
                    values.append(v)
            param_grid[name] = values

    if not param_grid:
        print("[ERROR] Parameter grid kosong. Gunakan --param atau hapus --no-default-params")
        sys.exit(1)

    total_combos = 1
    for v in param_grid.values():
        total_combos *= len(v)
    print(f"\n  Total parameter combinations: {total_combos}")
    print(f"  Stocks: {args.codes}")
    print(f"  Param grid: {param_grid}")
    print()

    start = time.time()
    results = run_calibration(
        codes=args.codes,
        param_grid=param_grid,
        capital=args.capital,
        length=args.length,
    )
    elapsed = time.time() - start

    print(f"\n  Completed {total_combos} combos x {len(args.codes)} stocks in {elapsed:.1f}s")
    print()

    print_leaderboard(results, metric=args.metric, top_n=args.top)

    if args.output:
        output_data = [
            {
                "params": r.params,
                "aggregate": r.aggregate,
                "per_stock": {
                    code: {
                        k: v for k, v in asdict(metrics).items()
                        if k != "trades"  # exclude large trade list
                    }
                    for code, metrics in r.per_stock.items()
                },
            }
            for r in sorted(results, key=lambda x: x.aggregate.get(args.metric, 0), reverse=True)
        ]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"  Results exported to {args.output}")
        print()


if __name__ == "__main__":
    main()
