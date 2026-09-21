# Dispatch for Challenger 1 (Backend Adversarial Stress Testing)

## 2026-09-21T13:54:13Z
You are challenger_1, an adversarial verifier agent.
Your working directory is: c:\CodeKuliah\SwingPredictionBot\.agents\challenger_1
Original parent conversation ID: 5ca91e8d-e704-43ca-a4c4-a0ca233374a9

MANDATORY FIRST STEP:
Read the authoritative request file at:
c:\CodeKuliah\SwingPredictionBot\.agents\orchestrator\ORIGINAL_REQUEST.md
Also read the project specification at:
c:\CodeKuliah\SwingPredictionBot\.agents\orchestrator\PROJECT.md

TOOL USAGE DIRECTIVE:
DO NOT use `run_command` to create, touch, or edit files. Always use `write_to_file` and `replace_file_content` directly.
Use `run_command` to run empirical test scripts (`python -c ...` or test scripts).

OBJECTIVE:
Empirically stress-test the backend calculation engines and API endpoints with adversarial boundary inputs:
1. Boundary condition stress tests:
   - Pass empty arrays, all-zero arrays, single-element arrays, all-NaN arrays to `indicators.true_range`, `indicators.mfi`, `scoring.compute_score`, `risk.build_trade_plan`, `gorengan._liquidity_risk`.
   - Verify that none of these raise `IndexError`, `ZeroDivisionError`, `ValueError` (float NaN format), or unhandled exceptions.
2. Endpoint parameter stress tests:
   - Call FastAPI endpoints using `TestClient(app)` with edge-case parameters:
     - `/analisis/{kode}` with capital=0, capital=-1000, capital=float('nan'), capital=1e15, invalid ticker "XYZ999".
     - Date queries with `2026-99-99`, `2026-02-30`, `invalid-date`, `""`.
     - `/history/{kode}` and `/recovery/{kode}` with non-existent tickers.
   - Confirm that all endpoints return proper HTTP error codes (400, 404, 422, 502) and NEVER unhandled 500 exceptions.
3. Deliver your empirical test report with a clear verdict (`APPROVE` or `REJECT`) to:
   `c:\CodeKuliah\SwingPredictionBot\.agents\challenger_1\handoff.md`
   Send a message to parent with your verdict and test evidence.
