# Scoring System — Swing Score 0-100

| Item | Detail |
|------|--------|
| **Modul** | `backend/scoring.py` |
| **Versi** | v0.2.0 |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Swing Score adalah angka 0-100 yang merepresentasikan kekuatan sinyal swing trading untuk suatu saham. Skor ini dihitung dari 4 komponen equal-weight (masing-masing 25%) dengan ADX gating.

## 2. Komponen Swing Score

| Komponen | Bobot | Sumber | Gating |
|----------|-------|--------|--------|
| **Trend** | 0.25 | EMA(10,25) spread / ATR | ADX gate (ceiling 20) |
| **Momentum** | 0.25 | RSI(14) + MFI(14) average | ADX gate (sama) |
| **Volume** | 0.25 | RVOL(10) + arah harga | — |
| **Price Action** | 0.25 | S/R distance + Donchian breakout | RVOL ≥ 1.5 |

## 3. Detail Rumus

### 3.1 ADX Gate

```python
gate = min(ADX / 20, 1.0)   # ceiling 20 (kalibrasi v0.2.0)
trend_final = 0.5 + (trend_raw - 0.5) * gate
momentum_final = 0.5 + (momentum_raw - 0.5) * gate
```

Saat ADX = 0 (sideways): gate = 0 → komponen netral 0.5.
Saat ADX ≥ 20: gate = 1.0 → komponen full-scale.

### 3.2 Trend Score

```python
spread_atr = (EMA10 - EMA25) / ATR
normalized = clip((spread_atr + 3.0) / 6.0, 0.0, 1.0)
trend = 0.5 + (normalized - 0.5) * gate
```

### 3.3 Momentum Score

```python
raw = (RSI/100 + MFI/100) / 2.0
momentum = 0.5 + (raw - 0.5) * gate
```

### 3.4 Volume Score

```python
sign = 1 if close > close[-1] else -1
clamped = clip(RVOL - 1.0, 0.0, 1.0)
volume = 0.5 + sign * clamped * 0.5
```

### 3.5 Price Action Score

- Base: posisi harga dalam range S/R terdekat (0-1)
- Breakout: 1.0 jika close > Donchian Upper + RVOL ≥ 1.5
- Breakdown: 0.0 jika close < Donchian Lower + RVOL ≥ 1.5
- Selain itu: pakai base position

## 4. Recommendation Threshold

| Swing Score | Recommendation | Validated |
|-------------|----------------|-----------|
| ≥ 75 | BUY | ❌ (experimental, no independent edge) |
| 36 - 74 | HOLD | ✅ |
| ≤ 35 | SELL | ✅ (58% WR cross-regime) |

## 5. Confidence

```python
confidence = agreement_score * strength_factor
strength_factor = (gate + min(RVOL/1.5, 1.0)) / 2.0
```

| Rentang | Label | BUY adjustment |
|---------|-------|----------------|
| < 0.4 | Rendah | — |
| 0.4 - 0.75 | Sedang | → Rendah |
| > 0.75 | Tinggi | → Sedang |

## 6. Risk Level

```python
atr_ratio = ATR[-1] / mean(ATR[-50:])
```

| Rentang | Label |
|---------|-------|
| < 0.8 | Rendah |
| 0.8 - 1.5 | Sedang |
| > 1.5 | Tinggi |

## 7. Identified Issues

| Issue | Dampak | Status |
|-------|--------|--------|
| Equal-weight tidak optimal | Bobot 0.25 untuk semua komponen belum tentu optimal di semua regime | ❌ Belum dioptimasi |
| Threshold statis | Threshold 75/35 fixed, tidak adaptif terhadap volatilitas | ❌ Belum |
| Tidak ada regime filter | Sama scoring-nya di bull vs bear market | ❌ Belum |
| BUY tidak tervalidasi | Threshold 75 belum punya edge independen | ❌ Fase 6.5 |
| No walk-forward | Parameter mungkin overfit ke periode test | ❌ Belum |

## 8. Future Improvements (Fase 7)

- [ ] **Dynamic threshold**: threshold adaptif berdasarkan volatilitas pasar
- [ ] **Regime-dependent weights**: bobot komponen berubah sesuai regime (bull/bear/sideways)
- [ ] **Market regime filter**: hanya trading di regime yang sesuai
- [ ] **Walk-forward validation**: validasi parameter out-of-sample
- [ ] **Machine learning weighting**: XGBoost feature importance untuk bobot dinamis
