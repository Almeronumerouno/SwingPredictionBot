"""
Modul data trading dari IDX — pengganti Yahoo Finance untuk data harian.

Endpoint IDX yang dipakai:
- GetStockSummary?date=YYYYMMDD -> snapshot 1 hari SELURUH pasar (1 call doang!)
  Field: Value, Frequency, Bid, BidVolume, Offer, OfferVolume,
         ForeignBuy, ForeignSell, Volume, Close, Open, High, Low, ... (lengkap!)
- GetTradingInfoSS -> historis per saham (fallback/cek individual)

Dengan ini field yang tadinya "hilang" (Value, Frequency, Bid/Offer, Foreign Flow)
sekarang TERSEDIA. Yahoo Finance cuma dipakai sebagai fallback kalau IDX gagal.
"""

from __future__ import annotations

import json
import time
from typing import Optional

import cloudscraper

import config


class IdxTradingError(Exception):
    """Raised saat request ke IDX trading endpoint gagal."""


_SESSION: Optional[cloudscraper.CloudScraper] = None


def _get_session() -> cloudscraper.CloudScraper:
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    session = cloudscraper.create_scraper()
    session.get(
        config.IDX_BASE_URL + config.IDX_SESSION_INIT_PATH,
        headers={"User-Agent": config.IDX_REQUEST_USER_AGENT, "Referer": config.IDX_BASE_URL},
    )
    _SESSION = session
    return session


def _request_json(session: cloudscraper.CloudScraper, url: str, params: dict, retries: int = None) -> dict:
    retries = config.IDX_REQUEST_RETRIES if retries is None else retries
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=config.IDX_REQUEST_TIMEOUT)
            resp.raise_for_status()
            return json.loads(resp.text)
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise IdxTradingError(f"Gagal fetch {url} dengan params {params}: {last_err}")


def fetch_daily_stock_summary(date_str: str) -> list[dict]:
    """
    1x call ambil data trading SELURUH pasar untuk satu tanggal.

    Response format: DataTables wrapper -> {"draw":N, "recordsTotal":N,
    "recordsFiltered":N, "data": [...]}

    Args:
        date_str: format YYYYMMDD, misal "20260714"

    Returns:
        List dict, tiap item berisi field (konfirmasi via test:
        2026-07-14, sample AADI):
        - StockCode, StockName, Close, Volume, Value, Frequency
        - Bid, BidVolume, Offer, OfferVolume
        - ForeignBuy, ForeignSell
        - OpenPrice, High, Low, Previous
        - ListedShares, TradebleShares, NonRegularVolume, dll

        Catatan: data cuma tersedia untuk tanggal yang sudah market tutup (EOD snapshot).
        Hari ini (market masih buka) -> recordsTotal=0.
    """
    session = _get_session()
    url = config.IDX_BASE_URL + config.IDX_STOCK_SUMMARY_ENDPOINT
    result = _request_json(session, url, params={"date": date_str})
    raw = result.get("data") or result.get("Data") or result
    if isinstance(raw, dict):
        for key in ("data", "Data", "items", "Items", "result", "Result"):
            if key in raw and isinstance(raw[key], list):
                raw = raw[key]
                break
    if not isinstance(raw, list):
        raise IdxTradingError(
            f"Struktur response GetStockSummary tidak dikenali: {type(raw)}. "
            f"Sample: {str(raw)[:300]}"
        )
    return raw
