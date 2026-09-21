"""Test suite for SwingPredictionBot FastAPI backend (backend/api.py).

Covers all 7 core endpoints, schema serialization, boundary date validation,
and error handling paths with deterministic offline mocks.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from api import InsufficientDataError, app
from data_source.idx_client import Security
from data_source.idx_trading import IdxTradingError
from data_source.yahoo_client import DailyBar, YahooClientError

client = TestClient(app)

# Standard mock securities
MOCK_SECURITIES = [
    Security(code="BBCA", name="Bank Central Asia Tbk", listing_board="UTAMA", shares=123275050000.0),
    Security(code="BBRI", name="Bank Rakyat Indonesia Tbk", listing_board="UTAMA", shares=151559000000.0),
    Security(code="ASII", name="Astra International Tbk", listing_board="UTAMA", shares=40483553140.0),
]


def make_mock_bar(date_str: str = "2026-03-20", close: float = 1000.0, volume: float = 100000.0) -> DailyBar:
    return DailyBar(
        date=date_str,
        previous=close * 0.98,
        open_price=close * 0.99,
        high=close * 1.02,
        low=close * 0.98,
        close=close,
        volume=volume,
        approx_value=close * volume,
        frequency=500,
    )


# ---------------------------------------------------------------------------
# 1. Market Status Tests
# ---------------------------------------------------------------------------

def test_market_status():
    response = client.get("/market-status")
    assert response.status_code == 200
    data = response.json()
    assert "is_open" in data
    assert isinstance(data["is_open"], bool)
    assert "message" in data
    assert "current_time" in data
    assert "suggested_source" in data
    assert data["suggested_source"] in ("yahoo", "idx")


# ---------------------------------------------------------------------------
# 2. Gainers Endpoint Tests
# ---------------------------------------------------------------------------

def test_gainers_success(monkeypatch):
    mock_cached = {
        "scraped_at": "2026-03-20T16:00:00+07:00",
        "data": [
            {
                "code": "BBCA",
                "name": "Bank Central Asia Tbk",
                "close": 9500.0,
                "pct_change": 2.5,
                "volume": 1000000.0,
                "value": 9500000000.0,
                "frequency": 1500,
                "foreign_buy": 500000.0,
                "foreign_sell": 300000.0,
                "swing_score": 80.0,
                "recommendation": "BUY",
                "gorengan_score": 10.0,
                "gorengan_level": "LOW",
            }
        ],
    }
    monkeypatch.setattr("api.get_cached_gainers", lambda for_date=None: mock_cached)

    response = client.get("/gainers")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["data"][0]["code"] == "BBCA"
    assert data["date"] == "2026-03-20"


def test_gainers_not_found(monkeypatch):
    monkeypatch.setattr("api.get_cached_gainers", lambda for_date=None: None)

    response = client.get("/gainers")
    assert response.status_code == 404
    assert "Belum ada data gainers" in response.json()["detail"]


def test_gainers_corrupted_cache(monkeypatch):
    def _raise_error(for_date=None):
        raise ValueError("Corrupted JSON cache")

    monkeypatch.setattr("api.get_cached_gainers", _raise_error)

    response = client.get("/gainers")
    assert response.status_code == 404


def test_gainers_with_valid_date(monkeypatch):
    mock_cached = {
        "scraped_at": "2026-01-15T16:00:00+07:00",
        "data": [],
    }
    monkeypatch.setattr("api.get_cached_gainers", lambda for_date=None: mock_cached)

    response = client.get("/gainers", params={"date": "2026-01-15"})
    assert response.status_code == 404  # Empty data array triggers 404 cleanly


# ---------------------------------------------------------------------------
# 3. Analisis Endpoint Tests (including pattern_candles verification)
# ---------------------------------------------------------------------------

def test_analisis_valid_ticker(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    mock_analysis = {
        "kode": "BBCA",
        "nama": "Bank Central Asia Tbk",
        "harga": 9500.0,
        "last_updated": "2026-03-20",
        "fetched_at": "2026-03-20T16:00:00",
        "data_delayed": False,
        "score": {
            "valid": True,
            "swing_score": 78.5,
            "components": {"momentum": 80.0},
            "recommendation": "BUY",
            "confidence": "HIGH",
            "risk_level": "LOW",
            "regime": "BULL",
        },
        "trade_plan": {
            "direction": "BUY",
            "entry": 9500.0,
            "stop_loss": 9200.0,
            "take_profit": 10100.0,
            "shares": 1000,
            "lots": 10,
            "risk_reward_ratio": 2.0,
            "risk_per_trade_pct": 2.0,
            "note": "R:R optimal",
        },
        "raw_indicators": {
            "rsi": 55.0,
            "mfi": 60.0,
            "atr": 150.0,
            "adx": 28.0,
            "plus_di": 25.0,
            "minus_di": 15.0,
            "ema_fast": 9400.0,
            "ema_slow": 9200.0,
            "rvol": 1.5,
            "support": 9300.0,
            "resistance": 9800.0,
            "fibonacci": {"fib_0": 9000.0, "fib_1": 10000.0},
            "candlestick_patterns": ["Bullish Engulfing"],
            "pattern_candles": [
                {"open": 9300.0, "high": 9550.0, "low": 9250.0, "close": 9500.0},
                {"open": 9200.0, "high": 9350.0, "low": 9150.0, "close": 9300.0},
                {"open": 9100.0, "high": 9250.0, "low": 9050.0, "close": 9200.0},
            ],
        },
        "capital_used": 10000000.0,
        "risk_summary": {
            "regime": "BULL",
            "score": 80.0,
            "level": "LOW",
            "factors": {"volatility": 10.0},
            "warnings": [],
        },
        "gorengan_assessment": {
            "score": 5.0,
            "level": "LOW",
            "is_pump": False,
            "factors": {"market_cap_risk": 5.0},
            "warnings": [],
        },
        "notes": ["Sinyal terverifikasi."],
    }

    monkeypatch.setattr("api.analyze_stock", lambda *args, **kwargs: mock_analysis)

    response = client.get("/analisis/BBCA")
    assert response.status_code == 200
    data = response.json()
    assert data["kode"] == "BBCA"
    assert data["score"]["valid"] is True
    assert data["trade_plan"]["direction"] == "BUY"

    # CRITICAL: Verify pattern_candles is included and not stripped by Pydantic
    raw_ind = data["raw_indicators"]
    assert "pattern_candles" in raw_ind
    assert raw_ind["pattern_candles"] is not None
    assert len(raw_ind["pattern_candles"]) == 3
    assert raw_ind["pattern_candles"][0]["close"] == 9500.0


def test_analisis_unknown_ticker(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    response = client.get("/analisis/NONEXISTENT")
    assert response.status_code == 404
    assert "tidak ditemukan" in response.json()["detail"]


def test_analisis_insufficient_data(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    def _raise_insufficient(*args, **kwargs):
        raise InsufficientDataError("Data historis cuma 10 hari, minimal 150")

    monkeypatch.setattr("api.analyze_stock", _raise_insufficient)

    response = client.get("/analisis/BBCA")
    assert response.status_code == 404
    assert "cuma 10 hari" in response.json()["detail"]


def test_analisis_upstream_error(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    def _raise_yahoo(*args, **kwargs):
        raise YahooClientError("Upstream connection timeout")

    monkeypatch.setattr("api.analyze_stock", _raise_yahoo)

    response = client.get("/analisis/BBCA")
    assert response.status_code == 502
    assert "Gagal ambil data" in response.json()["detail"]


def test_analisis_invalid_capital():
    response = client.get("/analisis/BBCA", params={"capital": 0})
    assert response.status_code == 422

    response_neg = client.get("/analisis/BBCA", params={"capital": -500})
    assert response_neg.status_code == 422


# ---------------------------------------------------------------------------
# 4. History Endpoint Tests
# ---------------------------------------------------------------------------

def test_history_valid_ticker(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)
    mock_bars = [
        make_mock_bar("2026-03-18", 9300.0),
        make_mock_bar("2026-03-19", 9400.0),
        make_mock_bar("2026-03-20", 9500.0),
    ]
    monkeypatch.setattr("api.fetch_trading_info", lambda kode, length, target_date: mock_bars)

    response = client.get("/history/BBCA", params={"length": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["kode"] == "BBCA"
    assert len(data["bars"]) == 3
    assert data["bars"][-1]["close"] == 9500.0
    assert "date" in data["bars"][0]


def test_history_unknown_ticker(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    response = client.get("/history/XXXX")
    assert response.status_code == 404
    assert "tidak ditemukan" in response.json()["detail"]


def test_history_upstream_network_failure(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    def _raise_yahoo(*args, **kwargs):
        raise YahooClientError("Yahoo Finance API rate-limited (HTTP 429)")

    monkeypatch.setattr("api.fetch_trading_info", _raise_yahoo)

    response = client.get("/history/BBCA")
    assert response.status_code == 502
    assert "Gagal ambil data historis BBCA" in response.json()["detail"]


def test_history_upstream_idx_failure(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    def _raise_idx(*args, **kwargs):
        raise IdxTradingError("IDX API connection refused")

    monkeypatch.setattr("api.fetch_trading_info", _raise_idx)

    response = client.get("/history/BBCA")
    assert response.status_code == 502
    assert "Gagal ambil data historis BBCA" in response.json()["detail"]


def test_history_invalid_length():
    response = client.get("/history/BBCA", params={"length": 0})
    assert response.status_code == 422

    response_over = client.get("/history/BBCA", params={"length": 99999})
    assert response_over.status_code == 422


# ---------------------------------------------------------------------------
# 5. Recovery Endpoint Tests (including drop_pct: None fix)
# ---------------------------------------------------------------------------

def test_recovery_valid_ticker(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)
    mock_bars = [make_mock_bar("2026-03-20", 9000.0) for _ in range(70)]
    monkeypatch.setattr("api.fetch_trading_info", lambda kode, length, target_date: mock_bars)

    mock_rec = {
        "kode": "BBCA",
        "nama": "Bank Central Asia Tbk",
        "valid": True,
        "harga": 9000.0,
        "ref_price": 9500.0,
        "ref_days": 1,
        "last_updated": "2026-03-20",
        "distance_pct": -5.26,
        "drop_pct": 5.26,
        "drop_source": "user",
        "in_setup": True,
        "empirical": [
            {
                "horizon_days": 5,
                "n_events": 50,
                "n_recovered": 32,
                "rate": 0.64,
                "target": "previous_close",
            }
        ],
        "signal": "RECOVERY_HIGH",
        "signal_reason": "Probabilitas recovery tinggi dalam 5 hari",
        "exit_plan": {
            "target": 9500.0,
            "time_stop_days": 10,
            "stop_loss": 8700.0,
            "note": "Target previous close",
        },
    }
    monkeypatch.setattr("recovery.build_recovery_analysis", lambda *args, **kwargs: mock_rec)

    response = client.get("/recovery/BBCA")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["drop_pct"] == 5.26


def test_recovery_short_history_no_500(monkeypatch):
    """
    CRITICAL TEST: When historical bars are < RECOVERY_MIN_BARS (60 bars),
    recovery.build_recovery_analysis returns drop_pct: None.
    This must NOT trigger a FastAPI 500 ResponseValidationError.
    """
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)
    short_bars = [make_mock_bar(f"2026-01-{i+1:02d}", 1000.0) for i in range(15)]
    monkeypatch.setattr("api.fetch_trading_info", lambda kode, length, target_date: short_bars)

    # Real recovery.build_recovery_analysis behavior on short bars:
    mock_short_rec = {
        "kode": "BBCA",
        "nama": "Bank Central Asia Tbk",
        "valid": False,
        "harga": 1000.0,
        "ref_price": 1050.0,
        "ref_days": 1,
        "last_updated": "2026-01-15",
        "distance_pct": -4.76,
        "drop_pct": None,  # <--- Nullable field that previously caused 500!
        "drop_source": "auto",
        "in_setup": False,
        "empirical": [],
        "signal": "NO_SIGNAL",
        "signal_reason": "Data historis cuma 15 bar, minimal 60 untuk estimasi GBM yang stabil.",
        "exit_plan": None,
    }
    monkeypatch.setattr("recovery.build_recovery_analysis", lambda *args, **kwargs: mock_short_rec)

    response = client.get("/recovery/BBCA")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["drop_pct"] is None
    assert "cuma 15 bar" in data["signal_reason"]


def test_recovery_unknown_ticker(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    response = client.get("/recovery/NONEXISTENT")
    assert response.status_code == 404
    assert "tidak ditemukan" in response.json()["detail"]


def test_recovery_upstream_error(monkeypatch):
    monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

    def _raise_yahoo(*args, **kwargs):
        raise YahooClientError("Upstream timeout")

    monkeypatch.setattr("api.fetch_trading_info", _raise_yahoo)

    response = client.get("/recovery/BBCA")
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# 6. Gorengan and ReadyToFly Cache Resilience Tests
# ---------------------------------------------------------------------------

def test_gorengan_success(monkeypatch):
    mock_cached = {
        "scraped_at": "2026-03-20T16:00:00+07:00",
        "data": [
            {
                "code": "BUMI",
                "name": "Bumi Resources Tbk",
                "close": 120.0,
                "pct_change": 15.0,
                "volume": 50000000.0,
                "value": 6000000000.0,
                "frequency": 8000,
                "gorengan_score": 85.0,
                "gorengan_level": "EXTREME",
                "factors": {
                    "historical_pump_dump_risk": 80.0,
                    "liquidity_risk": 50.0,
                    "market_cap_risk": 60.0,
                    "active_pump": 90.0,
                    "mid_momentum": 70.0,
                    "distribution_risk": 65.0,
                    "turnover_gaps": 40.0,
                },
                "warnings": ["Volume spiking unusually high"],
            }
        ],
    }
    monkeypatch.setattr("api.get_cached_gorengan", lambda for_date=None: mock_cached)

    response = client.get("/gorengan")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["data"][0]["code"] == "BUMI"
    assert data["data"][0]["gorengan_level"] == "EXTREME"


def test_gorengan_not_found(monkeypatch):
    monkeypatch.setattr("api.get_cached_gorengan", lambda for_date=None: None)

    response = client.get("/gorengan")
    assert response.status_code == 404
    assert "belum discrape" in response.json()["detail"]


def test_gorengan_corrupted_cache(monkeypatch):
    def _corrupted(for_date=None):
        raise ValueError("Corrupted cache file")

    monkeypatch.setattr("api.get_cached_gorengan", _corrupted)

    response = client.get("/gorengan")
    assert response.status_code == 404


def test_readytofly_success(monkeypatch):
    mock_cached = {
        "scraped_at": "2026-03-20T16:00:00+07:00",
        "data": [
            {
                "code": "BRIS",
                "name": "Bank Syariah Indonesia Tbk",
                "close": 2800.0,
                "pct_change": 3.0,
                "status": "ready",
                "density_pct": 75.0,
                "k_heavy": 3,
                "window_days": 10,
                "ara_date": "2026-03-10",
                "ara_ref_price": 2500.0,
                "distance_pct": 12.0,
                "net_dist": 0.5,
                "net_dist_heavy": 0.8,
                "acc_density": 0.7,
                "post_ara_decay": 0.9,
                "strength": 82.0,
                "adv_vol_20": 2000000.0,
                "adv_val_20": 5600000000.0,
                "liquidity_ok": True,
                "liquidity_prima": True,
                "sma_gap_pct": 5.0,
                "sma20": 2650.0,
                "state_ma20": "above",
                "max_rvol": 2.5,
                "gates": {},
                "note": "Akumulasi kuat",
                "reason": "VCP breakout",
                "post_ara_volume": 1500000.0,
                "post_ara_value": 4200000000.0,
                "vcp_ratio": 0.85,
                "dryup_ratio": 0.35,
                "vcp_ok": True,
                "dryup_ok": True,
            }
        ],
    }
    monkeypatch.setattr("api.get_cached_ready_to_fly", lambda for_date=None: mock_cached)

    response = client.get("/readytofly")
    assert response.status_code == 200
    data = response.json()
    assert data["count_ready"] == 1
    assert data["data"][0]["code"] == "BRIS"


def test_readytofly_not_found(monkeypatch):
    monkeypatch.setattr("api.get_cached_ready_to_fly", lambda for_date=None: None)

    response = client.get("/readytofly")
    assert response.status_code == 404
    assert "belum discan" in response.json()["detail"]


def test_readytofly_corrupted_cache(monkeypatch):
    def _corrupted(for_date=None):
        raise ValueError("Corrupted cache file")

    monkeypatch.setattr("api.get_cached_ready_to_fly", _corrupted)

    response = client.get("/readytofly")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 7. Boundary Validation: Calendar Date and Regex Format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "invalid_date",
    [
        "2026-99-99",  # Invalid month and day
        "2026-02-30",  # February 30th does not exist
        "2026-13-01",  # Month 13 does not exist
        "2026-04-31",  # April has only 30 days
    ],
)
def test_boundary_invalid_calendar_dates(invalid_date):
    """
    Calendar dates matching regex \\d{4}-\\d{2}-\\d{2} but invalid on calendar
    must be caught by validate_query_date and return HTTP 400.
    """
    endpoints = [
        ("/gainers", {"date": invalid_date}),
        ("/analisis/BBCA", {"date": invalid_date}),
        ("/history/BBCA", {"date": invalid_date}),
        ("/recovery/BBCA", {"date": invalid_date}),
        ("/gorengan", {"date": invalid_date}),
        ("/readytofly", {"date": invalid_date}),
    ]

    for url, params in endpoints:
        resp = client.get(url, params=params)
        assert resp.status_code == 400, f"Expected 400 for {url}?date={invalid_date}, got {resp.status_code}"
        assert "Format tanggal tidak valid" in resp.json()["detail"]


@pytest.mark.parametrize(
    "regex_failing_date",
    [
        "not-a-date",
        "2026/01/15",
        "15-01-2026",
        "2026-1-1",
        "2026-001-01",
    ],
)
def test_boundary_regex_failing_dates(regex_failing_date):
    """
    Strings that violate \\d{4}-\\d{2}-\\d{2} must be rejected by FastAPI Query with HTTP 422.
    """
    endpoints = [
        ("/gainers", {"date": regex_failing_date}),
        ("/analisis/BBCA", {"date": regex_failing_date}),
        ("/history/BBCA", {"date": regex_failing_date}),
        ("/recovery/BBCA", {"date": regex_failing_date}),
        ("/gorengan", {"date": regex_failing_date}),
        ("/readytofly", {"date": regex_failing_date}),
    ]

    for url, params in endpoints:
        resp = client.get(url, params=params)
        assert resp.status_code == 422, f"Expected 422 for {url}?date={regex_failing_date}, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 8. Scraped Dates Inspection Endpoint
# ---------------------------------------------------------------------------

def test_scraped_dates():
    response = client.get("/scraped-dates")
    assert response.status_code == 200
    data = response.json()
    assert "dates" in data
    assert "by_category" in data
    assert "gainers" in data["by_category"]
    assert "gorengan" in data["by_category"]
    assert "readytofly" in data["by_category"]
    assert "details" in data


# ---------------------------------------------------------------------------
# CLI Runner fallback
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-v", __file__]))
