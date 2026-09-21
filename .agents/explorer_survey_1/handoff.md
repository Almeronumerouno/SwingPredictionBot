# Comprehensive Calculation Modules Survey Report

**Author**: `explorer_survey_1`  
**Date**: 2026-09-21  
**Scope**: Core backend calculation modules in `backend/` (`indicators.py`, `scoring.py`, `risk.py`, `recovery.py`, `gorengan.py`, `backtest.py`, `walkforward.py`)

---

## 1. Observation

Direct code inspections of the target modules revealed several critical edge-case runtime exceptions, type handling bugs, and architectural integration risks.

### 1.1 `backend/indicators.py`
- **File**: `backend/indicators.py` (871 lines)
- **Lines 90–92 (`true_range`)**:
  ```python
  90:     n = len(high)
  91:     tr = np.empty(n)
  92:     tr[0] = high[0] - low[0]
  ```
  If `len(high) == 0` (empty array/DataFrame), `tr[0]` immediately raises `IndexError: index 0 is out of bounds for axis 0 with size 0`.
- **Line 101–104 (`atr`) & Line 156 (`adx`)**:
  Both invoke `true_range(high, low, close)` unconditionally. Neither checks `len(high) == 0`, propagating the `IndexError`.
- **Lines 226–231 (`mfi`)**:
  ```python
  226:     n = len(close)
  228:     typical_price = (high + low + close) / 3.0
  ...
  231:     tp_delta = np.diff(typical_price, prepend=typical_price[0])
  ```
  If `len(close) == 0`, `typical_price[0]` immediately raises `IndexError: index 0 is out of bounds for axis 0 with size 0`.
- **Lines 369–370 (`support_resistance_levels`)**:
  ```python
  369:             last_cluster_mean = np.mean(clusters[-1])
  370:             if abs(p - last_cluster_mean) / last_cluster_mean * 100 <= tolerance_pct:
  ```
  If `last_cluster_mean == 0.0` (penny stock or uninitialized/zero price), line 370 raises `ZeroDivisionError: float division by zero`.
- **Lines 631, 637, 641, 647 (`candlestick_patterns`)**:
  ```python
  631:             if abs(c_high - p_high) / max(c_high, p_high) <= 0.01:
  637:             if abs(c_low - p_low) / max(c_low, p_low) <= 0.01:
  641:             if abs(c_close - p_low) / max(c_close, p_low) <= 0.01:
  ```
  If both prices evaluated are `0.0` (zero price or halted), `max(c_high, p_high) == 0`, triggering `ZeroDivisionError`.

### 1.2 `backend/scoring.py`
- **File**: `backend/scoring.py` (226 lines)
- **Lines 30–34 (`_volume_score`)**:
  ```python
  30: def _volume_score(rvol: np.ndarray, close: np.ndarray) -> np.ndarray:
  31:     sign = np.where(close > np.roll(close, 1), 1.0, -1.0)
  32:     sign[0] = 0.0
  ```
  If `len(close) == 0`, line 32 raises `IndexError: index 0 is out of bounds for axis 0 with size 0`.
- **Lines 147–160 (`compute_score` dictionary input expectations)**:
  ```python
  147:     close = data["close"]
  148:     rsi = data["rsi"]
  149:     atr_arr = data["atr"]
  150:     adx_arr = data["adx"]
  151:     mfi_arr = data["mfi"]
  152:     rvol_arr = data["rvol"]
  153:     ema_fast = data["ema_fast"]
  154:     ema_slow = data["ema_slow"]
  155:     donch_upper = data["donchian_upper"]
  156:     donch_lower = data["donchian_lower"]
  ```
  Uses hard dictionary lookups `data["key"]` without defensive fallback or validation. If any key is missing, raises `KeyError`.
- **Lines 171–173 (`compute_score`)**:
  ```python
  171:     i = -1
  172:     if any(np.isnan(x[i]) for x in (trend_scores, momentum_scores, volume_scores, pa_scores)):
  ```
  If `len(close) == 0`, `trend_scores` has length 0, causing `x[-1]` to raise `IndexError`.
- **Line 209 (`compute_score`)**:
  ```python
  209:     gate_i = float(_gate_adx(adx_arr)[-1]) if not np.isnan(adx_arr[-1]) else 0.0
  ```
  If `len(adx_arr) == 0`, `adx_arr[-1]` raises `IndexError`.
- **Line 140–142 (`_price_stagnation_gate`)**:
  ```python
  140:     if recent_high == recent_low or close[-1] == 0:
  141:         return True
  142:     range_pct = (recent_high - recent_low) / close[-1]
  ```
  If `close[-1]` is NaN, `recent_high == recent_low` is False, `close[-1] == 0` is False, but `range_pct` becomes NaN.

### 1.3 `backend/risk.py`
- **File**: `backend/risk.py` (110 lines)
- **Lines 62–63 (`build_trade_plan`) vs NaN handling**:
  ```python
  62:     if atr is None or atr <= 0:
  63:         return None
  ```
  In Python IEEE 754 float semantics:
  `float('nan') <= 0` evaluates to `False`.
  If `atr` is `np.nan`, it passes line 62 undetected.
  Then:
  Line 73: `sl = _stop_loss(...)` returns `NaN`.
  Line 74: `tp = _take_profit(...)` returns `NaN`.
  Line 40–41: `per_share_risk = abs(entry - stop_loss)` becomes `NaN`.
  Line 41: `if per_share_risk <= 0 or entry <= 0:` evaluates `NaN <= 0` to `False`!
  Line 44: `lots = int(capital / entry) // LOT_SIZE`
  Line 45: `shares = lots * LOT_SIZE`
  Line 50: `risk_amt = per_share_risk * shares` becomes `NaN`.
  Line 54:
  ```python
  54:         f" · risiko bila kena SL: Rp {risk_amt:,.0f} ({risk_pct_actual*100:.2f}% modal)"
  ```
  In Python, string formatting with comma separator on a NaN float (`f"{float('nan'):,.0f}"`) raises `ValueError: Cannot specify ',' with 's' or float NaN format`. This generates an unhandled 500 server crash in `api.py:503-508`.
- **Line 44 (`_position_shares`) & Line 91 (`build_trade_plan`)**:
  ```python
  44:     lots = int(capital / entry) // LOT_SIZE
  ...
  91:     "note": f"Butuh minimal Rp {int(entry_price * LOT_SIZE):,} untuk 1 lot"
  ```
  If `capital` or `entry_price` is `np.nan`, `int(NaN)` raises `ValueError: cannot convert float NaN to integer`.

### 1.4 `backend/recovery.py`
- **File**: `backend/recovery.py` (1224 lines)
- **Lines 206, 209, 213 (`_load_recovery_model_params`)**:
  ```python
  205:             print("recovery.py: REFUSED — provenance.locked != True "
  206:                   "(P7.4 hard guard); model recovery nonaktif.", file=sys.stderr)
  ...
  209:             print("recovery.py: REFUSED — provenance tidak lengkap (P7.4); "
  210:                   "model recovery nonaktif.", file=sys.stderr)
  ...
  212:             print("recovery.py: REFUSED — parameter_hash mismatch (P7.4); "
  213:                   "model recovery nonaktif.", file=sys.stderr)
  ```
  `sys` is NOT imported anywhere in `backend/recovery.py`!
  Top imports are:
  ```python
  import hashlib
  import math
  import os
  import json
  import numpy as np
  from typing import Optional
  import numpy as np
  import config
  import indicators as ind
  ```
  When any validation guard fails, executing `file=sys.stderr` raises `NameError: name 'sys' is not defined`. While swallowed by the outer `except Exception:` on line 217, it suppresses proper logging and conceals provenance verification failures.
- **Lines 648–655 (`detect_accumulation`)**:
  ```python
  647:             base = post_cum[cnt] / cnt  # mean(volume[anchor+1 : i])
  ...
  655:         heavy[i] = volume[i] >= config.ACCUM_HEAVY_RVOL * base
  ```
  If a stock is inactive/illiquid post-event such that `base == 0` and `volume[i] == 0`, `0 >= 2.0 * 0` evaluates to `0 >= 0` which is `True`. Days with zero traded volume are erroneously marked as `heavy=True` accumulation days.

### 1.5 `backend/gorengan.py`
- **File**: `backend/gorengan.py` (581 lines)
- **Lines 149–167 (`_liquidity_risk`)**:
  ```python
  149:     lookback = min(60, len(close))
  150:     daily_value = close[-lookback:] * volume[-lookback:]
  151:     median_value = np.median(daily_value)
  ...
  161:     else:
  162:         score = 100.0
  163: 
  164:     warning = None
  165:     if score > 50:
  166:         med_million = median_value / 1e6
  167:         warning = f"Saham pada dasarnya sepi/tidak likuid (median transaksi normal: Rp{med_million:,.0f}jt) — sangat mudah disetir bandar"
  ```
  If `len(close) == 0` (or `daily_value` is all NaNs), `np.median([])` returns `np.nan`.
  The comparisons on lines 153–160 all fail (`NaN > X` is False), leading to `score = 100.0`.
  Because `score > 50`, line 166 sets `med_million = np.nan / 1e6 = np.nan`.
  Line 167 then runs `f"Rp{med_million:,.0f}jt"`, which crashes with `ValueError: Cannot specify ',' with 's' or float NaN format`.
- **Line 134 (`_momentum`) & Line 412 (`_active_pump`)**:
  ```python
  134:     mom_val = (close[-1] - close[-1 - n]) / close[-1 - n] * 100
  ...
  412:             ret = (close[-1] - close[-1 - lookback]) / close[-1 - lookback] * 100
  ```
  If `close[-1 - n] == 0` or `close[-1 - lookback] == 0`, raises `ZeroDivisionError: float division by zero`.

### 1.6 `backend/backtest.py`
- **File**: `backend/backtest.py` (971 lines)
- **Lines 269–270 (`compute_signals`)**:
  ```python
  269:     sign = np.where(close > np.roll(close, 1), 1.0, -1.0)
  270:     sign[0] = 0.0
  ```
  If `len(close) == 0`, `sign[0] = 0.0` raises `IndexError: index 0 is out of bounds for axis 0 with size 0`.
- **Lines 468, 639, 648, 676, 691 (`run_backtest`)**:
  ```python
  468:             ret_mtm = (close[i] / pos["entry_price"] - 1)
  639:                 ret = (exit_price_candidate - pos["entry_price"]) / pos["entry_price"]
  648:                 net_ret = ret - fee_buy_rate - fee_sell_rate * (exit_price_candidate / pos["entry_price"])
  ```
  If bad market data contains an entry price of 0 (`pos["entry_price"] <= 0`), raises `ZeroDivisionError`.
- **Line 717 & Line 721 (`run_backtest` metrics calculation)**:
  ```python
  717:     total_return = (equity / capital - 1) * 100
  721:     buy_hold_ret = (buy_end - buy_start) / buy_start * 100
  ```
  If `capital == 0` or `buy_start == 0`, raises `ZeroDivisionError`.
- **Line 752 (`run_backtest`)**:
  ```python
  752:     total_calendar = (datetime.strptime(dates[last_idx], "%Y-%m-%d") - datetime.strptime(dates[warmup], "%Y-%m-%d")).days if dates else 0
  ```
  Hardcoded date format `%Y-%m-%d`. If timestamps are provided (e.g. `2026-09-21T00:00:00` or `str(ts)`), raises `ValueError: time data '...' does not match format '%Y-%m-%d'`.

### 1.7 `backend/walkforward.py`
- **File**: `backend/walkforward.py` (461 lines)
- **Line 18 (`walkforward.py`) vs `backend/requirements.txt`**:
  ```python
  18: from sklearn.metrics import roc_auc_score
  ```
  Checking `backend/requirements.txt` revealed:
  ```
  cloudscraper>=1.2.71
  pandas>=2.0
  numpy>=1.24
  python-dotenv>=1.0
  yfinance>=0.2.40
  fastapi>=0.115
  uvicorn[standard]>=0.34
  ```
  `scikit-learn` is completely missing from `requirements.txt`. Any fresh build or virtual environment running `pip install -r backend/requirements.txt` will fail to import `walkforward.py` with `ModuleNotFoundError: No module named 'sklearn'`.
- **Lines 386–389 (`walkforward.py`)**:
  ```python
  386:     precs = [r.oos_precision for r in all_results if r.oos_precision is not None]
  387:     aucs = [r.oos_auc_win for r in all_results if r.oos_auc_win is not None]
  388:     precs = [r.oos_precision for r in all_results if r.oos_precision is not None]
  389:     aucs = [r.oos_auc_win for r in all_results if r.oos_auc_win is not None]
  ```
  Redundant code duplication in reporting routine.

---

## 2. Logic Chain

### 2.1 The NaN Cascade Bug in Trade Planning
1. **Observation**: `risk.build_trade_plan` guards ATR only with `if atr is None or atr <= 0: return None`.
2. **Fact**: In Python and IEEE 754 float math, `math.isnan(atr)` evaluates `atr <= 0` as `False`.
3. **Inference**: If `atr_val[-1]` is `np.nan` (which occurs whenever market data has fewer than 15 bars, or if historical data contains NaN gaps), `atr` passes into calculation.
4. **Consequence**: Stop loss, take profit, and per-share risk all become `NaN`. The condition `if per_share_risk <= 0 or entry <= 0:` evaluates to `False`, allowing `_position_shares` to proceed.
5. **Impact**: `risk_amt` becomes `NaN`, and line 54 attempts string interpolation `f"Rp {risk_amt:,.0f}"`. Python raises a fatal `ValueError` on comma-formatting a NaN float, triggering an unhandled 500 error on `/analisis/{kode}`.
6. **Solution**: Guard ATR with `if atr is None or np.isnan(atr) or atr <= 0: return None`, and add defensive validation across `_position_shares`.

### 2.2 Boundary Condition Crash on Empty Arrays
1. **Observation**: `indicators.true_range` indexes `tr[0] = high[0] - low[0]`, `mfi` indexes `typical_price[0]`, `scoring._volume_score` indexes `sign[0] = 0.0`, and `scoring.compute_score` indexes `x[-1]`.
2. **Fact**: When input arrays have 0 elements, indexing any element raises `IndexError`.
3. **Inference**: If a stock has no trading data or if an empty slice is provided from upstream filtering, all downstream calculation engines immediately crash with tracebacks rather than returning clean empty or `valid: False` dictionaries.
4. **Solution**: Guard each function with `if len(arr) == 0: return np.full(0, np.nan)` or `return {"valid": False, ...}`.

### 2.3 Undocumented Library Dependency
1. **Observation**: `walkforward.py:18` imports `sklearn.metrics.roc_auc_score`.
2. **Fact**: `scikit-learn` is absent from `backend/requirements.txt`.
3. **Inference**: Automated CI/CD pipelines, Docker container builds, or production instances deploying from `requirements.txt` will crash immediately upon importing `walkforward.py`.
4. **Solution**: Either add `scikit-learn>=1.3` to `backend/requirements.txt` or implement an optional lazy-import fallback in `walkforward.py`.

---

## 3. Caveats

1. **Static Analysis Focus**: Because interactive terminal commands timed out awaiting user confirmation, all findings were derived from comprehensive static source code analysis, syntax parsing, and line-by-line tracing of the 7 modules, cross-referenced with `api.py`, `portfolio.py`, `regime.py`, and `config.py`.
2. **Upstream Data Assumptions**: `api.py:analyze_stock()` currently relies on `MIN_TRADING_DAYS = 150` to shield `compute_score` and `build_trade_plan` from short series during normal API calls. However, direct callers, test suites, scanner scripts (`gorengan_scanner.py`, `readytofly_scanner.py`), and backtests bypass this shield, exposing the uncovered edge cases.
3. **Read-Only Constraint**: In strict adherence to agent guidelines, no source code was modified or overwritten. All findings are packaged as actionable recommendations and diff proposals.

---

## 4. Conclusion

The core calculation modules are conceptually sound and quantitatively sophisticated, but they exhibit 5 classes of stabilization vulnerabilities:
1. **Unchecked IEEE 754 NaN formatting crashes**: Particularly in `risk.py` (`build_trade_plan`) and `gorengan.py` (`_liquidity_risk`).
2. **Unchecked array indexing on boundary conditions (0-length or single-bar)**: In `indicators.py`, `scoring.py`, `gorengan.py`, and `backtest.py`.
3. **Potential Division by Zero**: In `indicators.py` (`support_resistance_levels`, `candlestick_patterns`), `gorengan.py` (`_momentum`, `_active_pump`), and `backtest.py` (`ret_mtm`, `total_return`).
4. **Missing runtime dependency**: `scikit-learn` missing from `backend/requirements.txt`.
5. **Missing standard library import**: Missing `import sys` in `backend/recovery.py`.

---

## 5. Inter-Module Dependency Map & Interface Contracts

```
                       [ Market Data Source ]
                    (DailyBar / numpy OHLCV)
                                |
                                v
                      +-------------------+
                      |   indicators.py   | (Pure numpy: EMA, ATR, RSI, ADX,
                      +-------------------+  MFI, RVOL, Donchian, S/R, Candlestick)
                        /       |        \
                       /        |         \
                      v         v          v
          +---------------+ +-----------+ +------------------+
          |   regime.py   | |  risk.py  | |   gorengan.py    |
          +---------------+ +-----------+ +------------------+
                 |              ^           (7-component risk score,
                 v              |            Z-score & raw pump thresholds)
          +---------------+     |
          |  scoring.py   |-----+
          +---------------+ (TradePlan: SL, TP, Position sizing, RR ratio)
          (Weights from regime,
           Swing score 0-100,
           BUY/SELL/HOLD)
                 |
                 +-----------------------+
                 |                       |
                 v                       v
          +---------------+      +-------------------+
          |  recovery.py  |      |    backtest.py    |
          +---------------+      +-------------------+
          (Empirical base rates, (Full execution simulation:
           Logistic drawdown,     slippage, fees, SL/TP/reversal,
           Ready-to-fly accum)    mark-to-market equity curve)
                                         |
                                         v
                                 +--------------------+
                                 |  walkforward.py    |
                                 +--------------------+
                                 (Rolling train-test,
                                  grid optimization)
                                         |
                                         v
                                 +--------------------+
                                 |   portfolio.py     |
                                 +--------------------+
                                 (Multi-stock equity,
                                  Sharpe, Sortino, DD)
                                         |
                                         v
                                 +--------------------+
                                 |      api.py        |
                                 +--------------------+
```

### Interface Contracts:
- `scoring.compute_score(data: dict)` expects:
  - Required keys: `"close"`, `"rsi"`, `"atr"`, `"adx"`, `"mfi"`, `"rvol"`, `"ema_fast"`, `"ema_slow"`, `"donchian_upper"`, `"donchian_lower"`.
  - Optional keys: `"support"`, `"resistance"`, `"high"`, `"low"`.
  - Returns: `dict` with keys `valid`, `swing_score`, `components`, `recommendation`, `confidence`, `risk_level`, `regime`.
- `risk.build_trade_plan(score_result: dict, entry_price: float, atr: float, capital: float)`:
  - Returns `TradePlanResponse` dict or `None`.
- `gorengan.compute_gorengan(close, open_, high, low, volume, atr_arr, adx_arr, rvol_arr, shares, listing_board)`:
  - Returns `GorenganResponse` dict with `score`, `level`, `factors`, `warnings`, `explanation`.
- `recovery.build_recovery_analysis(code, nama, bars, drop_pct, ref_days, last_updated)`:
  - Returns `RecoveryResponse` dict.

---

## 6. Concrete Recommendations for Stabilization & Defensive Guards

### 6.1 Stabilization Fix 1: `backend/risk.py`
**Target File**: `backend/risk.py:59-63`
- **Issue**: `atr <= 0` allows `NaN` through, triggering `ValueError` on comma-formatting.
- **Proposed Patch**:
```python
def build_trade_plan(score_result: dict, entry_price: float, atr: float, capital: float, position_pct: float | None = None):
    if not score_result or not score_result.get("valid") or score_result.get("recommendation") == "HOLD":
        return None
    if atr is None or np.isnan(atr) or atr <= 0:
        return None
    if entry_price is None or np.isnan(entry_price) or entry_price <= 0:
        return None
    if capital is None or np.isnan(capital) or capital <= 0:
        return None
```
In `_position_shares`:
```python
    risk_amt = per_share_risk * shares
    if np.isnan(risk_amt) or np.isnan(per_share_risk):
        return 0, None
```

### 6.2 Stabilization Fix 2: `backend/gorengan.py`
**Target File**: `backend/gorengan.py:145-170`
- **Issue**: Empty `close` or `daily_value` makes `median_value` `NaN`, crashing string formatting `f"Rp{med_million:,.0f}jt"`.
- **Proposed Patch**:
```python
def _liquidity_risk(close: np.ndarray, volume: np.ndarray) -> tuple[float, str | None]:
    if len(close) == 0 or len(volume) == 0:
        return 0.0, None
    lookback = min(60, len(close))
    daily_value = close[-lookback:] * volume[-lookback:]
    valid_value = daily_value[~np.isnan(daily_value)]
    if len(valid_value) == 0:
        return 0.0, None
    median_value = float(np.median(valid_value))
    if np.isnan(median_value):
        return 0.0, None
```
And guard momentum / pump division:
```python
    # In _momentum:
    if close[-1 - n] <= 0:
        return 0.0, None
    # In _active_pump:
    if close[-1 - lookback] <= 0:
        continue
```

### 6.3 Stabilization Fix 3: `backend/indicators.py`
**Target File**: `backend/indicators.py`
- **Issue**: `true_range` and `mfi` crash on `len == 0`.
- **Proposed Patch**:
```python
def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(high)
    if n == 0:
        return np.empty(0)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    if n > 1:
        prev_close = close[:-1]
        hl = high[1:] - low[1:]
        hc = np.abs(high[1:] - prev_close)
        lc = np.abs(low[1:] - prev_close)
        tr[1:] = np.maximum(hl, np.maximum(hc, lc))
    return tr
```
In `mfi`:
```python
    n = len(close)
    if n == 0:
        return np.empty(0)
```
In `support_resistance_levels`:
```python
    if last_cluster_mean == 0:
        clusters.append([p])
        continue
```

### 6.4 Stabilization Fix 4: `backend/scoring.py`
**Target File**: `backend/scoring.py`
- **Issue**: `KeyError` on missing keys, `IndexError` on empty arrays.
- **Proposed Patch**:
```python
def compute_score(data: dict) -> dict:
    required = ["close", "rsi", "atr", "adx", "mfi", "rvol", "ema_fast", "ema_slow", "donchian_upper", "donchian_lower"]
    for req in required:
        if req not in data or data[req] is None or len(data[req]) == 0:
            return {
                "valid": False, "swing_score": None, "components": None,
                "recommendation": None, "confidence": None, "risk_level": None,
                "prob_continuation": None, "prob_reversal": None, "regime": "sideways"
            }
```

### 6.5 Stabilization Fix 5: `backend/recovery.py`
**Target File**: `backend/recovery.py:32-40`
- **Issue**: Missing `import sys`.
- **Proposed Patch**: Add `import sys` to top-level imports.

### 6.6 Stabilization Fix 6: `backend/requirements.txt` & `backend/walkforward.py`
**Target File**: `backend/requirements.txt`
- **Issue**: Missing `scikit-learn`.
- **Proposed Patch**: Add `scikit-learn>=1.3.0` to `backend/requirements.txt`.
- In `walkforward.py`:
```python
try:
    from sklearn.metrics import roc_auc_score
except ImportError:
    roc_auc_score = None
```

---

## 7. Verification Method

To independently verify these findings:

1. **Verify `scikit-learn` absence in requirements**:
   Inspect `backend/requirements.txt` to confirm absence of `scikit-learn`.
2. **Verify missing `sys` in `recovery.py`**:
   Search imports in `backend/recovery.py` (lines 32–47) and confirm lines 206, 209, 213 reference `sys.stderr` without importing `sys`.
3. **Verify NaN formatting exception**:
   Execute Python snippet:
   ```python
   risk_amt = float('nan')
   try:
       print(f"{risk_amt:,.0f}")
   except ValueError as e:
       print("Confirmed ValueError:", e)
   ```
4. **Verify empty array boundary condition**:
   Execute:
   ```python
   import numpy as np
   from indicators import true_range
   try:
       true_range(np.array([]), np.array([]), np.array([]))
   except IndexError as e:
       print("Confirmed IndexError on empty true_range:", e)
   ```
