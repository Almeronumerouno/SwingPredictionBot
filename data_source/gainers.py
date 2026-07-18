"""
Modul untuk menentukan Top N Gainers harian.

STRATEGI BARU (via IDX):
1. 1x call `fetch_daily_stock_summary(today)` -> data SELURUH pasar dalam 1 request
   Field: Code, Name, Close, Previous (-> pct_change), Volume, Value, Frequency,
          Bid, BidVolume, Offer, OfferVolume, ForeignBuy, ForeignSell — LENGKAP!
2. Sort by pct_change -> ambil Top 15
3. Kalau IDX gagal, fallback ke Yahoo Finance (scan paralel ~900 saham)

Dampak:
- Jauh lebih CEPAT (1 request vs ~900 request)
- Field Value, Frequency, Foreign Flow sekarang TERSEDIA (dulu "hilang")
- Tidak perlu lagi depend pada yfinance untuk daily gainers

Alur yang disarankan:
1. Jalankan `scan_top_gainers()` sekali sehari (idealnya setelah market
   close, ~15:15 WIB) -> hasilnya di-cache ke file JSON per tanggal.
2. Command /gainers dan /analisis di bot MEMBACA dari cache ini, bukan
   scan ulang tiap kali ada yang chat (biar responsif & tidak membebani IDX).
"""

from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import config
from data_source.idx_client import Security, fetch_all_securities
from data_source.idx_trading import IdxTradingError, fetch_daily_stock_summary
from data_source.yahoo_client import DailyBar, YahooClientError, fetch_trading_info

WIB = ZoneInfo("Asia/Jakarta")


@dataclass
class GainerEntry:
    code: str
    name: str
    close: float
    pct_change: float
    volume: float
    value: float = 0.0       # nilai transaksi Rupiah asli (dari IDX), 0 kalau fallback Yahoo
    frequency: float = 0.0   # jumlah transaksi (dari IDX), 0 kalau fallback Yahoo
    foreign_buy: float = 0.0
    foreign_sell: float = 0.0
    swing_score: float | None = None
    recommendation: str | None = None


def _ensure_cache_dir() -> None:
    os.makedirs(config.CACHE_DIR, exist_ok=True)


def get_or_fetch_securities_list(force_refresh: bool = False) -> list[Security]:
    """Ambil daftar seluruh saham terdaftar, pakai cache lokal supaya tidak
    perlu hit endpoint pagination tiap kali (daftar emiten jarang berubah)."""
    _ensure_cache_dir()
    path = config.SECURITIES_LIST_CACHE_FILE

    if not force_refresh and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Security(**row) for row in raw]

    securities = fetch_all_securities()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in securities], f, ensure_ascii=False, indent=2)

    return securities


def _fetch_one_for_scan_yahoo(code: str) -> Optional[GainerEntry]:
    """Fallback: ambil data 1 saham via Yahoo Finance (thread pool).
    Dipakai kalau IDX gagal.
    """
    try:
        bars = fetch_trading_info(code, length=config.FALLBACK_SCAN_LENGTH)
        if len(bars) < 2:
            return None

        latest: DailyBar = bars[-1]

        if not math.isfinite(latest.volume) or latest.volume <= 0:
            return None
        if not math.isfinite(latest.pct_change):
            return None

        return GainerEntry(
            code=code,
            name="",  # diisi belakangan dari securities list
            close=latest.close,
            pct_change=latest.pct_change,
            volume=latest.volume,
        )
    except YahooClientError as e:
        print(f"[WARN] Gagal fetch {code} (Yahoo fallback): {e}")
        return None
    except Exception as e:
        print(f"[WARN] Error tak terduga untuk {code} (Yahoo fallback): {e}")
        return None


def _scan_via_idx() -> list[GainerEntry]:
    """Strategi utama: 1x call GetStockSummary -> sort by %change.
    Coba hari ini dulu, kalau kosong (libur / EOD blm ready) mundur max 3 hari ke belakang cari data terakhir yang ada.
    """
    today = date.today()
    raw = []
    for offset in range(config.IDX_FALLBACK_MAX_DAYS):
        d = today - timedelta(days=offset)
        date_str = d.strftime("%Y%m%d")
        raw = fetch_daily_stock_summary(date_str)
        if raw:
            break

    results: list[GainerEntry] = []
    for item in raw:
        code = str(item.get("StockCode", "")).strip()
        close = float(item.get("Close", 0) or 0)
        previous = float(item.get("Previous", 0) or 0)
        pct = ((close - previous) / previous * 100.0) if previous else 0.0
        volume = float(item.get("Volume", 0) or 0)

        if not code or not math.isfinite(close) or volume <= 0:
            continue

        results.append(GainerEntry(
            code=code,
            name=str(item.get("StockName", "") or ""),
            close=close,
            pct_change=pct,
            volume=volume,
            value=float(item.get("Value", 0) or 0),
            frequency=float(item.get("Frequency", 0) or 0),
            foreign_buy=float(item.get("ForeignBuy", 0) or 0),
            foreign_sell=float(item.get("ForeignSell", 0) or 0),
        ))

    results.sort(key=lambda e: e.pct_change, reverse=True)
    return results[: config.TOP_GAINERS_COUNT]


def _scan_via_yahoo(securities: list[Security]) -> list[GainerEntry]:
    """Fallback: scan paralel ~900 saham via Yahoo Finance."""
    name_by_code = {s.code: s.name for s in securities}
    results: list[GainerEntry] = []

    with ThreadPoolExecutor(max_workers=config.SCAN_MAX_WORKERS) as executor:
        futures = {executor.submit(_fetch_one_for_scan_yahoo, s.code): s.code for s in securities}
        for future in as_completed(futures):
            entry = future.result()
            if entry is not None:
                entry.name = name_by_code.get(entry.code, "")
                results.append(entry)

    results.sort(key=lambda e: e.pct_change, reverse=True)
    return results[: config.TOP_GAINERS_COUNT]


def scan_top_gainers(securities: Optional[list[Security]] = None) -> list[GainerEntry]:
    """
    Strategi utama: 1x call IDX GetStockSummary -> sort by pct_change.
    Kalau IDX gagal, fallback ke scan paralel Yahoo Finance (~900 request).
    """
    scraped_at = datetime.now(WIB)
    top_n: list[GainerEntry] = []

    try:
        top_n = _scan_via_idx()
        source = "IDX"
    except (IdxTradingError, Exception) as e:
        print(f"[WARN] IDX GetStockSummary gagal, fallback ke Yahoo: {e}")
        if securities is None:
            securities = get_or_fetch_securities_list()
        top_n = _scan_via_yahoo(securities)
        source = "Yahoo (fallback)"

    print(f"[INFO] Top gainers diambil dari {source}: {len(top_n)} saham")
    _cache_gainers(top_n, scraped_at)
    return top_n


def _cache_gainers(entries: list[GainerEntry], scraped_at: datetime) -> None:
    _ensure_cache_dir()
    path = config.DAILY_GAINERS_CACHE_FILE.format(date=scraped_at.date().isoformat())
    payload = {
        "scraped_at": scraped_at.isoformat(),
        "data": [asdict(e) for e in entries],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _migrate_row(row: dict) -> dict:
    """Backward compat: cache lama pake approx_value -> value."""
    row = dict(row)
    if "approx_value" in row and "value" not in row:
        row["value"] = row.pop("approx_value")
    return row


def get_cached_gainers(for_date: Optional[str] = None) -> Optional[dict]:
    """
    Baca hasil scan gainers dari cache (dipakai oleh bot, bukan scan ulang).
    Return dict: {"scraped_at": str, "data": list[GainerEntry]} atau None kalau belum ada cache.
    """
    for_date = for_date or datetime.now(WIB).date().isoformat()
    path = config.DAILY_GAINERS_CACHE_FILE.format(date=for_date)

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return {
        "scraped_at": raw["scraped_at"],
        "data": [GainerEntry(**_migrate_row(row)) for row in raw["data"]],
    }


if __name__ == "__main__":
    print("Scanning top gainers via IDX GetStockSummary (1 request doang)...")
    gainers = scan_top_gainers()

    cached = get_cached_gainers()
    print(f"\nData discrape pada: {cached['scraped_at']}")
    print(f"Top {len(gainers)} Gainers:")
    for i, g in enumerate(gainers, start=1):
        print(f"{i}. {g.code} ({g.name}) - {g.pct_change:.2f}% - Close {g.close}")
