"""api.py — Fase 4: API Layer (FastAPI)."""

from typing import Any

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


class AnalisisResponse(BaseModel):
    kode: str
    nama: str
    harga: float
    last_updated: str
    score: ScoreResponse
    trade_plan: TradePlanResponse | None
    capital_used: float


class HistoryResponse(BaseModel):
    kode: str
    bars: list[HistoryBar]


for _model in (ScoreResponse, TradePlanResponse, HistoryBar, GainerEntryResponse,
               GainersResponse, AnalisisResponse, HistoryResponse):
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

    return {
        "kode": kode,
        "harga": float(close[-1]),
        "last_updated": bars[-1].date,
        "score": score_result,
        "trade_plan": trade_plan,
        "capital_used": capital,
    }


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


@app.post("/scrape")
def trigger_scrape():
    try:
        securities = get_or_fetch_securities_list()
        gainers = scan_top_gainers(securities)
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
            bars = fetch_trading_info(entry.code, length=config.HISTORY_LOOKBACK_DAYS)
            if len(bars) < config.MIN_TRADING_DAYS:
                continue

            close = np.array([b.close for b in bars])
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

            score_result = scoring.compute_score({
                "close": close, "rsi": rsi_val, "atr": atr_val,
                "adx": adx_val["adx"], "plus_di": adx_val["plus_di"],
                "minus_di": adx_val["minus_di"], "ema_fast": ema_val["ema_fast"],
                "ema_slow": ema_val["ema_slow"], "mfi": mfi_val, "rvol": rvol_val,
                "donchian_upper": donch["upper"], "donchian_lower": donch["lower"],
                "support": sr["support"], "resistance": sr["resistance"],
            })

            if score_result.get("valid"):
                entry.swing_score = score_result["swing_score"]
                entry.recommendation = score_result["recommendation"]

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
