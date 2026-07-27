# Swing Bot IDX — Execution Plan v0.3.0

## Ringkasan

9 rekomendasi improvement dari riset akademik, GitHub, dan backtest 20 saham.
Detail lengkap: `PRD/09-Production-Improvements.md`.

## Prioritas

### P1 — Exit Strategy (Dampak Tertinggi, Termudah)
- [ ] Partial Profit Taking (50/30/20 scale out + trailing stop)
- [ ] Dynamic ATR Multiplier (volatility-adjusted)
- [ ] Circuit Breaker (kurangi size 50% setelah 2 loss)

### P2 — Adaptive Threshold & Regime Filter
- [ ] Dynamic buy/sell threshold (volatility-based)
- [ ] Market regime detection (bull/bear/sideways)
- [ ] Regime-dependent component weights

### P3 — Validation & Safety
- [ ] Walk-forward validation (purge + embargo)
- [ ] Long-only mode (nonaktifkan SELL)
- [ ] Fees & slippage modeling

### P4 — ML Enhancement
- [ ] XGBoost feature weighting
- [ ] Ensemble scoring (3 config voting)
- [ ] Sentiment overlay (FinBERT)

## Target v0.3.0

| Metrik | v0.2.0 | Target |
|--------|--------|--------|
| Win Rate | 55.3% | >60% |
| TP_HIT rate | 40.4% | >55% |
| Sharpe | 0.24 | >0.50 |
| Alpha vs B&H | +5.38% | >+8% |
