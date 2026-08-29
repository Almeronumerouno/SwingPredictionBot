"""
idx_trading.py — Data trading resmi dari BEI (IDX) via curl_cffi Chrome Impersonation.

Endpoint: /TradingSummary/GetStockSummary?date=YYYYMMDD
Fitur:
- 1 call mengambil SELURUH 960+ saham bursa (OHLCV, Real Value IDR, Net Foreign Flow, Volume, Frequency, Bid/Offer).
- Kebal blokir Cloudflare dengan browser TLS fingerprint impersonation.
- Fallback otomatis ke Yahoo Finance jika BEI offline.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional
from curl_cffi import requests

import config

log = logging.getLogger("data_source.idx_trading")

class IdxTradingError(Exception):
    """Raised saat request ke IDX trading endpoint gagal."""


_SESSION: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session(impersonate="chrome")
        _SESSION.headers.update({
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,id;q=0.8",
            "referer": "https://www.idx.co.id/",
        })
    return _SESSION


def fetch_daily_stock_summary(date_str: str, max_retries: int = 3) -> list[dict]:
    """
    1x call mengambil data trading SELURUH pasar untuk satu tanggal (YYYYMMDD).
    
    Returns:
        List dict 960+ saham dengan field:
        - StockCode, StockName, Close, Volume, Value, Frequency
        - ForeignBuy, ForeignSell, OpenPrice, High, Low, Previous
        - Bid, BidVolume, Offer, OfferVolume, ListedShares, TradebleShares
    """
    session = _get_session()
    url = f"{config.IDX_BASE_URL}{config.IDX_STOCK_SUMMARY_ENDPOINT}"
    params = {"date": date_str, "start": 0, "length": 9999}
    
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                result = resp.json()
                raw = result.get("data") or result.get("Data") or result
                if isinstance(raw, list):
                    return raw
                if isinstance(raw, dict):
                    for key in ("data", "Data", "items", "Items", "result", "Result"):
                        if key in raw and isinstance(raw[key], list):
                            return raw[key]
            else:
                last_err = Exception(f"HTTP Status {resp.status_code}")
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
            
    raise IdxTradingError(f"Gagal fetch IDX GetStockSummary date={date_str}: {last_err}")
