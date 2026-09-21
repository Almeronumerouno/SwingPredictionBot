## 2026-09-21T13:26:46Z
You are worker_m1, an implementation worker agent.
Your working directory is: c:\CodeKuliah\SwingPredictionBot\.agents\worker_m1
Original parent conversation ID: 5ca91e8d-e704-43ca-a4c4-a0ca233374a9

MANDATORY FIRST STEP:
Read the authoritative request file at:
c:\CodeKuliah\SwingPredictionBot\.agents\orchestrator\ORIGINAL_REQUEST.md
Also read the project specification and survey findings at:
c:\CodeKuliah\SwingPredictionBot\.agents\orchestrator\PROJECT.md
c:\CodeKuliah\SwingPredictionBot\.agents\explorer_survey_1\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

WRITE OWNERSHIP:
You exclusively own and may edit ONLY these backend files:
- `backend/indicators.py`
- `backend/scoring.py`
- `backend/risk.py`
- `backend/recovery.py`
- `backend/gorengan.py`
- `backend/backtest.py`
- `backend/walkforward.py`
- `backend/requirements.txt`
DO NOT touch any frontend files or `backend/api.py`.

OBJECTIVE & IMPLEMENTATION TASKS:
1. `backend/risk.py`:
   - In `build_trade_plan`: Guard against `atr is None or np.isnan(atr) or atr <= 0` and ensure `entry_price` and `capital` are not None, NaN, or <= 0.
   - In `_position_shares`: Return `0, None` if `per_share_risk` or `risk_amt` is NaN.
   - Guard `int(entry_price * LOT_SIZE)` in the note so NaN does not raise ValueError.
2. `backend/gorengan.py`:
   - In `_liquidity_risk`: Check for empty `close`/`volume`. Filter out NaNs from `daily_value` before `np.median`. If `valid_value` is empty or `median_value` is NaN, return `0.0, None`.
   - In `_momentum` and `_active_pump`: Guard division by zero when price is <= 0.
3. `backend/indicators.py`:
   - In `true_range`: Return `np.empty(0)` when `len(high) == 0`.
   - In `mfi`: Return `np.empty(0)` when `len(close) == 0`.
   - In `support_resistance_levels`: Guard against `last_cluster_mean == 0`.
   - In `candlestick_patterns`: Guard against zero price division (`max(c_high, p_high) == 0`).
4. `backend/scoring.py`:
   - In `_volume_score`: Guard against empty array indexing.
   - In `compute_score`: Validate that all required keys exist and have non-empty length. If empty or missing, return `{"valid": False, "swing_score": None, ...}` cleanly.
5. `backend/recovery.py`:
   - Add `import sys` to top-level imports.
   - Guard zero-volume logic in `detect_accumulation` where `base == 0`.
6. `backend/backtest.py`:
   - In `compute_signals`: Guard against empty array indexing (`sign[0]`).
   - In `run_backtest`: Guard against division by zero on `pos["entry_price"] <= 0` and `capital <= 0`.
7. `backend/walkforward.py`:
   - Wrap `from sklearn.metrics import roc_auc_score` with `try...except ImportError: roc_auc_score = None`.
8. `backend/requirements.txt`:
   - Add `scikit-learn>=1.3.0`, `httpx>=0.27.0`, `curl_cffi>=0.15.0`, `pytest>=8.0.0`.

VERIFICATION:
- Compile all backend files: `python -m py_compile backend/indicators.py backend/scoring.py backend/risk.py backend/recovery.py backend/gorengan.py backend/backtest.py backend/walkforward.py`
- Test boundary cases via `python -c` verification commands (e.g. empty arrays, NaN inputs).
- Document all modified files, diffs, and verification commands/outputs in `c:\CodeKuliah\SwingPredictionBot\.agents\worker_m1\handoff.md`.
- Send completion message to parent when done.
