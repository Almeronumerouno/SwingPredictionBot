# Frontend Dashboard — Next.js

| Item | Detail |
|------|--------|
| **Stack** | Next.js 16.2.10 + React 19.2.4 |
| **Chart** | lightweight-charts 5.2.0 |
| **CSS** | Tailwind CSS 4.3.3 |
| **Font** | Inter (Google Fonts) |
| **Last Updated** | 27 Juli 2026 |

## 1. Halaman

| Route | Halaman | Status |
|-------|---------|--------|
| `/` | Dashboard — Top Gainers overview + signal badges | ✅ |
| `/saham/[kode]` | Detail Saham — Score, chart, trade plan, indicators | ✅ |
| `/analisis` | Analisis — Form input kode saham | ✅ |
| `/top-gainers` | Full Gainers List | ✅ |

## 2. Komponen

| Component | Type | States | File |
|-----------|------|--------|------|
| GainersTable | Client | Loading, empty, data, error | `components/gainers-table.tsx` |
| ScoreCard | Server | Default, positive, negative | `components/score-card.tsx` |
| TradePlanCard | Server | Default, empty (HOLD) | `components/trade-plan-card.tsx` |
| PriceChart | Client | Loading, data, empty | `components/price-chart.tsx` |
| ScrapeButton | Client | Idle, loading, success toast, error toast | `components/scrape-button.tsx` |
| DatePicker | Client | Default, selected | `app/date-picker.tsx` |
| CapitalControl | Client | Default, applied | `app/saham/[kode]/capital-control.tsx` |
| Sidebar | Server | Active link, hover | `components/sidebar.tsx` |
| SignalScreener | Client | Default, filtered | `components/signal-screener.tsx` |
| GorenganCard | Server | LOW/HIGH/EXTREME | `components/gorengan-card.tsx` |
| TechnicalIndicators | Server | RSI, ADX, MFI, RVOL, S/R, Fibo | `components/technical-indicators.tsx` |
| CandlestickPatterns | Server | Pattern cards + SVG | `components/candlestick-patterns.tsx` |

## 3. Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#F8FAFC` | Page background |
| `--color-surface` | `#FFFFFF` | Card background |
| `--color-border` | `#E6E8EA` | Borders, dividers |
| `--color-text-primary` | `#0F172A` | Main text, headings |
| `--color-text-secondary` | `#64748B` | Body text, descriptions |
| `--color-text-muted` | `#94A3B8` | Labels, hints |
| `--color-primary` | `#334155` | Interactive elements |
| `--color-up` | `#059669` | Bullish, positive, buy |
| `--color-down` | `#DC2626` | Bearish, negative, sell |
| `--color-muted-bg` | `#F2F3F4` | Table header background |

## 4. Layout

```
┌─────────┬──────────────────────────────────────────────────┐
│ Sidebar │  Header (title + actions)                        │
│  64px   │                                                  │
│ sticky  ├──────────────────────────────────────────────────┤
│ h-screen│  Content                                          │
│         │  - Stat cards (grid-cols-3/4)                     │
│ Logo    │  - Table / Cards / Chart                          │
│ Nav:    │  - Full width, max-w-[1400px]                     │
│  - Dash │                                                   │
│  - Anal │  Footer (copyright + disclaimer)                  │
├─────────┴──────────────────────────────────────────────────┤
```

## 5. Yang Sudah Ditampilkan

| Data | Display | Halaman |
|------|---------|---------|
| Swing Score | Signal badge (BUY/SELL/HOLD + score) | Dashboard |
| Swing Score | ScoreCard + badge | Detail |
| 4 Components | 4 progress bars 0-100% | Detail |
| Confidence | ScoreCard | Detail |
| Risk Level | ScoreCard | Detail |
| Data Valid | ScoreCard (Yes/No) | Detail |
| Trade Plan | TradePlanCard (SL, TP, lots, R:R) | Detail |
| OHLCV | Candlestick chart | Detail |
| RSI, MFI, ADX | GaugeBar components | Detail |
| RVOL | GaugeBar | Detail |
| ATR, EMA | Text display | Detail |
| S/R Levels | Text display | Detail |
| Fibonacci | Progress bar display | Detail |
| Candlestick Patterns | Pattern cards + SVG | Detail |
| Gorengan Score | GorenganCard | Detail |

## 6. Missing Features

| Fitur | Status | Prioritas |
|-------|--------|-----------|
| Dark Mode | ❌ | Medium |
| Search / Filter gainers | ❌ | Medium |
| Sorting gainers table | ❌ | Low |
| Auto-refresh scrape | ❌ | Low |
| Export PDF laporan | ❌ | Low |
| Loading skeleton halus | ✅ | — |

## 7. Performance Targets

| Metrik | Target | Current |
|--------|--------|---------|
| First Contentful Paint | < 1.5s | ✅ |
| Largest Contentful Paint | < 2.5s | ✅ |
| Time to Interactive | < 3.0s | ✅ |
| API response time | < 3s per saham | ✅ |
| Dashboard load | < 5s (15 saham) | ✅ |
