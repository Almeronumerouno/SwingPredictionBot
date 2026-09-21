"""Adversarial boundary stress tests for SwingPredictionBot calculation engines and API endpoints.

Verification suite designed for Challenger Agent:
1. Boundary condition stress tests on indicators, scoring, risk, and gorengan.
2. Endpoint parameter stress tests on FastAPI routes using TestClient.
3. Boundary adversarial edge cases (including IEEE 754 infinity behavior).
"""

import os
import sys
import numpy as np
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import indicators as ind
import scoring
import risk
import gorengan
from api import app
from data_source.idx_client import Security
from data_source.yahoo_client import DailyBar

client = TestClient(app)

MOCK_SECURITIES = [
    Security(code="BBCA", name="Bank Central Asia Tbk", listing_board="UTAMA", shares=123275050000.0),
    Security(code="BBRI", name="Bank Rakyat Indonesia Tbk", listing_board="UTAMA", shares=151559000000.0),
]


def make_mock_bars(n: int = 60, base_price: float = 5000.0) -> list[DailyBar]:
    bars = []
    for i in range(n):
        d_str = f"2026-01-{(i % 28) + 1:02d}"
        bars.append(
            DailyBar(
                date=d_str,
                previous=base_price,
                open_price=base_price,
                high=base_price * 1.02,
                low=base_price * 0.98,
                close=base_price,
                volume=1_000_000.0,
                approx_value=base_price * 1_000_000.0,
                frequency=1000,
            )
        )
    return bars


# ===========================================================================
# 1. Boundary Condition Stress Tests: indicators.true_range
# ===========================================================================

class TestTrueRangeBoundary:
    """Stress tests for indicators.true_range with empty, zeros, single, NaN arrays."""

    def test_empty_arrays(self):
        h = np.array([])
        l = np.array([])
        c = np.array([])
        res = ind.true_range(h, l, c)
        assert isinstance(res, np.ndarray)
        assert len(res) == 0

    def test_all_zero_arrays(self):
        for length in [1, 2, 5, 50]:
            h = np.zeros(length)
            l = np.zeros(length)
            c = np.zeros(length)
            res = ind.true_range(h, l, c)
            assert isinstance(res, np.ndarray)
            assert len(res) == length
            assert np.all(res == 0.0)

    def test_single_element_array(self):
        h = np.array([105.0])
        l = np.array([95.0])
        c = np.array([100.0])
        res = ind.true_range(h, l, c)
        assert isinstance(res, np.ndarray)
        assert len(res) == 1
        assert res[0] == 10.0

    def test_all_nan_arrays(self):
        for length in [1, 2, 14, 50]:
            h = np.full(length, np.nan)
            l = np.full(length, np.nan)
            c = np.full(length, np.nan)
            res = ind.true_range(h, l, c)
            assert isinstance(res, np.ndarray)
            assert len(res) == length
            assert np.all(np.isnan(res))


# ===========================================================================
# 2. Boundary Condition Stress Tests: indicators.mfi
# ===========================================================================

class TestMFIBoundary:
    """Stress tests for indicators.mfi with empty, zeros, single, NaN arrays."""

    def test_empty_arrays(self):
        h = np.array([])
        l = np.array([])
        c = np.array([])
        v = np.array([])
        res = ind.mfi(h, l, c, v)
        assert isinstance(res, np.ndarray)
        assert len(res) == 0

    def test_all_zero_arrays(self):
        for length in [1, 5, 14, 30]:
            h = np.zeros(length)
            l = np.zeros(length)
            c = np.zeros(length)
            v = np.zeros(length)
            res = ind.mfi(h, l, c, v)
            assert isinstance(res, np.ndarray)
            assert len(res) == length
            # Period is 14 bars. For bars with index >= 14 (i.e. length > 14),
            # pos_sum=0 and neg_sum=0 defaults to 50.0 safely without ZeroDivisionError
            if length > 14:
                assert not np.isnan(res[14])
                assert res[14] == 50.0

    def test_single_element_array(self):
        h = np.array([105.0])
        l = np.array([95.0])
        c = np.array([100.0])
        v = np.array([1000.0])
        res = ind.mfi(h, l, c, v)
        assert isinstance(res, np.ndarray)
        assert len(res) == 1
        assert np.isnan(res[0])  # Insufficient bars returns NaN safely

    def test_all_nan_arrays(self):
        for length in [1, 5, 14, 30]:
            h = np.full(length, np.nan)
            l = np.full(length, np.nan)
            c = np.full(length, np.nan)
            v = np.full(length, np.nan)
            res = ind.mfi(h, l, c, v)
            assert isinstance(res, np.ndarray)
            assert len(res) == length
            # NaNs are handled gracefully without exceptions


# ===========================================================================
# 3. Boundary Condition Stress Tests: scoring.compute_score
# ===========================================================================

class TestScoringComputeScoreBoundary:
    """Stress tests for scoring.compute_score with empty, zeros, single, NaN arrays."""

    REQUIRED_KEYS = [
        "close", "rsi", "atr", "adx", "mfi", "rvol",
        "ema_fast", "ema_slow", "donchian_upper", "donchian_lower",
    ]

    def test_empty_or_none(self):
        for empty_val in [{}, None, "not-a-dict", []]:
            res = scoring.compute_score(empty_val)
            assert isinstance(res, dict)
            assert res["valid"] is False
            assert res["swing_score"] is None
            assert res["recommendation"] is None

    def test_empty_arrays(self):
        data = {k: np.array([]) for k in self.REQUIRED_KEYS}
        res = scoring.compute_score(data)
        assert isinstance(res, dict)
        assert res["valid"] is False
        assert res["swing_score"] is None

    def test_all_zero_arrays(self):
        for length in [1, 5, 30]:
            data = {k: np.zeros(length) for k in self.REQUIRED_KEYS}
            res = scoring.compute_score(data)
            assert isinstance(res, dict)
            assert res["valid"] is False
            assert res["swing_score"] is None

    def test_single_element_array_normal_and_nan(self):
        data_normal = {k: np.array([100.0]) for k in self.REQUIRED_KEYS}
        res_normal = scoring.compute_score(data_normal)
        assert isinstance(res_normal, dict)
        assert "valid" in res_normal

        data_nan = {k: np.array([np.nan]) for k in self.REQUIRED_KEYS}
        res_nan = scoring.compute_score(data_nan)
        assert isinstance(res_nan, dict)
        assert res_nan["valid"] is False
        assert res_nan["swing_score"] is None

    def test_all_nan_arrays(self):
        for length in [1, 5, 30]:
            data = {k: np.full(length, np.nan) for k in self.REQUIRED_KEYS}
            res = scoring.compute_score(data)
            assert isinstance(res, dict)
            assert res["valid"] is False
            assert res["swing_score"] is None


# ===========================================================================
# 4. Boundary Condition Stress Tests: risk.build_trade_plan
# ===========================================================================

class TestRiskBuildTradePlanBoundary:
    """Stress tests for risk.build_trade_plan with boundary parameters."""

    @pytest.fixture
    def valid_score(self):
        return {
            "valid": True,
            "recommendation": "BUY",
            "risk_level": "sedang",
            "regime": "bull",
        }

    def test_invalid_scores(self):
        for invalid_score in [None, {}, {"valid": False}, {"valid": True, "recommendation": "HOLD"}]:
            res = risk.build_trade_plan(invalid_score, entry_price=1000.0, atr=50.0, capital=10_000_000.0)
            assert res is None

    def test_edge_entry_prices(self, valid_score):
        for ep in [0.0, -100.0, float("nan"), None]:
            res = risk.build_trade_plan(valid_score, entry_price=ep, atr=50.0, capital=10_000_000.0)
            assert res is None

    def test_edge_atr(self, valid_score):
        for a in [0.0, -10.0, float("nan"), None]:
            res = risk.build_trade_plan(valid_score, entry_price=1000.0, atr=a, capital=10_000_000.0)
            assert res is None

    def test_edge_capital(self, valid_score):
        for cap in [0.0, -1_000_000.0, float("nan"), None]:
            res = risk.build_trade_plan(valid_score, entry_price=1000.0, atr=50.0, capital=cap)
            assert res is None

        # Extreme large capital (1e15)
        res_huge = risk.build_trade_plan(valid_score, entry_price=1000.0, atr=50.0, capital=1e15)
        assert res_huge is not None
        assert res_huge["shares"] > 0
        assert res_huge["risk_per_trade_pct"] is not None

        # Tiny capital (Rp 100 < 1 lot)
        res_tiny = risk.build_trade_plan(valid_score, entry_price=1000.0, atr=50.0, capital=100.0)
        assert res_tiny is not None
        assert res_tiny["shares"] == 0
        assert res_tiny["lots"] == 0
        assert "Butuh minimal" in res_tiny["note"]

    def test_infinity_vulnerability_discovery(self, valid_score):
        """
        Adversarial Finding: Passing float('inf') reveals that risk.py checks np.isnan()
        but lacks np.isinf() guards, triggering OverflowError on int conversion.
        """
        with pytest.raises(OverflowError):
            risk.build_trade_plan(valid_score, entry_price=float("inf"), atr=50.0, capital=10_000_000.0)


# ===========================================================================
# 5. Boundary Condition Stress Tests: gorengan._liquidity_risk
# ===========================================================================

class TestGorenganLiquidityRiskBoundary:
    """Stress tests for gorengan._liquidity_risk with boundary inputs."""

    def test_empty_arrays(self):
        c = np.array([])
        v = np.array([])
        score, warn = gorengan._liquidity_risk(c, v)
        assert score == 0.0
        assert warn is None

    def test_all_zero_arrays(self):
        for length in [1, 5, 60]:
            c = np.zeros(length)
            v = np.zeros(length)
            score, warn = gorengan._liquidity_risk(c, v)
            assert isinstance(score, float)
            assert score == 100.0  # Zero median transaction value flagged as illiquid
            assert warn is not None

    def test_single_element_array(self):
        score0, warn0 = gorengan._liquidity_risk(np.array([0.0]), np.array([0.0]))
        assert score0 == 100.0

        score1, warn1 = gorengan._liquidity_risk(np.array([5000.0]), np.array([1_000_000.0]))
        assert isinstance(score1, float)

    def test_all_nan_arrays(self):
        for length in [1, 5, 60]:
            c = np.full(length, np.nan)
            v = np.full(length, np.nan)
            score, warn = gorengan._liquidity_risk(c, v)
            assert score == 0.0
            assert warn is None

    def test_mismatched_lengths_and_infinities(self):
        c = np.ones(60) * 1000.0
        v = np.ones(30) * 50000.0
        score, warn = gorengan._liquidity_risk(c, v)
        assert isinstance(score, float)

        score_inf, warn_inf = gorengan._liquidity_risk(np.array([np.inf]), np.array([1000.0]))
        assert isinstance(score_inf, float)


# ===========================================================================
# 6. Endpoint Parameter Stress Tests
# ===========================================================================

class TestFastAPIEndpointStress:
    """Edge-case parameter testing on FastAPI endpoints via TestClient."""

    def test_analisis_capital_boundary_validation(self, monkeypatch):
        monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

        # capital=0 violates gt=0 -> HTTP 422
        resp_zero = client.get("/analisis/BBCA?capital=0")
        assert resp_zero.status_code == 422, f"Expected 422 for capital=0, got {resp_zero.status_code}"

        # capital=-1000 violates gt=0 -> HTTP 422
        resp_neg = client.get("/analisis/BBCA?capital=-1000")
        assert resp_neg.status_code == 422, f"Expected 422 for capital=-1000, got {resp_neg.status_code}"

        # capital=nan is rejected by FastAPI float parsing -> HTTP 422
        resp_nan = client.get("/analisis/BBCA?capital=nan")
        assert resp_nan.status_code == 422, f"Expected 422 for capital=nan, got {resp_nan.status_code}"

    def test_analisis_capital_extreme_large(self, monkeypatch):
        monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)
        mock_res = {
            "kode": "BBCA",
            "nama": "Bank Central Asia Tbk",
            "harga": 9500.0,
            "last_updated": "2026-03-20",
            "fetched_at": "2026-03-20T16:00:00",
            "data_delayed": False,
            "score": {
                "valid": True, "swing_score": 80.0, "components": {"momentum": 80.0},
                "recommendation": "BUY", "confidence": "tinggi", "risk_level": "sedang", "regime": "bull"
            },
            "trade_plan": {
                "direction": "BUY", "entry": 9500.0, "stop_loss": 9200.0, "take_profit": 10100.0,
                "shares": 100000000, "lots": 1000000, "risk_reward_ratio": 2.0, "risk_per_trade_pct": 2.0, "note": "Huge cap"
            },
            "raw_indicators": {
                "rsi": 55.0, "mfi": 60.0, "atr": 150.0, "adx": 28.0, "plus_di": 25.0, "minus_di": 15.0,
                "ema_fast": 9400.0, "ema_slow": 9200.0, "rvol": 1.5, "support": 9300.0, "resistance": 9800.0,
                "fibonacci": None, "candlestick_patterns": [],
                "pattern_candles": [{"open": 9300.0, "high": 9550.0, "low": 9250.0, "close": 9500.0}]
            },
            "capital_used": 1e15,
            "gorengan": None,
            "buy_signal_validated": True,
            "validation_note": "Valid",
        }
        monkeypatch.setattr("api.analyze_stock", lambda *args, **kwargs: mock_res)

        resp = client.get("/analisis/BBCA?capital=1000000000000000")
        assert resp.status_code == 200
        assert resp.json()["capital_used"] == 1e15

    def test_analisis_invalid_ticker_not_found(self, monkeypatch):
        monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

        resp = client.get("/analisis/XYZ999")
        assert resp.status_code == 404
        assert "tidak ditemukan di daftar efek IDX" in resp.json()["detail"]

    def test_date_queries_edge_cases(self, monkeypatch):
        monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

        # 1. 2026-99-99: Regex matches, calendar invalid -> HTTP 400
        resp_99 = client.get("/analisis/BBCA?date=2026-99-99")
        assert resp_99.status_code == 400
        assert "Format tanggal tidak valid" in resp_99.json()["detail"]

        # 2. 2026-02-30: Regex matches, calendar invalid -> HTTP 400
        resp_feb30 = client.get("/analisis/BBCA?date=2026-02-30")
        assert resp_feb30.status_code == 400
        assert "Format tanggal tidak valid" in resp_feb30.json()["detail"]

        # 3. invalid-date: Violates regex pattern -> HTTP 422
        resp_inv = client.get("/analisis/BBCA?date=invalid-date")
        assert resp_inv.status_code == 422

        # 4. "": Empty string violates regex pattern -> HTTP 422
        resp_empty = client.get("/analisis/BBCA?date=")
        assert resp_empty.status_code == 422

    def test_history_and_recovery_nonexistent_ticker(self, monkeypatch):
        monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

        # Non-existent ticker on /history/{kode} -> HTTP 404
        resp_h = client.get("/history/XYZ999")
        assert resp_h.status_code == 404
        assert "tidak ditemukan di daftar efek IDX" in resp_h.json()["detail"]

        # Non-existent ticker on /recovery/{kode} -> HTTP 404
        resp_r = client.get("/recovery/XYZ999")
        assert resp_r.status_code == 404
        assert "tidak ditemukan di daftar efek IDX" in resp_r.json()["detail"]

    def test_no_unhandled_500_on_boundary_inputs(self, monkeypatch):
        """Cross-cutting check: Verify that none of the edge inputs produce HTTP 500."""
        monkeypatch.setattr("api.get_or_fetch_securities_list", lambda: MOCK_SECURITIES)

        endpoints = [
            "/analisis/XYZ999",
            "/analisis/BBCA?capital=0",
            "/analisis/BBCA?capital=-1000",
            "/analisis/BBCA?capital=nan",
            "/analisis/BBCA?date=2026-99-99",
            "/analisis/BBCA?date=2026-02-30",
            "/analisis/BBCA?date=invalid-date",
            "/analisis/BBCA?date=",
            "/history/XYZ999",
            "/history/BBCA?date=2026-99-99",
            "/history/BBCA?date=invalid-date",
            "/recovery/XYZ999",
            "/recovery/BBCA?date=2026-99-99",
            "/recovery/BBCA?date=invalid-date",
        ]

        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code != 500, f"Endpoint {ep} produced unhandled HTTP 500: {resp.text}"
            assert resp.status_code in (400, 404, 422, 502), f"Endpoint {ep} returned unexpected {resp.status_code}"
