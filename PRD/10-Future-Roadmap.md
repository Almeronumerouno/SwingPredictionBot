# Future Roadmap

| Item | Detail |
|------|--------|
| **Last Updated** | 21 September 2026 |

## Fase 7 — Production Readiness (Short-term)

### Exit Strategy Enhancement
- [ ] **Partial Profit Taking (Scale Out)** — 50% di T1, 30% di T2, 20% trailing
- [ ] **Trailing Stop** — ATR-based trailing untuk sisa posisi
- [ ] **Dynamic ATR Multiplier** — adjust multiplier based on volatility regime
- [ ] **Circuit Breaker** — kurangi size 50% setelah 2 loss beruntun

### Adaptive Threshold
- [ ] Dynamic buy/sell threshold berdasarkan 30-day volatility
- [x] Market regime filter (bull/bear/sideways) — ✅ `regime.py` (SMA200+ADX, 3 profiles)
- [x] Regime-dependent component weights — ✅ bull/sideways/bear bobot adaptif di `regime.py`

### Validation
- [x] Walk-forward validation (purge + embargo) — ✅ `walkforward.py` (461 baris, fully functional)
- [x] Long-only mode — ✅ tested & deliberately kept OFF (SELL validated 58% WR)
- [x] Fees & slippage modeling — ✅ `FEE_BUY_PCT=0.18%`, `FEE_SELL_PCT=0.28%` (asimetris)

### Quality of Life
- [ ] Dark mode
- [x] Sorting & filtering gainers table — ✅ Selesai (`SignalScreener` di `components/signal-screener.tsx`)
- [ ] Auto-refresh scrape (cron/scheduler)

## Fase 8 — Platform Maturity (Medium-term)

### ML Enhancement
- [ ] XGBoost/Random Forest for dynamic feature weighting
- [ ] Ensemble scoring (3 set parameter, consensus signal)
- [ ] Regime classification via Hidden Markov Model
- [ ] Sentiment overlay (FinBERT untuk berita IDX)

### Risk Management
- [ ] Dynamic position sizing by confidence score
- [ ] Trailing stop untuk winning trades
- [ ] Multiple timeframe filter (weekly trend confirmation)
- [ ] Monte Carlo simulation untuk risk estimation

### Infrastructure
- [ ] Docker + cron scheduler (daily scan IDX)
- [ ] Database persistence (SQLite/PostgreSQL)
- [ ] Rate limiting & request queuing
- [ ] Prometheus metrics + monitoring

### Gorengan Detection
- [ ] Volume Profile analysis (VPVR)
- [ ] Cross-sectional anomaly ranking
- [ ] UMA monitoring auto-track
- [ ] Order flow imbalance (jika data tick tersedia)

## Fase 9 — Full Platform (Long-term)

### Multi-User
- [x] User accounts & authentication — ✅ Selesai (Frontend auth routes: `/login`, `/register`, `/profile`)
- [ ] Watchlist / portfolio tracking
- [ ] Personalized notification (email/push)
- [ ] Trade journal & history

### Advanced Features
- [ ] Real-time data (WebSocket IDX)
- [x] Screening engine (scan seluruh pasar untuk sinyal) — ✅ Selesai (`/readytofly`, `/gorengan`, `/scrape/all` + UI routes)
- [ ] Backtest-on-demand via UI
- [x] Export laporan PDF — ✅ Selesai (`download-pdf-button.tsx` via jspdf)

### Market Expansion
- [ ] Multi-exchange support (SGX, NYSE)
- [ ] Crypto market integration
- [ ] Multi-language support

## Known Gaps

| Gap | Impact | Status |
|-----|--------|--------|
| BUY not validated | Edge tidak konsisten antara bullish vs bearish | ⚠️ Open |
| No walk-forward | Parameter mungkin overfit | ✅ Resolved (`walkforward.py`) |
| Equal-weight suboptimal | Bobot tidak adaptif terhadap regime | ✅ Resolved (`regime.py` adaptive weights) |
| No trailing stop | Sering kehilangan profit setelah TP | ⚠️ Open (S4+) |
| No partial exit | Semua atau tidak sama sekali | ⚠️ Open (S4+) |
| Fee/slippage not modeled | Return overstate 2-5% | ✅ Resolved (`FEE_BUY/SELL_PCT`) |
| Short selling bias | SELL signal tidak applicable untuk retail | ✅ Resolved (SELL 58% WR, kept as entry) |
| Micro-cap not suitable | Optimal di mid-big cap liquid | ⚠️ Open |
| No sentiment | Hanya data teknikal | ⚠️ Open (Fase 8) |
| No intermarket analysis | Tidak ada konteks makro | ⚠️ Open (Fase 9) |
