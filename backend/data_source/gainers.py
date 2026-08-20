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
import numpy as np
import indicators as ind
import scoring
import gorengan
import short_selling

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


def gainer_from_bars(code: str, bars: list[DailyBar]) -> Optional[GainerEntry]:
    """Buat GainerEntry dari bars yang SUDAH di-fetch (dipakai juga oleh scan_all
    supaya 1 fetch dipakai banyak analisis). Nama diisi belakangan dari daftar efek."""
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


def _fetch_one_for_scan_yahoo(code: str) -> Optional[GainerEntry]:
    """Fallback: ambil data 1 saham via Yahoo Finance (thread pool).
    Dipakai kalau IDX gagal.
    """
    try:
        bars = fetch_trading_info(code, length=config.FALLBACK_SCAN_LENGTH)
        return gainer_from_bars(code, bars)
    except YahooClientError as e:
        print(f"[WARN] Gagal fetch {code} (Yahoo fallback): {e}")
        return None
    except Exception as e:
        print(f"[WARN] Error tak terduga untuk {code} (Yahoo fallback): {e}")
        return None


def build_gainers_from_raw(raw: list[dict]) -> list[GainerEntry]:
    """Mapping snapshot IDX GetStockSummary -> Top N gainers (dipakai juga oleh
    scan_all untuk memakai snapshot yang sama)."""
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


def _scan_via_idx(target_date: Optional[str] = None) -> list[GainerEntry]:
    """Strategi utama: 1x call GetStockSummary -> sort by %change.
    Coba hari ini dulu, kalau kosong (libur / EOD blm ready) mundur max 3 hari ke belakang cari data terakhir yang ada.
    Jika target_date diberikan (format YYYY-MM-DD), gunakan tanggal tersebut sebagai titik awal.
    """
    if target_date:
        start = date.fromisoformat(target_date)
    else:
        start = date.today()
    raw = []
    for offset in range(config.IDX_FALLBACK_MAX_DAYS):
        d = start - timedelta(days=offset)
        date_str = d.strftime("%Y%m%d")
        raw = fetch_daily_stock_summary(date_str)
        if raw:
            break

    return build_gainers_from_raw(raw)


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


def scan_top_gainers(securities: Optional[list[Security]] = None,
                     force_source: Optional[str] = None,
                     target_date: Optional[str] = None) -> list[GainerEntry]:
    """
    Strategi utama: 1x call IDX GetStockSummary -> sort by pct_change.
    Kalau IDX gagal, fallback ke scan paralel Yahoo Finance (~900 request).

    Args:
        securities: daftar Security (di-fetch otomatis kalau None).
        force_source: "yahoo" -> paksa Yahoo, "idx" -> paksa IDX,
                      None -> auto (IDX dulu, fallback Yahoo).
        target_date: format YYYY-MM-DD, jika diberikan maka scrape untuk tanggal tersebut.
    """
    scraped_at = datetime.now(WIB)
    top_n: list[GainerEntry] = []

    if force_source == "yahoo":
        if securities is None:
            securities = get_or_fetch_securities_list()
        top_n = _scan_via_yahoo(securities)
        source = "Yahoo (paksa)"
    elif force_source == "idx":
        try:
            top_n = _scan_via_idx(target_date=target_date)
            source = "IDX (paksa)"
        except (IdxTradingError, Exception) as e:
            raise
    else:
        try:
            top_n = _scan_via_idx(target_date=target_date)
            source = "IDX"
        except (IdxTradingError, Exception) as e:
            print(f"[WARN] IDX GetStockSummary gagal, fallback ke Yahoo: {e}")
            if securities is None:
                securities = get_or_fetch_securities_list()
            top_n = _scan_via_yahoo(securities)
            source = "Yahoo (fallback)"

    print(f"[INFO] Top gainers diambil dari {source}: {len(top_n)} saham")
    enrich_gainers(top_n, target_date=target_date)
    _cache_gainers(top_n, scraped_at, cache_date=target_date)
    return top_n


def enrich_gainers(gainers: list[GainerEntry], target_date: Optional[str] = None, gorengan_dict: Optional[dict] = None) -> None:
    """Tambahkan swing_score dan gorengan_level ke GainerEntry dengan melakukan 1x fetch history."""
    securities = get_or_fetch_securities_list()
    sec_map = {s.code: s for s in securities}

    for g in gainers:
        try:
            sec = sec_map.get(g.code)
            shares = sec.shares if sec else None
            board = sec.listing_board if sec else None

            if gorengan_dict and g.code in gorengan_dict:
                gore = gorengan_dict[g.code]
                g.gorengan_score = gore.gorengan_score
                g.gorengan_level = gore.gorengan_level

            bars = fetch_trading_info(g.code, length=config.HISTORY_LOOKBACK_DAYS, target_date=target_date)
            if len(bars) >= config.MIN_TRADING_DAYS:
                close = np.array([b.close for b in bars])
                open_ = np.array([b.open_price for b in bars])
                high = np.array([b.high for b in bars])
                low = np.array([b.low for b in bars])
                volume = np.array([b.volume for b in bars])

                rsi_val = ind.rsi(close)
                atr_val = ind.atr(high, low, close)
                ema_val = ind.ema_trend(close)
                adx_val = ind.adx(high, low, close)
                mfi_val = ind.mfi(high, low, close, volume)
                rvol_val = ind.rvol(volume, config.RVOL_WINDOW)
                donch = ind.donchian_channel(high, low)
                sr = ind.support_resistance_levels(high, low)

                score_input: scoring.ScoreInput = {
                    "close": close, "rsi": rsi_val, "atr": atr_val,
                    "adx": adx_val["adx"], "plus_di": adx_val["plus_di"], "minus_di": adx_val["minus_di"],
                    "ema_fast": ema_val["ema_fast"], "ema_slow": ema_val["ema_slow"],
                    "mfi": mfi_val, "rvol": rvol_val,
                    "donchian_upper": donch["upper"], "donchian_lower": donch["lower"],
                    "support": sr["support"], "resistance": sr["resistance"],
                }
                score_result = scoring.compute_score(score_input)

                # Filter short selling BEI (sama seperti api.py)
                if (score_result["valid"] and score_result["recommendation"] == "SELL" 
                    and config.SHORT_SELLING_ENFORCE and not short_selling.is_short_selling_eligible(g.code)):
                    score_result["recommendation"] = "HOLD"

                if score_result["valid"]:
                    g.swing_score = score_result["swing_score"]
                    g.recommendation = score_result["recommendation"]

                if not gorengan_dict or g.code not in gorengan_dict:
                    gor_result = gorengan.compute_gorengan(
                        close=close, open_=open_, high=high, low=low, volume=volume,
                        atr_arr=atr_val, adx_arr=adx_val["adx"],
                        rvol_arr=rvol_val, shares=shares, listing_board=board,
                    )
                    if gor_result:
                        g.gorengan_score = gor_result["score"]
                        g.gorengan_level = gor_result["level"]

        except Exception as e:
            print(f"[WARN] Gagal hitung swing_score untuk {g.code}: {e}")

def _cache_gainers(entries: list[GainerEntry], scraped_at: datetime, cache_date: Optional[str] = None) -> None:
    _ensure_cache_dir()
    file_date = cache_date or scraped_at.date().isoformat()
    path = config.DAILY_GAINERS_CACHE_FILE.format(date=file_date)
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
