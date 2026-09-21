# Project: SwingPredictionBot Stabilization, Debugging & Audit

## Architecture
- **Backend**: Python 3.10+ FastAPI service (`backend/api.py`) orchestrating:
  - Technical calculation engine: `indicators.py`, `scoring.py`, `regime.py`
  - Risk & execution planning: `risk.py`, `gorengan.py`, `portfolio.py`
  - Statistical & ML recovery models: `recovery.py`, `backtest.py`, `walkforward.py`
  - Market data integration: `data_source/yahoo_client.py`, `idx_client.py`, `idx_trading.py`
- **Frontend**: Next.js 16 (Turbopack) with React 19, TypeScript, Tailwind CSS v4 (`frontend/`):
  - Dashboard routes: `/`, `/analisis`, `/saham/[kode]`, `/top-gainers`, `/ready-to-fly`, `/gorengan`, `/ai-trade`
  - Financial charts: Lightweight Charts (`components/price-chart.tsx`), SVG Candlestick patterns (`components/candlestick-patterns.tsx`)
  - Reporting: Client-side PDF export (`components/download-pdf-button.tsx`)

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Backend Calculation Engine Hardening | Fix NaN formatting crashes in `risk.py` & `gorengan.py`, guard 0-length array `IndexError` in `indicators.py`, `scoring.py`, `backtest.py`, add `import sys` to `recovery.py`, handle optional `scikit-learn` in `walkforward.py` | M1 | explorer_survey_1 |
| 2 | Python Environment & Dependency Manifest | Add missing dependencies (`scikit-learn`, `httpx`, `curl_cffi`, `pytest`) to `backend/requirements.txt` | M1 | explorer_survey_1 & 2 |
| 3 | API Schema Alignment & Serialization | Add `pattern_candles` to `RawIndicatorsResponse` in `backend/api.py` so candle shapes reach frontend visualizer; make `RecoveryResponse.drop_pct` nullable to prevent 500 ResponseValidationError | M2 | explorer_survey_2 |
| 4 | Endpoint Robustness & Exception Handling | Add `try...except (YahooClientError, IdxTradingError)` to `GET /history/{kode}`; catch invalid calendar dates in date query parameter | M2 | explorer_survey_2 |
| 5 | Test Suite Modernization & Smoke Verification | Modernize `backend/test_api.py` into structured pytest-compatible test suite with assertions and coverage across all 7 core endpoints; verify `python -m py_compile` | M2 | explorer_survey_2 |
| 6 | Frontend Lint & Code Quality Stabilization | Fix 14 ESLint errors (`react-hooks/set-state-in-effect`, `@typescript-eslint/no-explicit-any`) and 3 warnings in Next.js frontend | M3 | explorer_survey_3 |
| 7 | Frontend Dead Code Removal & Layout Guarding | Clean up unused legacy components and empty route folders; harden `fmtDate` against undefined/empty dates | M3 | explorer_survey_3 |
| 8 | Frontend Production Build Verification | Verify `npm run build` succeeds with exit code 0 and zero fatal errors | M3 | explorer_survey_3 |
| 9 | Dual-Track End-to-End Verification & Audit | Multi-agent verification (Reviewers, Challengers, Forensic Auditor) confirming all acceptance criteria and integrity standards | M4 | orchestrator |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Calculation Engine & Dependencies | `backend/indicators.py`, `backend/scoring.py`, `backend/risk.py`, `backend/recovery.py`, `backend/gorengan.py`, `backend/backtest.py`, `backend/walkforward.py`, `backend/requirements.txt` | none | DONE |
| M2 | Backend API Endpoints & Test Modernization | `backend/api.py`, `backend/test_api.py` | M1 | DONE |
| M3 | Frontend Next.js Lint & Build Stabilization | `frontend/` (pages, components, types, build scripts) | none | DONE |
| M4 | Comprehensive E2E Verification & Victory Audit | Full system test run, reviewer checks, challenger stress tests, forensic integrity audit | M1, M2, M3 | DONE |

## Interface Contracts
### `scoring.py` ↔ `api.py`
- `compute_score(data: dict)` returns a dictionary with keys:
  `valid: bool`, `swing_score: float | None`, `components: dict | None`, `recommendation: str | None`, `confidence: float | None`, `risk_level: str | None`, `regime: str`.
- Gracefully handles empty data arrays without throwing `IndexError` or `KeyError`.

### `risk.py` ↔ `api.py`
- `build_trade_plan(score_result: dict, entry_price: float, atr: float, capital: float, position_pct: float | None = None)`
- Returns `TradePlanResponse` dict or `None`.
- If `atr` or `entry_price` or `capital` is NaN, None, or <= 0, returns `None` without raising `ValueError` on formatting.

### `api.py` ↔ `frontend` (`RawIndicatorsResponse`)
- `RawIndicatorsResponse` must include `pattern_candles: list[dict] | None = None` so frontend `CandlestickPatterns` receives real candlestick geometry.
- `RecoveryResponse.drop_pct` must be `float | None = None` so stocks with < 60 trading bars do not crash FastAPI serialization.

## Code Layout
- `backend/`: Python backend source files and tests.
- `frontend/`: Next.js 16 frontend app, components, and styling.
- `.agents/`: Coordination and agent metadata files only (no source code).
