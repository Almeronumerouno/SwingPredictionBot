# Product Requirements Document — Swing Bot IDX

| Item | Detail |
|------|--------|
| **Product Name** | Swing Bot IDX |
| **Version** | 0.2.0 |
| **Status** | Fase 6 (Testing & Refinement) selesai |
| **Last Updated** | 25 Juli 2026 |

---

## 1. Product Overview

### 1.1 Ringkasan

Swing trading signal generator untuk Bursa Efek Indonesia (IDX). Sistem mengambil data pasar dari IDX (1 call = seluruh pasar), menghitung indikator teknikal Wilder-class, menghasilkan Swing Score 0-100 dari 4 komponen dengan ADX gating, dan menyusun trade plan (SL/TP/sizing) berbasis ATR.

### 1.2 Mengapa Ini Dibutuhkan

- Rata-rata investor ritel IDX tidak punya alat analisis teknikal yang terstruktur
- Data IDX tersebar dan sulit diakses — sistem ini mengkonsolidasi 2 endpoint IDX + Yahoo Finance
- Scoring kuantitatif menghilangkan bias subjektif dalam membaca indikator
- Risk management terintegrasi (posisi sizing, SL/TP) melindungi modal

### 1.3 Perubahan dari Rencana Awal

Awalnya direncanakan bot Telegram. Diubah menjadi **dashboard web** (FastAPI + Next.js) karena:
- Dashboard web lebih kaya secara visual (chart, tabel, warna)
- Lebih mudah diakses via browser tanpa instalasi
- Bisa dikembangkan jadi platform multi-user

---

## 2. Goals & Objectives

### 2.1 Tujuan Utama

1. **Menyediakan analisis teknikal otomatis** untuk seluruh saham IDX
2. **Memberikan sinyal trading objektif** (BUY/SELL/HOLD) berbasis data
3. **Mengintegrasikan risk management** (SL, TP, posisi sizing)
4. **Akses cepat via web dashboard** dalam 2 klik dari gainers ke detail

### 2.2 Success Metrics

| Metrik | Target |
|--------|--------|
| Waktu scrape seluruh pasar | < 1 menit (IDX primary), < 5 menit (Yahoo fallback) |
| Waktu analisis per saham | < 3 detik (termasuk fetch Yahoo + compute) |
| Cakupan saham | Seluruh saham IDX (~900 emiten) |
| Akurasi scoring (mid-big cap liquid) | Win Rate 55.3%, Alpha +5.38% vs B&H, Sharpe 0.24 |

---

## 3. Target Audience

| Segmen | Kebutuhan | Prioritas |
|--------|-----------|-----------|
| **Investor ritel individu** | Analisis cepat, rekomendasi jelas, risk management | **Primary** |
| **Trader swing pemula** | Panduan entry/exit, sizing aman, edukasi indikator | Secondary |
| **Analis / research house** | Data mentah indikator, screening cepat | Tersier |

---

## 4. Features & Requirements

### Fase 0 — Setup & Validasi Data Source (100% Selesai)

| ID | Requirement | Status |
|----|-------------|--------|
| F0.1 | Fetch seluruh daftar saham IDX via `GetSecuritiesStock` | ✅ |
| F0.2 | Fetch snapshot harian seluruh pasar via `GetStockSummary` | ✅ |
| F0.3 | Fetch data historis OHLCV via Yahoo Finance (suffix `.JK`) | ✅ |
| F0.4 | Cloudflare bypass via `cloudscraper` | ✅ |
| F0.5 | Caching daftar saham ke JSON (tidak perlu fetch tiap kali) | ✅ |

### Fase 1 — Layer Indikator (100% Selesai)

| ID | Requirement | Sumber | Periode | Algoritma |
|----|-------------|--------|---------|-----------|
| F1.1 | **EMA Trend** — EMA(10, 25) sebagai filter tren | `indicators.py:74` | 10/25 | EMA standar, seed SMA |
| F1.2 | **ATR** — Average True Range Wilder | `indicators.py:101` | 14 | Wilder RMA |
| F1.3 | **RSI** — Relative Strength Index Wilder | `indicators.py:111` | 14 | Wilder RMA, edge case handling |
| F1.4 | **ADX** — Directional Movement System (+DI, -DI, DX) | `indicators.py:144` | 14 | Wilder RMA dobel |
| F1.5 | **MFI** — Money Flow Index | `indicators.py:202` | 14 | Rolling sum (BUKAN Wilder) |
| F1.6 | **RVOL** — Relative Volume | `indicators.py:241` | 20 | Excluding hari ini dari baseline |
| F1.7 | **Donchian Channel** — Upper/Lower 20 hari | `indicators.py:260` | 20 | Rolling min/max |
| F1.8 | **Swing Points** — Fractal 5-bar (Bill Williams) | `indicators.py:278` | 2 | Lagging by design |
| F1.9 | **S/R Levels** — Clustering swing points | `indicators.py:313` | 1% toleransi | Mean-shift clustering |
| F1.10 | **Fibonacci** — Retracement 7 level + Extension | `indicators.py:353,364` | — | Ratio 0/23.6/38.2/50/61.8/78.6/100 |
| F1.11 | **Candlestick Patterns** — Doji, Hammer, Engulfing | `indicators.py:375` | — | Threshold-based detection |

### Fase 2 — Normalisasi & Scoring (100% Selesai)

| ID | Requirement | Detail | Sumber |
|----|-------------|--------|--------|
| F2.1 | **Trend Score** | EMA spread / ATR, dinormalisasi 0-1, ADX-gated | `scoring.py:49` |
| F2.2 | **Momentum Score** | Rata-rata RSI + MFI, ADX-gated | `scoring.py:57` |
| F2.3 | **Volume Score** | RVOL × arah perubahan harga | `scoring.py:65` |
| F2.4 | **Price Action Score** | Posisi harga di S/R + Donchian breakout (RVOL ≥ 2) | `scoring.py:73` |
| F2.5 | **Swing Score** | 0-100 = 0.25 × (trend + momentum + volume + price_action) | `scoring.py:268` |
| F2.6 | **ADX Gate** | Linear 0→1 dari ADX=0 sampai ADX=25 (ceiling) | `scoring.py:21` |
| F2.7 | **Recommendation** | BUY ≥ 65, SELL ≤ 35, HOLD di antaranya | `scoring.py:276` |
| F2.8 | **Confidence** | agreement_score × strength_factor (gate + rvol_strength)/2 | `scoring.py:130` |
| F2.9 | **Risk Level** | ATR[-1] / mean(ATR[-50:]), cutoff 0.8/1.5 | `scoring.py:155` |
| F2.10 | **Validity Gate** | Return `valid: False` jika komponen mana pun NaN | `scoring.py:243` |

### Fase 3 — Risk & Trade Plan (100% Selesai)

| ID | Requirement | Rumus | Sumber |
|----|-------------|-------|--------|
| F3.1 | **Stop Loss** | entry ± ATR × 1.5 (0.8 × multiplier jika risk tinggi) | `risk.py:10` |
| F3.2 | **Take Profit** | entry ± ATR × 2.5 (R:R ~1:1.67) | `risk.py:20` |
| F3.3 | **Position Sizing** | capital × 25% / entry_price, rounded ke lot (100 lembar) | `risk.py:28` |
| F3.4 | **Fallback sizing** | Jika 25% < 1 lot, coba 50% capital | `risk.py:51` |
| F3.5 | **Risk info** | Hitung risk aktual, tampilkan sebagai info (bukan warning) | `risk.py:55` |

### Fase 4 — API Layer (100% Selesai)

| ID | Endpoint | Method | Deskripsi | Sumber |
|----|----------|--------|-----------|--------|
| F4.1 | `/scrape` | POST | Trigger scrape gainers dari IDX (fallback Yahoo) | `api.py:191` |
| F4.2 | `/gainers?date=` | GET | Top N gainers + Swing Score per saham | `api.py:206` |
| F4.3 | `/analisis/{kode}?capital=` | GET | Analisis lengkap 1 saham (indikator → scoring → risk) | `api.py:270` |
| F4.4 | `/history/{kode}?length=` | GET | Data OHLCV historis mentah | `api.py:300` |
| F4.5 | CORS | — | Allow origins dari config (`localhost:3000`) | `api.py:182` |

### Fase 5 — Frontend Dashboard (100% Selesai)

| ID | Requirement | Status | Route |
|----|-------------|--------|-------|
| F5.1 | **Dashboard** — Top Gainers table + signal badges | ✅ | `/` |
| F5.2 | **Detail Saham** — Score cards, component bars, chart, trade plan | ✅ | `/saham/[kode]` |
| F5.3 | **Scrape Button** — Trigger scrape + toast notification | ✅ | `/` (header) |
| F5.4 | **Date Picker** — Pilih tanggal gainers | ✅ | `/` (header) |
| F5.5 | **Sidebar Nav** — Dashboard, Analisis | ✅ | Layout |
| F5.6 | **Halaman Analisis** — Form input kode saham | ✅ | `/analisis` |
| F5.7 | **Capital Control** — Ubah modal & history length | ✅ | `/saham/[kode]` |
| F5.8 | **Loading Skeleton** | ✅ | `/saham/[kode]` |
| F5.9 | **Error & Not Found** | ✅ | Global + per-route |
| F5.10 | **Toast Notification** | ✅ | Auto-dismiss 4 detik |
| F5.11 | **Capital auto-format** (Indonesian thousand separator) | ✅ | CapitalControl |
| F5.12 | **Logo swingbot** — ganti favicon + metadata | ✅ | Layout |
| F5.13 | **Sidebar "Top Gainers" → "Dashboard"** | ✅ | Sidebar |
| F5.14 | **Dark Mode** | ❌ | Belum |
| F5.15 | **Search / Filter** gainers | ❌ | Belum |

### Fase 6 — Testing & Refinement (100% Selesai)

| ID | Requirement | Status | Hasil |
|----|-------------|--------|-------|
| F6.1 | Backtest engine (`backtest.py`) | ✅ | Walk-bar simulation, compute_signals (replikasi scoring), metrics (Win Rate, Sharpe, Max DD, Alpha vs B&H), CLI argparse, ANSI report |
| F6.2 | Calibration runner (`backtest_calibrate.py`) | ✅ | Cartesian product 243 combo × 4+ saham, leaderboard by Sharpe/return, export JSON |
| F6.3 | Calibrate ADX gate ceiling | ✅ | Optimal **20** (default 25 — lebih sensitif, meningkatkan jumlah sinyal di tren lemah) |
| F6.4 | Calibrate RVOL window | ✅ | Optimal **10** (default 20 — lebih responsif terhadap perubahan volume) |
| F6.5 | Calibrate R:R ratio (ATR multipliers) | ✅ | SL multiplier optimal **3.0** (default 1.5 — SL lebih longgar, win rate naik 35.6%→58.0%) |
| F6.6 | Buy threshold calibration | ✅ | Optimal **70** (default 65 — lebih selektif, mengurangi false signal) |
| F6.7 | RVOL breakout confirm | ✅ | Optimal **1.5** (default 2.0 — lebih longgar, menangkap lebih banyak sinyal valid) |

**Parameter Default Produksi (setelah kalibrasi):**

| Parameter | Default Lama | Default Baru (v0.2.0) |
|-----------|:-----------:|:--------------------:|
| `ADX_GATE_CEILING` | 25 | **20** |
| `SWING_BUY_THRESHOLD` | 65 | **70** |
| `ATR_SL_MULTIPLIER` | 1.5 | **3.0** |
| `RVOL_WINDOW` | 20 | **10** |
| `RVOL_BREAKOUT_CONFIRM` | 2.0 | **1.5** |

**Hasil Backtest Lengkap (mid-big cap liquid, 19 saham):**

| Metrik | Default (Fase 1-5) | **Kalibrasi (v0.2.0)** |
|--------|:-----------------:|:---------------------:|
| **Win Rate** | 35.6% | **55.3%** |
| **Total Return** | -1.92% | **+0.41%** |
| **Alpha vs B&H** | +0.86% | **+5.38%** |
| **Sharpe Ratio** | -0.72 | **0.24** |
| **Max Drawdown** | 5.25% | **5.94%** |
| **Beat B&H Ratio** | — | **13/19 (68%)** |

**Catatan Penting:**
- Sistem **unggul di bear market**: proteksi modal dengan max DD 5.94%, sementara B&H rata-rata -4.98%
- Sistem **kalah di bull market**: ketinggalan saham dengan kenaikan eksplosif (ADRO +51%, GGRM +43%) — sistem dirancang konservatif
- **Micro-cap gainers tidak cocok** untuk sistem ini (win rate 38.8%, alpha -21.01%) — sistem optimal di saham likuid mid-big cap
- **Fees & slippage belum dimodelkan** — return overstate ~2-5%
- **Short selling bias** — IDX retail tidak bisa short, SELL signal belum dinonaktifkan
- **Look-ahead minor**: S/R levels pakai full history (Price Action komponen, efek kecil)
- **Walk-forward validation belum dilakukan** — parameter optimal mungkin overfit ke periode test

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
│                                                                  │
│  ┌─────────────────────┐    ┌───────────────────────────────┐    │
│  │  IDX (idx.co.id)    │    │  Yahoo Finance (yfinance)     │    │
│  │  - GetSecuritiesStock│    │  - Historical OHLCV           │    │
│  │  - GetStockSummary   │    │  - Fallback gainers scan     │    │
│  └──────────┬──────────┘    └──────────┬────────────────────┘    │
└─────────────┼──────────────────────────┼──────────────────────────┘
              │                          │
              ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND (Python)                         │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ indices │  │ scoring │  │  risk   │  │   api    │         │
│  │  .py    │→│  .py    │→│  .py    │→│  .py    │         │
│  │ (numpy) │  │ (4 comp)│  │ (SL/TP) │  │(FastAPI)│         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
│                           │            │                         │
│                           ▼            ▼                         │
│                    ┌──────────┐  ┌──────────┐                    │
│                    │  Cache   │  │  Config  │                    │
│                    │ (JSON)   │  │  .py    │                    │
│                    └──────────┘  └──────────┘                    │
└─────────────────────────────────┬────────────────────────────────┘
                                  │ JSON (FastAPI)
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 16)                        │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │Dashboard │  │Analisis  │  │ Stock    │  │Sidebar  │         │
│  │ /gainers │  │ Search   │  │ Detail   │  │ Nav     │         │
│  │ Table    │  │ Form     │  │ Chart    │  │ Links   │         │
│  │ + Signal │  │          │  │ Score    │  │         │         │
│  └──────────┘  └──────────┘  │ Trade    │  └──────────┘         │
│                              │ Plan     │                        │
│                              └──────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Data Flow Lengkap

```
User klik "Scrape Data"
        │
        ▼
POST /scrape
        │
        ├─▶ IDX GetStockSummary (1 call)
        │       │
        │       ├─▶ Sukses → sort by %change → Top 15
        │       │
        │       └─▶ Gagal → ThreadPool Yahoo (~900 saham)
        │
        ▼
Cache ke gainers_{date}.json
        │
        ▼
Halaman refresh → GET /gainers
        │
        ▼
Untuk tiap gainer:
  ├─▶ Yahoo Finance fetch 250 hari
  ├─▶ compute indicators (RSI, ADX, MFI, ATR, EMA, RVOL, Donchian, S/R)
  ├─▶ compute_score() → Swing Score + recommendation
  └─▶ Annotate entry (swing_score, recommendation)
        │
        ▼
Tampilkan table + signal badges

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

User klik kode saham → /saham/BBCA
        │
        ▼
Parallel fetch:
  ├─▶ GET /analisis/BBCA?capital=10000000
  │       │
  │       ├─▶ Validasi kode di securities list
  │       ├─▶ Yahoo Finance fetch 250 hari
  │       ├─▶ compute indicators
  │       ├─▶ compute_score()
  │       ├─▶ Jika BUY/SELL → build_trade_plan()
  │       └─▶ Return AnalisisResponse
  │
  └─▶ GET /history/BBCA?length=250
          │
          └─▶ Yahoo Finance fetch → Return OHLCV bars
        │
        ▼
Render:
  ├─▶ ScoreCard (Swing Score, Confidence, Risk Level, Valid)
  ├─▶ Component bars (Trend, Momentum, Volume, Price Action)
  ├─▶ PriceChart (candlestick, lightweight-charts)
  ├─▶ TradePlanCard (SL/TP/lots/R:R)
  └─▶ CapitalControl (modal, history length)
```

### 5.3 Stack

| Layer | Teknologi | Versi |
|-------|-----------|-------|
| **Backend Framework** | FastAPI (Python) | 3.14 |
| **Indikator** | NumPy | — |
| **Data Source** | cloudscraper + yfinance | — |
| **Cache** | JSON file | — |
| **Frontend** | Next.js | 16.2.10 |
| **UI Library** | React | 19.2.4 |
| **Chart** | lightweight-charts | 5.2.0 |
| **CSS** | Tailwind CSS | 4.3.3 |
| **Font** | Inter (Google Fonts) | — |

---

## 6. API Specification

### 6.1 POST /scrape

Trigger scraping top gainers dari IDX (fallback Yahoo).

**Request:**
```
POST /scrape
Content-Type: application/json
```

**Response 200:**
```json
{
  "status": "ok",
  "count": 15,
  "message": "Scrape berhasil. 15 gainers ditemukan."
}
```

**Response 500:**
```json
{
  "detail": "Scrape gagal: <error message>"
}
```

### 6.2 GET /gainers

Ambil daftar top gainers + Swing Score.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `date` | string | No | Hari ini | Format `YYYY-MM-DD` |

**Response 200:** `GainersResponse` — lihat detail di response model.

**Response 404:** Belum ada data gainers untuk tanggal tersebut.

### 6.3 GET /analisis/{kode}

Analisis teknikal lengkap untuk satu saham.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `kode` | string | Kode saham IDX (case-insensitive) |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `capital` | float | No | 10,000,000 | Modal trading dalam IDR |

**Response 200:** `AnalisisResponse`

| Field | Type | Description |
|-------|------|-------------|
| `kode` | string | Kode saham |
| `nama` | string | Nama emiten |
| `harga` | float | Harga penutupan terakhir |
| `last_updated` | string | Tanggal data terakhir |
| `score.valid` | bool | Apakah data scoring valid |
| `score.swing_score` | float | 0-100 |
| `score.components` | dict | `trend`, `momentum`, `volume`, `price_action` (0-1) |
| `score.recommendation` | string | `BUY` / `SELL` / `HOLD` |
| `score.confidence` | string | `tinggi` / `sedang` / `rendah` |
| `score.risk_level` | string | `rendah` / `sedang` / `tinggi` |
| `trade_plan` | object | null jika HOLD / tidak valid |
| `capital_used` | float | Modal yang digunakan |

**TradePlan Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `direction` | string | `BUY` / `SELL` |
| `entry` | float | Harga entry |
| `stop_loss` | float | Level stop loss |
| `take_profit` | float | Level take profit |
| `shares` | int | Jumlah lembar saham |
| `lots` | int | Jumlah lot (1 lot = 100 lembar) |
| `risk_reward_ratio` | float | Rasio risk/reward |
| `note` | string | Pesan jika capital tidak cukup |

### 6.4 GET /history/{kode}

Data OHLCV historis mentah.

**Query Parameters:**

| Parameter | Type | Required | Default | Max | Description |
|-----------|------|----------|---------|-----|-------------|
| `length` | int | No | 250 | 365 | Hari kalender |

**Response 200:** `HistoryResponse` — array `bars` dengan `date`, `close`, `open`, `high`, `low`, `volume`.

---

## 7. Scoring System Detail

### 7.1 Komponen Swing Score

| Komponen | Bobot | Rumus | Gating |
|----------|-------|-------|--------|
| **Trend** | 0.25 | `(EMA10 - EMA25) / ATR`, normalized 0-1 | ADX gate (0→1) |
| **Momentum** | 0.25 | `(RSI/100 + MFI/100) / 2` | ADX gate (sama) |
| **Volume** | 0.25 | `0.5 + sign(price_change) × min(RVOL-1, 1) × 0.5` | — |
| **Price Action** | 0.25 | Posisi di S/R range + Donchian breakout | RVOL ≥ 1.5 untuk breakout (kalibrasi) |

### 7.2 ADX Gate

```
gate = min(ADX / 20, 1.0)   # ceiling 20 (kalibrasi v0.2.0)
trend_final = 0.5 + (trend_raw - 0.5) × gate
momentum_final = 0.5 + (momentum_raw - 0.5) × gate
```

Saat ADX = 0 (sideways), gate = 0 → trend & momentum ditarik ke netral 0.5.
Saat ADX ≥ 20 (kalibrasi v0.2.0), gate = 1.0 → komponen full-scale.

### 7.3 Confidence

```
confidence = agreement_score × strength_factor
strength_factor = (gate + min(rvol/2, 1)) / 2
```

| Rentang | Label |
|---------|-------|
| < 0.4 | Rendah |
| 0.4 - 0.75 | Sedang |
| > 0.75 | Tinggi |

### 7.4 Risk Level

```
atr_ratio = ATR[-1] / mean(ATR[-50:])
```

| Rentang | Label |
|---------|-------|
| < 0.8 | Rendah |
| 0.8 - 1.5 | Sedang |
| > 1.5 | Tinggi |

### 7.5 Recommendation Threshold

| Swing Score | Recommendation |
|-------------|----------------|
| ≥ 70 | BUY |  # threshold dinaikkan (kalibrasi v0.2.0)
| 36 - 69 | HOLD |
| ≤ 35 | SELL |

---

## 8. Risk Management

| Parameter | Value | Notes |
|-----------|-------|-------|
| Position sizing | 25% alokasi modal (fallback 50%) | Capital-based, bukan risk-based |
| Risk per trade | Bervariasi — informasional | Ditampilkan sebagai "Risiko aktual X%" |
| Stop Loss | entry ± ATR × **3.0** | Kalibrasi v0.2.0 (default lama 1.5 — SL diperlonggar untuk naikkin win rate) |
| Take Profit | entry ± ATR × 2.5 | R:R ~1:0.83 |
| Lot size | 100 lembar | Konvensi IDX |
| Minimal capital | ~Rp 100,000 | Tergantung harga saham (1 lot termurah) |

---

## 9. UI/UX Design System

### 9.1 Design Tokens

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

### 9.2 Typography

- **Font**: Inter (300, 400, 500, 600, 700, 800)
- **Body**: 14px, line-height 1.5
- **Financial data**: `tabular-nums` (monospaced figures)
- **Scale**: 10px → 12px → 14px → 16px → 18px → 24px → 30px → 36px

### 9.3 Layout Pattern

```
┌─────────┬──────────────────────────────────────────────────┐
│ Sidebar │  Header (title + actions)                        │
│  64px   │                                                  │
│ sticky  ├──────────────────────────────────────────────────┤
│ h-screen│  Content                                          │
│         │  - Stat cards (grid-cols-3)                       │
│ Logo    │  - Table / Cards / Chart                          │
│ Nav:    │  - Full width, max-w-[1400px]                     │
│  - Dash │                                                   │
│  - Anal │  Footer (copyright + disclaimer)                  │
├─────────┴──────────────────────────────────────────────────┤
```

### 9.4 Component Inventory

| Component | Type | States | Location |
|-----------|------|--------|----------|
| GainersTable | Client | Loading, empty, data, error | `components/gainers-table.tsx` |
| ScoreCard | Server | Default, positive, negative | `components/score-card.tsx` |
| TradePlanCard | Server | Default, empty (HOLD) | `components/trade-plan-card.tsx` |
| PriceChart | Client | Loading, data, empty | `components/price-chart.tsx` |
| ScrapeButton | Client | Idle, loading, success toast, error toast | `components/scrape-button.tsx` |
| DatePicker | Client | Default, selected | `app/date-picker.tsx` |
| CapitalControl | Client | Default, applied | `app/saham/[kode]/capital-control.tsx` |
| Sidebar | Server | Active link, hover | `components/sidebar.tsx` |

### 9.5 Navigasi

```
Sidebar
├── Dashboard     →  /           (Top Gainers + signal badges)
└── Analisis      →  /analisis   (Form input kode saham)
                      │
                      └── /saham/{kode}  (Detail analisis lengkap)
```

---

## 10. Data Sources Comparison

| Data | Sumber | Frekuensi | Coverage | Latency |
|------|--------|-----------|----------|---------|
| Securities list | IDX GetSecuritiesStock | 1x (cache ke JSON) | ~900 emiten | ~3 detik |
| Daily snapshot | IDX GetStockSummary | 1x per hari | Seluruh pasar | ~3 detik |
| Historical OHLCV | Yahoo Finance (.JK) | Per request | Per saham | ~1-2 detik |
| Top Gainers | IDX (primary), Yahoo (fallback) | 1x per hari | 15 saham | ~3 detik (IDX) / ~3 menit (Yahoo) |

---

## 11. Implementasi di Frontend

### 11.1 Yang Sudah Ditampilkan

| Backend Component | Frontend Display | Halaman |
|-------------------|-----------------|---------|
| Swing Score | Signal badge (BUY/SELL/HOLD + score) | Dashboard table |
| Swing Score | ScoreCard + badge | Detail saham header |
| Components (trend, momentum, volume, price_action) | 4 progress bars 0-100% | Detail saham |
| Confidence | ScoreCard | Detail saham |
| Risk Level | ScoreCard | Detail saham |
| Data Valid gate | ScoreCard (Yes/No) | Detail saham |
| Trade Plan (SL, TP, lots, R:R) | TradePlanCard | Detail saham |
| OHLCV history | Candlestick chart (lightweight-charts) | Detail saham |
| RSI(14), MFI(14), ADX + DI | GaugeBar components (Oscillators) | Detail saham |
| RVOL(20) | GaugeBar component (Volume) | Detail saham |
| ATR(14), EMA(10,25) | Text display (Parameters) | Detail saham |
| Support/Resistance levels | Text display (Price Action) | Detail saham |
| Fibonacci levels | Progress bar display (Price Action) | Detail saham |
| Candlestick patterns | Pattern cards dengan dynamic SVG (Price Action) | Detail saham |
| Scrape timestamp | Stat card "Terakhir Diambil" | Detail saham |

### 11.2 Yang Belum Ditampilkan (Tersedia di Backend)

*Semua data dari backend sudah ditampilkan di frontend (Fase 5 selesai sepenuhnya).*

### 11.3 Yang Tidak Ada di Backend

| Fitur | Keterangan |
|-------|------------|
| MACD | Belum diimplementasi di indicators.py |
| Probability continuation/reversal | Placeholder (butuh backtest) |

---

## 12. Konfigurasi

### 12.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | No | `""` | Legacy (tidak dipakai) |
| `API_BASE_URL` (server) | No | `http://localhost:8000` | Backend URL untuk server component |
| `NEXT_PUBLIC_API_BASE_URL` (client) | No | `http://localhost:8000` | Backend URL untuk client component |

### 12.2 Parameter Scoring & Risk

Semua parameter operasional di `config.py` — lihat tabel di bagian 4 untuk detail lengkap.

---

## 13. Future Roadmap

### Short-term (Sudah Selesai — Fase 5)
- ✅ Scrape trigger + toast notification
- ✅ Capital control dengan auto-format
- ✅ Logo swingbot + favicon
- ✅ Trade Plan note informatif ("Risiko aktual X%")
- ✅ Sidebar navigation (Dashboard, Analisis)
- ✅ Stock detail page (ScoreCard, chart, trade plan, capital control)
- ✅ Indicator detail panel (RSI, ADX, MFI, RVOL, S/R, Fibonacci, Candlestick)

### Short-term (Next)
- [ ] Dark mode
- [ ] Sorting & filtering gainers table
- [ ] Auto-refresh scrape (cron/scheduler)
- [ ] Export laporan PDF
- [ ] Long-only mode (nonaktifkan SELL untuk IDX retail)
- [ ] Fees & slippage modeling (broker 0.15-0.35% round trip)

### Medium-term (Fase 7 — Production)
- [ ] Walk-forward validation (test calibrated params out-of-sample)
- [ ] Docker + cron scheduler (daily scan IDX)
- [ ] Market regime filter (bear/bull/sideways — sesuaikan parameter otomatis)
- [ ] Trailing stop untuk winning trades
- [ ] Dynamic position sizing by confidence score
- [ ] Weight optimization (bobot 4 komponen via grid search)
- [ ] Multiple timeframe filter (weekly trend konfirmasi)

### Long-term
- [ ] Multi-user accounts
- [ ] Watchlist / portfolio tracking
- [ ] Real-time data (WebSocket IDX)
- [ ] Screening engine (scan seluruh pasar untuk sinyal BUY/SELL)
- [ ] Notification (email/push) untuk sinyal baru
- [ ] Ensemble scoring (3 set parameter, consensus signal)

---

## 14. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| IDX mengubah endpoint | Scraping gagal | Cloudscraper, retry logic, Yahoo fallback |
| Yahoo rate limit | Data historis lambat | Cache history ke JSON, minimal request |
| Cloudflare blocking | Gagal akses IDX | Session init, user-agent rotate |
| Data tidak akurat | Sinyal salah | Validity gate (NaN → invalid), backtest kalibrasi |
| IdX data baru tersedia setelah market tutup | Gainers kosong | Fallback max 3 hari ke belakang |
