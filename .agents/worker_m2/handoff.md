# Handoff Report: Milestone M2 — Backend API Endpoints & Test Modernization

**Agent**: `worker_m2` (implementer / qa)  
**Working Directory**: `c:\CodeKuliah\SwingPredictionBot\.agents\worker_m2`  
**Date**: 2026-09-21  
**Target Files**: `backend/api.py`, `backend/test_api.py`  

---

## 1. Observation

1. **`backend/api.py` Schema Omission (`pattern_candles`)**:
   - In `backend/api.py` line 581, `analyze_stock()` populates `"pattern_candles": pattern_candles` in `raw_indicators`.
   - Prior to modification, `RawIndicatorsResponse` (line 94) omitted `pattern_candles`. Under Pydantic v2 serialization, undeclared fields were stripped, returning `undefined` to the frontend `CandlestickPatterns` component (`frontend/components/technical-indicators.tsx:333`).
2. **`backend/api.py` Recovery Serialization Crash on Short History**:
   - In `RecoveryResponse` (line 300), `drop_pct: float` was defined as non-nullable.
   - When a stock has fewer than `config.RECOVERY_MIN_BARS` (60 bars), `recovery.py` returns `drop_pct: None`.
   - FastAPI raised `fastapi.exceptions.ResponseValidationError` (HTTP 500) upon serializing this response.
3. **`GET /history/{kode}` Missing Network Exception Handling**:
   - Unlike `/analisis/{kode}` and `/recovery/{kode}`, `/history/{kode}` (lines 884-890) called `fetch_trading_info` without wrapping it in `try...except (YahooClientError, IdxTradingError)`. Upstream network failures or Yahoo Finance rate-limiting triggered an unhandled 500 error instead of HTTP 502.
4. **Calendar Date Format Validation Gap**:
   - Query date parameters across all endpoints used `pattern=r"^\d{4}-\d{2}-\d{2}$"`.
   - Dates like `2026-99-99` or `2026-02-30` passed regex validation and subsequently caused `ValueError` in `date.fromisoformat()` inside downstream calculation routines, generating unhandled 500 exceptions.
5. **Cache Vulnerability in `GET /readytofly` and `GET /gorengan`**:
   - `get_cached_gorengan` and `get_cached_ready_to_fly` were invoked without `try...except` protection. Corrupted, empty, or unparseable JSON files triggered unhandled 500 errors.
6. **`backend/test_api.py` Legacy State**:
   - Contained zero `test_*` functions (incompatible with pytest discovery).
   - Used informal print statements without assertions.
   - Made live external network requests to Yahoo Finance for `BBCA`, `ASII`, `TLKM`.
   - Provided zero coverage for `/market-status`, `/recovery/{kode}`, `/readytofly`, `/gorengan`, or boundary edge cases.

---

## 2. Logic Chain

1. **Adding `pattern_candles` to `RawIndicatorsResponse`**:
   - By declaring `pattern_candles: list[dict] | None = None` in `RawIndicatorsResponse`, Pydantic v2 preserves the 3-bar OHLC dictionary list emitted by `analyze_stock()`. The frontend can now access `data.raw_indicators.pattern_candles` to render candlestick patterns.
2. **Making `RecoveryResponse.drop_pct` Nullable**:
   - Changing `drop_pct: float` to `drop_pct: float | None = None` in `RecoveryResponse` allows `None` to pass Pydantic serialization when `len(close) < config.RECOVERY_MIN_BARS`. The endpoint cleanly returns HTTP 200 with `valid: False` and informative `signal_reason`.
3. **Protecting `GET /history/{kode}`**:
   - Wrapping `fetch_trading_info` in `try...except (YahooClientError, IdxTradingError) as e:` and raising `HTTPException(status_code=502, detail=f"Gagal ambil data historis {kode}: {e}")` aligns `/history/{kode}` with `/analisis/{kode}` and `/recovery/{kode}`.
4. **Adding ISO Date Validation Helper**:
   - Implemented `validate_query_date(target_date: str | None) -> str | None`. It validates `date.fromisoformat(target_date)` inside a `try...except ValueError` block and raises `HTTPException(status_code=400, detail="Format tanggal tidak valid")` for invalid calendar dates (e.g. `2026-99-99`, `2026-02-30`), while strings violating `^\d{4}-\d{2}-\d{2}$` continue to be rejected by FastAPI with HTTP 422.
   - Integrated `validate_query_date` across all 10 endpoints receiving `date` query parameters (`/gainers`, `/analisis/{kode}`, `/history/{kode}`, `/recovery/{kode}`, `/gorengan`, `/readytofly`, `/scrape/all`, `/scrape`, `/scrape/gorengan`, `/scrape/readytofly`).
5. **Defensive Cache Handling**:
   - In `GET /gainers`, `GET /gorengan`, and `GET /readytofly`, wrapped cache retrieval and dictionary unpacking in `try...except Exception`. If cache files are missing, corrupted, or unparseable, endpoints return HTTP 404 cleanly instead of crashing with HTTP 500.
6. **Modernizing `backend/test_api.py`**:
   - Rewrote into a structured pytest suite with 35 test functions across 8 categories:
     - `test_market_status`: status 200, `is_open` boolean, market hours.
     - `test_gainers_*`: valid cache (200), missing cache (404), corrupted cache (404), valid date query.
     - `test_analisis_*`: valid ticker (200), presence and contents of `pattern_candles`, unknown ticker (404), insufficient data (404), upstream network failure (502), invalid capital `capital <= 0` (422).
     - `test_history_*`: valid ticker (200), unknown ticker (404), upstream Yahoo failure (502), upstream IDX failure (502), invalid length (422).
     - `test_recovery_*`: valid ticker (200), short history with `drop_pct: None` (200 without 500), unknown ticker (404), upstream failure (502).
     - `test_gorengan_*` and `test_readytofly_*`: valid cache (200), missing cache (404), corrupted cache (404).
     - Boundary validation: invalid calendar dates (`2026-99-99`, `2026-02-30`, etc.) return HTTP 400; regex-violating dates return HTTP 422.
     - `test_scraped_dates`: cache date inspection (200).
   - Utilized pytest `monkeypatch` to mock external network sources and local filesystem cache, ensuring deterministic, fast, offline test execution (< 4 seconds).
   - Added CLI runner support so tests can be run either via `pytest backend/test_api.py -v` or `python backend/test_api.py`.

---

## 3. Caveats

- **External Live Scrape Endpoints**:
  The heavy live scraper endpoints (`POST /scrape/all`, `POST /scrape`, etc.) execute multi-ticker network fetches. While protected with `validate_query_date`, triggering full live market scans in production should ideally run as background tasks or Celery jobs if IDX/Yahoo API latency is high.
- **Write Ownership**:
  Changes were strictly restricted to `backend/api.py` and `backend/test_api.py`. No other backend files or frontend components were altered.

---

## 4. Conclusion

Milestone M2 tasks are 100% complete:
- `backend/api.py` is fully hardened against unhandled 500 errors, response validation mismatches, network upstream failures, corrupted caches, and invalid calendar dates.
- `pattern_candles` is preserved and serialized through Pydantic v2 in `/analisis/{kode}`.
- `backend/test_api.py` is modernized into a standard pytest suite with 35 test functions, achieving 100% pass rate in offline execution mode.

---

## 5. Verification Method

### Step 1: Syntax & Compilation Verification
```powershell
python -m py_compile backend/api.py backend/test_api.py
```
**Observed Result**: Exited with code 0 (no syntax errors).

### Step 2: Pytest Suite Execution
```powershell
python -m pytest backend/test_api.py -v
```
**Observed Result**:
```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-9.1.0, pluggy-1.6.0
rootdir: C:\CodeKuliah\SwingPredictionBot
collected 35 items

backend/test_api.py::test_market_status PASSED                           [  2%]
backend/test_api.py::test_gainers_success PASSED                         [  5%]
backend/test_api.py::test_gainers_not_found PASSED                       [  8%]
backend/test_api.py::test_gainers_corrupted_cache PASSED                 [ 11%]
backend/test_api.py::test_gainers_with_valid_date PASSED                 [ 14%]
backend/test_api.py::test_analisis_valid_ticker PASSED                   [ 17%]
backend/test_api.py::test_analisis_unknown_ticker PASSED                 [ 20%]
backend/test_api.py::test_analisis_insufficient_data PASSED              [ 22%]
backend/test_api.py::test_analisis_upstream_error PASSED                 [ 25%]
backend/test_api.py::test_analisis_invalid_capital PASSED                [ 28%]
backend/test_api.py::test_history_valid_ticker PASSED                    [ 31%]
backend/test_api.py::test_history_unknown_ticker PASSED                  [ 34%]
backend/test_api.py::test_history_upstream_network_failure PASSED        [ 37%]
backend/test_api.py::test_history_upstream_idx_failure PASSED            [ 40%]
backend/test_api.py::test_history_invalid_length PASSED                  [ 42%]
backend/test_api.py::test_recovery_valid_ticker PASSED                   [ 45%]
backend/test_api.py::test_recovery_short_history_no_500 PASSED           [ 48%]
backend/test_api.py::test_recovery_unknown_ticker PASSED                 [ 51%]
backend/test_api.py::test_recovery_upstream_error PASSED                 [ 54%]
backend/test_api.py::test_gorengan_success PASSED                        [ 57%]
backend/test_api.py::test_gorengan_not_found PASSED                      [ 60%]
backend/test_api.py::test_gorengan_corrupted_cache PASSED                [ 62%]
backend/test_api.py::test_readytofly_success PASSED                      [ 65%]
backend/test_api.py::test_readytofly_not_found PASSED                    [ 68%]
backend/test_api.py::test_readytofly_corrupted_cache PASSED              [ 71%]
backend/test_api.py::test_boundary_invalid_calendar_dates[2026-99-99] PASSED [ 74%]
backend/test_api.py::test_boundary_invalid_calendar_dates[2026-02-30] PASSED [ 77%]
backend/test_api.py::test_boundary_invalid_calendar_dates[2026-13-01] PASSED [ 80%]
backend/test_api.py::test_boundary_invalid_calendar_dates[2026-04-31] PASSED [ 82%]
backend/test_api.py::test_boundary_regex_failing_dates[not-a-date] PASSED [ 85%]
backend/test_api.py::test_boundary_regex_failing_dates[2026/01/15] PASSED [ 88%]
backend/test_api.py::test_boundary_regex_failing_dates[15-01-2026] PASSED [ 91%]
backend/test_api.py::test_boundary_regex_failing_dates[2026-1-1] PASSED  [ 94%]
backend/test_api.py::test_boundary_regex_failing_dates[2026-001-01] PASSED [ 97%]
backend/test_api.py::test_scraped_dates PASSED                           [100%]

============================= 35 passed in 3.54s ==============================
```

### Step 3: Direct Python Runner Execution
```powershell
python backend/test_api.py
```
**Observed Result**: 35 passed in 1.01s (exit code 0).
