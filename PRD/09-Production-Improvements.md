# Production Improvements — Fase 7

| Item | Detail |
|------|--------|
| **Target Version** | v0.3.0 |
| **Status** | Perencanaan |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Berdasarkan riset ekstensif dari paper akademik (Lopez de Prado 2018, Kaminski & Lo 2014, Li et al. 2026), GitHub repositori (mlfinlab, mefai-signal-engine, TradingbotAI), dan analisis 20-saham backtest, berikut prioritas improvement.

## 2. Prioritas P1: Exit Strategy Enhancement

Dampak tertinggi dengan kompleksitas terendah.

### 2.1 Partial Profit Taking (Scale Out)

| Stage | Aksi | Stop Management |
|-------|------|----------------|
| Entry | Full posisi | SL awal 3.0× ATR |
| T1 (+1.0× ATR) | Close **50%** | Pindah SL ke breakeven |
| T2 (+2.0× ATR) | Close **30%** | Trailing stop 0.5× ATR dari high |
| Sisa 20% | Biarkan running | Trail sampai kena atau timeout 20 hari |

**Referensi:** BreakOrb 28.7M test — TP Trail optimal di **43.3% strategi**. SnapPChart: Scale-out unggul di 2/3 skenario.

### 2.2 Dynamic ATR Multiplier

```python
base_sl = 3.0
if volatility_regime == "HIGH": sl *= 0.8
elif volatility_regime == "LOW": sl *= 1.2
```

## 3. Prioritas P2: Adaptive Threshold & Regime Filter

### 3.1 Dynamic Threshold

Threshold adaptif berdasarkan volatilitas 30 hari:

```python
vol = std(close_returns[-30:])
baseline_vol = mean(std(close_returns[-252:]))
vol_ratio = vol / baseline_vol

if vol_ratio > 1.5:  # High volatility
    buy_threshold = 65  # Lebih longgar
elif vol_ratio < 0.7:  # Low volatility
    buy_threshold = 75  # Lebih ketat
else:  # Normal
    buy_threshold = 70
```

**Referensi:** Rony-Hossain — **40-60% reduksi false positive**, 25-35% improvement true positive.

### 3.2 Market Regime Detection

```python
def detect_regime(close, adx):
    sma200 = mean(close[-200:])
    trend = "bull" if close[-1] > sma200 else "bear"
    strength = "strong" if adx[-1] > 25 else "weak"
    volatility = "high" if atr_ratio > 1.5 else "normal"
    return f"{trend}_{strength}_{volatility}"
```

**Regime-based rules:**

| Regime | Action | Position Size |
|--------|--------|--------------|
| bull_strong | Full swing trading | 100% |
| bull_weak | Hanya BUY signal kuat | 75% |
| bear_strong | Short-only (atau skip) | 50% |
| bear_weak | Mean-reversion preferred | 25% |
| sideways (ADX<20) | Skip trend signal | 0% |

**Referensi:** LedgerMind — 78% sinyal reversal di ADX>25 adalah FALSE. TrustyBull — ~70% strategi gagal di regime berbeda.

### 3.3 Regime-Dependent Component Weights

| Regime | Trend | Momentum | Volume | Price Action |
|--------|-------|----------|--------|-------------|
| Bull Strong | 0.35 | 0.25 | 0.15 | 0.25 |
| Bull Weak | 0.20 | 0.20 | 0.35 | 0.25 |
| Bear | 0.15 | 0.30 | 0.30 | 0.25 |
| Sideways | 0.15 | 0.15 | 0.25 | 0.45 |

## 4. Prioritas P3: Walk-Forward Validation

Implementasi walk-forward optimization untuk mencegah overfitting:

```python
# 6 bulan train → 3 bulan test → roll
windows = [
    (0, 126),     # train: Jan-Jun
    (126, 189),   # test: Jul-Sep
    (63, 189),    # train: Apr-Sep
    (189, 252),   # test: Oct-Dec
    ...
]

# Purge: hapus 20 hari sebelum/ sesudah test dari training
# Embargo: gap 20 hari antara train dan test
```

**Referensi:** Lopez de Prado "Advances in Financial ML", mlfinlab. Metrik validasi: concatenated OOS equity curve.

## 5. Prioritas P4: Machine Learning Enhancement

### 5.1 XGBoost Feature Weighting

Gunakan XGBoost classifier untuk menentukan bobot optimal tiap komponen scoring:

```
Features: RSI, MFI, ADX, RVOL, EMA_spread, ATR_ratio, S/R_position, Donchian_breakout
Target: next_5d_return > ATR (binary classification)
```

**Referensi:** `gammarinaldi/ml-trading-random-forest-xgboost` — 83% improvement dari optimasi. `mefai-signal-engine` — production-grade ML scoring.

### 5.2 Ensemble Scoring

Kombinasi 3 set parameter, voting untuk sinyal final:

```python
configs = [
    {"trend_weight": 0.35, "momentum_weight": 0.25, ...},  # Conservative
    {"trend_weight": 0.25, "momentum_weight": 0.35, ...},  # Aggressive
    {"trend_weight": 0.20, "momentum_weight": 0.20, ...},  # Balanced
]
# Consensus: minimal 2/3 setuju
```

## 6. Target Performance (v0.3.0)

| Metrik | Current (v0.2.0) | Target (v0.3.0) |
|--------|-----------------|-----------------|
| Win Rate | 55.3% | >60% |
| TP_HIT rate | 40.4% | >55% |
| Sharpe Ratio | 0.24 | >0.50 |
| Max Drawdown | 5.94% | <5% |
| Alpha vs B&H | +5.38% | >+8% |
| Avg R:R | 0.83 | >1.2 |

## 7. Timeline Estimasi

| Task | Complexity | Waktu | Dependency |
|------|-----------|-------|-----------|
| Partial Profit Taking + Trailing | Rendah | 2 hari | — |
| Dynamic Threshold | Rendah | 1 hari | — |
| Market Regime Filter | Rendah | 1-2 hari | — |
| Dynamic Weights | Sedang | 2-3 hari | Regime Filter |
| Walk-Forward Validation | Sedang | 3-4 hari | — |
| XGBoost Scoring | Tinggi | 5-7 hari | Walk-Forward |
| Ensemble Scoring | Tinggi | 3-5 hari | XGBoost |
