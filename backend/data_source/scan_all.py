"""
scan_all.py — SATU putaran data → TIGA analisis sekaligus.

Prinsip (sesuai permintaan user: "scrape 1x lalu disaring, bukan 3x 900"):
  1. 1x  daftar efek (IDX, cache lokal)
  2. 1x  snapshot harian IDX (GetStockSummary) -> basis Top Gainers + filter volume
  3. Nx  fetch bars Yahoo per saham (sekali per saham, panjang maksimal)
     └── dari batch bars YANG SAMA dihitung: gorengan (compute_gorengan)
         & ready-to-fly (detect_accumulation); gainer fallback kalau IDX gagal.
  4. Tulis 3 cache (gainers_, gorengan_, readytofly_) format identik per-scanner.

Endpoint pemanggil: POST /scrape/all (api.py).
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import config
from data_source.gainers import (
    GainerEntry,
    _cache_gainers,
    build_gainers_from_raw,
    gainer_from_bars,
    get_or_fetch_securities_list,
)
from data_source.gorengan_scanner import GorenganEntry, _fetch_and_compute_one
from data_source.idx_trading import fetch_daily_stock_summary
from data_source.readytofly_scanner import ReadyToFlyEntry, _fetch_and_check_one
from data_source.yahoo_client import fetch_trading_info

WIB = ZoneInfo("Asia/Jakarta")


def _scan_one(
    code: str,
    name: str,
    daily_data: dict,
    shares: float | None,
    listing_board: str | None,
    target_date: Optional[str],
):
    """Satu saham: 1x fetch bars -> hitung gorengan & ready-to-fly sekaligus."""
    gore: Optional[GorenganEntry] = None
    rtf: Optional[ReadyToFlyEntry] = None
    fallback_gainer: Optional[GainerEntry] = None

    try:
        bars = fetch_trading_info(
            code,
            length=config.RECOVERY_HISTORY_LOOKBACK_DAYS,  # terpanjang (500) — yang lain tinggal dipotong
            target_date=target_date,
        )
        # Gorengan butuh MIN_TRADING_DAYS, RTF butuh RECOVERY_MIN_BARS — bisa beda,
        # jadi cek masing-masing sesuai fungsi asalnya (di dalam fungsi itu sendiri).
        gore = _fetch_and_compute_one(code, name, daily_data, shares, listing_board,
                                      target_date=target_date, bars=bars)
        rtf = _fetch_and_check_one(code, name, daily_data, target_date=target_date, bars=bars)
        fallback_gainer = gainer_from_bars(code, bars)
    except Exception:
        pass
    return gore, rtf, fallback_gainer


def run_scan_all(target_date: Optional[str] = None, force_source: Optional[str] = None,
                 max_codes: Optional[int] = None) -> dict:
    """
    Scan seluruh pasar dengan SATU putaran fetch.

    Args:
        target_date: format YYYY-MM-DD — data untuk tanggal itu (mundur sampai 3 hari kalau kosong).
        force_source: "yahoo" -> abaikan snapshot IDX (semua dari bars);
                      "idx" / None -> snapshot IDX dulu utk gainers & filter aktivitas.
        max_codes: batasi jumlah saham (untuk smoke test), None = semua.
    """
    scraped_at = datetime.now(WIB)

    # 1. Daftar efek (cache lokal)
    securities = get_or_fetch_securities_list()
    sec_map = {s.code: s for s in securities}

    # 2. Snapshot IDX (1 request) — utama utk gainers & menyaring saham aktif
    if target_date:
        start = date.fromisoformat(target_date)
    else:
        start = date.today()

    raw = []
    if force_source != "yahoo":
        for offset in range(config.IDX_FALLBACK_MAX_DAYS):
            d = start - timedelta(days=offset)
            date_str = d.strftime("%Y%m%d")
            try:
                raw = fetch_daily_stock_summary(date_str)
                if raw:
                    break
            except Exception:
                pass

    snapshot_ok = bool(raw)
    if not snapshot_ok:
        print("[WARN] Gagal snapshot IDX — Top Gainers akan dihitung dari bar terakhir Yahoo.")
        raw = [{"StockCode": s.code, "StockName": s.name} for s in securities]

    # Filter saham yang aktif (volume > 0 kalau field-nya ada)
    active_stocks = []
    for item in raw:
        code = str(item.get("StockCode", "")).strip()
        vol = float(item.get("Volume", 0) or 0)
        if code and (vol > 0 or "Volume" not in item):
            active_stocks.append(item)

    if max_codes is not None and len(active_stocks) > max_codes:
        print(f"[INFO] max_codes={max_codes}: sample {max_codes} dari {len(active_stocks)} saham aktif.")
        active_stocks = active_stocks[:max_codes]

    # 4. Scan paralel — SATU fetch per saham, tiga analisis
    gorengan_list: list[GorenganEntry] = []
    rtf_list: list[ReadyToFlyEntry] = []
    fallback_gainers: list[GainerEntry] = []

    with ThreadPoolExecutor(max_workers=config.SCAN_MAX_WORKERS) as executor:
        futures = {}
        for item in active_stocks:
            code = str(item.get("StockCode", "")).strip()
            name = str(item.get("StockName", "") or "")
            sec = sec_map.get(code)
            shares = sec.shares if sec else None
            board = sec.listing_board if sec else None
            futures[
                executor.submit(_scan_one, code, name, item, shares, board, target_date)
            ] = code

        for future in as_completed(futures):
            gore, rtf, fallback = future.result()
            if gore is not None:
                gorengan_list.append(gore)
            if rtf is not None:
                rtf_list.append(rtf)
            if fallback is not None:
                fallback_gainers.append(fallback)

    # 5. Finish & order (sama persis dengan scanner masing-masing)
    if snapshot_ok:
        gainers_list = build_gainers_from_raw(raw)
    else:
        fallback_gainers.sort(key=lambda e: e.pct_change, reverse=True)
        gainers_list = fallback_gainers[: config.TOP_GAINERS_COUNT]
    # Nama fallback yang kosong diisi dari daftar efek
    for g in gainers_list:
        if not g.name:
            sec = sec_map.get(g.code)
            g.name = sec.name if sec else ""

    gorengan_list.sort(key=lambda x: x.gorengan_score, reverse=True)
    rtf_list.sort(key=lambda x: (0 if x.status == "ready" else 1, -(x.density_pct or 0)))

    # 6. Cache — format sama persis dengan scanner per-kategori
    file_date = target_date or scraped_at.date().isoformat()
    _cache_gainers(gainers_list, scraped_at, cache_date=target_date)

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(os.path.join(config.CACHE_DIR, f"gorengan_{file_date}.json"), "w", encoding="utf-8") as f:
        json.dump({"scraped_at": scraped_at.isoformat(), "data": [asdict(e) for e in gorengan_list]},
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(config.CACHE_DIR, f"readytofly_{file_date}.json"), "w", encoding="utf-8") as f:
        json.dump({"scraped_at": scraped_at.isoformat(), "data": [asdict(e) for e in rtf_list]},
                  f, ensure_ascii=False, indent=2)

    count_ready = sum(1 for e in rtf_list if e.status == "ready")
    count_almost = sum(1 for e in rtf_list if e.status == "almost")

    return {
        "status": "ok",
        "message": (
            f"Scan selesai: {len(gainers_list)} gainers, {len(gorengan_list)} gorengan, "
            f"{count_ready} siap terbang, {count_almost} hampir siap."
        ),
        "stats": {
            "gainers": len(gainers_list),
            "gorengan": len(gorengan_list),
            "ready_to_fly": count_ready,
            "ready_almost": count_almost,
        },
    }


if __name__ == "__main__":
    import sys

    codes = int(sys.argv[1]) if len(sys.argv) > 1 else None
    res = run_scan_all(max_codes=codes)
    print(res["message"])