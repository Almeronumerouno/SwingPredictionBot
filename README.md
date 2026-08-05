# Swing Bot IDX — Swing Trading Signal System

Swing trading signal generator untuk Bursa Efek Indonesia (IDX). Data dari IDX langsung (1 call = seluruh pasar), indikator teknis Wilder-class, scoring 4 komponen dengan ADX gating.

## Progress

| Fase | Deskripsi | Status |
|------|-----------|--------|
| 0 | Setup & Validasi Data Source | **100%** |
| 1 | Layer Indikator (`indicators.py`) | **100%** |
| 2 | Layer Normalisasi & Scoring (`scoring.py`) | **100%** |
| 3 | Risk & Trade Plan (`risk.py`) | **100%** |
| 4 | API Layer (`api.py`, FastAPI) | **100%** |
| 5 | Frontend Dashboard (Next.js) | **100%** |
| 6 | Testing & Refinement | **100%** |
| **7** | **Production Readiness** (v0.3.0-wip) | **Sprint 1 berjalan** |

### Hasil Backtest (Fase 6)

**Parameter optimal (kalibrasi 243 combo × 19 saham):**

| Parameter | Default | Kalibrasi |
|-----------|:-------:|:---------:|
| ADX gate ceiling | 25 | **20** |
| Swing buy threshold | 65 | **70** |
| ATR SL multiplier | 1.5 | **3.0** |
| RVOL window | 20 | **10** |
| RVOL breakout confirm | 2.0 | **1.5** |

**Backtest 19 mid-big cap liquid (2025-12-23 → 2026-07-24):**

| Metrik | Default | **Kalibrasi** |
|--------|:-------:|:------------:|
| Win Rate | 35.6% | **55.3%** |
| Total Return | -1.92% | **+0.41%** |
| Alpha vs B&H | +0.86% | **+5.38%** |
| Sharpe | -0.72 | **0.24** |
| Max DD | 5.25% | **5.94%** |
| Beat B&H | — | **13/19 (68%)** |

**Cara pakai backtest:**
```bash
# 1 saham
python backtest.py BBCA --capital 10000000 --verbose

# Multi saham
python backtest.py BBCA BMRI BBRI ASII TLKM --capital 100000000

# Parameter kustom
python backtest.py BBCA --adx-ceiling 20 --buy-threshold 70 --sl-multiplier 3.0

# Kalibrasi otomatis
python backtest_calibrate.py
```

### Fase 7 — Sprint Plan

| Sprint | Item | Status |
|--------|------|--------|
| S1A | Walk-forward harness skeleton (`walkforward.py`) | ❌ |
| S1B | Fix R:R — TP multiplier 3.0 | ❌ |
| S1C | Breakeven stop rule (1.0 ATR) | ❌ |
| S1D | Long-only mode (SELL advisory) | ❌ |
| S1E | **Fitur Mean Reversion / Recovery** (`/recovery/{kode}` + card detail) | ✅ |
| S2 | Rekonsiliasi sizing + validasi OOS S1 | ❌ |
| S3 | Regime detection (SMA200+ADX) + adaptive weights | ❌ |
| S4+ | Scale-out, trailing, ML (ditunda) | ❌ |

### Fitur Mean Reversion / Recovery (Sprint 1)

Menjawab pertanyaan: *"Saham ini turun X% di bawah previous close — berapa peluangnya balik ke previous close dalam 1 hari sampai 1 bulan?"*

- **Metode**: model GBM analitik (first-passage time, CDF Inverse Gaussian via `math.erf`, tanpa dependensi baru) + base rate empiris saham tsb (event = close turun ≥ X% di bawah previous close dalam 500 hari terakhir).
- **Signal**:
  - `POTENTIAL` — P(recovery ≤ 21 hari) ≥ 60%
  - `WATCH` — probabilitas menengah
  - `NO_SETUP` — belum turun cukup jauh atau data tidak valid
  - Sinyal memakai **empirical base rate** saat `n_events ≥ 5` (lebih kalibrasi dari GBM), fallback ke GBM.
- **Exit plan** (bila entry): target = previous close, time-stop 63 hari trading (~3 bulan), stop-loss = entry − 2× jarak drop.
- **Validasi walk-forward** (BBCA BMRI BBRI ASII TLKM, 35 event, drop ≥ 5%): GBM **under-predict** peluang — Brier 1d 0.057 → 63d 0.372; pred vs aktual 3d: 7% vs 31%; 63d: 56% vs 73%. Karena itu sinyal mengutamakan base rate empiris.

**Cara pakai:**
```bash
# API — tanpa param = threshold otomatis dari volatilitas saham
curl "http://localhost:8000/recovery/BBCA"

# API — manual override
curl "http://localhost:8000/recovery/BBCA?drop_pct=5"

# Validasi walk-forward
python _validate_recovery.py BBCA BMRI BBRI ASII TLKM --drop 5 --length 800
```

Frontend: card "Mean Reversion / Recovery" di halaman detail saham + kontrol Recovery Setup (mode **Otomatis** = 2.5× σ_daily, clamp 2%–30% mengikuti tier harga IDX: <200→30%, 200-5000→18%, ≥5000→13%; atau **Manual** lewat `?drop_pct=`).

### Fase 5 Checklist

| Item | Status |
|------|--------|
| Dashboard — Top Gainers table + signal badges | ✅ |
| Detail Saham — ScoreCard, component bars, price chart, trade plan | ✅ |
| Scrape Button — Trigger + toast notification auto-dismiss | ✅ |
| Date Picker — Pilih tanggal gainers | ✅ |
| Sidebar Nav — Dashboard + Analisis | ✅ |
| Halaman Analisis — Form input kode saham | ✅ |
| Capital Control — Input modal (auto-format) + history length | ✅ |
| Stock detail page — Loading skeleton, error, not found | ✅ |
| Logo swingbot (public/logo.png) | ✅ |
| Trade Plan note — "Risiko aktual X%" alih-alih warning keras | ✅ |

### Fase 4 — Fase 0
*(Status 100% — lihat PRD.md untuk detail lengkap)*

## Change of Plan

Awalnya direncanakan bot Telegram (Fase 4), tapi diubah jadi **dashboard web**:
- **Fase 4** → API Layer (FastAPI): `GET /gainers`, `GET /analisis/{kode}`, `GET /history/{kode}`
- **Fase 5** → Frontend Dashboard (Next.js + TypeScript): ranking gainers, detail analisis per saham, chart harga
- Response JSON terstruktur, bukan format teks Telegram

## Sumber Data

1. **Daftar saham** — `GetSecuritiesStock` → field `Code`/`Name`/`Shares`
2. **Data pasar harian** — `GetStockSummary?date=YYYYMMDD` → **1 call untuk SELURUH pasar**. Field: Close, Volume, Value, Frequency, ForeignBuy/ForeignSell
3. **Data historis** — Yahoo Finance (`yfinance`) via kode saham + suffix `.JK`
4. **Top Gainers** — prioritas IDX (1 call), fallback Yahoo (ThreadPool scan)

## Struktur Folder

```
├── README.md
├── PRD.md
├── riset.md
│
├── backend/                 # Python backend (FastAPI + scoring engine)
│   ├── config.py            # Semua konstanta terpusat
│   ├── indicators.py        # Fase 1: Indikator teknis (numpy)
│   ├── scoring.py           # Fase 2: Swing Score + gating + confidence
│   ├── risk.py              # Fase 3: SL/TP sizing, trade plan
│   ├── gorengan.py          # Gorengan Detection Engine (pump & dump)
│   ├── api.py               # Fase 4: FastAPI (gainers, analisis, history)
│   ├── backtest.py          # Fase 6: Backtest engine
│   ├── backtest_calibrate.py
│   ├── requirements.txt
│   ├── data_source/
│   │   ├── idx_client.py    # Daftar saham via GetSecuritiesStock
│   │   ├── idx_trading.py   # Snapshot harian via GetStockSummary
│   │   ├── gainers.py       # Top N Gainers (IDX → Yahoo fallback)
│   │   └── yahoo_client.py  # Data historis via yfinance
│   └── cache/               # Cache JSON (securities list, gainers, history)
│
└── frontend/                # Fase 5: Next.js dashboard
    ├── app/                 # Pages (Dashboard, Analisis, Stock Detail)
    ├── components/          # UI components
    └── lib/                 # API client & types
```

## Scoring System (Fase 2)

4 komponen SwingScore (equal-weight 0.25), ATR dipisah ke risk sizing:

| Komponen | Sumber | Gating |
|----------|--------|--------|
| **Trend** | EMA(10,25) spread / ATR | ADX gate (ceiling **20**, kalibrasi v0.2.0) |
| **Momentum** | RSI(14) + MFI(14) average | ADX gate (sama) |
| **Volume** | RVOL(**10**) + arah harga | — |
| **Price Action** | S/R distance + Donchian(20) | RVOL ≥ **1.5** untuk breakout (kalibrasi) |

**Confidence** = agreement_score × strength_factor, strength_factor = (gate + rvol_strength) / 2. Confidence label: < 0.4 = rendah, 0.4–0.75 = sedang, > 0.75 = tinggi.

**Risk Level** = ATR ratio (ATR[-1] / mean(ATR[-50:])). Cutoff: < 0.8 = rendah, 0.8–1.5 = sedang, > 1.5 = tinggi.

**Rekomendasi**: Buy ≥ **70** (kalibrasi), Sell ≤ 35, Hold di antaranya.

## Risk Management (Fase 3)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Position sizing | 100% dari capital input user | Frontend CapitalControl handle kendali modal |
| Risk per trade | Bervariasi — ditampilkan sebagai "Risiko aktual X%" | Tergantung jarak SL |
| Stop Loss | entry ± ATR × **3.0** | Kalibrasi v0.2.0 |
| Take Profit | entry ± ATR × **3.0** | v0.3.0 — R:R 1:1 (naik dari 2.5) |
| Breakeven trigger | entry + ATR × **1.0** | v0.3.0 — SL ke entry setelah profit tercapai |
| Long-only mode | **Default: aktif** | SELL advisory — short entry dinonaktifkan |
| Lot size | 100 lembar | Konvensi IDX |

**v0.3.0 changes:** R:R fix → TP 3.0 (dari 2.5); breakeven stop baru; long-only mode default; sizing reconciled ke 100% (dokumen konsisten dengan kode). Semua perubahan divalidasi via walk-forward harness sebelum rilis.

## Setup

```bash
cd backend && pip install -r requirements.txt
cd frontend && npm install

# Terminal 1: Backend
cd backend && python -m uvicorn api:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

## Testing

```bash
cd backend
python test_real_data.py              # Smoke test indikator + scoring
python -m data_source.gainers         # Test gainers scan
python backtest.py BBCA --verbose     # Backtest 1 saham
python backtest_calibrate.py          # Kalibrasi multi-parameter
python backtest.py BBCA --adx-ceiling 20 --buy-threshold 75 --sl-multiplier 3.0  # Custom params
```

## Catatan Arsitektur

- Semua parameter operasional di `config.py`, bukan hardcode di fungsi
- `indicators.py` murni numpy, tanpa dependensi scraper/bot
- `scoring.py` independen dari data source (input: dict numpy arrays)
- Backtest engine di `backtest.py` (walk-bar simulation, metrics, CLI)
- Hasil kalibrasi parameter sudah diintegrasi ke `config.py` (v0.2.0)

## Deviasi dari Riset (Sadar & Didokumentasi)

### 4 komponen vs 5 komponen SwingScore
Riset menyebutkan 5 komponen (Trend, Momentum, Volume, **Volatility**, Price Action). Kode menggunakan **4 komponen** — Volatility/ATR dikeluarkan dari SwingScore dan dipindah ke `risk.py` untuk SL/TP sizing.

**Alasan**: Riset sendiri tidak konsisten — deskripsi awal bilang 5 faktor, tapi contoh formula di "Spesifikasi Teknis Akhir" hanya memuat ADX+RSI+MFI+ATR. ATR juga tidak directional (tidak bisa dibedakan bullish/bearish), sehingga tidak cocok sebagai komponen linear SwingScore 0-100. Keputusan arsitektural: pisah signal (arah) vs risk sizing (besaran volatilitas).

### Position sizing: capital-based bukan risk-based
Riset menyebutkan risk 1% per trade. Dalam praktik, untuk modal retail Rp 100rb–10jt, aturan ini terlalu ketat dan menghasilkan posisi yang tidak berarti (1-3 lot dari modal yang mampu membeli 10-100 lot). Kode menggunakan **25% alokasi modal** sebagai patokan, risk aktual diinformasikan ke user.

### Fibonacci — 7 level vs 5 level
Riset: 5 level (23.6%–78.6%). Kode: 7 level (+ 0% dan 100% endpoint). Penambahan minor untuk completeness.

### RVOL window
Riset menyarankan 5/10/30 hari. Kode default 20 → setelah kalibrasi: **optimal 10**.

### ADX gate ceiling
Riset: threshold ADX ≥ 20. Kode default ceiling 25 → setelah kalibrasi: **optimal 20**, gate linear 0→1 dari ADX=0 sampai ADX=20.
