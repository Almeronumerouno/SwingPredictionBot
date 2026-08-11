"""
_validate_recovery.py — Walk-forward validation untuk model Recovery (GBM FPT).

Untuk tiap event "close turun X% di bawah previous close" dalam history:
  1. Estimasi mu/sigma GBM HANYA dari bar sebelum event (anti look-ahead).
  2. Prediksi P(hit ref dalam h hari) via first_passage_cdf.
  3. Actual: max(high[i+1..i+h]) >= ref ?

Output per horizon: n, mean prediksi, actual rate, Brier score, dan
kalibrasi bucket. Brier ~0.25 = tebak konstan; model baik < 0.25.

Usage:
    python _validate_recovery.py BBCA BMRI BBRI [--drop 5] [--length 800] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

import config as CFG
from recovery import estimate_gbm_params, first_passage_cdf
from data_source.yahoo_client import fetch_trading_info


def _events_for_code(code: str, drop_pct: float, length: int) -> dict:
    bars = fetch_trading_info(code, length=length)
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    if len(close) < CFG.RECOVERY_MIN_BARS:
        return {"code": code, "error": f"data cuma {len(close)} bar"}

    threshold = 1.0 - drop_pct / 100.0
    n = len(close)
    records = {h: [] for h in CFG.RECOVERY_HORIZONS_DAYS}  # horizon -> [(pred, actual)]

    for i in range(1, n):
        ref = close[i - 1]
        if ref <= 0 or close[i] > ref * threshold:
            continue

        a = float(np.log(ref / close[i]))
        mu, sigma = estimate_gbm_params(close[: i + 1])
        if sigma <= 0:
            continue

        for h in CFG.RECOVERY_HORIZONS_DAYS:
            end = i + 1 + h
            if end > n:
                continue
            pred = first_passage_cdf(a, mu, sigma, h)
            actual = 1.0 if np.nanmax(high[i + 1 : end]) >= ref else 0.0
            records[h].append((pred, actual))

    return {"code": code, "records": records, "n_events": len(records[CFG.RECOVERY_HORIZONS_DAYS[0]])}


def _summarize(all_records: dict[int, list]) -> dict:
    out = {}
    for h, pairs in all_records.items():
        preds = np.array([p for p, _ in pairs])
        actuals = np.array([a for _, a in pairs])
        n = len(preds)
        if n == 0:
            out[h] = {"n": 0}
            continue
        brier = float(np.mean((preds - actuals) ** 2))
        actual_rate = float(np.mean(actuals))
        # Kalibrasi: bucket 0-0.2, 0.2-0.4, ..., 0.8-1.0
        buckets = []
        for lo in np.arange(0.0, 1.0, 0.2):
            mask = (preds >= lo) & (preds < lo + 0.2)
            if mask.sum() == 0:
                continue
            buckets.append({
                "bucket": f"{lo:.0%}-{min(lo+0.2,1.0):.0%}",
                "n": int(mask.sum()),
                "mean_pred": round(float(preds[mask].mean()), 3),
                "actual_rate": round(float(actuals[mask].mean()), 3),
            })
        out[h] = {
            "n": n,
            "mean_pred": round(float(preds.mean()), 3),
            "actual_rate": round(actual_rate, 3),
            "brier": round(brier, 4),
            "buckets": buckets,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward validation model recovery")
    parser.add_argument("codes", nargs="+", help="Kode saham IDX")
    parser.add_argument("--drop", type=float, default=CFG.RECOVERY_DROP_DEFAULT)
    parser.add_argument("--length", type=int, default=800, help="Hari kalender history")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    all_records: dict[int, list] = {h: [] for h in CFG.RECOVERY_HORIZONS_DAYS}
    n_total = 0
    per_code = []

    for code in args.codes:
        try:
            res = _events_for_code(code, args.drop, args.length)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {code}: {e}", file=sys.stderr)
            continue
        if "error" in res:
            print(f"[WARN] {code}: {res['error']}", file=sys.stderr)
            continue
        per_code.append({"code": res["code"], "n_events": res["n_events"]})
        n_total += res["n_events"]
        for h, pairs in res["records"].items():
            all_records[h].extend(pairs)

    summary = _summarize(all_records)

    if args.json:
        print(json.dumps({"codes": args.codes, "drop_pct": args.drop,
                          "total_events": n_total, "per_code": per_code,
                          "horizons": summary}, indent=2))
        return

    print()
    print("=" * 68)
    print(f"  WALK-FORWARD VALIDATION — RECOVERY MODEL (GBM FPT)")
    print(f"  Codes: {', '.join(args.codes)} | Drop threshold: {args.drop:.1f}% | Events: {n_total}")
    print("=" * 68)
    print(f"  {'Horizon':>8} {'N':>5} {'MeanPred':>9} {'Actual':>8} {'Brier':>7}   Bucket (mean_pred -> actual)")
    print("-" * 68)
    for h in CFG.RECOVERY_HORIZONS_DAYS:
        s = summary.get(h, {})
        if not s.get("n"):
            print(f"  {h:>8} {'-':>5}")
            continue
        bucket_txt = " | ".join(
            f"{b['mean_pred']:.2f}->{b['actual_rate']:.2f}" for b in s["buckets"]
        )
        print(f"  {h:>8} {s['n']:>5} {s['mean_pred']:>9.3f} {s['actual_rate']:>8.3f} {s['brier']:>7.4f}   {bucket_txt}")
    print("-" * 68)
    print("  Brier 0.25 = tebak konstan; < 0.25 = model punya skill. Kalibrasi ideal: mean_pred ~= actual.")
    print()


if __name__ == "__main__":
    main()
