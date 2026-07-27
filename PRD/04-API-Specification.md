# API Specification — FastAPI Backend

| Item | Detail |
|------|--------|
| **Modul** | `backend/api.py` |
| **Framework** | FastAPI (Python 3.14) |
| **Versi** | 0.1.0 |
| **Last Updated** | 27 Juli 2026 |

## 1. Endpoints

### 1.1 POST /scrape

Trigger scraping top gainers dari IDX (fallback Yahoo).

**Response 200:**
```json
{
  "status": "ok",
  "count": 15,
  "message": "Scrape berhasil. 15 gainers ditemukan."
}
```

### 1.2 GET /gainers

Ambil daftar top gainers + Swing Score.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `date` | string | No | Hari ini | Format `YYYY-MM-DD` |

### 1.3 GET /analisis/{kode}

Analisis teknikal lengkap untuk satu saham.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `kode` | string | Yes | — | Kode saham IDX (case-insensitive) |
| `capital` | float | No | 10,000,000 | Modal trading dalam IDR |
| `date` | string | No | — | Target date YYYY-MM-DD |

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `kode` | string | Kode saham |
| `nama` | string | Nama emiten |
| `harga` | float | Harga penutupan terakhir |
| `last_updated` | string | Tanggal data terakhir |
| `score.valid` | bool | Apakah data scoring valid |
| `score.swing_score` | float | 0-100 |
| `score.components` | dict | trend, momentum, volume, price_action (0-1) |
| `score.recommendation` | string | BUY / SELL / HOLD |
| `score.confidence` | string | tinggi / sedang / rendah |
| `score.risk_level` | string | rendah / sedang / tinggi |
| `trade_plan` | object | null jika HOLD/tidak valid |
| `raw_indicators` | object | RSI, MFI, ATR, ADX, EMA, RVOL, S/R, Fibonacci, Candlestick |
| `gorengan` | object | Gorengan detection result |
| `buy_signal_validated` | bool | Status validasi BUY |

### 1.4 GET /history/{kode}

Data OHLCV historis mentah.

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| `length` | int | No | 250 | 365 |
| `date` | string | No | — | — |

### 1.5 GET /market-status

Cek status pasar IDX (buka/tutup).

## 2. Data Sources

| Data | Sumber | Frekuensi | Coverage | Latency |
|------|--------|-----------|----------|---------|
| Securities list | IDX GetSecuritiesStock | 1× (cache) | ~900 emiten | ~3 detik |
| Daily snapshot | IDX GetStockSummary | 1× per hari | Seluruh pasar | ~3 detik |
| Historical OHLCV | Yahoo Finance (.JK) | Per request | Per saham | ~1-2 detik |
| Top Gainers | IDX (primary), Yahoo (fallback) | 1× per hari | 15 saham | ~3 detik / ~3 menit |

## 3. Config

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | No | `""` | Legacy (tidak dipakai) |
| `API_BASE_URL` (server) | No | `http://localhost:8000` | Backend URL untuk server component |
| `NEXT_PUBLIC_API_BASE_URL` (client) | No | `http://localhost:8000` | Backend URL untuk client component |

## 4. Error Codes

| Status | Description |
|--------|-------------|
| 404 | Kode saham tidak ditemukan / data gainers kosong |
| 502 | Gagal fetch data dari Yahoo Finance / IDX |
| 500 | Scrape gagal / error internal |

## 5. Future Endpoints

- [ ] `GET /screener` — Scan seluruh pasar untuk sinyal BUY/SELL
- [ ] `GET /watchlist` — Portfolio tracking multi-user
- [ ] `GET /backtest` — On-demand backtest via API
- [ ] `WebSocket /realtime` — Real-time data streaming
