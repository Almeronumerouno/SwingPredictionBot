"""
idx_client.py — Mengambil daftar saham terdaftar di BEI via curl_cffi / GetStockSummary.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from curl_cffi import requests

import config

log = logging.getLogger("data_source.idx_client")

class IdxClientError(Exception):
    """Raised saat request ke idx.co.id gagal."""


@dataclass
class Security:
    code: str
    name: str
    listing_date: str = ""
    shares: float = 0.0
    listing_board: str = ""


def fetch_all_securities() -> list[Security]:
    """
    Ambil seluruh daftar saham terdaftar di BEI via GetStockSummary (1 request = 960+ emiten lengkap).
    """
    from data_source.idx_trading import fetch_daily_stock_summary
    
    # Coba tanggal hari ini / kemarin / beberapa hari ke belakang
    now = datetime.now()
    securities = []
    
    for day_offset in range(5):
        dt_str = (now - timedelta(days=day_offset)).strftime("%Y%m%d")
        try:
            raw_data = fetch_daily_stock_summary(dt_str)
            if raw_data and len(raw_data) > 100:
                seen = set()
                for row in raw_data:
                    code = str(row.get("StockCode") or row.get("Code") or "").strip()
                    name = str(row.get("StockName") or row.get("Name") or "").strip()
                    shares = float(row.get("ListedShares") or row.get("Shares") or 0.0)
                    if code and code not in seen:
                        seen.add(code)
                        securities.append(Security(code=code, name=name, shares=shares))
                if len(securities) > 100:
                    log.info("Successfully fetched %d securities from IDX (%s)", len(securities), dt_str)
                    return securities
        except Exception as e:
            log.warning("Failed fetching securities for date=%s: %s", dt_str, e)
            
    # Fallback jika IDX offline: load dari universe local
    try:
        from data_source.local_dataset import load_local_universe
        uni = load_local_universe()
        for c in uni.get("codes", []):
            code_clean = c.decode() if isinstance(c, bytes) else str(c)
            securities.append(Security(code=code_clean, name=code_clean))
        if securities:
            return securities
    except Exception:
        pass
        
    raise IdxClientError("Gagal mengambil daftar saham dari IDX maupun fallback lokal.")
