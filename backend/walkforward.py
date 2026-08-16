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

from sklearn.metrics import roc_auc_score

import config as CFG
from backtest import BacktestConfig, run_backtest
from portfolio import events_from_wf_results, build_portfolio_series


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
    # metrik evaluasi KLASIFIKASI (MED#2): seberapa baik entry_score
    # membedakan trade menang vs kalah di OOS. None kalau sampel < 2 kelas.
    oos_precision: float | None = None   # = win rate (@ threshold default)
    oos_auc_win: float | None = None     # AUC-ROC(entry_score, return_pct>0)


def run_walk_forward(
    code: str,
    capital: float = 10_000_000,
    candidates: list[dict] | None = None,
    length: int = 365,
    bars: list | None = None,
    train_days: int | None = None,
    test_days: int | None = None,
    purge_days: int | None = None,
    embargo_days: int | None = None,
    min_trades: int | None = None,
    return_meta: bool = False,
) -> list[WFResult] | tuple[list[WFResult], dict]:
    """
    Run walk-forward validation untuk satu kode saham.

    ALUR (audit fix #4 — dulu train window dihitung tapi TIDAK dipakai):
      per window (train → purge/embargo → test):
       1. semua kandidat grid di-backtest di data TRAIN window
       2. kandidat dengan trade >= WF_OPT_MIN_TRADES (filter) dan metrik
          WF_OPT_METRIC (default sharpe) terbaik -> PEMENANG
       3. HANYA pemenang yang di-backtest di data TEST (OOS)
      hasil OOS tiap window dikumpulkan -> gabungan equity curve OOS.

    P6.6 (Agu 2026): transparansi skip window (audit C8). Bila return_meta=True,
    return (results, meta) dengan meta = {
      windows_total, windows_evaluated, windows_skipped,
      skip_reasons: {no_train_fit, under_min_trades, oos_error},
      skip_log: [{window_id, reason, n_trials}] }

    bars: bar lokal (data_source.local_dataset.load_local_bars) — bila
          diberikan, fetch Yahoo di-skip. Saat bars dipakai, beri
          train_days/test_days lebih panjang (mis. 252/63) krn sinyal swing
          jarang (~3 trade per 63 hari) — window pendek meleset di bawah
          min_trades sehingga semua window ter-skip.
    Default length=365 agar cukup untuk beberapa window.
    """
    if candidates is None:
        candidates = DEFAULT_CANDIDATES

    if bars is None:
        from data_source.yahoo_client import fetch_trading_info
        bars = fetch_trading_info(code, length=length)
    else:
        # length hanya dipakai fetch; saat bars lokal, samakan dgn data
        length = len(bars)
    if len(bars) < CFG.MIN_TRADING_DAYS:
        raise ValueError(f"Data {code} tidak cukup: {len(bars)} hari")

    train_days = train_days if train_days is not None else CFG.WF_TRAIN_DAYS
    test_days = test_days if test_days is not None else CFG.WF_TEST_DAYS
    purge_days = purge_days if purge_days is not None else CFG.WF_PURGE_DAYS
    embargo_days = embargo_days if embargo_days is not None else CFG.WF_EMBARGO_DAYS
    min_trades = min_trades if min_trades is not None else CFG.WF_OPT_MIN_TRADES

    n_bars = len(bars)
    windows = build_windows(n_bars, train_days, test_days, purge_days, embargo_days)

    results: list[WFResult] = []
    # P6.6: transparansi skip (audit C8)
    skip_reasons = {"no_train_fit": 0, "under_min_trades": 0, "oos_error": 0}
    skip_log: list[dict] = []

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
                    bars=bars,
                )
            except Exception:
                continue
            train_metrics.append((params, metrics))

        if not train_metrics:
            skip_reasons["no_train_fit"] += 1
            skip_log.append({"window_id": win.id, "reason": "no_train_fit",
                             "n_trials": 0})
            continue

        # Filter jumlah trade minimal di train → metrik pemenang
        qualified = [
            (p, m) for p, m in train_metrics
            if m.total_trades >= min_trades
        ]
        pool = qualified if qualified else []  # kalau semuanya gugur → window skip
        if not pool:
            skip_reasons["under_min_trades"] += 1
            skip_log.append({"window_id": win.id, "reason": "under_min_trades",
                             "n_trials": len(train_metrics)})
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
                bars=bars,
            )
        except Exception:
            skip_reasons["oos_error"] += 1
            skip_log.append({"window_id": win.id, "reason": "oos_error",
                             "n_trials": len(train_metrics)})
            continue

        oos_trades = [asdict(t) for t in oos.trades]
        # MED#2 — metrik klasifikasi: entry_score vs outcome win/loss
        prec = None
        auc = None
        if oos.trades:
            prec = round(
                oos.winning_trades / oos.total_trades, 4
            ) if oos.total_trades else None
            ys = [1.0 if t.return_pct > 0 else 0.0 for t in oos.trades]
            scores = [t.entry_score for t in oos.trades]
            if len(set(ys)) == 2 and len(scores) >= 4:
                try:
                    auc = round(roc_auc_score(ys, scores), 4)
                except ValueError:
                    auc = None
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
            oos_precision=prec,
            oos_auc_win=auc,
        ))

    if return_meta:
        meta = {
            "windows_total": len(windows),
            "windows_evaluated": len(results),
            "windows_skipped": len(windows) - len(results),
            "skip_reasons": skip_reasons,
            "skip_log": skip_log,
            "n_trials_per_window": len(candidates),
        }
        return results, meta
    return results


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────

def main() -> None:
    import argparse
    from data_source import local_dataset

    parser = argparse.ArgumentParser(description="Walk-Forward Validation")
    parser.add_argument("codes", nargs="+", help="Kode saham IDX")
    parser.add_argument("--capital", type=float, default=10_000_000)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--local", action="store_true",
        help="pakai dataset lokal universe_ohlcv.npz (tanpa fetch Yahoo)",
    )
    parser.add_argument("--npz", default=None, help="path universe_ohlcv.npz")
    parser.add_argument(
        "--train-days", type=int, default=None,
        help="panjang train window (default config WF_TRAIN_DAYS; "
             "saat --local disarankan 252 krn sinyal swing jarang)",
    )
    parser.add_argument(
        "--test-days", type=int, default=None,
        help="panjang test/OOS window (default config WF_TEST_DAYS; "
             "saat --local disarankan 63)",
    )
    parser.add_argument(
        "--min-trades", type=int, default=None,
        help="minimal trade di train window utk kandidat (default config)",
    )
    args = parser.parse_args()

    # Saat --local, default window yang masuk akal utk ~900 bar dataset
    train_days = args.train_days if args.train_days is not None else (
        252 if args.local else CFG.WF_TRAIN_DAYS)
    test_days = args.test_days if args.test_days is not None else (
        63 if args.local else CFG.WF_TEST_DAYS)

    all_oos_trades = []
    all_results = []
    # P7.2: harga close per saham utk mark-to-market portfolio
    price_map: dict[str, dict[str, float]] = {}
    # P6.6: agregasi meta skip lintas saham (audit C8)
    meta_total = {"windows_total": 0, "windows_evaluated": 0,
                  "windows_skipped": 0, "skip_reasons": {},
                  "skip_log": []}

    for code in args.codes:
        try:
            bars = None
            if args.local:
                bars = local_dataset.load_local_bars(code, args.npz)
            else:
                # P7.2: fetch sekali di main (dipakai juga utk portfolio mtm);
                # run_walk_forward tidak fetch lagi bila bars diberikan.
                from data_source.yahoo_client import fetch_trading_info
                bars = fetch_trading_info(code, length=365)
            results, meta = run_walk_forward(
                code,
                capital=args.capital,
                bars=bars,
                train_days=train_days,
                test_days=test_days,
                min_trades=args.min_trades,
                return_meta=True,
            )
            all_results.extend(results)
            for r in results:
                all_oos_trades.extend(r.oos_trades)
            price_map[code] = {b.date: float(b.close) for b in bars}
            for k in ("windows_total", "windows_evaluated", "windows_skipped"):
                meta_total[k] += meta[k]
            for k, v in meta["skip_reasons"].items():
                meta_total["skip_reasons"][k] = meta_total["skip_reasons"].get(k, 0) + v
            meta_total["skip_log"].extend(meta["skip_log"])
        except Exception as e:
            print(f"[ERROR] {code}: {e}", file=sys.stderr)

    # Audit fix #5 + P7.2: portfolio metrics TIDAK lagi dihitung dari
    # sum(trade_return_pct) atau mean(window_sharpe). Semua metric portfolio
    # (return, Sharpe, Sortino, max DD, CAGR, turnover, total cost) dihitung
    # dari SATU chronological equity/cash/position series (portfolio.py).
    oos_rets = [t["return_pct"] / 100 for t in all_oos_trades]
    n = len(oos_rets)
    win_rate = sum(1 for r in oos_rets if r > 0) / n * 100 if n else 0.0

    portfolio = None
    if all_results:
        events = events_from_wf_results(all_results)
        if events:
            portfolio = build_portfolio_series(
                events,
                price_map,
                capital=args.capital,
                max_positions=3,
                fee_buy_pct=CFG.FEE_BUY_PCT,
                fee_sell_pct=CFG.FEE_SELL_PCT,
            )

    # MED#2 — metrik klasifikasi agregat: precision & AUC(score→win) OOS
    precs = [r.oos_precision for r in all_results if r.oos_precision is not None]
    aucs = [r.oos_auc_win for r in all_results if r.oos_auc_win is not None]
    # MED#2 — metrik klasifikasi agregat: precision & AUC(score→win) OOS
    precs = [r.oos_precision for r in all_results if r.oos_precision is not None]
    aucs = [r.oos_auc_win for r in all_results if r.oos_auc_win is not None]
    report = {
        "codes": args.codes,
        # P7.2: window identity = (code, window_id) — window_id per saham
        # tidak unik global (build_windows mulai dari 1 utk tiap saham).
        "windows": len(set((r.code, r.window_id) for r in all_results)),
        "param_sets": len(DEFAULT_CANDIDATES),
        "oos_trades": n,
        "oos_win_rate": round(win_rate, 1),
        # P7.2: metrik portfolio-level dari SATU chronological series.
        # Per-window/per-stock metrics tetap tersedia di "results".
        "oos_total_return": portfolio.total_return_pct if portfolio else 0.0,
        "oos_sharpe": portfolio.sharpe if portfolio else None,
        "oos_max_dd": portfolio.max_drawdown_pct if portfolio else 0.0,
        "portfolio_metrics": {
            "sortino": portfolio.sortino if portfolio else None,
            "cagr_pct": portfolio.cagr_pct if portfolio else None,
            "turnover": portfolio.turnover if portfolio else 0.0,
            "total_cost": portfolio.total_cost if portfolio else 0.0,
            "n_days": portfolio.n_days if portfolio else 0,
            "avg_exposure": portfolio.avg_exposure if portfolio else 0.0,
            "peak_positions": portfolio.peak_positions if portfolio else 0,
            "skipped_events": portfolio.skipped_events if portfolio else 0,
        } if portfolio else None,
        "oos_precision": round(float(np.mean(precs)), 4) if precs else None,
        "oos_auc_win": round(float(np.mean(aucs)), 4) if aucs else None,
        # P6.6: transparansi skip window lintas saham (audit C8)
        "wf_meta": {
            "windows_total": meta_total["windows_total"],
            "windows_evaluated": meta_total["windows_evaluated"],
            "windows_skipped": meta_total["windows_skipped"],
            "skip_reasons": meta_total["skip_reasons"],
            "n_skip_log_entries": len(meta_total["skip_log"]),
        },
        "results": [asdict(r) for r in all_results],
    }
    if portfolio is not None:
        report["portfolio_series"] = [asdict(p) for p in portfolio.series]

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print()
        print("=" * 60)
        print("  WALK-FORWARD VALIDATION (portfolio-level, P7.2)")
        print("=" * 60)
        print(f"  Codes:        {', '.join(args.codes)}")
        print(f"  Windows:      {report['windows']}")
        print(f"  Param sets:   {report['param_sets']}")
        print(f"  OOS Trades:   {report['oos_trades']}")
        print(f"  OOS Win Rate: {report['oos_win_rate']}%")
        if portfolio is not None:
            print(f"  Port. Return: {portfolio.total_return_pct}%  (CAGR {portfolio.cagr_pct}%)")
            print(f"  Port. Sharpe: {portfolio.sharpe}   Sortino: {portfolio.sortino}")
            print(f"  Port. Max DD: {portfolio.max_drawdown_pct}%")
            print(f"  Turnover:     {portfolio.turnover}   Cost: Rp {portfolio.total_cost:,.0f}")
            print(f"  Days:         {portfolio.n_days}   Avg exposure: {portfolio.avg_exposure:.1%}  "
                  f"Peak pos: {portfolio.peak_positions}")
        else:
            print(f"  (tidak ada trade OOS — portfolio metrics kosong)")
        print(f"  OOS Prec:     {report['oos_precision']}")
        print(f"  OOS AUC(win): {report['oos_auc_win']}")
        wm = report["wf_meta"]
        print(f"  WF windows:   {wm['windows_evaluated']} evaluated / "
              f"{wm['windows_total']} total ({wm['windows_skipped']} skipped)")
        if wm["skip_reasons"]:
            print(f"    skip: {wm['skip_reasons']}")
        print()


if __name__ == "__main__":
    main()
