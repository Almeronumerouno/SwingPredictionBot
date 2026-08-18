"""P8: regenerate cache scanner Ready-To-Fly dengan gate anti-repetisi AKTIF.

Konteks: keputusan user 16-08-2026 menyalakan RTF_MAX_STREAK_DAYS di produksi.
Cache tanggal terakhir (2026-08-14) dibuat SEBELUM gate dinyalakan -> regenerate
dari local dataset (universe_ohlcv.npz, bar sama dgn riset forensik) memakai
detect_accumulation(..., apply_streak_gate=True) + logika _fetch_and_check_one
yang sama dgn scanner produksi.

Catatan semantik: saham yang kena gate (streak>3) tidak hilang dari cache —
statusnya turun ready -> almost (gate kualitas lain masih lolos). Frontend
daftar utama (ready) jadi 8 dari 11.

Pemakaian: python _p83_rtf_regenerate_cache.py [YYYY-MM-DD]
"""
import json
import os
import sys
from dataclasses import asdict
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from data_source.readytofly_scanner import (  # noqa: E402
    _fetch_and_check_one,
    _get_cache_path,
)

NPZ_PATH = os.path.join("data", "universe_ohlcv.npz")


def make_bars(rows, dates, c: int, m: int) -> list:
    bars = []
    cl = rows[c, :m, 3]
    for i in range(m):
        r = rows[c, i]
        prev = float(cl[i - 1]) if i > 0 else float(r[3])
        bars.append(SimpleNamespace(
            date=dates[i], previous=prev,
            open_price=float(r[0]), high=float(r[1]), low=float(r[2]),
            close=float(r[3]), raw_close=float(r[3]),
            adj_close=float(r[4]) if len(r) > 4 else float(r[3]),
            volume=float(r[5]) if len(r) > 5 else 0.0,
            approx_value=0.0, frequency="1d",
            bid=0.0, offer=0.0, foreign_buy=0.0, foreign_sell=0.0,
        ))
    return bars


def sort_key(x):
    score = x.strength if x.status == "ready" else (x.density_pct or 0.0)
    return (0 if x.status == "ready" else 1, -(score or 0.0))


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "2026-08-14"
    path = _get_cache_path(target)
    if not os.path.exists(path):
        print(f"[ERR] cache tidak ada: {path}")
        sys.exit(1)

    old = json.load(open(path, encoding="utf-8"))
    old_entries = old["data"]
    name_map = {e["code"]: e["name"] for e in old_entries}
    old_ready = [e for e in old_entries if e["status"] == "ready"]
    print(f"cache lama  : {len(old_entries)} entries (ready {len(old_ready)}) scraped_at={old['scraped_at']}")

    d = np.load(NPZ_PATH, allow_pickle=True)
    rows, lens = d["rows"], d["lens"]
    raw_dates = d["dates"]
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    idx_of = {c: i for i, c in enumerate(codes)}
    tgt_dt = np.datetime64(target)

    new_entries, dropped, errs = [], [], []
    for e in old_entries:
        code = e["code"]
        ci = idx_of.get(code)
        if ci is None:
            dropped.append((code, "tidak ada di npz"))
            continue
        m = int(lens[ci])
        if m < config.RECOVERY_MIN_BARS or raw_dates[ci] is None:
            dropped.append((code, "bar kurang / dates None"))
            continue
        dsc = np.asarray(raw_dates[ci], dtype="datetime64[D]")
        # potong agar bar terakhir = target (sama dgn fetch target_date)
        k = int(np.searchsorted(dsc, tgt_dt))
        if k >= m or dsc[k] != tgt_dt:
            dropped.append((code, f"npz terakhir {dsc[m-1]} != target"))
            continue
        m2 = k + 1
        close = rows[ci, :m2, 3]
        if not np.isfinite(close).all() or (close <= 0).any():
            dropped.append((code, "data non-finite"))
            continue
        bars = make_bars(rows, [str(x)[:10] for x in dsc], ci, m2)
        name = name_map.get(code, code)
        entry = _fetch_and_check_one(code, name, {"StockCode": code, "StockName": name},
                                     target, bars=bars)
        if entry is None:
            dropped.append((code, "entry None (lolos gate?)"))
        else:
            new_entries.append(entry)

    new_entries.sort(key=sort_key)
    payload = {"scraped_at": old["scraped_at"], "data": [asdict(x) for x in new_entries]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    new_ready = [x for x in new_entries if x.status == "ready"]
    print(f"cache baru  : {len(new_entries)} entries (ready {len(new_ready)})")
    print(f"dropped     : {len(dropped)}")
    for code, why in dropped:
        print(f"  {code}: {why}")
    old_ready_codes = {e["code"] for e in old_ready}
    new_ready_codes = {x.code for x in new_ready}
    demoted = sorted(old_ready_codes - new_ready_codes)
    promoted = sorted(new_ready_codes - old_ready_codes)
    print(f"ready -> turun status : {demoted}")
    print(f"naik ke ready         : {promoted}")
    print("READY list baru:")
    for x in new_ready:
        print(f"  {x.code} {x.name[:40]:<42} streak={x.gates.get('anti_repetition')}")


if __name__ == "__main__":
    main()