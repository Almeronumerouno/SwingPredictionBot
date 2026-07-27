# Indicators Layer — Technical Indicator Engine

| Item | Detail |
|------|--------|
| **Modul** | `backend/indicators.py` |
| **Versi** | v1.0 |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Layer indikator teknikal murni numpy, tanpa dependensi ke scraper/bot. Input array OHLCV numpy (lama → baru), output array nilai indikator sejajar input. Semua rumus mengikuti riset akademik dan Wilder "New Concepts in Technical Trading Systems" (1978).

## 2. Daftar Indikator

| ID | Indikator | Kategori | Periode | Algoritma | Sumber Fungsi |
|----|-----------|----------|---------|-----------|---------------|
| I1 | EMA(10,25) | Trend | 10/25 | α=2/(N+1), seed SMA | `indicators.py:74` |
| I2 | ATR(14) | Volatility | 14 | Wilder RMA | `indicators.py:101` |
| I3 | RSI(14) | Momentum | 14 | Wilder RMA, edge case handling | `indicators.py:111` |
| I4 | ADX(14) + DI | Trend Strength | 14 | Wilder RMA dobel | `indicators.py:144` |
| I5 | MFI(14) | Volume-Momentum | 14 | Rolling sum (BUKAN Wilder) | `indicators.py:202` |
| I6 | RVOL(10) | Volume | 10 | Excluding hari ini dari baseline | `indicators.py:241` |
| I7 | Donchian Channel(20) | Price Action | 20 | Rolling min/max | `indicators.py:260` |
| I8 | Swing Points (fractal 5-bar) | Price Action | 2 | Bill Williams fractal | `indicators.py:278` |
| I9 | S/R Levels | Price Action | 1% toleransi | Mean-shift clustering | `indicators.py:313` |
| I10 | Fibonacci 7-level | Price Action | — | Ratio 0/23.6/38.2/50/61.8/78.6/100 | `indicators.py:353,364` |
| I11 | Candlestick Patterns | Price Action | — | Threshold-based (30+ patterns) | `indicators.py:375` |

## 3. Building Blocks

### 3.1 EMA Standar

```python
alpha = 2 / (period + 1)
seed = mean(values[0:period])
out[period-1] = seed
out[i] = values[i] * alpha + out[i-1] * (1 - alpha)
```

### 3.2 Wilder RMA (Wilder's Smoothed MA)

**PENTING**: BUKAN EMA biasa. α = 1/period (bukan 2/(period+1)). Ini adalah kesalahan paling umum yang bikin implementasi RSI/ATR/ADX "generic" beda dari versi asli Wilder — termasuk indikator built-in MetaTrader 4.

```python
seed = mean(values[0:period])
out[period-1] = seed
out[i] = (out[i-1] * (period - 1) + values[i]) / period
```

## 4. Warm-up Requirements

| Indikator | Warm-up (bars) | Stabil (bars) |
|-----------|---------------|---------------|
| EMA(10,25) | 25 | 50 |
| ATR(14) | 14 | 50 |
| RSI(14) | 14 | 50 |
| ADX(14) | 27 (14 DX + 14 ADX) | 150 (Wilder) |
| MFI(14) | 14 | 30 |
| RVOL(10) | 10 | 20 |
| Donchian(20) | 20 | 20 |

Config: `HISTORY_LOOKBACK_DAYS = 250`, `MIN_TRADING_DAYS = 150`.

## 5. Candlestick Patterns

### Single Candle
- Doji (body ≤ 10% range)
- Dragonfly Doji, Gravestone Doji, Long-Legged Doji
- Hammer / Hanging Man (lower shadow ≥ 2× body)
- Inverted Hammer / Shooting Star (upper shadow ≥ 2× body)
- Marubozu (body ≥ 95% range)
- Belt Hold Bullish/Bearish
- Spinning Top

### Double Candle
- Bullish/Bearish Engulfing
- Bullish/Bearish Harami
- Harami Cross
- Piercing Line
- Dark Cloud Cover
- Tweezer Top/Bottom
- On-Neck, In-Neck
- Kicker Bullish/Bearish

### Triple Candle
- Morning Star / Evening Star
- Abandoned Baby (Bullish/Bearish)
- Three White Soldiers / Three Black Crows
- Three Inside Up/Down
- Three Outside Up/Down
- Rising Three Methods / Falling Three Methods

## 6. Deviations from Standard Implementations

| Indikator | Standar | Implementasi | Alasan |
|-----------|---------|-------------|--------|
| MFI | Wilder smoothing | Rolling sum | Sesuai riset: MFI pakai rolling sum biasa |
| RSI edge case | Div-by-zero | RSI=100/50 | Handle avg_loss=0 |
| ADX alignment | N/A | Re-align ke index asli | Wilder RMA di atas array non-NaN |

## 7. Future Improvements

- [ ] **MACD** — belum diimplementasi (placeholder di PRD)
- [ ] **Parabolic SAR** — untuk trailing stop alternatif
- [ ] **Chandelier Exit** — trailing stop berbasis ATR
- [ ] **Volume Profile** — VPVR untuk S/R level lebih akurat
- [ ] **Efficiency Ratio (Kaufman)** — alternatif ADX gate
