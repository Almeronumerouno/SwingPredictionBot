# Handoff Report: Backend API & Test Suite Comprehensive Survey

**Agent**: `explorer_survey_2`  
**Date**: 2026-09-21  
**Scope**: `backend/api.py`, `backend/test_api.py`, `backend/requirements.txt`, and related data-source/model layers.  

---

## 1. Observation

### 1.1 Python Syntax & Module Imports
- **`backend/api.py`** and **`backend/test_api.py`**:
  Both files adhere to standard Python 3.10+ syntax (e.g. pipe unions `float | None`, type hints `dict[str, Any]`, FastAPI endpoint decorators).
- **Missing Dependencies in `backend/requirements.txt`**:
  `backend/requirements.txt` currently specifies only:
  ```text
  cloudscraper>=1.2.71
  pandas>=2.0
  numpy>=1.24
  python-dotenv>=1.0
  yfinance>=0.2.40
  fastapi>=0.115
  uvicorn[standard]>=0.34
  ```
  However, critical imports across the backend require libraries NOT present in `requirements.txt`:
  1. `backend/test_api.py:3`: `from fastapi.testclient import TestClient` requires **`httpx`**. Without `httpx`, creating a `TestClient` fails at runtime with `RuntimeError: The testclient requires the httpx library to be installed`.
  2. `backend/data_source/idx_client.py:12` and `backend/data_source/idx_trading.py:17`: `from curl_cffi import requests` unconditionally imports **`curl_cffi`**.
  3. Running automated tests in a standard CI pipeline requires **`pytest`**, which is unlisted.

---

### 1.2 Endpoint Audit & Error Handling

#### Endpoint 1: `GET /market-status` (`backend/api.py:693-716`)
- **Signature**: `@app.get("/market-status", response_model=MarketStatusResponse)`
- **Behavior**: Evaluates current time in `ZoneInfo("Asia/Jakarta")` (WIB) against weekday and market hours (09:00 - 15:00 WIB).
- **Error Handling**: Pure in-memory calculation; zero external network or database calls. Completely stable and exception-free.

#### Endpoint 2: `GET /gainers` (`backend/api.py:808-834`)
- **Signature**: `@app.get("/gainers", response_model=GainersResponse)`
- **Parameters**: `date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")`
- **Behavior**: Calls `get_cached_gainers(for_date=date)`. If file is missing, returns HTTP 404 (`"Belum ada data gainers untuk tanggal {label}."`).
- **Error Handling**: Wrapped in `try...except Exception as e:` returning HTTP 500 (`"Gagal membaca data gainers."`).

#### Endpoint 3: `GET /analisis/{kode}` (`backend/api.py:836-867`)
- **Signature**: `@app.get("/analisis/{kode}", response_model=AnalisisResponse)`
- **Parameters**:
  - `kode: str` (path parameter; `.strip().upper()` applied at line 842).
  - `capital: float = Query(config.DEFAULT_CAPITAL, gt=0)`.
  - `date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")`.
- **Validation & Exception Handling**:
  - Validates `kode` against `securities = get_or_fetch_securities_list()`. If not found, returns HTTP 404 (lines 846-850).
  - Catches `InsufficientDataError` -> returns HTTP 404 (lines 857-858).
  - Catches `(YahooClientError, IdxTradingError)` -> returns HTTP 502 (lines 859-863).
- **CRITICAL DEFECT — Response Serialization Strips `pattern_candles`**:
  In `analyze_stock` (`backend/api.py:557-581`):
  ```python
  557: lookback = min(3, len(close))
  558: pattern_candles = [
  559:     {
  560:         "open": float(open_[-lookback + i]),
  561:         "high": float(high[-lookback + i]),
  562:         "low": float(low[-lookback + i]),
  563:         "close": float(close[-lookback + i]),
  564:     }
  565:     for i in range(lookback)
  566: ]
  ...
  581:     "pattern_candles": pattern_candles
  ```
  However, in `RawIndicatorsResponse` (`backend/api.py:94-108`):
  ```python
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
      # NOTE: pattern_candles is completely missing!
  ```
  Because `response_model=AnalisisResponse` serializes through Pydantic v2 (default `extra="ignore"`), `pattern_candles` is **silently dropped from the JSON response**.
  Meanwhile, the frontend in `frontend/types/api.ts:64` and `frontend/components/technical-indicators.tsx:333` explicitly expects `data.pattern_candles` to render candlestick pattern visuals.

#### Endpoint 4: `GET /history/{kode}` (`backend/api.py:870-895`)
- **Signature**: `@app.get("/history/{kode}", response_model=HistoryResponse)`
- **Parameters**:
  - `kode: str` (path parameter)
  - `length: int = Query(config.HISTORY_LOOKBACK_DAYS, gt=0, le=config.MAX_HISTORY_QUERY_DAYS)`
  - `date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")`
- **CRITICAL DEFECT — Missing Exception Handling (Unhandled 500)**:
  Lines 884-890:
  ```python
  884: bars = fetch_trading_info(kode, length=length, target_date=date)
  885: 
  886: if not bars:
  887:     raise HTTPException(
  888:         status_code=502,
  889:         detail=f"Gagal ambil data historis {kode} dari Yahoo.",
  890:     )
  ```
  Unlike `/analisis/{kode}` and `/recovery/{kode}`, `/history/{kode}` **DOES NOT** wrap `fetch_trading_info` in `try...except (YahooClientError, IdxTradingError)`.
  If Yahoo Finance rate-limits, drops connection, or encounters network failure, `fetch_trading_info` raises `YahooClientError`, resulting in an **unhandled HTTP 500 crash**.

#### Endpoint 5: `GET /recovery/{kode}` (`backend/api.py:898-932`)
- **Signature**: `@app.get("/recovery/{kode}", response_model=RecoveryResponse)`
- **Parameters**:
  - `kode: str`
  - `drop_pct: float | None = Query(None, gt=0, le=50)`
  - `date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")`
  - `ref_days: int | None = Query(None, ge=1, le=252)`
- **CRITICAL DEFECT — Response Validation Error (500) on Insufficient Historical Bars**:
  In `RecoveryResponse` (`backend/api.py:300`):
  ```python
  class RecoveryResponse(BaseModel):
      kode: str
      nama: str
      valid: bool
      ...
      drop_pct: float   # <--- NOT OPTIONAL / NON-NULLABLE!
  ```
  In `backend/recovery.py:1040, 1057-1062`:
  ```python
  1040: base = { ... "drop_pct": drop_pct, ... }
  ...
  1057: if len(close) < config.RECOVERY_MIN_BARS:
  1058:     base["signal_reason"] = (
  1059:         f"Data historis cuma {len(close)} bar, minimal {config.RECOVERY_MIN_BARS} "
  1060:         "untuk estimasi GBM yang stabil."
  1061:     )
  1062:     return base
  ```
  When a stock has fewer than `config.RECOVERY_MIN_BARS` (e.g. newly listed or thinly traded), and `drop_pct` query parameter is omitted (default `None`), `base["drop_pct"]` remains `None`.
  FastAPI's Pydantic response serializer validates `base` against `RecoveryResponse`, detects `None` for non-nullable `drop_pct: float`, and raises an internal `ResponseValidationError` (HTTP 500).

#### Endpoint 6: `GET /readytofly` (`backend/api.py:1005-1066`) & `GET /gorengan` (`backend/api.py:948-980`)
- **Parameters**: `date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")`
- **Behavior**: Reads JSON cache from `backend/cache/`. If cache is missing, returns HTTP 404.
- **Vulnerability**: Neither endpoint wraps `get_cached_gorengan` or `get_cached_ready_to_fly` in `try...except Exception`. If a cache file is corrupted, truncated during concurrent write, or contains invalid JSON, the endpoint crashes with an unhandled HTTP 500.

#### Endpoint 7: Calendar Date Format Bypass (Across All Endpoints with Date Parameter)
- All date queries use `pattern=r"^\d{4}-\d{2}-\d{2}$"`.
- A query string like `?date=2026-99-99` or `?date=2026-02-30` passes the regex regex check.
- When `date.fromisoformat(target_date)` is subsequently executed in `analyze_stock` (`api.py:417`), `readytofly_scanner.py:192`, or `yahoo_client.py:118`, it raises `ValueError: Invalid isoformat string`.
- Because `ValueError` is uncaught by endpoint route handlers, this causes an **unhandled HTTP 500** instead of HTTP 400 or HTTP 422.

#### Supplementary Endpoints (Scraper Triggers & Cache Inspection)
- `GET /scraped-dates` (`api.py:719`): Stable; inspects cache directory and returns available dates per category.
- `POST /scrape/all`, `POST /scrape`, `POST /scrape/gorengan`, `POST /scrape/readytofly`:
  All execute heavy synchronous market-wide scans (fetching hundreds to thousands of ticker bars) within the request thread. They catch general exceptions and return 500, but block request execution for 2 to 10 minutes, making them prone to client/proxy timeouts.

---

### 1.3 `backend/test_api.py` Inspection
- **Code Style & Runner Compatibility**:
  `backend/test_api.py` is written as a procedural, imperative Python script rather than a standard test suite:
  - It contains zero `test_*` functions or `Test*` classes.
  - If executed with `pytest backend/test_api.py`, pytest reports `collected 0 items`.
- **Lack of Assertions (False Confidence)**:
  - Out of 9 test sections, 8 sections use `print()` statements and conditional strings (`"PASS"` / `"FAIL"`).
  - Only Section 9 (`GET /scraped-dates`) contains an actual assertion (`assert r.status_code == 200`).
  - If `/analisis/BBCA` returns a 500 crash or unexpected status, the script simply prints `FAIL` and proceeds to exit with status code 0. A CI pipeline will report green even when endpoints crash!
- **External Network Tight-Coupling**:
  - The script makes live HTTP requests to Yahoo Finance for `BBCA`, `ASII`, `TLKM`.
  - When run offline, or during Yahoo Finance API disruption or rate limiting, the test script fails or hangs.
- **Coverage Deficit**:
  - Missing tests for: `/market-status`, `/recovery/{kode}`, `/readytofly`, `/gorengan`, `/scrape/all`, `/scrape`, `/scrape/gorengan`, `/scrape/readytofly`.
  - Missing boundary validation tests (e.g. invalid calendar dates `2026-99-99`, zero volume, negative lookback, empty cache handling).

---

## 2. Logic Chain

1. **Premise 1 (Response Schema Integrity)**:
   - `frontend/components/technical-indicators.tsx:333` binds `realCandles={data.pattern_candles}`.
   - `api.py:581` outputs `"pattern_candles": pattern_candles` inside the `raw_indicators` payload.
   - However, `RawIndicatorsResponse` (`api.py:94-108`) does not declare `pattern_candles: list[dict] | None = None`.
   - In Pydantic v2 / FastAPI serialization, undeclared fields are excluded.
   - **Conclusion 1**: The frontend receives `undefined` for `pattern_candles`, causing technical pattern chart components to receive no candle data.

2. **Premise 2 (Runtime Stability of `/history/{kode}`)**:
   - Network interactions with external APIs (Yahoo Finance, IDX) are inherently fallible (timeouts, rate limits, 503s).
   - In `backend/api.py`, `/analisis/{kode}` and `/recovery/{kode}` catch `(YahooClientError, IdxTradingError)` and convert them to HTTP 502 Bad Gateway.
   - `/history/{kode}` (`api.py:884`) invokes `fetch_trading_info` without a `try...except` block.
   - **Conclusion 2**: Any network error or Yahoo Finance failure during history retrieval causes an unhandled 500 internal server error.

3. **Premise 3 (Runtime Stability of `/recovery/{kode}`)**:
   - `recovery.py:1057-1062` returns early with `base` when `len(close) < config.RECOVERY_MIN_BARS`.
   - In that early return, `base["drop_pct"]` is `None` (if no `drop_pct` query parameter was passed).
   - `api.py:300` enforces `drop_pct: float` (non-nullable).
   - FastAPI validates the returned dictionary against `RecoveryResponse`.
   - **Conclusion 3**: Querying `/recovery/{kode}` for any stock with short trading history (e.g. < 60 days) triggers a FastAPI `ResponseValidationError` (HTTP 500).

4. **Premise 4 (Test Suite Viability & CI/CD Readiness)**:
   - Automated testing relies on pytest discovery conventions (`test_*` functions) and non-zero exit codes upon failure (`assert`).
   - `test_api.py` has no `test_*` functions and only prints failure strings without raising exceptions or asserting.
   - `httpx` and `pytest` are missing from `requirements.txt`.
   - **Conclusion 4**: The existing test suite cannot be run reliably by pytest or integrated into CI pipelines, and live network calls make it non-deterministic.

---

## 3. Caveats

1. **No Live Execution of `run_command` in This Session**:
   Interactive permissions for `run_command` timed out during agent initialization; all findings were derived from deep static analysis, AST inspection, cross-referencing frontend/backend contracts, and inspecting cached bytecode metadata (`__pycache__`).
2. **Local Cache Presence**:
   Endpoints relying on cache (`/gainers`, `/gorengan`, `/readytofly`, `/scraped-dates`) depend on files in `backend/cache/`. In fresh clone environments without pre-scraped data, these endpoints appropriately return 404 until a scrape is run.
3. **Yahoo Finance API Volatility**:
   Yahoo Finance is an unofficial data source susceptible to upstream changes, user-agent blocks, and intermittent delays.

---

## 4. Conclusion

The FastAPI backend has sound core mathematical engines (indicators, scoring, risk calculation, recovery GBM), but suffers from four high-impact architectural and error-handling flaws:
1. **Schema Mismatch**: `RawIndicatorsResponse` drops `pattern_candles`, breaking frontend candlestick visualizers.
2. **Unhandled 500s**:
   - `/history/{kode}` lacks `try...except (YahooClientError, IdxTradingError)`.
   - `/recovery/{kode}` crashes with `ResponseValidationError` on short-history tickers due to non-nullable `drop_pct: float`.
   - Malformed calendar dates (e.g. `2026-99-99`) pass regex and crash with unhandled `ValueError`.
3. **Missing Critical Dependencies**: `httpx`, `curl_cffi`, and `pytest` are omitted from `backend/requirements.txt`.
4. **Test Suite Deficiencies**: `backend/test_api.py` is an un-asserted procedural script that cannot be executed by pytest, hits live external networks, and misses more than 50% of the endpoint surface.

---

## 5. Verification Method & Actionable Fix Recommendations

### 5.1 Proposed Code Modifications

#### A. Fix `RawIndicatorsResponse` in `backend/api.py`
Add `PatternCandleBar` and include `pattern_candles` in `RawIndicatorsResponse`:
```python
class PatternCandleBar(BaseModel):
    open: float
    high: float
    low: float
    close: float

class RawIndicatorsResponse(BaseModel):
    ...
    candlestick_patterns: list[str]
    pattern_candles: list[PatternCandleBar] | list[dict] | None = None
```

#### B. Fix `RecoveryResponse.drop_pct` in `backend/api.py`
Make `drop_pct` nullable to prevent `ResponseValidationError` when data is insufficient:
```python
class RecoveryResponse(BaseModel):
    ...
    distance_pct: float | None
    drop_pct: float | None = None
    drop_source: str
```

#### C. Protect `GET /history/{kode}` in `backend/api.py`
Wrap `fetch_trading_info` with proper exception handling:
```python
    try:
        bars = fetch_trading_info(kode, length=length, target_date=date)
    except (YahooClientError, IdxTradingError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gagal ambil data historis {kode}: {e}",
        )
```

#### D. Validate Calendar Dates Globally
Catch `ValueError` when parsing `date.fromisoformat(target_date)` or define a custom Pydantic/FastAPI validator:
```python
def validate_iso_date(target_date: str | None) -> str | None:
    if not target_date:
        return None
    try:
        date.fromisoformat(target_date)
        return target_date
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tanggal '{target_date}' bukan format kalender valid (YYYY-MM-DD).")
```

#### E. Update `backend/requirements.txt`
Add the missing runtime and test dependencies:
```text
cloudscraper>=1.2.71
pandas>=2.0
numpy>=1.24
python-dotenv>=1.0
yfinance>=0.2.40
fastapi>=0.115
uvicorn[standard]>=0.34
curl_cffi>=0.15.0
httpx>=0.27.0
pytest>=8.0.0
```

#### F. Modernize `backend/test_api.py`
Refactor into formal pytest test cases with mocks:
```python
import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_market_status():
    r = client.get("/market-status")
    assert r.status_code == 200
    assert "is_open" in r.json()

def test_history_invalid_ticker():
    r = client.get("/history/NONEXISTENTTICKER")
    assert r.status_code == 404

def test_analisis_invalid_capital():
    r = client.get("/analisis/BBCA", params={"capital": 0})
    assert r.status_code == 422
```

### 5.2 Independent Verification Instructions
1. Run syntax compilation check:
   `python -m py_compile backend/api.py backend/test_api.py`
2. Test import resolution in virtual environment:
   `python -c "import httpx, curl_cffi; from api import app; print('Imports OK')"`
3. Execute modernized test suite:
   `pytest backend/test_api.py -v`
