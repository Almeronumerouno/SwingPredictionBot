"""
_build_recovery_dataset.py — Bangun dataset OHLCV universe IDX untuk
kalibrasi model recovery & scoring (sekali fetch, dipakai banyak eksperimen).

Output:
  data/universe_ohlcv.npz   — OHLCV mentah + adjusted + volume per saham
  data/universe_meta.json   — metadata (kode, panjang, tanggal, warnings)

Catatan (anti-silent-failure):
  - Kode yang gagal fetch / data pendek dicatat di warnings, TIDAK di-drop.
  - Setiap 50 kode selesai, checkpoint disimpan (tahan restart).
  - Kolom disimpan mentah dari Yahoo (auto_adjust=False): Close = raw,
    Adj Close = adjusted. Semua field OHLC lain = raw (Open/High/Low tidak
    di-adjust oleh yfinance; adj dihitung di script kalibrasi via faktor
    adj = AdjClose/Close bila diperlukan).

Usage:
    python _build_recovery_dataset.py            # universe penuh
    python _build_recovery_dataset.py --codes BBCA BMRI   # subset
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np

import config as CFG
from data_source.gainers import get_or_fetch_securities_list
from data_source.yahoo_client import DailyBar, fetch_trading_info

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
META_PATH = os.path.join(DATA_DIR, "universe_meta.json")
CHECKPOINT_PATH = os.path.join(DATA_DIR, "universe_ohlcv.partial.npz")

FETCH_LENGTH = 900          # hari kalender (~625 bar trading) — cukup untuk
                            # peak-lookback 252 + horizon 63 + warmup
MAX_BARS = 900              # padding maksimum per saham di array (lebar)

N_FIELDS = 6                # open, high, low, close(raw), adj_close, volume


def _bar_to_row(b: DailyBar) -> tuple[str, list[float]]:
    adj = b.adj_close if getattr(b, "adj_close", 0.0) > 0 else b.close
    return b.date, [b.open_price, b.high, b.low, b.close, adj, b.volume]


def build_dataset(codes: list[str], length: int, workers: int,
                  save_path: str, meta_path: str) -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)

    n = len(codes)
    dates: list[object] = []
    rows = np.zeros((n, MAX_BARS, N_FIELDS), dtype=np.float64)
    lens = np.zeros(n, dtype=np.int32)
    ok = np.zeros(n, dtype=bool)
    warnings = {"fetch_errors": [], "short_data": [], "empty_data": []}

    t0 = time.time()
    done = 0

    def _process(code: str) -> tuple[int, object, int]:
        bars = fetch_trading_info(code, length=length)
        return bars, len(bars), None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_process, c): i for i, c in enumerate(codes)}
        for fut in as_completed(futs):
            i = futs[fut]
            code = codes[i]
            try:
                bars, nb, _ = fut.result()
            except Exception as e:  # noqa: BLE001
                warnings["fetch_errors"].append({"code": code, "error": str(e)})
                done += 1
                continue
            if not bars:
                warnings["empty_data"].append(code)
                done += 1
                continue
            if len(bars) < 300:
                warnings["short_data"].append(code)
            nb = min(len(bars), MAX_BARS)
            dates.append(bars[-nb:])
            for j, b in enumerate(bars[-nb:]):
                _, vals = _bar_to_row(b)
                rows[i, j] = vals
            lens[i] = nb
            ok[i] = True
            done += 1
            if done % 50 == 0:
                # checkpoint
                _save(save_path=CHECKPOINT_PATH, rows=rows, lens=lens,
                      ok=ok, dates=dates, codes=codes)
                el = time.time() - t0
                print(f"[{datetime.now():%H:%M:%S}] {done}/{n} "
                      f"({el:.0f}s, {el / max(done, 1):.2f}s/kode)", flush=True)

    # Simpan final (rename checkpoint terakhir jadi file final)
    _save(save_path=save_path, rows=rows, lens=lens, ok=ok, dates=dates, codes=codes)
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)

    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": os.path.basename(save_path),
        "fetch_length_calendar_days": length,
        "n_codes": n,
        "n_ok": int(ok.sum()),
        "max_bars": MAX_BARS,
        "fields": ["open", "high", "low", "close_raw", "adj_close", "volume"],
        "warnings": warnings,
        "codes": codes,
        "note": "raw close = harga pasar; adj_close = disesuaikan dividen/split "
                "(dipakai model recovery supaya gap dividen tidak jadi drawdown palsu).",
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


def _save(save_path: str, rows, lens, ok, dates, codes) -> None:
    # dates: list of list of DailyBar → simpan string ISO (object array)
    dates_arr = np.empty(len(codes), dtype=object)
    for i, bars in enumerate(dates):
        dates_arr[i] = [b.date for b in bars]
    np.savez_compressed(
        save_path,
        codes=np.array(codes, dtype="S12"),
        rows=rows, lens=lens, ok=ok,
        dates=dates_arr,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codes", nargs="*", default=None,
                    help="batasi ke kode tertentu (default: seluruh universe)")
    ap.add_argument("--length", type=int, default=FETCH_LENGTH)
    ap.add_argument("--workers", type=int, default=CFG.SCAN_MAX_WORKERS)
    ap.add_argument("--out", default=NPZ_PATH)
    ap.add_argument("--meta", default=META_PATH)
    args = ap.parse_args()

    if args.codes:
        codes = [c.upper() for c in args.codes]
    else:
        secs = get_or_fetch_securities_list()
        codes = sorted({s.code for s in secs})
        print(f"Universe: {len(codes)} kode", flush=True)

    print(f"Fetch {len(codes)} kode (length={args.length} kalender, "
          f"workers={args.workers})…", flush=True)
    meta = build_dataset(codes, args.length, args.workers, args.out, args.meta)
    print(f"Selesai. OK={meta['n_ok']}/{meta['n_codes']} "
          f"fetch_errors={len(meta['warnings']['fetch_errors'])} "
          f"short={len(meta['warnings']['short_data'])}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
