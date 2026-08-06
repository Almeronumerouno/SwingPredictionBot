"""
Config terpusat. Semua nilai sensitif (token dll) diambil dari environment
variable / file .env, TIDAK di-hardcode di source code.

Cara pakai:
1. Copy file `.env.example` jadi `.env`
2. Isi TELEGRAM_BOT_TOKEN dengan token dari @BotFather
3. Jalankan bot seperti biasa (python bot.py)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_BACKEND_DIR = Path(__file__).resolve().parent

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

# ---- Risk / Trade Plan ----
ATR_SL_MULTIPLIER = 3.0       # v0.2.0: dinaikkan dari 1.5
ATR_TP_MULTIPLIER = 2.5       # baseline; 3.0 diuji terpisah sebagai eksperimen
BREAKEVEN_TRIGGER = 999.0     # disabled — degrades TP_HIT & WR (tested 1.0/1.2/1.5/2.0)
LONG_ONLY_MODE = False        # SELL tetap jadi entry signal (validated 58% WR)
DEFAULT_POSITION_PCT = 1.0    # v0.3.0: 100% dari capital input user
RISK_PER_TRADE_PCT = 0.01     # 1% capital per trade

# ---- Scoring ----
SCORE_WEIGHTS = {"trend": 0.25, "momentum": 0.25, "volume": 0.25, "price_action": 0.25}
ADX_GATE_CEILING = 20
RVOL_WINDOW = 10
RVOL_BREAKOUT_CONFIRM = 1.5
SWING_BUY_THRESHOLD = 72
SWING_SELL_THRESHOLD = 35
SWING_BUY_VALIDATED = False
SWING_SELL_VALIDATED = True
RISK_ATR_LOOKBACK = 50
RISK_HIGH_CUTOFF = 1.5
RISK_LOW_CUTOFF = 0.8
CONFIDENCE_LOW_CUTOFF = 0.4
CONFIDENCE_HIGH_CUTOFF = 0.75

# ---- Regime detection ----
REGIME_SMA_PERIOD = 200
REGIME_ADX_SIDEWAYS_CUTOFF = 20
REGIME_MULTIPLIER_BULL = 1.0
REGIME_MULTIPLIER_SIDEWAYS = 0.93
REGIME_MULTIPLIER_BEAR = 0.90

# ---- Walk-forward ----
WF_TRAIN_DAYS = 63
WF_TEST_DAYS = 21
WF_PURGE_DAYS = 10
WF_EMBARGO_DAYS = 10

# ---- Recovery ke Previous Price (Mean Reversion) ----
RECOVERY_DROP_DEFAULT = 5.0        # X% di bawah previous close sebagai setup
RECOVERY_HORIZONS_DAYS = [1, 3, 5, 10, 21, 42, 63]  # horizon trading day (1D → 3 bulan)
RECOVERY_HISTORY_LOOKBACK_DAYS = 500  # kalender; estimasi mu/sigma & base rate lebih stabil
RECOVERY_MIN_BARS = 150            # minimal bar agar estimasi GBM valid
RECOVERY_MU_LOOKBACK_DAYS = 63     # drift diestimasi dari 3 bulan terakhir (momentum kini)
RECOVERY_SIGMA_LOOKBACK_DAYS = 252 # vol diestimasi dari 1 tahun terakhir
RECOVERY_SIGNAL_P_MIN = 0.60       # sinyal POTENTIAL jika P(hit ≤ 21d) ≥ 60%
RECOVERY_SIGNAL_HORIZON_DAYS = 21  # horizon acuan sinyal (~1 bulan)
RECOVERY_TIME_STOP_DAYS = 63       # time stop: exit jika target belum tercapai (~3 bulan)
RECOVERY_SL_DISTANCE_MULT = 2.0    # SL = entry - 2x jarak ke previous close

# Posisi harga sekarang vs close N hari trading lalu (deteksi "masih di bawah / udah di atas")
RECOVERY_VS_LOOKBACKS_DAYS = [1, 5, 21, 63]  # 1D, 1W, 1M, 3M
RECOVERY_VS_LABELS = {1: "1D", 5: "1W", 21: "1M", 63: "3M"}

# Accumulation ("masih di bawah + banyak hari volume tinggi = akumulasi = siap boom")
# Divalidasi walk-forward (24+ saham IDX, 2026): makin banyak hari RVOL >= ACCUM_HEAVY_RVOL
# dalam ACCUM_LOOKBACK_DAYS terakhir sambil close MASIH DI BAWAH close 5 hari lalu,
# makin besar P(breakout/boom 5 hari ke depan) -- kasus SOLA: 31 Jul-5 Ags volume 19-25M
# sambil harga cekung 102->88, lalu 6 Ags melesat +14.5% dengan 114M.
ACCUM_LOOKBACK_DAYS = 5        # jendela jumlah hari "heavy"
ACCUM_MIN_HEAVY_DAYS = 3       # minimal hari RVOL >= threshold
ACCUM_HEAVY_RVOL = 2.0         # RVOL yang dianggap heavy (vol / avg 20 hari sebelumnya)
ACCUM_BELOW_LOOKBACK_DAYS = 5  # harga harus masih di bawah close N hari trading lalu
ACCUM_RVOL_PERIOD = 20         # periode baseline RVOL

# Auto-drop: threshold dihitung dari volatilitas saham biar setup bermakna per saham
RECOVERY_AUTO_SIGMA_MULT = 2.5     # threshold auto = mult x sigma_daily
RECOVERY_AUTO_MIN = 2.0            # floor (%)
# Cap bervariasi sesuai batas fluktuasi harian IDX (auto reject), biar cocok utk semua tier harga
RECOVERY_AUTO_CAP_UNDER_200 = 30.0     # harga < Rp 200 (limit ±35%)
RECOVERY_AUTO_CAP_200_TO_5000 = 18.0   # Rp 200 - <Rp 5000 (limit ±20%)
RECOVERY_AUTO_CAP_AT_5000 = 13.0       # harga >= Rp 5000 (limit ±15%)

# ---- Gorengan Detection ----
GORENGAN_PUMP_PCT = 80       # min % naik dari low ke peak utk dianggap pump
GORENGAN_DUMP_PCT = 40       # min % turun dari peak utk dianggap dump
GORENGAN_SWING_EXTREME = 150 # swing 20d dianggap ekstrem (buat hist P&D)
GORENGAN_VOL_SPIKE_HIGH = 5  # RVOL Z-score mapping (unused — keep for ref)
GORENGAN_VOL_SPIKE_MED = 3
GORENGAN_VOL_SPIKE_LOW = 1.5
GORENGAN_ATR_HIGH = 3        # ATR ratio mapping (unused)
GORENGAN_ATR_MED = 2
GORENGAN_ATR_LOW = 1.2
GORENGAN_LIQ_HIGH = 20e9     # median daily value dianggap likuid
GORENGAN_LIQ_MED = 10e9
GORENGAN_LIQ_LOW = 3e9
GORENGAN_LIQ_MIN = 1e9
GORENGAN_MCAP_HIGH = 500e9   # market cap threshold: <500B = score 100
GORENGAN_MCAP_MED = 2e12     # <2T = score 60
GORENGAN_MCAP_LOW = 10e12    # <10T = score 25
GORENGAN_TURNOVER_HIGH = 0.15# turnover >15% float = score 100
GORENGAN_TURNOVER_MED = 0.08 # >8% = score 60
GORENGAN_TURNOVER_LOW = 0.03 # >3% = score 25
GORENGAN_GAP_COUNT = 2       # minimal gap-up dalam 5 hari terakhir
GORENGAN_GAP_PCT = 2         # gap-up threshold (%)
GORENGAN_ZSCORE_HIGH = 3.0   # Z-score threshold (unused)
GORENGAN_ZSCORE_MED = 2.0
GORENGAN_ZSCORE_LOW = 1.0

# ---- Active Pump — raw thresholds (BUKAN Z-score) ----
GORENGAN_RVOL_EXTREME = 5.0    # RVOL >5 → score 100
GORENGAN_RVOL_HIGH = 3.0       # RVOL >3 → score 70
GORENGAN_RVOL_MODERATE = 1.5   # RVOL >1.5 → score 30
GORENGAN_MOMENTUM_EXTREME = 25 # 5d return >25% → score 100
GORENGAN_MOMENTUM_HIGH = 12    # 5d return >12% → score 70
GORENGAN_MOMENTUM_MODERATE = 7 # 5d return >7% → score 40
GORENGAN_MOMENTUM_LOW = 3      # 5d return >3% → score 20
GORENGAN_MOMENTUM_10D_EXTREME = 35
GORENGAN_MOMENTUM_10D_HIGH = 18
GORENGAN_MOMENTUM_10D_MODERATE = 10
GORENGAN_MOMENTUM_10D_LOW = 5
GORENGAN_VOLA_EXTREME = 3.0    # 5d ATR / 14d baseline >3 → score 100
GORENGAN_VOLA_HIGH = 2.0       # >2 → score 70
GORENGAN_VOLA_MODERATE = 1.5   # >1.5 → score 40

# ---- Level thresholds (diturunin biar lebih sensitif) ----
GORENGAN_LEVEL_EXTREME = 65
GORENGAN_LEVEL_HIGH = 45
GORENGAN_LEVEL_MEDIUM = 20

# ---- Data Freshness & Validity Gates ----
MAX_DATA_STALE_DAYS = 5         # max days bar terakhir vs target date
STAGNATION_LOOKBACK = 5         # hari buat deteksi harga stagnan
STAGNATION_RANGE_PCT = 0.005    # 0.5% — min range harga dalam lookback

# ---- API ----
API_CORS_ORIGINS = ["http://localhost:3000"]
DEFAULT_CAPITAL = 10_000_000
MAX_HISTORY_QUERY_DAYS = 365

# Lokasi cache lokal — absolute path, selalu di dalam folder backend/
CACHE_DIR = str(_BACKEND_DIR / "cache")
SECURITIES_LIST_CACHE_FILE = os.path.join(CACHE_DIR, "securities_list.json")
DAILY_GAINERS_CACHE_FILE = os.path.join(CACHE_DIR, "gainers_{date}.json")
STOCK_HISTORY_CACHE_FILE = os.path.join(CACHE_DIR, "history_{code}.json")
