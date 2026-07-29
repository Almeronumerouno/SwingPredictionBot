# Backtest Engine — Walk-Bar Simulation

| Item | Detail |
|------|--------|
| **Modul** | `backend/backtest.py`, `backend/backtest_calibrate.py` |
| **Versi** | v0.2.0 |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Backtest engine mensimulasikan strategi Swing Score (BUY/SELL/HOLD) + SL/TP ATR-based pada data historis. Zero modification ke kode existing (Fase 1-5).

## 2. Pendekatan

1. Compute ALL indicators 1x → full numpy arrays
2. Compute ALL component scores 1x → full arrays
3. Walk bars: sinyal → entry → SL/TP check → exit → metrics

## 3. Configuration Override

Semua parameter bisa di-override via `BacktestConfig` tanpa sentuh `config.py`:

```python
@dataclass
class BacktestConfig:
    adx_gate_ceiling: int = 20
    swing_buy_threshold: int = 75
    swing_sell_threshold: int = 35
    atr_sl_multiplier: float = 3.0
    atr_tp_multiplier: float = 3.0
    rvol_breakout_confirm: float = 1.5
    rvol_window: int = 10
    position_pct: float = 1.0
    fee_pct: float = 0.25
    long_only: bool = True
    max_holding_days: int = 20
```

## 4. Triple-Barrier Labeling (Lopez de Prado, 2018)

Setiap entry di-label menggunakan triple-barrier method:

| Label | Meaning | Hit Rate (Current) |
|-------|---------|-------------------|
| TP_FIRST | Upper barrier kena duluan | 40.4% |
| SL_FIRST | Lower barrier kena duluan | 25.5% |
| TIMEOUT | Vertical barrier 20 hari expired | 34.0% |

**Tie-break:** SL menang jika dua barrier kena di candle yang sama (konservatif).

## 5. Exit Reasons

| Reason | Description |
|--------|-------------|
| SL_HIT | Stop loss tersentuh |
| TP_HIT | Take profit tersentuh |
| REVERSAL | Sinyal berlawanan (BUY → SELL signal) |
| END_OF_DATA | Data habis (posisi masih terbuka) |

## 6. Metrics

| Metrik | Rumus | Target |
|--------|-------|--------|
| Win Rate | winning / total × 100 | >55% |
| Total Return | (equity_akhir / capital - 1) × 100 | >+1% |
| Alpha vs B&H | total_return - buy_hold_return | >+5% |
| Sharpe Ratio | mean(daily_ret) / std(daily_ret) × √252 | >0.20 |
| Max Drawdown | max(peak - trough) / peak × 100 | <10% |
| Avg Return/Trade | mean(trade_return) | >+1% |
| Avg Holding Days | mean(holding_days) | 8-15 |
| Avg R:R | mean(reward/risk) | >1.0 |

## 7. CLI Usage

```bash
# Single stock
python backtest.py BBCA --capital 10000000 --verbose

# Multiple stocks
python backtest.py BBCA BMRI ASII --capital 50000000

# Custom parameters
python backtest.py BBCA --buy-threshold 70 --sl-multiplier 3.0

# JSON output
python backtest.py BBCA BMRI --json > results.json

# Calibration (grid search)
python backtest_calibrate.py
```

## 8. Hasil Kalibrasi (Fase 6)

Grid search 243 combo × 19 saham mid-big cap liquid.

### Parameter Optimal

| Parameter | Default | Kalibrasi | Effect |
|-----------|:-------:|:---------:|--------|
| ADX_GATE_CEILING | 25 | **20** | Lebih sensitif, naikin jumlah sinyal |
| SWING_BUY_THRESHOLD | 65 | **70** | Lebih selektif, kurangi false signal |
| ATR_SL_MULTIPLIER | 1.5 | **3.0** | SL lebih longgar, WR naik 35.6→55.3% |
| RVOL_WINDOW | 20 | **10** | Lebih responsif volume spike |
| RVOL_BREAKOUT_CONFIRM | 2.0 | **1.5** | Lebih longgar, tangkap sinyal valid |

### Performance Comparison

| Metrik | Default | Kalibrasi (v0.2.0) |
|--------|:-------:|:------------------:|
| Win Rate | 35.6% | **55.3%** |
| Total Return | -1.92% | **+0.41%** |
| Alpha vs B&H | +0.86% | **+5.38%** |
| Sharpe | -0.72 | **0.24** |
| Max DD | 5.25% | **5.94%** |

## 9. Walk-Forward Validation (Sprint 1A)

### 9.1 Tujuan

Mencegah overfitting — parameter optimal dari kalibrasi in-sample (Fase 6) mungkin tidak bekerja di data baru. Walk-forward validation mensimulasikan deployment realistis: train → optimize → test OOS → roll.

### 9.2 Design

**Modul baru:** `backend/walkforward.py`

```
Window 1: Train (6 bln) │purge│embargo│ Test (3 bln) │
                         20d   20d
Window 2:                │ Train (6 bln) │purge│embargo│ Test (3 bln) │
                                                  20d   20d
Window 3:                                   │ Train (6 bln) │...
```

Purge (Lopez de Prado, 2018): hapus 20 hari sebelum test untuk menghindari leak dari data overlap.
Embargo: gap 20 hari antara train dan test — menghilangkan serial correlation spillover.

### 9.3 Metrik Final

Concat **semua** OOS trade dari seluruh (saham × window) jadi 1 equity curve:

| Metrik | Sumber | Notes |
|--------|--------|-------|
| OOS Win Rate | Concat trade OOS | Bukan rata-rata per-saham |
| OOS Sharpe | Equity curve harian OOS | Risk-adjusted return |
| OOS Return | Equity curve total | Net return |
| OOS Max DD | Equity curve | Drawdown maksimal |
| Parameter Stability | Stdev parameter antar window | Parameter yang stabil = sinyal bagus |

### 9.4 Penerapan

- Sprint 1A menulis skeleton harness (split, purge, embargo, concat)
- Setelah S1B-S1D diimplementasi, harness dijalankan untuk membandingkan baseline v0.2.0 vs v0.3.0
- Setiap sprint berikutnya (S3, S4+) wajib divalidasi lewat harness yang sama
- **Tidak ada parameter baru yang ditumpuk tanpa validasi OOS**

## 10. Identified Issues

| Issue | Impact | Status |
|-------|--------|--------|
| Walk-forward belum ada | Parameter overfit ke periode test | **Sprint 1A** |
| Fee model sederhana | Return overstate ~2-5% | Belum dijadwalkan |
| S/R look-ahead minor | S/R pakai full history | PIT di backtest |
| Short selling bias | IDX retail tidak bisa short | **Sprint 1D** |
| R:R 0.83 | EV rendah (0.04 ATR/trade) | **Sprint 1B** |
| No exit flexibility | Satu TP/SL untuk semua trade | **Sprint 1C** |
| No regime filter | Performa tidak konsisten | **Sprint 3** |

## 11. Roadmap Sprint

| Sprint | Item | Kode |
|--------|------|------|
| **S1A** | Walk-forward harness skeleton | `walkforward.py` |
| **S1B** | Fix R:R — TP multiplier 3.0 | `config.py`, `backtest.py` |
| **S1C** | Breakeven stop (1.0 ATR) | `backtest.py`, `risk.py` |
| **S1D** | Long-only mode | `config.py`, `risk.py`, `api.py` |
| S2 | Rekonsiliasi sizing + validasi OOS | — |
| S3 | Regime detection + adaptive weights | `scoring.py`, `regime.py` |
| S4+ | Scale-out, trailing, ML | — |

## 12. Future Improvements (Post v0.3.0)

- [ ] **Purged cross-validation** — Lopez de Prado CPCV
- [ ] **Multiple timeframe filter** — weekly trend confirmation
- [ ] **Monte Carlo simulation** — distribusi return estimasi
- [ ] **Deflated Sharpe Ratio** — overfit detection
- [ ] **Full fee & slippage modeling** — broker 0.15-0.35% round trip
- [ ] **PIT S/R levels** — point-in-time di backtest
