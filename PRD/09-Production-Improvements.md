# Production Improvements — Fase 7

| Item | Detail |
|------|--------|
| **Target Version** | v0.3.0 |
| **Status** | Sprint 1 — Walk-Forward + Quick Win |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Berdasarkan riset paper akademik (Lopez de Prado 2018, Kaminski & Lo 2014), GitHub repositori, dan analisis backtest, berikut prioritas improvement yang sudah diurutkan berdasarkan dependensi validasi.

**Aturan utama:** Setiap sprint hanya jalan setelah sprint sebelumnya divalidasi OOS via walk-forward harness. Tidak ada parameter baru yang ditumpuk sebelum divalidasi.

## 2. Sprint 1 — Fondasi Validasi + Quick Win

### 2.1 S1A: Walk-Forward Harness Skeleton

Ekstensi `backtest.py` → modul `walkforward.py` terpisah.

**Design:**
- Ambil data historis per saham (OHLCV)
- Split ke N rolling window dengan ukuran tetap
- Setiap window: train (6 bulan) → optimize parameter → test OOS (3 bulan)
- Purge: hapus 20 hari sebelum test window dari training
- Embargo: gap 20 hari antara train dan test
- Concat **semua** OOS trade dari seluruh (saham × window) jadi 1 equity curve final
- Output: metrik OOS (Win Rate, Sharpe, Return, Max DD, Parameter Stability)

**Purge & Embargo (Lopez de Prado, "Advances in Financial ML"):**

```
Train ──────────┤ gap ├── Test ──────────
                20d   20d
```

### 2.2 S1B: Fix R:R Ratio

**Masalah:** R:R rata-rata 0.83 (TP 2.5 ATR, SL 3.0 ATR). EV = 0.55 × 2.5 - 0.45 × 3.0 = 0.04 ATR/trade.

**Solusi:** Naikkan `ATR_TP_MULTIPLIER` dari 2.5 ke **3.0** → R:R 1:1.

Dampak teoritis pada EV (dengan asumsi rough order WR dan TP hit rate serupa):
- EV baru = 0.55 × 3.0 - 0.45 × 3.0 = **0.30 ATR/trade** (7.5× lipat)

### 2.3 S1C: Breakeven Stop Rule

Parameter baru: `BREAKEVEN_TRIGGER = 1.0`.

Begitu harga mencapai entry + 1.0 ATR, SL dipindah ke entry price. Trade berikutnya risk-free.

**Justifikasi:**
- Melindungi modal setelah profit tercapai
- Tidak ada downside risk tambahan
- 1 parameter saja — mudah divalidasi
- Didukung literatur sebagai cara paling murah naikkin expectancy

### 2.4 S1D: Long-Only Mode

Default: `LONG_ONLY_MODE = True`.

**Alasan:**
- SELL sinyal paling tervalidasi (58% WR) tapi kebanyakan retail IDX tidak punya akses short-selling
- Jika tidak diperbaiki, dashboard akan merekomendasikan trade yang tidak bisa dieksekusi
- Solusi: SELL tetap tampil di scoring sebagai advisory/exit signal, trade plan tidak dibuat

**Implementasi:**
- Toggle di config, 0 parameter tuning
- SELL → `trade_plan = None`, `validation_note` menjelaskan
- BELL → tetap dihitung scoring-nya (informasi tetap berguna untuk exit)

## 3. Sprint 2 — Rekonsiliasi & Validasi

**Rekonsiliasi Position Sizing:**
- Dokumen (PRD/README) bilang 25%, kode `risk.py` pakai 100%
- Luruskan: pilih 100% — frontend CapitalControl sudah handle input user
- Update semua dokumentasi agar konsisten

**Validasi S1:**
- Jalanin walk-forward harness untuk konfigurasi v0.2.0 (baseline OOS)
- Jalanin harness untuk v0.3.0 (R:R fix + breakeven + long-only)
- Bandingkan metrik OOS — hanya lanjut jika improvement signifikan

## 4. Sprint 3 — Adaptive Threshold & Regime Filter

### 4.1 Market Regime Detection (Simple — SMA200 + ADX)

```python
def detect_regime(close, adx):
    sma200 = mean(close[-200:])
    trend = "bull" if close[-1] > sma200 else "bear"
    if adx[-1] < 20:
        trend = "sideways"
    return trend
```

Sengaja tidak pakai HMM — sample terlalu kecil (19 saham × 250 hari) untuk estimasi transition probability yang stabil.

### 4.2 Regime-Dependent Component Weights

| Regime | Trend | Momentum | Volume | PA |
|--------|:-----:|:--------:|:-----:|:--:|
| **Bull** | 0.35 | 0.25 | 0.15 | 0.25 |
| **Sideways** | 0.15 | 0.15 | 0.25 | **0.45** |
| **Bear** | 0.15 | **0.30** | 0.30 | 0.25 |

### 4.3 Regime-Dependent Buy Threshold

| Regime | Buy Threshold | Position Size |
|--------|:------------:|:------------:|
| Bull | 75 | 100% |
| Sideways | 70 | 50% |
| Bear | N/A (long-only) | 25% |

### 4.4 Circuit Breaker

Kurangi posisi size 50% setelah 2 loss beruntun. Reset setelah 1 winning trade.

## 5. Sprint 4+ — Enhancement Lanjutan (Ditunda)

### 5.1 Full Scale Out (50/30/20 + Trailing)

| Stage | Trigger | Aksi | Stop |
|-------|---------|------|------|
| Entry | Signal BUY | Full posisi | SL 3.0 ATR |
| T1 | +1.0 ATR | Close 50% | SL ke breakeven |
| T2 | +2.0 ATR | Close 30% | Trail 0.5 ATR |
| Sisa | — | Running | Trail sampai kena |

Hanya dikerjakan jika:
- Sprint 1-3 sudah selesai dan divalidasi OOS
- Ada bukti bahwa scale-out memberikan improvement signifikan dibanding breakeven rule saja

### 5.2 Dynamic ATR Multiplier

```python
if volatility_regime == "HIGH": sl *= 0.8
elif volatility_regime == "LOW": sl *= 1.2
```

### 5.3 XGBoost Feature Weighting

Gunakan XGBoost classifier untuk menentukan bobot optimal komponen scoring. Ditunda karena:
- Butuh data lebih banyak (sample 19 saham terlalu kecil)
- Butuh walk-forward yang matang sebagai validasi
- Manfaat mungkin marginal setelah regime filter diimplementasi

### 5.4 Ensemble Scoring

Kombinasi 3 set parameter, voting untuk sinyal final.

### 5.5 HMM Regime Detection

Pengganti SMA200+ADX jika terbukti regime filter saat ini masih kurang akurat.

## 6. Target Performance (v0.3.0)

| Metrik | v0.2.0 | Target S1-S2 | Target S3 | Target S4+ |
|--------|:------:|:------------:|:---------:|:----------:|
| Win Rate | 55.3% | 55-58% | >60% | >62% |
| TP_HIT rate | 40.4% | >50% | >55% | >60% |
| R:R rata-rata | 0.83 | 1.0+ | 1.2+ | 1.5+ |
| Sharpe | 0.24 | 0.30-0.40 | >0.50 | >0.60 |
| Max DD | 5.94% | <5.5% | <5% | <4.5% |
| Alpha vs B&H | +5.38% | +6-7% | >+8% | >+10% |

## 7. Timeline Estimasi

| Task | Complexity | Waktu | Dependensi |
|------|-----------|-------|-----------|
| S1A: Walk-forward harness | Sedang | 3-4 hari | — |
| S1B: Fix R:R (TP 3.0) | Rendah | <1 hari | S1A |
| S1C: Breakeven stop | Rendah | 1 hari | S1A |
| S1D: Long-only mode | Rendah | <1 hari | — |
| S2: Rekonsiliasi + validasi | Rendah | 1-2 hari | S1A–D |
| S3: Regime detection + adaptive | Rendah-Sedang | 2-3 hari | S2 |
| S4+: Scale-out, trailing, ML | Tinggi | 5-10 hari | S3 |
