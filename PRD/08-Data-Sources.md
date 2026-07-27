# Data Sources — IDX & Yahoo Finance

| Item | Detail |
|------|--------|
| **Modul** | `backend/data_source/` |
| **Last Updated** | 27 Juli 2026 |

## 1. Data Sources

| Data | Source | Suffix | Method | Cache |
|------|--------|--------|--------|-------|
| Securities list | IDX `GetSecuritiesStock` | — | cloudscraper GET | `securities_list.json` (permanent) |
| Daily snapshot | IDX `GetStockSummary` | — | cloudscraper POST | — |
| Historical OHLCV | Yahoo Finance | `.JK` | `yfinance` library | `history_{code}.json` (temporary) |
| Top Gainers | IDX primary → Yahoo fallback | — | ThreadPool scan | `gainers_{date}.json` |

## 2. IDX Endpoints

```python
IDX_BASE_URL = "https://www.idx.co.id"
IDX_SECURITIES_ENDPOINT = "/primary/StockData/GetSecuritiesStock"
IDX_STOCK_SUMMARY_ENDPOINT = "/primary/TradingSummary/GetStockSummary"
IDX_TRADING_INFO_SS_ENDPOINT = "/primary/ListedCompany/GetTradingInfoSS"
IDX_SESSION_INIT_PATH = "/id"
```

**Catatan:** IDX migrasi dari Umbraco ke Nuxt.js (Juli 2026). Endpoint lama sudah 404. Endpoint baru dikonfirmasi jalan via testing manual.

## 3. Yahoo Finance

```python
YAHOO_TICKER_SUFFIX = ".JK"  # BBCA → BBCA.JK
```

- Library: `yfinance`
- Fallback untuk historical data saat IDX endpoint mati
- Fallback untuk gainers scan (ThreadPool, 8 workers, 0.5s delay)

## 4. Caching Strategy

| Cache File | Refresh | Format |
|-----------|---------|--------|
| `securities_list.json` | Manual (permanent) | JSON array of Securities |
| `gainers_{date}.json` | Per scrape | JSON with scraped_at + data |
| `history_{code}.json` | Per request | JSON array of OHLCV bars |

## 5. Error Handling

| Error | Mitigation |
|-------|-----------|
| IDX endpoint 404 | Cloudscraper session init, retry 3× |
| Yahoo rate limit | Cache history, minimal request, ThreadPool delay |
| Cloudflare blocking | Session init, user-agent rotate |
| Empty gainers | Fallback max 3 hari ke belakang |
| Insufficient data | MIN_TRADING_DAYS = 150 guard |

## 6. Config

```python
IDX_REQUEST_TIMEOUT = 15
IDX_REQUEST_RETRIES = 3
IDX_REQUEST_USER_AGENT = "Mozilla/5.0"
SCAN_MAX_WORKERS = 8
SCAN_REQUEST_DELAY = 0.5
TOP_GAINERS_COUNT = 15
IDX_FALLBACK_MAX_DAYS = 3
FALLBACK_SCAN_LENGTH = 5
```

## 7. Future Improvements

- [ ] **Data persistence** — SQLite/PostgreSQL instead of JSON
- [ ] **Scheduled daily scrape** — cron job di pagi hari
- [ ] **Multiple exchange support** — SGX, NYSE sebagai ekspansi
- [ ] **WebSocket IDX** — real-time data jika tersedia
- [ ] **Sector classification** — tambah sektor IDX untuk intermarket analysis
