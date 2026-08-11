"""
_validate_recovery.py — Walk-forward validation untuk model Recovery.

Dua mode:
  gbm  (lama): untuk tiap event "close turun X% di bawah previous close"
        dalam history per saham yang di-fetch live: estimasi mu/sigma GBM
        HANYA dari bar sebelum event (anti look-ahead), prediksi via
        first_passage_cdf, actual = max(high[i+1..i+h]) >= ref.
  dataset (default, baru): validasi model EMPIRIS GLOBAL (logistic drawdown,
        target prior high) atas universe_ohlcv.npz (963 saham IDX, lokal,
        tanpa rate limit). Prediksi memakai parameter yang SAMA dengan
        produksi (data/recovery_model_params.json) dan HANYA observasi
        test-split (30% terakhir per saham) — OOS murni, tidak double-dip.
        Metrik: AUC, Brier, base rate empiris & kalibrasi per bucket dd.

Output per horizon: n, mean prediksi, actual rate, Brier, AUC, dan
kalibrasi bucket. Brier ~0.25 = tebak konstan; model baik < 0.25.

Usage:
    python _validate_recovery.py --mode dataset            # 963 saham, lokal
    python _validate_recovery.py --mode dataset --npz data/universe_ohlcv.npz
    python _validate_recovery.py --mode gbm BBCA BMRI BBRI [--drop 5] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from sklearn.metrics import roc_auc_score

import config as CFG
from recovery import estimate_gbm_params, first_passage_cdf, recovery_model_probs
from data_source.yahoo_client import fetch_trading_info

from _calibrate_recovery_model import (
    DD_BUCKETS,
    HORIZONS as CAL_HORIZONS,
    TRAIN_FRAC,
    _collect_rows,
)


def _validate_model_dataset(npz_path: str) -> dict:
    """Validasi OOS model empiris global atas test-split dataset lokal.

    Observasi = hari drawdown point-in-time (target prior high). Split sama
    persis dengan kalibrasi (TRAIN_FRAC pertama = train, sisanya = test);
    validasi hanya memakai observasi TEST supaya OOS murni. Prediksi memakai
    parameter PRODUKSI (data/recovery_model_params.json), jadi hasilnya
    mencerminkan apa yang akan dikeluarkan API.
    """
    import recovery as REC

    params = REC._load_recovery_model_params()
    if params is None:
        return {"error": "recovery_model_params.json tidak ditemukan / tidak valid. "
                         "Jalankan _calibrate_recovery_model.py dulu."}

    d = np.load(npz_path)
    rows, lens = d["rows"], d["lens"]
    collected = _collect_rows(rows, lens, CFG.RECOVERY_PEAK_LOOKBACK_DAYS)

    out: dict = {"dataset": os.path.basename(npz_path),
                 "split": "temporal per saham: train 70% / test 30% (test saja dipakai)",
                 "n_codes": int(len(lens))}
    for h in CAL_HORIZONS:
        dd = collected[h]["dd"]
        y = collected[h]["y"]
        n = len(dd)
        n_train = int(n * TRAIN_FRAC)
        m_test = np.arange(n) >= n_train
        dd_t, y_t = dd[m_test], y[m_test]
        r = params["horizons"].get(str(h))
        if len(dd_t) == 0 or not r or not r.get("fitted"):
            out[str(h)] = {"n": int(len(dd_t)), "note": "tidak ada observasi/param"}
            continue
        preds = 1.0 / (1.0 + np.exp(-(r["a"] + r["b"] * dd_t)))
        auc = float(roc_auc_score(y_t, preds)) if len(np.unique(y_t)) > 1 else None
        brier = float(np.mean((preds - y_t) ** 2))
        buckets = []
        for lo, hi in DD_BUCKETS:
            m = (dd_t >= lo) & (dd_t < hi)
            if m.sum() < 30:
                continue
            buckets.append({
                "bucket": f"{lo:.2f}-{hi:.2f}",
                "n": int(m.sum()),
                "pred": round(float(preds[m].mean()), 3),
                "actual": round(float(y_t[m].mean()), 3),
            })
        out[str(h)] = {
            "n": int(len(dd_t)),
            "rec_rate": round(float(y_t.mean()), 4),
            "mean_dd": round(float(dd_t.mean()), 4),
            "auc": round(auc, 4) if auc is not None else None,
            "brier": round(brier, 5),
            "buckets": buckets,
        }
    return out


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
    parser.add_argument("codes", nargs="*", help="Kode saham IDX (mode gbm)")
    parser.add_argument("--mode", choices=("dataset", "gbm"), default="dataset",
                        help="dataset = validasi model empiris global atas universe lokal (default)")
    parser.add_argument("--npz", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "universe_ohlcv.npz"))
    parser.add_argument("--drop", type=float, default=CFG.RECOVERY_DROP_DEFAULT)
    parser.add_argument("--length", type=int, default=800, help="Hari kalender history")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.mode == "dataset":
        if not os.path.exists(args.npz):
            print(f"[ERROR] dataset tidak ada: {args.npz} — jalankan fetch dataset dulu.",
                  file=sys.stderr)
            sys.exit(1)
        res = _validate_model_dataset(args.npz)
        if "error" in res:
            print(f"[ERROR] {res['error']}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(res, indent=2))
            return
        print()
        print("=" * 88)
        print("  VALIDASI OOS — MODEL RECOVERY EMPIRIS GLOBAL (logistic drawdown)")
        print(f"  Dataset: {res['dataset']} | {res['n_codes']} saham | split: {res['split']}")
        print("=" * 88)
        print(f"  {'Horizon':>8} {'N':>9} {'Rec%':>7} {'MeanDD':>7} {'AUC':>7} "
              f"{'Brier':>8}   Base rate test per bucket dd (pred -> actual)")
        print("-" * 88)
        for h in CAL_HORIZONS:
            s = res.get(str(h), {})
            if not s.get("n"):
                print(f"  {h:>8} {s.get('n', 0):>9,}")
                continue
            bucket_txt = " | ".join(
                f"{b['bucket']}:{b['pred']:.2f}->{b['actual']:.2f}" for b in s["buckets"]
            )
            print(f"  {h:>8} {s['n']:>9,} {s['rec_rate']*100:>6.1f}% {s['mean_dd']:>7.3f} "
                  f"{str(s['auc']):>7} {s['brier']:>8.4f}   {bucket_txt}")
        print("-" * 88)
        print("  AUC 0.5 = acak; Brier 0.25 = tebak konstan. Prediksi = param produksi,")
        print("  observasi = test-split 30% (OOS murni). Kalibrasi ideal: pred ~= actual.")
        print()
        return

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
