"""
backtest_calibrate.py — Multi-parameter calibration untuk Swingbot IDX.

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
from dataclasses import dataclass, asdict, field
from typing import Any, Optional

import numpy as np

import config as CFG
from backtest import BacktestConfig, BacktestMetrics, run_backtest, print_report


# ──────────────────────────────────────────────
#  Default Parameter Grid
# ──────────────────────────────────────────────

# audit fix #3: grid default dibuat SEKECIL mungkin (ikut CFG.WF_OPT_GRID =
# 36 kombinasi, bukan 1.280 kombinasi lama yang 100% in-sample). Optimasi
# jalan di data TRAIN; ranking akhir divalidasi ulang di data TEST (OOS).
DEFAULT_PARAM_GRID: dict[str, list[Any]] = dict(CFG.WF_OPT_GRID)

DEFAULT_CODES = ["BBCA", "BMRI", "ASII", "TLKM", "ADRO"]

DEFAULT_METRIC = "sharpe"


# ──────────────────────────────────────────────
#  Calibration Runner
# ──────────────────────────────────────────────

@dataclass
class CalibrationResult:
    params: dict[str, Any]
    aggregate: dict[str, float]                 # metrik di data TRAIN
    per_stock: dict[str, BacktestMetrics]
    oos_aggregate: dict[str, float] = field(default_factory=dict)  # metrik di data TEST
    oos_per_stock: dict[str, BacktestMetrics] = field(default_factory=dict)


def run_calibration(
    codes: list[str],
    param_grid: dict[str, list[Any]],
    capital: float = 100_000_000,
    length: int = 365,
    target_date: str | None = None,
    fixed_params: Optional[dict] = None,
    test_days: int = 63,
    train_top_n: int = 10,
) -> list[CalibrationResult]:
    """
    Iterate all parameter combinations, run backtest on TRAIN window for each
    stock, aggregate, then re-validate the top-N combos on the TEST (OOS)
    window — audit fix #3 (sebelumnya: optimasi 100% in-sample, 1.280
    kombinasi, tanpa validasi out-of-sample sama sekali).

    Args:
        codes: List kode saham IDX
        param_grid: Dict {param_name: [values_to_try]}
        capital: Modal untuk backtest
        length: Hari kalender historis
        target_date: Optional YYYY-MM-DD
        fixed_params: Parameter yang tetap (not in grid)
        test_days: Jumlah trading day terakhir yang dijadikan TEST (OOS)
        train_top_n: Top-N kombinasi (urut by aggregate[metric]) yang
                     di-validasi ulang di data TEST

    Returns:
        List CalibrationResult sorted by aggregate[metric].oos_aggregate
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

    # ── Tentukan titik potong TRAIN/TEST per saham ──
    from data_source.yahoo_client import fetch_trading_info
    test_start_idx_by_code: dict[str, int] = {}
    for code in codes:
        bars = fetch_trading_info(code, length=length, target_date=target_date)
        n_bars = len(bars)
        test_start_idx_by_code[code] = max(0, n_bars - test_days)

    for idx, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        merged = {**fixed_params, **params}

        # Build BacktestConfig
        cfg = BacktestConfig()
        for k, v in merged.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

        sys.stdout.write(f"\r  Calibrating (TRAIN) [{idx}/{total}] {params}... ")
        sys.stdout.flush()

        per_stock: dict[str, BacktestMetrics] = {}
        aggregate: dict[str, float] = {m: 0.0 for m in metric_names}

        valid_count = 0
        for code in codes:
            try:
                metrics = run_backtest(
                    code, capital=capital, bt_config=cfg,
                    length=length, target_date=target_date,
                    sim_end_idx=test_start_idx_by_code.get(code),
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
        time.sleep(0.05)

    print()

    # ── Audit fix #3: validasi OOS untuk top-N ──
    candidates_ranked = sorted(
        results,
        key=lambda r: r.aggregate.get(DEFAULT_METRIC, 0.0),
        reverse=True,
    )[:train_top_n]

    print(f"  Validasi OOS top-{len(candidates_ranked)} kombinasi (TEST window, {test_days} hari)...")
    for r in candidates_ranked:
        cfg = BacktestConfig()
        for k, v in r.params.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

        oos_agg: dict[str, float] = {m: 0.0 for m in metric_names}
        oos_valid = 0
        r.oos_per_stock = {}
        for code in codes:
            try:
                metrics = run_backtest(
                    code, capital=capital, bt_config=cfg,
                    length=length, target_date=target_date,
                    sim_start_idx=test_start_idx_by_code.get(code, 0),
                )
                r.oos_per_stock[code] = metrics
                if metrics.total_trades > 0:
                    for m in metric_names:
                        oos_agg[m] += getattr(metrics, m, 0.0)
                    oos_valid += 1
            except (ValueError, Exception) as e:
                sys.stdout.write(f"[OOS {code}:{e}] ")
        if oos_valid > 0:
            for m in metric_names:
                oos_agg[m] /= oos_valid
        r.oos_aggregate = oos_agg

    # Rank utama: kombinasi yang DIVALIDASI OOS selalu di atas yang tidak
    # (fix: sebelumnya oos_aggregate kosong = 0.0, menang palsu atas OOS
    #  sharpe negatif → leaderboard bisa dipenuhi kombinasi tanpa validasi)
    def _rank_key(r: CalibrationResult) -> tuple[int, float, float]:
        validated = 1 if r.oos_per_stock else 0
        oos = r.oos_aggregate.get(DEFAULT_METRIC, 0.0) if validated else 0.0
        train = r.aggregate.get(DEFAULT_METRIC, 0.0)
        return (validated, oos, train)

    results.sort(key=_rank_key, reverse=True)
    return results


# ──────────────────────────────────────────────
#  Report
# ──────────────────────────────────────────────

def print_leaderboard(
    results: list[CalibrationResult],
    metric: str = "sharpe",
    top_n: int = 10,
) -> None:
    """Print top-N parameter combinations ranked by (OOS, train) metric."""
    sorted_results = sorted(
        results,
        key=lambda r: (1 if r.oos_per_stock else 0,
                       r.oos_aggregate.get(metric, 0.0) if r.oos_per_stock else 0.0,
                       r.aggregate.get(metric, 0.0)),
        reverse=True,
    )

    sep = "=" * 88
    header = (
        f"  {'Rank':>4}  {'WinRate':>7}  {'TotRet':>8}  {'OOS.Sharpe':>10}  "
        f"{'Trn.Sharpe':>10}  {'MaxDD':>7}  {'OOS.Trades':>10}  {'Params'}"
    )

    print()
    print(sep)
    print(f"  CALIBRATION LEADERBOARD — ranked by {metric} (OOS primary, train tiebreak)")
    print(sep)
    print(header)
    print("-" * 88)

    for rank, r in enumerate(sorted_results[:top_n], 1):
        a = r.aggregate
        oos_a = r.oos_aggregate
        validated = bool(r.oos_per_stock)
        oos_trades = int(oos_a.get("total_trades", 0)) if validated else -1
        param_str = " ".join(f"{k}={v}" for k, v in r.params.items())
        print(
            f"  {rank:>4}  "
            f"{a.get('win_rate', 0):>6.1f}%  "
            f"{a.get('total_return_pct', 0):>+7.2f}%  "
            f"{oos_a.get(metric, 0) if validated else float('nan'):>10.3f}  "
            f"{a.get(metric, 0):>10.3f}  "
            f"{a.get('max_drawdown_pct', 0):>6.2f}%  "
            f"{str(oos_trades) if validated else '-':>10}  "
            f"{param_str}"
        )

    print("-" * 80)

    # Best params per OOS (bukan train in-sample) — HANYA dari kombinasi
    # yang benar-benar divalidasi di data TEST (fix: sebelumnya bisa memilih
    # kombinasi tanpa validasi sama sekali)
    validated_results = [r for r in sorted_results if r.oos_per_stock]
    if not validated_results:
        print("  TIDAK ADA kombinasi yang divalidasi OOS — cek train_top_n / data TEST.")
        return
    best = validated_results[0]
    print()
    print("  RECOMMENDED PARAMETERS (terbaik di data TEST/OOS):")
    print(f"    {best.params}")
    print(f"    OOS Sharpe:    {best.oos_aggregate.get(metric, 0):.3f}  (data TEST)")
    print(f"    Train Sharpe:  {best.aggregate.get(metric, 0):.3f}  (data TRAIN — hanya referensi)")
    print(f"    OOS Win Rate:  {best.oos_aggregate.get('win_rate', 0):.1f}%")
    print(f"    OOS Trades:    {int(best.oos_aggregate.get('total_trades', 0))}")
    print()


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Calibrate Swingbot IDX parameters — Fase 6",
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
    parser.add_argument("--test-days", type=int, default=63,
                        help="Trading day terakhir yang jadi data TEST (OOS)")
    parser.add_argument("--train-top", type=int, default=10,
                        help="Top-N kombinasi (by train metric) yang divalidasi di TEST")
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
        test_days=args.test_days,
        train_top_n=args.train_top,
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
                "oos_aggregate": r.oos_aggregate,
                "per_stock": {
                    code: {
                        k: v for k, v in asdict(metrics).items()
                        if k != "trades"  # exclude large trade list
                    }
                    for code, metrics in r.per_stock.items()
                },
            }
            for r in results
        ]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"  Results exported to {args.output}")
        print()


if __name__ == "__main__":
    main()
