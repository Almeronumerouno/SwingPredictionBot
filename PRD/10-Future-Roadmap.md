# Future Roadmap

| Item | Detail |
|------|--------|
| **Last Updated** | 27 Juli 2026 |

## Fase 7 — Production Readiness (Short-term)

### Exit Strategy Enhancement
- [ ] **Partial Profit Taking (Scale Out)** — 50% di T1, 30% di T2, 20% trailing
- [ ] **Trailing Stop** — ATR-based trailing untuk sisa posisi
- [ ] **Dynamic ATR Multiplier** — adjust multiplier based on volatility regime
- [ ] **Circuit Breaker** — kurangi size 50% setelah 2 loss beruntun

### Adaptive Threshold
- [ ] Dynamic buy/sell threshold berdasarkan 30-day volatility
- [ ] Market regime filter (bull/bear/sideways)
- [ ] Regime-dependent component weights

### Validation
- [ ] Walk-forward validation (purge + embargo)
- [ ] Long-only mode (nonaktifkan SELL untuk IDX retail)
- [ ] Fees & slippage modeling (broker 0.15-0.35%)

### Quality of Life
- [ ] Dark mode
- [ ] Sorting & filtering gainers table
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
- [ ] User accounts & authentication
- [ ] Watchlist / portfolio tracking
- [ ] Personalized notification (email/push)
- [ ] Trade journal & history

### Advanced Features
- [ ] Real-time data (WebSocket IDX)
- [ ] Screening engine (scan seluruh pasar untuk sinyal)
- [ ] Backtest-on-demand via UI
- [ ] Export laporan PDF

### Market Expansion
- [ ] Multi-exchange support (SGX, NYSE)
- [ ] Crypto market integration
- [ ] Multi-language support

## Known Gaps

| Gap | Impact | Timeline |
|-----|--------|----------|
| BUY not validated | Edge tidak konsisten antara bullish vs bearish | Fase 7 |
| No walk-forward | Parameter mungkin overfit | Fase 7 |
| Equal-weight suboptimal | Bobot tidak adaptif terhadap regime | Fase 7 |
| No trailing stop | Sering kehilangan profit setelah TP | Fase 7 |
| No partial exit | Semua atau tidak sama sekali | Fase 7 |
| Fee/slippage not modeled | Return overstate 2-5% | Fase 7 |
| Short selling bias | SELL signal tidak applicable untuk retail | Fase 7 |
| Micro-cap not suitable | Optimal di mid-big cap liquid | Fase 8 |
| No sentiment | Hanya data teknikal | Fase 8 |
| No intermarket analysis | Tidak ada konteks makro | Fase 9 |
