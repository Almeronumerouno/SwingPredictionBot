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
| 6 | Testing & Refinement | **0%** |

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

### Fase 4 Checklist

| Item | Status |
|------|--------|
| `requirements.txt` — fastapi, uvicorn | ✅ |
| `config.py` — CORS, DEFAULT_CAPITAL, MAX_HISTORY_QUERY_DAYS | ✅ |
| Pydantic response models | ✅ |
| `analyze_stock()` service layer | ✅ |
| `POST /scrape` | ✅ |
| `GET /gainers?date=` | ✅ |
| `GET /analisis/{kode}?capital=` | ✅ |
| `GET /history/{kode}?length=` | ✅ |
| CORS middleware | ✅ |

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
├── config.py              # Semua konstanta terpusat
├── indicators.py          # Fase 1: Indikator teknis (numpy)
├── scoring.py             # Fase 2: Swing Score + gating + confidence
├── risk.py                # Fase 3: SL/TP sizing, trade plan
├── api.py                 # Fase 4: FastAPI (gainers, analisis, history)
├── test_real_data.py      # Smoke test indikator + scoring (BBCA)
│
├── data_source/
│   ├── idx_client.py      # Daftar saham via GetSecuritiesStock
│   ├── idx_trading.py     # Snapshot harian via GetStockSummary
│   ├── gainers.py         # Top N Gainers (IDX → Yahoo fallback)
│   └── yahoo_client.py    # Data historis via yfinance
│
├── frontend/              # Fase 5: Next.js dashboard
│   ├── app/               # Pages (Dashboard, Analisis, Stock Detail)
│   ├── components/        # UI components
│   └── lib/               # API client & types
│
└── cache/                 # Cache JSON (securities list, gainers, history)
```

## Scoring System (Fase 2)

4 komponen SwingScore (equal-weight 0.25), ATR dipisah ke risk sizing:

| Komponen | Sumber | Gating |
|----------|--------|--------|
| **Trend** | EMA(10,25) spread / ATR | ADX gate (ceiling 25) |
| **Momentum** | RSI(14) + MFI(14) average | ADX gate (sama) |
| **Volume** | RVOL(20) + arah harga | — |
| **Price Action** | S/R distance + Donchian(20) | RVOL ≥ 2 untuk breakout |

**Confidence** = agreement_score × strength_factor, strength_factor = (gate + rvol_strength) / 2. Confidence label: < 0.4 = rendah, 0.4–0.75 = sedang, > 0.75 = tinggi.

**Risk Level** = ATR ratio (ATR[-1] / mean(ATR[-50:])). Cutoff: < 0.8 = rendah, 0.8–1.5 = sedang, > 1.5 = tinggi.

**Rekomendasi**: Buy ≥ 65, Sell ≤ 35, Hold di antaranya.

## Risk Management (Fase 3)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Position sizing | 25% alokasi modal (fallback 50%) | Capital-based, bukan risk-based |
| Risk per trade | Bervariasi — ditampilkan sebagai "Risiko aktual X%" | Tergantung jarak SL |
| Stop Loss | entry ± ATR × 1.5 (× 0.8 jika risk tinggi) | |
| Take Profit | entry ± ATR × 2.5 | R:R ~1:1.67 |
| Lot size | 100 lembar | Konvensi IDX |

**Perubahan penting**: Sejak 18 Juli 2026, position sizing diubah dari risk-based 1% (terlalu konservatif untuk modal retail) menjadi **capital-based 25%**. Risk aktual dihitung dan ditampilkan sebagai informasi, bukan peringatan.

## Setup

```bash
pip install -r requirements.txt
cd frontend && npm install

# Terminal 1: Backend
python -m uvicorn api:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

## Testing

```bash
python test_real_data.py  # Smoke test indikator + scoring
python -m data_source.gainers  # Test gainers scan
```

## Catatan Arsitektur

- Semua parameter operasional di `config.py`, bukan hardcode di fungsi
- `indicators.py` murni numpy, tanpa dependensi scraper/bot
- `scoring.py` independen dari data source (input: dict numpy arrays)
- Probabilitas (continuation/reversal) ditunda sampai ada backtest data

## Deviasi dari Riset (Sadar & Didokumentasi)

### 4 komponen vs 5 komponen SwingScore
Riset menyebutkan 5 komponen (Trend, Momentum, Volume, **Volatility**, Price Action). Kode menggunakan **4 komponen** — Volatility/ATR dikeluarkan dari SwingScore dan dipindah ke `risk.py` untuk SL/TP sizing.

**Alasan**: Riset sendiri tidak konsisten — deskripsi awal bilang 5 faktor, tapi contoh formula di "Spesifikasi Teknis Akhir" hanya memuat ADX+RSI+MFI+ATR. ATR juga tidak directional (tidak bisa dibedakan bullish/bearish), sehingga tidak cocok sebagai komponen linear SwingScore 0-100. Keputusan arsitektural: pisah signal (arah) vs risk sizing (besaran volatilitas).

### Position sizing: capital-based bukan risk-based
Riset menyebutkan risk 1% per trade. Dalam praktik, untuk modal retail Rp 100rb–10jt, aturan ini terlalu ketat dan menghasilkan posisi yang tidak berarti (1-3 lot dari modal yang mampu membeli 10-100 lot). Kode menggunakan **25% alokasi modal** sebagai patokan, risk aktual diinformasikan ke user.

### Fibonacci — 7 level vs 5 level
Riset: 5 level (23.6%–78.6%). Kode: 7 level (+ 0% dan 100% endpoint). Penambahan minor untuk completeness.

### RVOL window
Riset menyarankan 5/10/30 hari. Kode menggunakan 20 hari (default). Belum ada bukti empiris mana yang optimal — kandidat tuning saat backtest (Fase 6).

### ADX gate ceiling
Riset: threshold ADX ≥ 20. Kode: ceiling di ADX=25 dengan gate naik linear dari 0→1. Lihat diskusi di scoring.py: ceiling 25 memberi ruang transisi 20→25, konsisten dengan kategori "tren kuat" Wilder (>25).
