"""
Modul untuk melakukan scanning saham gorengan ke seluruh bursa.
"""
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
import numpy as np

import config
import indicators as ind
from gorengan import compute_gorengan
from data_source.idx_client import Security, fetch_all_securities
from data_source.idx_trading import IdxTradingError, fetch_daily_stock_summary
from data_source.yahoo_client import YahooClientError, fetch_trading_info

WIB = ZoneInfo("Asia/Jakarta")

@dataclass
class GorenganEntry:
    code: str
    name: str
    close: float
    pct_change: float
    volume: float
    value: float
    frequency: float
    gorengan_score: float
    gorengan_level: str
    factors: dict
    warnings: list[str]

def _ensure_cache_dir() -> None:
    os.makedirs(config.CACHE_DIR, exist_ok=True)

def _get_gorengan_cache_path(date_str: str) -> str:
    return os.path.join(config.CACHE_DIR, f"gorengan_{date_str}.json")

def _fetch_and_compute_one(code: str, name: str, daily_data: dict, shares: float, listing_board: str, target_date: Optional[str]) -> Optional[GorenganEntry]:
    try:
        bars = fetch_trading_info(code, length=config.HISTORY_LOOKBACK_DAYS, target_date=target_date)
        if len(bars) < config.MIN_TRADING_DAYS:
            return None
            
        close = np.array([b.close for b in bars])
        open_ = np.array([b.open_price for b in bars])
        high = np.array([b.high for b in bars])
        low = np.array([b.low for b in bars])
        volume = np.array([b.volume for b in bars])
        
        atr_val = ind.atr(high, low, close)
        adx_val = ind.adx(high, low, close)
        rvol_val = ind.rvol(volume, config.RVOL_WINDOW)
        
        gor_result = compute_gorengan(
            close=close, open_=open_, high=high, low=low, volume=volume,
            atr_arr=atr_val, adx_arr=adx_val["adx"], rvol_arr=rvol_val,
            shares=shares, listing_board=listing_board
        )
        
        # Only include if level is EXTREME or HIGH
        if gor_result["level"] not in ("EXTREME", "HIGH"):
            return None
            
        prev = float(daily_data.get("Previous", 0) or 0)
        c = float(daily_data.get("Close", close[-1]) or close[-1])
        pct = ((c - prev) / prev * 100.0) if prev else 0.0
            
        return GorenganEntry(
            code=code,
            name=name,
            close=c,
            pct_change=pct,
            volume=float(daily_data.get("Volume", 0) or 0),
            value=float(daily_data.get("Value", 0) or 0),
            frequency=float(daily_data.get("Frequency", 0) or 0),
            gorengan_score=gor_result["score"],
            gorengan_level=gor_result["level"],
            factors=gor_result["factors"],
            warnings=gor_result["warnings"]
        )
    except Exception as e:
        return None

def scan_gorengan(target_date: Optional[str] = None) -> list[GorenganEntry]:
    """
    Melakukan scan seluruh saham untuk mencari saham dengan risiko gorengan tinggi.
    """
    scraped_at = datetime.now(WIB)
    
    # 1. Ambil daftar security
    securities = fetch_all_securities()
    sec_map = {s.code: s for s in securities}
    
    # 2. Ambil snapshot IDX harian untuk mempersempit pencarian
    if target_date:
        start = date.fromisoformat(target_date)
    else:
        start = date.today()
        
    raw = []
    for offset in range(config.IDX_FALLBACK_MAX_DAYS):
        d = start - timedelta(days=offset)
        date_str = d.strftime("%Y%m%d")
        try:
            raw = fetch_daily_stock_summary(date_str)
            if raw:
                break
        except Exception:
            pass
            
    if not raw:
        print("[WARN] Gagal mendapatkan snapshot harian, akan mencoba full scan.")
        raw = [{"StockCode": s.code, "StockName": s.name} for s in securities]

    # Filter stocks with active volume
    active_stocks = []
    for item in raw:
        code = str(item.get("StockCode", "")).strip()
        vol = float(item.get("Volume", 0) or 0)
        if code and (vol > 0 or "Volume" not in item):
            active_stocks.append(item)
            
    results: list[GorenganEntry] = []
    
    # 3. Scan paralel ke Yahoo
    with ThreadPoolExecutor(max_workers=config.SCAN_MAX_WORKERS) as executor:
        futures = {}
        for item in active_stocks:
            code = str(item.get("StockCode", "")).strip()
            name = str(item.get("StockName", "") or "")
            sec = sec_map.get(code)
            shares = sec.shares if sec else None
            board = sec.listing_board if sec else None
            
            futures[executor.submit(_fetch_and_compute_one, code, name, item, shares, board, target_date)] = code
            
        for future in as_completed(futures):
            entry = future.result()
            if entry is not None:
                results.append(entry)
                
    results.sort(key=lambda x: x.gorengan_score, reverse=True)
    
    # 4. Cache
    _ensure_cache_dir()
    file_date = target_date or scraped_at.date().isoformat()
    path = _get_gorengan_cache_path(file_date)
    payload = {
        "scraped_at": scraped_at.isoformat(),
        "data": [asdict(e) for e in results]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        
    return results

def get_cached_gorengan(for_date: Optional[str] = None) -> Optional[dict]:
    for_date = for_date or datetime.now(WIB).date().isoformat()
    path = _get_gorengan_cache_path(for_date)

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return {
        "scraped_at": raw["scraped_at"],
        "data": [GorenganEntry(**row) for row in raw["data"]],
    }
