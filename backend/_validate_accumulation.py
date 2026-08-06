"""
_validate_accumulation.py — [v1 — DIKALAHKAN] Walk-forward validation hipotesis "akumulasi".

STATUS: Desain v1 ini (1 hari RVOL spike dalam 3 hari) TIDAK dikonfirmasi
(pengujian 24+ saham: B tidak lebih baik dari A untuk recovery/breakout).
Desain final yang TERBUKTI adalah "banyak hari RVOL tinggi (>=3 dari 5)
sambil harga masih di bawah close 5 hari lalu" -> lihat _validate_accum2.py.
Disimpan sebagai rekam jejak validasi & perbandingan desain.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

import config as CFG
import indicators as ind
from data_source.yahoo_client import fetch_trading_info

HORIZONS = [1, 3, 5, 21, 63]
RVOL_PERIOD = CFG.RVOL_WINDOW


def _ara_mult(price: float) -> float:
    if price < 200:
        return 1.35  # tier small cap
    if price < 5000:
        return 1.20
    return 1.15


def _color_of(close: np.ndarray, i: int) -> str:
    d = close[i] - close[i - 1]
    if d > 0:
        return "green"
    if d < 0:
        return "red"
    return "flat"


def _class_of(price: float) -> str:
    if price < 200:
        return "small<200"
    if price < 5000:
        return "mid<5k"
    return "big>=5k"


def _events_for_code(code: str, drop_pct: float, length: int, thresholds: list[float]) -> dict:
    bars = fetch_trading_info(code, length=length)
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)

    if len(close) < CFG.RECOVERY_MIN_BARS:
        return {"code": code, "error": f"data cuma {len(close)} bar"}

    rvol = ind.rvol(volume, RVOL_PERIOD)
    threshold = 1.0 - drop_pct / 100.0
    n = len(close)
    events: dict[tuple[str, str, str], list[dict]] = {}

    for i in range(RVOL_PERIOD + 3, n):
        ref = close[i - 1]
        if ref <= 0 or close[i] > ref * threshold:
            continue

        win = rvol[i - 2: i + 1]
        if np.all(np.isnan(win)):
            continue
        max_rv = float(np.nanmax(win))
        color = _color_of(close, i)
        price_cls = _class_of(ref)

        out: dict[int, tuple] = {}
        for h in HORIZONS:
            end = i + 1 + h
            if end > n:
                continue
            mx = float(np.nanmax(high[i + 1: end]))
            out[h] = (
                1.0 if mx >= ref else 0.0,
                1.0 if mx >= ref * 1.05 else 0.0,
                1.0 if mx >= ref * _ara_mult(ref) else 0.0,
            )

        for thr in thresholds:
            grp = "B-vol" if max_rv >= thr else "A-base"
            key = (f"{price_cls}|{thr}", grp, color)
            events.setdefault(key, []).append(out)

    return {"code": code, "events": events}


def _agg(rows: list[dict]) -> dict:
    out = {}
    for h in HORIZONS:
        recs, b5s, aras = [], [], []
        for r in rows:
            v = r.get(h)
            if v is None:
                continue
            recs.append(v[0]); b5s.append(v[1]); aras.append(v[2])
        if not recs:
            continue
        out[h] = {
            "n": len(recs),
            "rec": round(float(np.mean(recs)), 3),
            "b5": round(float(np.mean(b5s)), 3),
            "ara": round(float(np.mean(aras)), 3),
        }
    return out


def _summarize(events: dict[tuple[str, str, str], list[dict]]) -> dict:
    out = {}
    for (cls_thr, grp, color), rows in sorted(events.items()):
        cls, thr = cls_thr.split("|")
        key = f"{thr}|{cls}|{grp}|{color}"
        out[key] = _agg(rows)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Validasi hipotesis akumulasi (volume saat masih di bawah)")
    parser.add_argument("codes", nargs="+")
    parser.add_argument("--drop", type=float, default=CFG.RECOVERY_DROP_DEFAULT)
    parser.add_argument("--length", type=int, default=800)
    parser.add_argument("--thresholds", type=str, default="2.0,2.5,3.0")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    thresholds = [float(x) for x in args.thresholds.split(",")]
    all_events: dict[tuple[str, str, str], list[dict]] = {}
    total = 0

    for code in args.codes:
        try:
            res = _events_for_code(code, args.drop, args.length, thresholds)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {code}: {e}", file=sys.stderr)
            continue
        if "error" in res:
            print(f"[WARN] {code}: {res['error']}", file=sys.stderr)
            continue
        for k, rows in res["events"].items():
            all_events.setdefault(k, []).extend(rows)
            total += len(rows)

    summary = _summarize(all_events)

    if args.json:
        print(json.dumps({"codes": args.codes, "drop": args.drop,
                          "total_events": total, "summary": summary}, indent=2))
        return

    print()
    print("=" * 92)
    print("  VALIDASI AKUMULASI - 'masih di bawah previous close' + volume spike")
    print(f"  Codes: {', '.join(args.codes)} | drop {args.drop:.1f}% | RVOL threshold(s): {args.thresholds}")
    print("  rec = balik ke previous close | b5 = breakout +5% | ara = nembus batas ARA tier")
    print("=" * 92)

    for thr in thresholds:
        print(f"\n  === RVOL threshold {thr} ===")
        hdr = f"  {'kelas':<12}{'grup':<7}{'warna':<7}{'n':>5} | " + " | ".join(
            f"h{h:<5}" for h in HORIZONS
        ) + "   <- 'rec b5 ara' per horizon"
        print(hdr)
        print("  " + "-" * 88)
        for (cls_thr, grp, color), _ in sorted(all_events.items()):
            cls, thr_k = cls_thr.split("|")
            if float(thr_k) != thr:
                continue
            key = f"{thr}|{cls}|{grp}|{color}"
            s = summary.get(key, {})
            if not s:
                continue
            cells = []
            for h in HORIZONS:
                v = s.get(h)
                cells.append(f"{v['rec']:.2f} {v['b5']:.2f} {v['ara']:.2f}" if v else "  -    -    -")
            print(f"  {cls:<12}{grp:<7}{color:<7}{s.get(HORIZONS[0],{}).get('n',0):>5} | " + " | ".join(cells))

        base_n = 0
        vol_n = 0
        for (cls_thr, grp, color), rows in all_events.items():
            cls, thr_k = cls_thr.split("|")
            if float(thr_k) != thr:
                continue
            if grp == "A-base":
                base_n += len(rows)
            else:
                vol_n += len(rows)
        print(f"\n  Total event: {base_n} tanpa volume (A) vs {vol_n} dengan volume (B)")
    print()


if __name__ == "__main__":
    main()
