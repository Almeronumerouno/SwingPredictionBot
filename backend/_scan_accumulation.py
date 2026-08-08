"""
_scan_accumulation.py — Scan seluruh universe IDX untuk pola akumulasi "siap terbang".

Untuk tiap saham: fetch bars -> recovery.detect_accumulation() ->
filter ready_to_fly == True. Keluar daftar terurut (k_heavy desc, volume desc).

Usage:
    python _scan_accumulation.py                # semua sekuritas (cache)
    python _scan_accumulation.py --limit 50     # hanya 50 pertama (debug cepat)
    python _scan_accumulation.py --codes SOLA ENZO BBCA
    python _scan_accumulation.py --min-value 1e9   # hanya saham likuid
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import config as CFG
import recovery
from data_source.gainers import get_or_fetch_securities_list
from data_source.yahoo_client import fetch_trading_info

LENGTH = 150  # bar kalender cukup utk ACCUM (butuh ~30) + biar cek stabil


def _one(code: str, name: str) -> dict | None:
    try:
        bars = fetch_trading_info(code, length=LENGTH)
    except Exception:
        return None
    if not bars:
        return None
    acc = recovery.detect_accumulation(bars)
    if not acc.get("valid") or not acc.get("ready_to_fly"):
        return None
    return {
        "code": code,
        "nama": name,
        "k_heavy": acc.get("k_heavy", 0),
        "window_days": acc.get("window_days", 0),
        "density_pct": acc.get("density_pct"),
        "rvol": acc.get("rvol"),
        "max_rvol": acc.get("max_rvol"),
        "ara_date": acc.get("ara_date"),
        "ara_ref_price": acc.get("ara_ref_price"),
        "state_ma20": acc.get("state_ma20"),
        "double_ara": acc.get("double_ara", False),
    }


def _diag(code: str, name: str) -> dict | None:
    """Klasifikasi funnel utk --diag: kenapa tiap saham TIDAK jadi sinyal."""
    try:
        bars = fetch_trading_info(code, length=LENGTH)
    except Exception:
        return {"code": code, "stage": "error"}
    if not bars:
        return {"code": code, "stage": "error"}
    acc = recovery.detect_accumulation(bars)
    if acc.get("valid") and acc.get("ready_to_fly"):
        return {"code": code, "stage": "READY", "acc": acc}

    gates = acc.get("gates") or {}
    if gates:
        # valid == False tapi gates ada => "Belum pola akumulasi post-ARA"
        if not gates.get("below"):
            return {"code": code, "stage": "recovered_above", "acc": acc}
        if gates.get("density") and gates.get("min_heavy") and not gates.get("above_ma"):
            return {"code": code, "stage": "pantau_no_ma", "acc": acc}
        if not gates.get("density") or not gates.get("min_heavy"):
            return {"code": code, "stage": "weak_density", "acc": acc}
        return {"code": code, "stage": "above_ma_fail", "acc": acc}

    reason = acc.get("reason", "")
    if "Hari ini hari ARA" in reason:
        return {"code": code, "stage": "today_ara", "acc": acc}
    if "Belum pernah ada ARA" in reason:
        return {"code": code, "stage": "no_ara", "acc": acc}
    return {"code": code, "stage": "data", "acc": acc}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan saham dengan sinyal akumulasi siap terbang")
    parser.add_argument("--limit", type=int, default=0, help="0 = semua")
    parser.add_argument("--min-value", type=float, default=0.0, help="min nilai transaksi harian (IDX)")
    parser.add_argument("--workers", type=int, default=CFG.SCAN_MAX_WORKERS)
    parser.add_argument("--diag", action="store_true",
                        help="mode diagnosis: hitung saham per gate funnel (bukan daftar sinyal)")
    args = parser.parse_args()

    securities = get_or_fetch_securities_list()
    if not securities:
        print("Daftar sekuritas kosong.", file=sys.stderr)
        return

    if args.min_value > 0:
        securities = [s for s in securities if getattr(s, "value", 0.0) >= args.min_value]
    if args.limit > 0:
        securities = securities[: args.limit]

    print(f"Scan {len(securities)} saham dengan {args.workers} worker…")

    if args.diag:
        _run_diag(securities, args.workers)
        return

    hits: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_one, s.code, s.name): s.code for s in securities}
        done = 0
        for fut in as_completed(futures):
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f"  …{done}/{len(futures)}", file=sys.stderr)
            r = fut.result()
            if r:
                hits.append(r)

    hits.sort(key=lambda r: (-r["k_heavy"], -(r["max_rvol"] or 0)))

    print()
    print("=" * 96)
    print("  SAHAM DENGAN SINYAL 'SIAP TERBANG' (akumulasi post-ARA + konfirmasi SMA20)")
    print("=" * 96)
    if not hits:
        print("  (tidak ada)")
        return
    print(f"  {'Kode':<12}{'Nama':<26}{'heavy':>6}{'sejak-ARA':>12}{'density':>9}{'RVOL max':>10}{'MA20':>10}{'ref':>9}{'2xARA':>7}")
    print("  " + "-" * 94)
    for h in hits:
        mx = f"{h['max_rvol']:.1f}x" if h["max_rvol"] is not None else "—"
        den = f"{h['density_pct']:.0f}%" if h["density_pct"] is not None else "—"
        hv = f"{h['k_heavy']}h" if h.get("k_heavy") else "—"
        ma = h.get("state_ma20") or "—"
        ref = f"{h['ara_ref_price']:,.0f}" if h["ara_ref_price"] is not None else "—"
        when = h["ara_date"] if h["ara_date"] else "—"
        dbl = "2x" if h.get("double_ara") else ""
        print(f"  {h['code']:<12}{h['nama'][:24]:<26}{hv:>6}{when:>12}{den:>9}{mx:>10}{ma:>10}{ref:>9}{dbl:>7}")
    print("=" * 96)


def _run_diag(securities, workers: int) -> None:
    from collections import Counter
    counter: Counter = Counter()
    err: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_diag, s.code, s.name): s.code for s in securities}
        done = 0
        for fut in as_completed(futures):
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f"  …{done}/{len(futures)}", file=sys.stderr)
            r = fut.result()
            if not r:
                continue
            st = r["stage"]
            counter[st] += 1
            if st not in err:
                err[st] = []
            if len(err[st]) < 8:
                err[st].append(r["code"])

    print()
    print("=" * 72)
    print("  FUNNEL DETEKSI AKUMULASI (berapa saham gugur di gerbang mana)")
    print("=" * 72)
    order = ["READY", "pantau_no_ma", "weak_density", "recovered_above",
             "today_ara", "no_ara", "data", "error"]
    total = sum(counter.values())
    for st in order:
        n = counter.get(st, 0)
        if n == 0:
            continue
        pct = n / total * 100 if total else 0.0
        bar = "#" * int(pct / 2)
        print(f"  {st:<18}{n:>6} ({pct:5.1f}%) {bar}")
        if st == "pantau_no_ma":
            # gerbang density/min-heavy sudah LULUS, tinggal konfirmasi SMA20
            print(f"      -> {n} saham SUDAH memenuhi pola volume, hanya belum lolos SMA20 "
                  f"(contoh: {', '.join(err.get(st, [])[:6])})")
    print(f"  {'total':<18}{total:>6}")
    print("=" * 72)


if __name__ == "__main__":
    main()