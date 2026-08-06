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
import gorengan
import recovery
from data_source.gainers import get_cached_gainers, get_or_fetch_securities_list, scan_top_gainers
from data_source.gorengan_scanner import get_cached_gorengan, scan_gorengan
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
    regime: str | None = None


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
    gorengan_score: float | None = None
    gorengan_level: str | None = None


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
from data_source.gorengan_scanner import get_cached_gorengan, scan_gorengan
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
    regime: str | None = None


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
    gorengan_score: float | None = None
    gorengan_level: str | None = None


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


class GorenganFactors(BaseModel):
    historical_pump_dump_risk: float
    liquidity_risk: float
    market_cap_risk: float
    active_pump: float
    mid_momentum: float
    distribution_risk: float
    turnover_gaps: float


class GorenganScannerEntryResponse(BaseModel):
    code: str
    name: str
    close: float
    pct_change: float
    volume: float
    value: float
    frequency: float
    gorengan_score: float
    gorengan_level: str
    factors: GorenganFactors
    warnings: list[str]


class GorenganScannerResponse(BaseModel):
    scraped_at: str
    date: str
    count: int
    data: list[GorenganScannerEntryResponse]


class GorenganResponse(BaseModel):
    score: float
    level: str
    factors: GorenganFactors
    warnings: list[str]
    explanation: str


class AnalisisResponse(BaseModel):
    kode: str
    nama: str
    harga: float
    last_updated: str
    fetched_at: str = ""
    data_delayed: bool = True
    score: ScoreResponse
    trade_plan: TradePlanResponse | None
    raw_indicators: RawIndicatorsResponse | None
    capital_used: float
    gorengan: GorenganResponse | None = None
    buy_signal_validated: bool = False
    validation_note: str | None = None


class HistoryResponse(BaseModel):
    kode: str
    bars: list[HistoryBar]


class RecoveryProbability(BaseModel):
    horizon_days: int
    p_hit: float


class RecoveryEmpirical(BaseModel):
    horizon_days: int
    n_events: int
    n_recovered: int
    rate: float | None


class RecoveryGbm(BaseModel):
    mu_daily: float
    sigma_daily: float
    mu_annual: float
    sigma_annual: float
    p_hit_ever: float
    probabilities: list[RecoveryProbability]


class RecoveryExitPlan(BaseModel):
    target: float
    time_stop_days: int
    stop_loss: float
    note: str


class RecoveryVsLookback(BaseModel):
    days: int
    label: str
    ref_price: float
    distance_pct: float
    status: str  # "above" = udah di atas harga acuan, "below" = masih di bawah


class RecoveryAccumulation(BaseModel):
    valid: bool
    ready_to_fly: bool = False
    k_heavy: int = 0
    window_days: int = 0
    density_pct: float | None = None
    rvol: float | None = None
    max_rvol: float | None = None
    ara_date: str | None = None
    ara_ref_price: float | None = None
    sma20: float | None = None
    state_ma20: str | None = None  # "above" | "breakout" | "below"
    distance_pct: float | None = None
    note: str | None = None
    warning: str | None = None
    reason: str | None = None


class RecoveryResponse(BaseModel):
    kode: str
    nama: str
    valid: bool
    harga: float | None
    ref_price: float | None
    last_updated: str
    distance_pct: float | None
    drop_pct: float
    drop_source: str
    in_setup: bool
    gbm: RecoveryGbm | None
    empirical: list[RecoveryEmpirical]
    signal: str
    signal_reason: str
    exit_plan: RecoveryExitPlan | None
    vs_lookbacks: list[RecoveryVsLookback] = []
    accumulation: RecoveryAccumulation | None = None


class MarketStatusResponse(BaseModel):
    is_open: bool
    message: str
    current_time: str
    suggested_source: str


for _model in (ScoreResponse, TradePlanResponse, HistoryBar, GainerEntryResponse,
               GainersResponse, RawIndicatorsResponse, GorenganFactors, GorenganResponse,
               AnalisisResponse, HistoryResponse, MarketStatusResponse,
               RecoveryProbability, RecoveryEmpirical, RecoveryGbm,
               RecoveryExitPlan, RecoveryVsLookback, RecoveryAccumulation, RecoveryResponse,
               GorenganScannerEntryResponse, GorenganScannerResponse):
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


def analyze_stock(kode: str, capital: float, target_date: str | None = None,
                  shares: float | None = None, listing_board: str | None = None) -> dict:
    bars = fetch_trading_info(kode, length=config.HISTORY_LOOKBACK_DAYS, target_date=target_date)

    if len(bars) < config.MIN_TRADING_DAYS:
        raise InsufficientDataError(
            f"Data historis {kode} cuma {len(bars)} hari, minimal {config.MIN_TRADING_DAYS}"
        )

    ref_date = date.fromisoformat(target_date) if target_date else date.today()
    # Data historis (tanggal lampau) sudah final -> tidak delay; hanya hari ini/None
    # yang bisa kena delay saat jam bursa berlangsung.
    data_delayed = _is_data_delayed() if ref_date >= datetime.now(WIB).date() else False
    last_bar_date = date.fromisoformat(bars[-1].date)
    stale_days = (ref_date - last_bar_date).days
    stale_reason = None
    if stale_days > config.MAX_DATA_STALE_DAYS:
        stale_reason = (
            f"Data terakhir {kode} tanggal {bars[-1].date} "
            f"({stale_days} hari yang lalu) — saham mungkin suspended atau delisting. "
            "Sinyal tidak dihasilkan."
        )
    _invalid_stale = {
        "kode": kode, "nama": "", "harga": 0.0,
        "last_updated": bars[-1].date,
        "fetched_at": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(timespec="seconds"),
        "data_delayed": data_delayed,
        "score": {"valid": False, "swing_score": None, "components": None,
                  "recommendation": None, "confidence": None,
                  "risk_level": None, "regime": None},
        "trade_plan": None, "raw_indicators": None,
        "capital_used": capital, "gorengan": None,
        "buy_signal_validated": False, "validation_note": stale_reason,
    }
    if stale_reason:
        return _invalid_stale

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

    # Gorengan detection
    gor_result = gorengan.compute_gorengan(
        close=close, open_=open_, high=high, low=low, volume=volume,
        atr_arr=atr_val, adx_arr=adx_val["adx"],
        rvol_arr=rvol_val, shares=shares, listing_board=listing_board,
    )

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
    _CANDLE_LABELS = {
        "doji": "Doji", "dragonfly_doji": "Dragonfly Doji", "gravestone_doji": "Gravestone Doji",
        "long_legged_doji": "Long-Legged Doji", "hammer": "Hammer", "hanging_man": "Hanging Man",
        "inverted_hammer": "Inverted Hammer", "shooting_star": "Shooting Star",
        "marubozu": "Marubozu", "belt_hold_bullish": "Belt Hold Bullish",
        "belt_hold_bearish": "Belt Hold Bearish", "spinning_top": "Spinning Top",
        "bullish_engulfing": "Bullish Engulfing", "bearish_engulfing": "Bearish Engulfing",
        "bullish_harami": "Bullish Harami", "bearish_harami": "Bearish Harami",
        "harami_cross": "Harami Cross", "piercing": "Piercing", "dark_cloud_cover": "Dark Cloud Cover",
        "tweezer_top": "Tweezer Top", "tweezer_bottom": "Tweezer Bottom",
        "on_neck": "On-Neck", "in_neck": "In-Neck",
        "kicker_bullish": "Kicker Bullish", "kicker_bearish": "Kicker Bearish",
        "morning_star": "Morning Star", "evening_star": "Evening Star",
        "abandoned_baby_bullish": "Abandoned Baby Bullish", "abandoned_baby_bearish": "Abandoned Baby Bearish",
        "three_white_soldiers": "Three White Soldiers", "three_black_crows": "Three Black Crows",
        "three_inside_up": "Three Inside Up", "three_inside_down": "Three Inside Down",
        "three_outside_up": "Three Outside Up", "three_outside_down": "Three Outside Down",
        "rising_three_methods": "Rising Three Methods", "falling_three_methods": "Falling Three Methods",
    }
    detected_patterns = [label for key, label in _CANDLE_LABELS.items() if candles.get(key, np.array([False]))[-1]]

    lookback = min(3, len(close))
    pattern_candles = [
        {
            "open": float(open_[-lookback + i]),
            "high": float(high[-lookback + i]),
            "low": float(low[-lookback + i]),
            "close": float(close[-lookback + i]),
        }
        for i in range(lookback)
    ]

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
        "candlestick_patterns": detected_patterns,
        "pattern_candles": pattern_candles
    }

    return {
        "kode": kode,
        "harga": float(close[-1]),
        "last_updated": bars[-1].date,
        "fetched_at": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(timespec="seconds"),
        "data_delayed": data_delayed,
        "score": score_result,
        "trade_plan": trade_plan,
        "raw_indicators": raw_indicators,
        "capital_used": capital,
        "gorengan": gor_result,
        "buy_signal_validated": config.SWING_BUY_VALIDATED,
        "validation_note": (
            "BUY direkomendasikan hanya saat regime bull/sideways."
            " SELL bersifat advisory (long-only mode aktif)."
        ),
    }


# ---------------------------------------------------------------------------
# Market Status
# ---------------------------------------------------------------------------

WIB = ZoneInfo("Asia/Jakarta")


def _is_data_delayed() -> bool:
    """
    Data Yahoo dianggap masih bisa delay bila masih dalam jam bursa atau
    belum final (~1 jam setelah penutupan sesi II, jadi sampai 17:00 WIB).
    Akhir pekan & di luar jam itu data sudah final (tidak delay).
    """
    now = datetime.now(WIB)
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=17, minute=0, second=0, microsecond=0)
    return start <= now < end


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
def trigger_scrape(
    source: str | None = Query(None, pattern=r"^(yahoo|idx)$"),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    try:
        securities = get_or_fetch_securities_list()
        gainers = scan_top_gainers(securities, force_source=source, target_date=date)
        date_label = f" untuk tanggal {date}" if date else ""
        return {
            "status": "ok",
            "count": len(gainers),
            "message": f"Scrape berhasil{date_label}. {len(gainers)} gainers ditemukan.",
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

    securities = get_or_fetch_securities_list()
    sec_by_code = {s.code: s for s in securities}

    for entry in data:
        try:
            sec = sec_by_code.get(entry.code)
            result = analyze_stock(entry.code, config.DEFAULT_CAPITAL,
                                   shares=sec.shares if sec else None,
                                   listing_board=sec.listing_board if sec else None)
            if result["score"]["valid"]:
                entry.swing_score = result["score"]["swing_score"]
                entry.recommendation = result["score"]["recommendation"]
            if result.get("gorengan"):
                entry.gorengan_score = result["gorengan"]["score"]
                entry.gorengan_level = result["gorengan"]["level"]
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
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    kode = kode.strip().upper()

    securities = get_or_fetch_securities_list()
    sec = next((s for s in securities if s.code == kode), None)
    if sec is None:
        raise HTTPException(
            status_code=404,
            detail=f"Kode saham {kode} tidak ditemukan di daftar efek IDX.",
        )

    nama = sec.name

    try:
        result = analyze_stock(kode, capital, target_date=date,
                               shares=sec.shares, listing_board=sec.listing_board)
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
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    kode = kode.strip().upper()

    securities = get_or_fetch_securities_list()
    if kode not in {s.code for s in securities}:
        raise HTTPException(
            status_code=404,
            detail=f"Kode saham {kode} tidak ditemukan di daftar efek IDX.",
        )

    bars = fetch_trading_info(kode, length=length, target_date=date)

    if not bars:
        raise HTTPException(
            status_code=502,
            detail=f"Gagal ambil data historis {kode} dari Yahoo.",
        )

    return {
        "kode": kode,
        "bars": [_dailybar_to_historybar(b) for b in bars],
    }


@app.get("/recovery/{kode}", response_model=RecoveryResponse)
def get_recovery(
    kode: str,
    drop_pct: float | None = Query(None, gt=0, le=50),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    """
    Probabilitas harga kembali ke previous close (mean reversion).

    Model GBM first-passage time (CDF Inverse Gaussian) + base rate empiris
    dari history saham. drop_pct None = otomatis dari volatilitas saham.
    Hanya relevan saat harga di bawah previous close.
    """
    kode = kode.strip().upper()

    securities = get_or_fetch_securities_list()
    sec = next((s for s in securities if s.code == kode), None)
    if sec is None:
        raise HTTPException(
            status_code=404,
            detail=f"Kode saham {kode} tidak ditemukan di daftar efek IDX.",
        )

    try:
        bars = fetch_trading_info(kode, length=config.RECOVERY_HISTORY_LOOKBACK_DAYS, target_date=date)
    except (YahooClientError, IdxTradingError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gagal ambil data untuk {kode}: {e}",
        )

    return recovery.build_recovery_analysis(kode, sec.name, bars, drop_pct=drop_pct)


@app.post("/scrape/gorengan")
def trigger_scrape_gorengan(date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    """
    Trigger scan seluruh bursa untuk mendeteksi saham gorengan.
    Proses ini memakan waktu beberapa menit.
    """
    try:
        results = scan_gorengan(target_date=date)
        return {"status": "success", "count": len(results), "message": "Scrape gorengan selesai."}
    except Exception as e:
        logging.exception("Scrape gorengan gagal")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/gorengan", response_model=GorenganScannerResponse)
def get_gorengan(date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    """
    Mengambil data saham gorengan yang sudah di-scrape hari ini atau tanggal tertentu.
    """
    cached = get_cached_gorengan(for_date=date)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail="Data belum discrape hari ini. Silakan klik tombol 'Scrape Gorengan' terlebih dahulu.",
        )

    return {
        "scraped_at": cached["scraped_at"],
        "date": date or datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat(),
        "count": len(cached["data"]),
        "data": [
            {
                "code": e.code,
                "name": e.name,
                "close": e.close,
                "pct_change": e.pct_change,
                "volume": e.volume,
                "value": e.value,
                "frequency": e.frequency,
                "gorengan_score": e.gorengan_score,
                "gorengan_level": e.gorengan_level,
                "factors": e.factors,
                "warnings": e.warnings,
            }
            for e in cached["data"]
        ],
    }
