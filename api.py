"""api.py — Fase 4: API Layer (FastAPI)."""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import logging
import time

import numpy as np

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import indicators as ind
import risk
import scoring
from data_source.gainers import get_cached_gainers, get_or_fetch_securities_list, scan_top_gainers
from data_source.idx_trading import IdxTradingError
from data_source.yahoo_client import YahooClientError, fetch_trading_info

class InsufficientDataError(Exception):
    """Data historis kurang dari HISTORY_LOOKBACK_DAYS."""


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ScoreResponse(BaseModel):
    valid: bool
    swing_score: float | None
    components: dict | None
    recommendation: str | None
    confidence: str | None
    risk_level: str | None


class TradePlanResponse(BaseModel):
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    shares: int
    lots: int
    risk_reward_ratio: float | None
    note: str | None = None


class HistoryBar(BaseModel):
    date: str
    close: float
    open: float
    high: float
    low: float
    volume: float


class GainerEntryResponse(BaseModel):
    code: str
    name: str
    close: float
    pct_change: float
    volume: float
    value: float
    frequency: float
    foreign_buy: float
    foreign_sell: float
    swing_score: float | None = None
    recommendation: str | None = None


class GainersResponse(BaseModel):
    scraped_at: str
    date: str
    count: int
    data: list[GainerEntryResponse]


class RawIndicatorsResponse(BaseModel):
    rsi: float | None
    mfi: float | None
    atr: float | None
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    ema_fast: float | None
    ema_slow: float | None
    rvol: float | None
    support: float | None
    resistance: float | None
    fibonacci: dict[str, float] | None
    candlestick_patterns: list[str]


class AnalisisResponse(BaseModel):
    kode: str
    nama: str
    harga: float
    last_updated: str
    score: ScoreResponse
    trade_plan: TradePlanResponse | None
    raw_indicators: RawIndicatorsResponse | None
    capital_used: float


class HistoryResponse(BaseModel):
    kode: str
    bars: list[HistoryBar]


class MarketStatusResponse(BaseModel):
    is_open: bool
    message: str
    current_time: str
    suggested_source: str


for _model in (ScoreResponse, TradePlanResponse, HistoryBar, GainerEntryResponse,
               GainersResponse, RawIndicatorsResponse, AnalisisResponse, HistoryResponse,
               MarketStatusResponse):
    _model.model_rebuild()


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

def _dailybar_to_historybar(b: Any) -> dict:
    return {
        "date": b.date,
        "close": b.close,
        "open": b.open_price,
        "high": b.high,
        "low": b.low,
        "volume": b.volume,
    }


def analyze_stock(kode: str, capital: float) -> dict:
    bars = fetch_trading_info(kode, length=config.HISTORY_LOOKBACK_DAYS)

    if len(bars) < config.MIN_TRADING_DAYS:
        raise InsufficientDataError(
            f"Data historis {kode} cuma {len(bars)} hari, minimal {config.MIN_TRADING_DAYS}"
        )

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
    rvol_val = ind.rvol(volume)
    donch = ind.donchian_channel(high, low)
    sr = ind.support_resistance_levels(high, low)

    score_input: scoring.ScoreInput = {
        "close": close,
        "rsi": rsi_val,
        "atr": atr_val,
        "adx": adx_val["adx"],
        "plus_di": adx_val["plus_di"],
        "minus_di": adx_val["minus_di"],
        "ema_fast": ema_val["ema_fast"],
        "ema_slow": ema_val["ema_slow"],
        "mfi": mfi_val,
        "rvol": rvol_val,
        "donchian_upper": donch["upper"],
        "donchian_lower": donch["lower"],
        "support": sr["support"],
        "resistance": sr["resistance"],
    }

    score_result = scoring.compute_score(score_input)

    if score_result["valid"] and score_result["recommendation"] != "HOLD":
        trade_plan = risk.build_trade_plan(
            score_result,
            entry_price=float(close[-1]),
            atr=float(atr_val[-1]),
            capital=capital,
        )
    else:
        trade_plan = None

    def _safe_float(val) -> float | None:
        if isinstance(val, (np.ndarray, list)):
            val = val[-1]
        return float(val) if not np.isnan(val) else None
        
    sup_val = None
    if sr["support"]:
        sups = [s["level"] for s in sr["support"] if s["level"] <= close[-1]]
        sup_val = max(sups) if sups else None

    res_val = None
    if sr["resistance"]:
        reses = [r["level"] for r in sr["resistance"] if r["level"] > close[-1]]
        res_val = min(reses) if reses else None
        
    fib_val = None
    if sr["support"] and sr["resistance"]:
        max_h = max([r["level"] for r in sr["resistance"]])
        min_l = min([s["level"] for s in sr["support"]])
        if max_h > min_l:
            fib_val = ind.fibonacci_retracement(max_h, min_l)
            
    candles = ind.candlestick_patterns(open_, high, low, close)
    detected_patterns = []
    if candles["doji"][-1]: detected_patterns.append("Doji")
    if candles["hammer"][-1]: detected_patterns.append("Hammer")
    if candles["bullish_engulfing"][-1]: detected_patterns.append("Bullish Engulfing")
    if candles["bearish_engulfing"][-1]: detected_patterns.append("Bearish Engulfing")

    raw_indicators = {
        "rsi": _safe_float(rsi_val),
        "mfi": _safe_float(mfi_val),
        "atr": _safe_float(atr_val),
        "adx": _safe_float(adx_val["adx"]),
        "plus_di": _safe_float(adx_val["plus_di"]),
        "minus_di": _safe_float(adx_val["minus_di"]),
        "ema_fast": _safe_float(ema_val["ema_fast"]),
        "ema_slow": _safe_float(ema_val["ema_slow"]),
        "rvol": _safe_float(rvol_val),
        "support": sup_val,
        "resistance": res_val,
        "fibonacci": fib_val,
        "candlestick_patterns": detected_patterns
    }

    return {
        "kode": kode,
        "harga": float(close[-1]),
        "last_updated": bars[-1].date,
        "score": score_result,
        "trade_plan": trade_plan,
        "raw_indicators": raw_indicators,
        "capital_used": capital,
    }


# ---------------------------------------------------------------------------
# Market Status
# ---------------------------------------------------------------------------

WIB = ZoneInfo("Asia/Jakarta")


def _market_is_open() -> bool:
    now = datetime.now(WIB)
    if now.weekday() >= 5:
        return False
    open_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=0, second=0, microsecond=0)
    return open_time <= now < close_time


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Swing Bot IDX API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/market-status", response_model=MarketStatusResponse)
def get_market_status():
    now = datetime.now(WIB)
    is_open = _market_is_open()
    days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    day_name = days[now.weekday()]
    time_str = now.strftime("%H:%M")
    if is_open:
        message = f"Pasar sedang BUKA ({day_name}, {time_str} WIB)"
        suggested = "yahoo"
    else:
        if now.weekday() >= 5:
            message = f"Pasar TUTUP — hari {day_name}"
        elif now.hour < 9:
            message = f"Pasar TUTUP — belum dibuka ({time_str} WIB)"
        else:
            message = f"Pasar TUTUP — sudah tutup ({time_str} WIB)"
        suggested = "idx"
    return {
        "is_open": is_open,
        "message": message,
        "current_time": now.isoformat(),
        "suggested_source": suggested,
    }


@app.post("/scrape")
def trigger_scrape(source: str | None = Query(None, pattern=r"^(yahoo|idx)$")):
    try:
        securities = get_or_fetch_securities_list()
        gainers = scan_top_gainers(securities, force_source=source)
        return {
            "status": "ok",
            "count": len(gainers),
            "message": f"Scrape berhasil. {len(gainers)} gainers ditemukan.",
        }
    except Exception as e:
        logging.error("Scrape gagal: %s", e)
        raise HTTPException(status_code=500, detail=f"Scrape gagal: {e}")


@app.get("/gainers", response_model=GainersResponse)
def get_gainers(date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    try:
        cached = get_cached_gainers(for_date=date)
    except Exception as e:
        logging.error("Gagal baca cache gainers: %s", e)
        raise HTTPException(status_code=500, detail="Gagal membaca data gainers.")

    if cached is None:
        label = date or "hari ini"
        raise HTTPException(
            status_code=404,
            detail=f"Belum ada data gainers untuk tanggal {label}.",
        )

    data = cached["data"]

    for entry in data:
        try:
            result = analyze_stock(entry.code, config.DEFAULT_CAPITAL)
            if result["score"]["valid"]:
                entry.swing_score = result["score"]["swing_score"]
                entry.recommendation = result["score"]["recommendation"]
            time.sleep(0.3)
        except Exception:
            continue

    return {
        "scraped_at": cached["scraped_at"],
        "date": cached["scraped_at"][:10],
        "count": len(data),
        "data": data,
    }


@app.get("/analisis/{kode}", response_model=AnalisisResponse)
def get_analisis(
    kode: str,
    capital: float = Query(config.DEFAULT_CAPITAL, gt=0),
):
    kode = kode.strip().upper()

    securities = get_or_fetch_securities_list()
    if not any(s.code == kode for s in securities):
        raise HTTPException(
            status_code=404,
            detail=f"Kode saham {kode} tidak ditemukan di daftar efek IDX.",
        )

    nama = next((s.name for s in securities if s.code == kode), kode)

    try:
        result = analyze_stock(kode, capital)
    except InsufficientDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (YahooClientError, IdxTradingError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gagal ambil data untuk {kode}: {e}",
        )

    result["nama"] = nama
    return result


@app.get("/history/{kode}", response_model=HistoryResponse)
def get_history(
    kode: str,
    length: int = Query(config.HISTORY_LOOKBACK_DAYS, gt=0, le=config.MAX_HISTORY_QUERY_DAYS),
):
    kode = kode.strip().upper()

    securities = get_or_fetch_securities_list()
    if kode not in {s.code for s in securities}:
        raise HTTPException(
            status_code=404,
            detail=f"Kode saham {kode} tidak ditemukan di daftar efek IDX.",
        )

    bars = fetch_trading_info(kode, length=length)

    if not bars:
        raise HTTPException(
            status_code=502,
            detail=f"Gagal ambil data historis {kode} dari Yahoo.",
        )

    return {
        "kode": kode,
        "bars": [_dailybar_to_historybar(b) for b in bars],
    }
