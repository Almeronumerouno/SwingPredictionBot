"""
_p79_walkforward_transparency.py — P7.9: Walk-Forward Selection Transparency.

Menjalankan ulang walk-forward (train 252 / test 63, purge 10 + embargo 10,
grid 36 kandidat — sama dgn run P7.2) pada saham liquid dgn return_meta=True,
lalu melaporkan metadata seleksi utk audit:
- total candidate trials per window
- parameter-selection frequency & mode share (berapa sering kandidat sama menang)
- parameter stability antar-window berturut-turut
- skipped-window rate + breakdown by reason
- breakdown skipped windows by regime (up/down/sideways dari train slice)
- breakdown skipped windows by liquidity (avg volume train slice)
- full selection metadata per window (simpan utk audit)

Usage: python _p79_walkforward_transparency.py [--no-save]
Output: data/phase7_p79_walkforward.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

import numpy as np

from data_source import local_dataset
from walkforward import build_windows, run_walk_forward

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
OUT_JSON = os.path.join(DATA_DIR, "phase7_p79_walkforward.json")
CODES = ["BBCA", "BBRI", "ASII", "TLKM"]
TRAIN_DAYS, TEST_DAYS = 252, 63
PURGE_DAYS, EMBARGO_DAYS = 10, 10
MIN_TRADES = 10
CAPITAL = 10_000_000


def _classify_regime(bars: list) -> str:
    """Regime train slice: up/down/sideways dari perubahan close awal→akhir."""
    if len(bars) < 2:
        return "n/a"
    first = float(bars[0].close)
    last = float(bars[-1].close)
    chg = last / first - 1.0 if first else 0.0
    if chg > 0.10:
        return "up"
    if chg < -0.10:
        return "down"
    return "sideways"


def _params_key(params: dict) -> str:
    return json.dumps({k: v for k, v in sorted(params.items())}, sort_keys=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=None)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    per_window: list[dict] = []
    winners: list[tuple[str, int, str]] = []  # (code, window_id, params_key)

    for code in CODES:
        try:
            bars = local_dataset.load_local_bars(code, args.npz)
        except Exception as e:
            print(f"[ERROR] {code}: {e}", file=sys.stderr)
            continue
        if len(bars) < TRAIN_DAYS + PURGE_DAYS + EMBARGO_DAYS + TEST_DAYS:
            print(f"[SKIP] {code}: data terlalu pendek ({len(bars)})", file=sys.stderr)
            continue
        print(f"\n== {code} ({len(bars)} bar) ==", flush=True)
        results, meta = run_walk_forward(
            code,
            capital=CAPITAL,
            bars=bars,
            train_days=TRAIN_DAYS,
            test_days=TEST_DAYS,
            purge_days=PURGE_DAYS,
            embargo_days=EMBARGO_DAYS,
            min_trades=MIN_TRADES,
            return_meta=True,
        )
        res_by_wid = {r.window_id: r for r in results}
        skip_reason = {s["window_id"]: s["reason"] for s in meta["skip_log"]}
        wins = build_windows(len(bars), TRAIN_DAYS, TEST_DAYS, PURGE_DAYS, EMBARGO_DAYS)
        for w in wins:
            tr = bars[w.train_start:w.train_end]
            rec = {
                "code": code,
                "window_id": w.id,
                "skipped": w.id not in res_by_wid,
                "reason": skip_reason.get(w.id),
                "regime": _classify_regime(tr),
                "avg_vol_train": round(float(np.mean([b.volume for b in tr])), 1)
                    if tr else None,
                "winner_params": None,
                "train_sharpe": None,
                "train_trades": None,
                "oos_sharpe": None,
                "oos_total_return": None,
                "oos_win_rate": None,
            }
            r = res_by_wid.get(w.id)
            if r is not None:
                rec.update({
                    "winner_params": r.params,
                    "train_sharpe": r.train_sharpe,
                    "train_trades": r.train_trades,
                    "oos_sharpe": r.oos_sharpe,
                    "oos_total_return": r.oos_total_return,
                    "oos_win_rate": r.oos_win_rate,
                })
                winners.append((code, w.id, _params_key(r.params)))
            per_window.append(rec)
        print(f"  windows: {meta['windows_total']} eval={meta['windows_evaluated']} "
              f"skip={meta['windows_skipped']} "
              f"reasons={meta['skip_reasons']}", flush=True)

    if not per_window:
        print("Tidak ada window dievaluasi — cek data.", file=sys.stderr)
        sys.exit(1)

    # ── Statistik transparansi ──
    n_win = len(per_window)
    n_skip = sum(1 for r in per_window if r["skipped"])
    reasons = Counter(r["reason"] for r in per_window if r["skipped"])
    reg_total = Counter(r["regime"] for r in per_window)
    reg_skip = Counter(r["regime"] for r in per_window if r["skipped"])

    freq = Counter(k for _, _, k in winners)
    total_wins = len(winners)
    mode_key, mode_cnt = (freq.most_common(1)[0] if freq else (None, 0))
    mode_share = round(mode_cnt / total_wins, 4) if total_wins else None

    # stability antar-window berturut-turut (per saham)
    by_code: dict[str, list[dict]] = {}
    for r in per_window:
        by_code.setdefault(r["code"], []).append(r)
    adj_same, adj_total = 0, 0
    for code, recs in by_code.items():
        recs_sorted = sorted(recs, key=lambda x: x["window_id"])
        prev = None
        for r in recs_sorted:
            if r["skipped"]:
                prev = None
                continue
            if prev is not None and prev == r["winner_params"]:
                adj_same += 1
            adj_total += 1
            prev = r["winner_params"]
    adj_stability = round(adj_same / adj_total, 4) if adj_total else None

    # liquidity: median avg_vol evaluated vs skipped (per saham)
    liq: dict[str, dict] = {}
    for code, recs in by_code.items():
        ev = [r["avg_vol_train"] for r in recs if not r["skipped"]
              and r["avg_vol_train"] is not None]
        sk = [r["avg_vol_train"] for r in recs if r["skipped"]
              and r["avg_vol_train"] is not None]
        liq[code] = {
            "median_avg_vol_evaluated": round(float(np.median(ev)), 1) if ev else None,
            "median_avg_vol_skipped": round(float(np.median(sk)), 1) if sk else None,
        }

    summary = {
        "method": "P7.9 walk-forward selection transparency (re-run, return_meta=True)",
        "window_spec": {"train": TRAIN_DAYS, "test": TEST_DAYS,
                        "purge": PURGE_DAYS, "embargo": EMBARGO_DAYS},
        "candidates_per_window": 36,
        "codes": CODES,
        "windows_total": n_win,
        "windows_evaluated": n_win - n_skip,
        "windows_skipped": n_skip,
        "skipped_rate": round(n_skip / n_win, 4),
        "skip_by_reason": dict(reasons),
        "skip_by_regime": {k: {"total": reg_total[k], "skipped": reg_skip[k],
                               "skipped_rate": round(reg_skip[k] / reg_total[k], 4)
                               if reg_total[k] else None}
                           for k in sorted(reg_total)},
        "liquidity_median_avg_vol": liq,
        "selection_frequency": dict(freq.most_common()),
        "mode_share_same_candidate_wins": mode_share,
        "mode_candidate": mode_key,
        "adjacent_window_stability": adj_stability,
        "adjacent_pairs": adj_total,
        "per_window_log": per_window,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print("\n===== RINGKASAN =====")
    print(f"Windows: {n_win} (eval {n_win - n_skip}, skip {n_skip} = "
          f"{summary['skipped_rate']:.1%})")
    print(f"Skip reasons: {summary['skip_by_reason']}")
    print(f"Skip by regime: {summary['skip_by_regime']}")
    print(f"Mode share (kandidat sama menang): {mode_share}  [{mode_key}]")
    print(f"Adjacent-window stability: {adj_stability} ({adj_total} pasang)")
    print(f"Liquidity: {json.dumps(liq)}")

    if not args.no_save:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\nTersimpan: {args.out}")
    else:
        print("\n(no-save)")


if __name__ == "__main__":
    sys.exit(main())