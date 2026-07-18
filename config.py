"""
Config terpusat. Semua nilai sensitif (token dll) diambil dari environment
variable / file .env, TIDAK di-hardcode di source code.

Cara pakai:
1. Copy file `.env.example` jadi `.env`
2. Isi TELEGRAM_BOT_TOKEN dengan token dari @BotFather
3. Jalankan bot seperti biasa (python bot.py)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---- Telegram ----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ---- Network / Request ----
IDX_REQUEST_TIMEOUT = 15
IDX_REQUEST_RETRIES = 3
IDX_REQUEST_USER_AGENT = "Mozilla/5.0"

# ---- IDX Data Source ----
# CATATAN: idx.co.id migrasi dari Umbraco ke Nuxt.js, endpoint lama
# (GetSecuritiesStock, GetTradingInfoSS) sudah 404. Endpoint baru di bawah
# ini ditemukan & dikonfirmasi jalan oleh testing manual (Juli 2026).
IDX_BASE_URL = "https://www.idx.co.id"
IDX_SECURITIES_ENDPOINT = "/primary/StockData/GetSecuritiesStock"
IDX_STOCK_SUMMARY_ENDPOINT = "/primary/TradingSummary/GetStockSummary"
IDX_TRADING_INFO_SS_ENDPOINT = "/primary/ListedCompany/GetTradingInfoSS"
IDX_SESSION_INIT_PATH = "/id"

# Data trading historis TIDAK LAGI dari IDX langsung (endpoint lama mati),
# sekarang pakai Yahoo Finance (lihat data_source/yahoo_client.py).
# Kode saham IDX perlu ditambah suffix ".JK" untuk query ke Yahoo Finance.
YAHOO_TICKER_SUFFIX = ".JK"

# Berapa hari kalender historis buat kalkulasi indikator.
# ADX(14) butuh warm-up dobel: DX butuh 14 bar, ADX butuh 14 bar lagi ->
# mulai valid di bar ke-27, stabil beneran di ~150 bar (forum Wilder).
# Makanya HISTORY_LOOKBACK_DAYS dinaikin dari 60 jadi 250 (kalender),
# MIN_TRADING_DAYS = 150 (trading day) sebagai threshold guard.
HISTORY_LOOKBACK_DAYS = 250
MIN_TRADING_DAYS = 150
# Jumlah worker paralel saat scan seluruh saham buat nentuin Top Gainers
# (jangan set terlalu tinggi biar tidak dianggap serangan / kena rate limit)
SCAN_MAX_WORKERS = 8

# Jeda (detik) antar request dalam 1 worker, sebagai etika scraping
SCAN_REQUEST_DELAY = 0.5

# Berapa saham yang dianggap "Top Gainers" untuk dianalisis
TOP_GAINERS_COUNT = 15
IDX_FALLBACK_MAX_DAYS = 3
FALLBACK_SCAN_LENGTH = 5

# ---- Risk ----
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 2.5     # R:R ~1:1.67
RISK_PER_TRADE_PCT = 0.01    # 1% capital per trade

# ---- Scoring ----
SCORE_WEIGHTS = {"trend": 0.25, "momentum": 0.25, "volume": 0.25, "price_action": 0.25}
ADX_GATE_CEILING = 25         # ceiling gate: ADX >= 25 → gate=1.0 (tren kuat Wilder)
RVOL_BREAKOUT_CONFIRM = 2.0   # gating: breakout cuma valid kalau RVOL >= ini
SWING_BUY_THRESHOLD = 65
SWING_SELL_THRESHOLD = 35
RISK_ATR_LOOKBACK = 50
RISK_HIGH_CUTOFF = 1.5
RISK_LOW_CUTOFF = 0.8
CONFIDENCE_LOW_CUTOFF = 0.4     # < 0.4 → Rendah
CONFIDENCE_HIGH_CUTOFF = 0.75   # > 0.75 → Tinggi, sisanya Sedang

# ---- API ----
API_CORS_ORIGINS = ["http://localhost:3000"]
DEFAULT_CAPITAL = 10_000_000
MAX_HISTORY_QUERY_DAYS = 365

# Lokasi cache lokal
CACHE_DIR = "cache"
SECURITIES_LIST_CACHE_FILE = f"{CACHE_DIR}/securities_list.json"
DAILY_GAINERS_CACHE_FILE = f"{CACHE_DIR}/gainers_{{date}}.json"
STOCK_HISTORY_CACHE_FILE = f"{CACHE_DIR}/history_{{code}}.json"
