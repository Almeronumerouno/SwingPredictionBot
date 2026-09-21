# Handoff Report: Frontend Next.js Survey & Diagnosis

**Agent**: `explorer_survey_3`  
**Working Directory**: `c:\CodeKuliah\SwingPredictionBot\.agents\explorer_survey_3`  
**Target Subsystem**: Next.js Frontend (`c:\CodeKuliah\SwingPredictionBot\frontend\`)  
**Timestamp**: 2026-09-21T13:25:00Z  

---

## 1. Observation

### 1.1 Configuration & Build Tooling
- **Framework & Dependencies** (`frontend/package.json`):
  - Next.js: `^16.2.10`
  - React: `^19.2.4` / React-DOM: `^19.2.4`
  - TypeScript: `^5.9.3`
  - Styling: Tailwind CSS `^4.3.3` with `@tailwindcss/postcss: ^4.3.3`, PostCSS `^8.5.19`, Autoprefixer `^10.5.4`
  - Charting & PDF: `lightweight-charts: ^5.2.0`, `html-to-image: ^1.11.13`, `jspdf: ^4.2.1`
  - Linting: `eslint: ^9`, `eslint-config-next: 16.2.10`
- **Compiler Config** (`frontend/tsconfig.json`): Target `ES2017`, `moduleResolution: "bundler"`, `strict: true`, path alias `@/*` mapping to `./*`.
- **CSS Setup** (`frontend/app/globals.css`): Modern Tailwind v4 setup using `@import "tailwindcss";` with full dark/light theme CSS custom properties (`--color-bg`, `--color-surface`, `--color-up`, `--color-down`, etc.).

### 1.2 Build & Typecheck Diagnostics
- **Command 1**: `npx tsc --noEmit` in `c:\CodeKuliah\SwingPredictionBot\frontend`
  - **Result**: Exit code `0`. Zero type errors emitted by TypeScript compiler.
- **Command 2**: `npm run build` (`next build` with Turbopack) in `c:\CodeKuliah\SwingPredictionBot\frontend`
  - **Result**: Exit code `0`.
  - Output excerpt:
    ```
    ▲ Next.js 16.2.10 (Turbopack)
    ✓ Compiled successfully in 9.2s
      Running TypeScript ...
      Finished TypeScript in 9.8s ...
      Collecting page data using 10 workers ...
    ✓ Generating static pages using 10 workers (8/8) in 1787ms
      Finalizing page optimization ...

    Route (app)
    ┌ ƒ /
    ├ ○ /_not-found
    ├ ○ /ai-trade
    ├ ○ /analisis
    ├ ƒ /gorengan
    ├ ƒ /ready-to-fly
    ├ ƒ /saham/[kode]
    └ ƒ /top-gainers
    ```
- **Command 3**: `npm run lint` (`eslint`) in `c:\CodeKuliah\SwingPredictionBot\frontend`
  - **Result**: Exit code `1` (14 errors, 3 warnings).
  - Exact error log summary:
    1. `frontend/app/analisis/page.tsx:67:11`:
       `error: Avoid calling setState() directly within an effect (react-hooks/set-state-in-effect)`
    2. `frontend/app/saham/[kode]/simulation-controls.tsx:39:18`:
       `error: Calling setState synchronously within an effect can trigger cascading renders (react-hooks/set-state-in-effect)`
    3. `frontend/components/date-selector.tsx:69:9`:
       `error: Calling setState synchronously within an effect can trigger cascading renders (react-hooks/set-state-in-effect)`
    4. `frontend/components/date-selector.tsx:261:6`:
       `warning: React Hook useMemo has a missing dependency: 'isDateScraped' (react-hooks/exhaustive-deps)`
    5. `frontend/components/price-chart.tsx:93, 135, 143, 152, 161, 200, 211, 222, 231`:
       `error: Unexpected any. Specify a different type (@typescript-eslint/no-explicit-any)` (9 occurrences)
    6. `frontend/components/realtime-clock.tsx:11:5`:
       `error: Avoid calling setState() directly within an effect (react-hooks/set-state-in-effect)`
    7. `frontend/components/scrape-all-button.tsx:409:6`:
       `warning: React Hook useEffect has a missing dependency: 'executeScan' (react-hooks/exhaustive-deps)`
    8. `frontend/components/sidebar.tsx:111:5`:
       `error: Avoid calling setState() directly within an effect (react-hooks/set-state-in-effect)`
    9. `frontend/postcss.config.mjs:1:1`:
       `warning: Assign object to a variable before exporting as module default (import/no-anonymous-default-export)`

### 1.3 Cross-Boundary Interface Mismatches
- **Pattern Candles Serialization**:
  - In `backend/api.py` (lines 557-581), `analyze_stock` constructs `pattern_candles = [{"open": ..., "high": ..., "low": ..., "close": ...}, ...]` and embeds it in `raw_indicators`.
  - In `frontend/types/api.ts` (line 64), `RawIndicators` includes optional `pattern_candles?: { open: number; high: number; low: number; close: number }[]`.
  - In `frontend/components/candlestick-patterns.tsx` (lines 431-454), `CandlestickPatterns` checks `realCandles` to render accurate SVG candles matching real OHLC data.
  - **Defect**: In `backend/api.py` (lines 94-108), `RawIndicatorsResponse(BaseModel)` **omits** `pattern_candles`. As a consequence, FastAPI's Pydantic response filter strips `pattern_candles` out of the JSON response payload. The frontend visualizer always receives `undefined`, falling back to hardcoded mock candle heights.
- **Unmapped Optional Fields**:
  - `backend/api.py` line 47: `ScoreResponse.regime` is emitted by backend but not declared in `frontend/types/api.ts`.
  - `backend/api.py` lines 309 & 313: `RecoveryResponse.signal_target` and `RecoveryResponse.ca_note` are emitted by backend but not declared in `frontend/types/api.ts`.

### 1.4 SSR Hydration & DOM Safety
- `frontend/app/layout.tsx`: Includes `<html lang="id" suppressHydrationWarning>` and an early inline `<script>` to read `localStorage.getItem("swingbot-theme")` and toggle the `dark` class before DOM render. This avoids flash of light mode (FOUC).
- `frontend/components/sidebar.tsx`: `DarkModeToggle` renders a skeleton until mounted, preventing SSR mismatch. (Flagged by ESLint for synchronous `setMounted(true)`).
- `frontend/components/realtime-clock.tsx`: Renders a placeholder until mounted to prevent clock time differences between server render and client hydration. (Flagged by ESLint for synchronous `setMounted(true)`).
- `frontend/components/price-chart.tsx`: Correctly guards all Lightweight Charts DOM creation and `ResizeObserver` lifecycle inside `useEffect`.
- `frontend/components/download-pdf-button.tsx`: PDF rendering with `html-to-image` and `jspdf` is executed purely in a user-driven click event handler (`generatePDF`), safe from SSR execution.
- `frontend/components/scrape-all-button.tsx`: `createPortal(..., document.body)` is invoked for modal and toast. Currently guarded by `showModal` (boolean) and `toast` (object|null) which initialize to falsy values.

### 1.5 Runtime Layout Crash Risks & Dead Code
- `frontend/app/saham/[kode]/page.tsx` line 19:
  ```tsx
  const fmtDate = (d: string) => {
    const [y, m, day] = d.split("-");
    const months = ["Januari", ...];
    return `${parseInt(day)} ${months[parseInt(m) - 1]} ${y}`;
  };
  ```
  If `analisis.last_updated` is malformed, missing, or empty, `parseInt(day)` becomes `NaN` and `months[NaN]` is `undefined`, outputting `"NaN undefined undefined"`.
- **Orphaned / Dead Code Files**:
  - `frontend/app/saham/[kode]/capital-control.tsx` (73 lines): Replaced by `simulation-controls.tsx`, no longer imported anywhere.
  - `frontend/components/recovery-drop-control.tsx` (117 lines): Replaced by `simulation-controls.tsx`, no longer imported anywhere.
  - `frontend/components/capital-input.tsx` (23 lines): Unreferenced in any page or component.
  - `frontend/components/stockbit-formula-card.tsx` (84 lines): Unreferenced in any page or component.
  - Empty app route folders: `frontend/app/login/`, `frontend/app/register/`, `frontend/app/profile/` contain 0 files.

---

## 2. Logic Chain

1. **Build Success vs Lint Failure**:
   - `npm run build` succeeds because Next.js 16 decoupled ESLint from the production build command (`next build`).
   - However, standard CI pipelines and team quality gates typically run `npm run lint` or `eslint .`. Because `npm run lint` exits with code 1, the frontend fails strict CI/CD validation.
2. **Root Cause of `react-hooks/set-state-in-effect`**:
   - React 19 / eslint-plugin-react-hooks strictly forbids calling `setState` synchronously within the body of an `useEffect` because it induces an immediate second render pass before paint (cascading renders).
   - In `analisis/page.tsx`, `date-selector.tsx`, `simulation-controls.tsx`, `realtime-clock.tsx`, and `sidebar.tsx`, state setters are called unconditionally at the top of mount/sync effects.
   - For mounting checks (`realtime-clock.tsx`, `sidebar.tsx`), React 18/19 provides `useSyncExternalStore` (`const isMounted = useSyncExternalStore(() => () => {}, () => true, () => false)`), which completely eliminates the need for `useState` + `useEffect` mounting guards.
   - For prop-syncing (`date-selector.tsx`, `simulation-controls.tsx`), state can be adjusted during render or wrapped in `startTransition`.
3. **Root Cause of `@typescript-eslint/no-explicit-any`**:
   - In `price-chart.tsx`, lightweight-charts requires series data typed as `CandlestickData<Time>` or `SingleValueData`. Using `as any` bypassed typing at the expense of breaking ESLint rules.
4. **Impact of Missing `pattern_candles` in Backend Pydantic Model**:
   - Frontend developers built a sophisticated SVG candlestick pattern renderer in `components/candlestick-patterns.tsx` that computes true-to-life candle wicks and bodies from OHLC data.
   - Backend developers implemented the calculation in `analyze_stock()`.
   - But because `RawIndicatorsResponse` in `backend/api.py` lacked `pattern_candles: list[dict] | None = None`, FastAPI dropped the field upon JSON serialization.
   - Restoring this field in `backend/api.py` immediately connects the live candle visualizer without changing any frontend component logic.

---

## 3. Caveats

- The backend server was not running during this static analysis turn; API endpoint responses were surveyed by inspecting Pydantic schemas in `backend/api.py` and comparing them against TypeScript interfaces in `frontend/types/api.ts`.
- The Next.js Turbopack dev server was not tested in interactive browser sessions; however, both `next build` static page generation and `tsc --noEmit` were executed and verified directly in the local environment.

---

## 4. Conclusion

The Next.js frontend is structurally robust and builds cleanly to production with exit code 0 (`npm run build`). However, to achieve a 100% clean production build and pass strict CI linting:
1. **Resolve ESLint failures**:
   - Modernize mounting checks in `sidebar.tsx` and `realtime-clock.tsx` using `useSyncExternalStore` (or `startTransition`).
   - Fix prop-sync effects in `simulation-controls.tsx` and `date-selector.tsx`.
   - Replace explicit `as any` casts in `price-chart.tsx` with proper lightweight-charts types (`CandlestickData<Time>`, `SingleValueData`, `Time`).
   - Add missing hook dependencies in `date-selector.tsx` and `scrape-all-button.tsx`.
   - Fix anonymous default export in `postcss.config.mjs`.
2. **Expose `pattern_candles` in backend**:
   - Add `pattern_candles: list[dict] | None = None` to `RawIndicatorsResponse` in `backend/api.py`.
3. **Clean up legacy orphaned files**:
   - Safely remove unused legacy components: `capital-control.tsx`, `recovery-drop-control.tsx`, `capital-input.tsx`, `stockbit-formula-card.tsx`, and empty route directories (`login`, `register`, `profile`).
4. **Harden date parsing**:
   - Guard `fmtDate` in `app/saham/[kode]/page.tsx` against unexpected empty or non-ISO date strings.

---

## 5. Verification Method

To independently verify the frontend state:
1. **Typecheck**:
   ```bash
   cd c:\CodeKuliah\SwingPredictionBot\frontend
   npx tsc --noEmit
   # Must exit with code 0
   ```
2. **Production Build**:
   ```bash
   cd c:\CodeKuliah\SwingPredictionBot\frontend
   npm run build
   # Must generate all 8 routes with exit code 0
   ```
3. **Lint Verification**:
   ```bash
   cd c:\CodeKuliah\SwingPredictionBot\frontend
   npm run lint
   # Observe the 14 errors and 3 warnings documented in Section 1.2
   ```
4. **Backend Schema Inspection**:
   Inspect `backend/api.py` lines 94–108 (`RawIndicatorsResponse`) to verify the absence of `pattern_candles`.
