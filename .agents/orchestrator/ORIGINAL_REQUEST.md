# Original User Request

## 2026-09-21T13:11:07Z

Perform a comprehensive system-wide stabilization, debugging, and audit of the SwingPredictionBot project across both the FastAPI Python backend and the Next.js frontend, resolving any bugs, runtime exceptions, syntax errors, or build failures so the system operates completely error-free.

Working directory: c:\CodeKuliah\SwingPredictionBot
Integrity mode: development

## Requirements

### R1. Backend Codebase & Endpoint Robustness
Audit all backend modules (`backend/api.py`, `indicators.py`, `scoring.py`, `risk.py`, `recovery.py`, `gorengan.py`, `backtest.py`, `walkforward.py`) for runtime defects, edge-case crashes (such as division by zero, unexpected NaNs, or missing dictionary keys), and ensure all endpoints return proper HTTP error responses rather than unhandled 500 exceptions.

### R2. Test Suite & Validation Integrity
Ensure that backend test and verification scripts (including `backend/test_api.py` and module compilation) execute cleanly without failures. Verify that core calculation pathways (indicator generation, scoring, and trade plan creation) run stably across both normal and boundary market data.

### R3. Frontend Next.js Build & Lint Verification
Inspect the Next.js frontend application in `frontend/`. Resolve any TypeScript type errors, broken component imports, SSR hydration mismatches, or layout crashes. Guarantee that the production build pipeline (`npm run build`) passes cleanly with zero fatal errors.

## Acceptance Criteria

### Backend Verification
- [ ] All `.py` files in `backend/` compile successfully with `python -m py_compile` with zero syntax or import errors.
- [ ] Backend smoke verification (`test_api.py` or unit tests) executes without unhandled tracebacks or fatal crashes.
- [ ] Endpoints (`/market-status`, `/gainers`, `/analisis/{kode}`, `/history/{kode}`, `/recovery/{kode}`, `/readytofly`, `/gorengan`) correctly validate parameters and handle edge cases gracefully.

### Frontend Verification
- [ ] Next.js production build (`npm run build` in `frontend/`) completes successfully with exit code 0.
- [ ] No unresolved TypeScript errors or broken imports across pages and components.
