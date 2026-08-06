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
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan saham dengan sinyal akumulasi siap terbang")
    parser.add_argument("--limit", type=int, default=0, help="0 = semua")
    parser.add_argument("--min-value", type=float, default=0.0, help="min nilai transaksi harian (IDX)")
    parser.add_argument("--workers", type=int, default=CFG.SCAN_MAX_WORKERS)
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
    print(f"  {'Kode':<12}{'Nama':<26}{'heavy':>6}{'sejak-ARA':>12}{'density':>9}{'RVOL max':>10}{'MA20':>10}{'ref':>9}")
    print("  " + "-" * 94)
    for h in hits:
        mx = f"{h['max_rvol']:.1f}x" if h["max_rvol"] is not None else "—"
        den = f"{h['density_pct']:.0f}%" if h["density_pct"] is not None else "—"
        hv = f"{h['k_heavy']}h" if h.get("k_heavy") else "—"
        ma = h.get("state_ma20") or "—"
        ref = f"{h['ara_ref_price']:,.0f}" if h["ara_ref_price"] is not None else "—"
        when = h["ara_date"] if h["ara_date"] else "—"
        print(f"  {h['code']:<12}{h['nama'][:24]:<26}{hv:>6}{when:>12}{den:>9}{mx:>10}{ma:>10}{ref:>9}")
    print("=" * 96)


if __name__ == "__main__":
    main()