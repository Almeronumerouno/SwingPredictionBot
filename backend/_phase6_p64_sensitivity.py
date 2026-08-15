"""
_phase6_p64_sensitivity.py — P6.4: sensitivitas asumsi eksekusi backtest (C5/C6).

Grid: entry-mode {close, open} x slippage {0, 25, 50, 100} bps pada 5 saham
liquid. Tujuan: ukur seberapa besar hasil backtest bergantung pada asumsi
eksekusi — BUKAN memilih konfigurasi yang paling menguntungkan.

Output: data/phase6_execution_sensitivity.json + tabel stdout.

Usage:
    python _phase6_p64_sensitivity.py [--codes BBCA BMRI ASII TLKM BBNI]
"""

from __future__ import annotations

import argparse
import json
import os
import time

from backtest import BacktestConfig, run_backtest

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(BACKEND_DIR, "data", "phase6_execution_sensitivity.json")

GRID = [
    ("close", 0),    # baseline = perilaku lama (C5)
    ("open", 0),     # market order convention (backtrader)
    ("open", 25),
    ("open", 50),
    ("open", 100),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codes", nargs="+", default=["BBCA", "BMRI", "ASII", "TLKM", "BBNI"])
    ap.add_argument("--length", type=int, default=500)
    args = ap.parse_args()

    rows = []
    t0 = time.time()
    for mode, slip in GRID:
        agg = {"total_trades": 0, "win_rate": [], "total_return_pct": [],
               "sharpe": [], "avg_ret_per_trade": []}
        per_code = {}
        for code in args.codes:
            cfg = BacktestConfig(entry_mode=mode, slippage_bps=float(slip))
            try:
                m = run_backtest(code, bt_config=cfg, length=args.length)
            except Exception as e:  # noqa: BLE001
                per_code[code] = {"error": str(e)}
                continue
            per_code[code] = {
                "total_trades": m.total_trades, "win_rate": m.win_rate,
                "total_return_pct": m.total_return_pct, "sharpe": m.sharpe,
                "avg_ret_per_trade": m.avg_return_per_trade,
                "max_dd_pct": m.max_drawdown_pct,
            }
            if m.total_trades > 0:
                agg["total_trades"] += m.total_trades
                agg["win_rate"].append(m.win_rate)
                agg["total_return_pct"].append(m.total_return_pct)
                agg["sharpe"].append(m.sharpe)
                agg["avg_ret_per_trade"].append(m.avg_return_per_trade)
        n = max(1, len(agg["win_rate"]))
        rows.append({
            "entry_mode": mode, "slippage_bps": slip,
            "per_code": per_code,
            "agg": {
                "total_trades": agg["total_trades"],
                "avg_win_rate": round(sum(agg["win_rate"]) / n, 1),
                "avg_total_return_pct": round(sum(agg["total_return_pct"]) / n, 2),
                "avg_sharpe": round(sum(agg["sharpe"]) / n, 2),
                "avg_ret_per_trade": round(sum(agg["avg_ret_per_trade"]) / n, 2),
            },
        })
        a = rows[-1]["agg"]
        print(f"{mode:>5} + {slip:>3}bps  trades={a['total_trades']:>4}  "
              f"WR={a['avg_win_rate']:>5.1f}%  ret={a['avg_total_return_pct']:>7.2f}%  "
              f"sharpe={a['avg_sharpe']:>5.2f}  avg/trade={a['avg_ret_per_trade']:>5.2f}%",
              flush=True)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"grid": [{"entry_mode": m, "slippage_bps": s} for m, s in GRID],
                   "codes": args.codes, "length": args.length,
                   "rows": rows}, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {OUT_PATH} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()