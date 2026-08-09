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
# audit fix #15: yfinance sejak v0.2.54 (Feb 2025) me-default auto_adjust=True.
# Perilaku benar (split/dividen tidak menciptakan gap harga palsu yang merusak
# ATR/RSI/ADX & deteksi gorengan) — tapi harus di-set EKSPLISIT agar tahan
# terhadap perubahan default library di masa depan (requirements hanya pin
# batas bawah yfinance>=0.2.40).
YAHOO_AUTO_ADJUST = True

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
DEFAULT_POSITION_PCT = 1.0    # [DEPRECATED] digantikan POSITION_SIZING_MODE
RISK_PER_TRADE_PCT = 0.01     # 1% capital per-trade — utk backtest risk-based; TIDAK dipakai utk sizing all-in
# POSITION_SIZING_MODE: "all_in" = seluruh modal dialokasikan ke SATU saham
# (keputusan produk 2026: strategi ini all-in per saham, bukan membagi
# kapital antar banyak posisi). risk_budget/regime_mult tidak dipakai utk lot.
POSITION_SIZING_MODE = "all_in"

# Fee model asimetris (riset broker Indonesia 2025): beli ~0.15-0.25%,
# jual ~0.25-0.35% (termasuk PPh Final Pasal 4(2) 0.1% hanya di sisi jual).
# Round-trip riil ~0.44-0.48% vs asumsi simetris lama 0.50%.
FEE_BUY_PCT = 0.18            # fee entry (buy) dalam %
FEE_SELL_PCT = 0.28           # fee exit (sell) dalam % (termasuk PPh final 0.1%)

# ---- Short Selling Eligibility (BEI) ----
# Regulasi: hanya saham dalam "Daftar Efek Short Selling" BEI (direview tiap
# bulan) yang boleh di-short; syarat free float >= 20%, margin awal 50%,
# volume harian dibatasi ketat. Naked short selling dilarang (POJK 6/2024,
# Peraturan II-H BEI — SK Direksi Kep-00157/BEI/10-2024).
# Daftar bulanan TIDAK bisa di-fetch otomatis dari BEI secara stabil; solusi:
# admin menyalin daftar ke SHORT_SELLING_LIST_FILE (JSON array kode saham).
# Kalau file kosong/absent -> default = TIDAK eligible (konservatif): sinyal
# SELL tetap tampil sebagai advisory/exit-only, bukan entry short.
SHORT_SELLING_ENFORCE = True
SHORT_SELLING_DEFAULT_ELIGIBLE = False

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
# NOTE (audit #15): multiplier diterapkan pada skor mentah (titik jangkarnya 0,
# bukan 50). Efeknya asimetris thd titik netral: skor >50 diredam mendekati
# netral (BUY makin sulit), skor <50 dijauhkan (SELL makin tegas) — SELARAS
# dgn filosofi "defensif saat bear", disengaja & didokumentasikan. Kalau
# peredaman simetris thd netral yang diinginkan: 50 + (raw-50)*mult.
REGIME_MULTIPLIER_BULL = 1.0
REGIME_MULTIPLIER_SIDEWAYS = 0.93
REGIME_MULTIPLIER_BEAR = 0.90

# ---- Walk-forward ----
WF_TRAIN_DAYS = 63
WF_TEST_DAYS = 21
WF_PURGE_DAYS = 10
WF_EMBARGO_DAYS = 10
# Grid optimasi per window (dijalankan di data TRAIN window, hasil OOS di TEST).
# Ukuran kecil: 3x3x2x2 = 36 kombinasi/window — seimbang antara cakupan &
# biaya komputasi; per-saham data di-fetch sekali lalu dipakai ulang.
WF_OPT_GRID = {
    "adx_gate_ceiling": [15, 20, 25],
    "swing_buy_threshold": [68, 72, 76],
    "atr_sl_multiplier": [2.0, 3.0],
    "rvol_breakout_confirm": [1.2, 1.5],
}
WF_OPT_MIN_TRADES = 10        # filter robust: window train harus punya >= N trade
WF_OPT_METRIC = "sharpe"      # metrik pemilihan pemenang di data train

# ---- Recovery ke Previous Price (Mean Reversion) ----
RECOVERY_DROP_DEFAULT = 5.0        # X% di bawah previous close sebagai setup
RECOVERY_HORIZONS_DAYS = [1, 3, 5, 10, 21, 42, 63]  # horizon trading day (1D → 3 bulan)
RECOVERY_HISTORY_LOOKBACK_DAYS = 500  # kalender; estimasi mu/sigma & base rate lebih stabil
RECOVERY_MIN_BARS = 150            # minimal bar agar estimasi GBM valid
RECOVERY_MU_LOOKBACK_DAYS = 63     # drift diestimasi dari 3 bulan terakhir (momentum kini)
RECOVERY_SIGMA_LOOKBACK_DAYS = 252 # vol diestimasi dari 1 tahun terakhir
RECOVERY_SIGNAL_P_MIN = 0.68       # sinyal POTENTIAL jika P(hit ≤ 21d) ≥ 68%.
                                   # >= breakeven R:R exit plan (66.7% utk R:R=0.5)
                                   # + margin biaya transaksi (audit fix #12)
RECOVERY_SIGNAL_HORIZON_DAYS = 21  # horizon acuan sinyal (~1 bulan)
RECOVERY_TIME_STOP_DAYS = 63       # time stop: exit jika target belum tercapai (~3 bulan)
RECOVERY_SL_DISTANCE_MULT = 2.0    # SL = entry - 2x jarak ke previous close
                                   # => R:R = 1/2.0 = 0.5, breakeven WR = 66.7%

# Posisi harga sekarang vs close N hari trading lalu (deteksi "masih di bawah / udah di atas")
RECOVERY_VS_LOOKBACKS_DAYS = [1, 5, 21, 63]  # 1D, 1W, 1M, 3M
RECOVERY_VS_LABELS = {1: "1D", 5: "1W", 21: "1M", 63: "3M"}

# Accumulation ("siap terbang": ARA = puncak distribusi/dump, lalu volume besar
# sambil harga masih stagnant + konfirmasi SMA20).
# PERUBAHAN: baseline volume = mean SELURUH hari post-ARA sebelum hari berjalan
# (jendela akumulasi itu sendiri, tanpa hari ARA & tanpa hari ini — anti-self-
# referencing), bukan 20 hari pre-ARA. Sinyal = minimal
# ACCUM_MIN_HEAVY_DAYS hari heavy; ACCUM_DENSITY_PCT hanya info (bukan gate).
# ACCUM_HEAVY_RVOL = knob sensitivitas (2.0x; turunkan ~1.5-1.8x bila lonjakan
# banyak yang kelewat).
# Validasi HISTORIS (baseline pre-ARA + density>=40%, _validate_accum3.py,
# 963 saham IDX, 2026, sub-arm yang masih di bawah ARA):
#   pola: rec5=48.7% b5=26.8% b10=16.8% up1=34.0% (n=2958)
#   kontrol: rec5=18.4% b5=9.6% b10=5.9% up1=26.5% (n=228459)
#   => edge ~3x pada boom +10%/5d. Angka ini untuk logika LAMA; baseline
#   post-ARA perlu re-validasi (menunggu logika final).
ACCUM_ARA_RISE_PCT = 10.0       # hari ARA: close >= prev * (1 + pct/100)
ACCUM_ARA_RISE_PCT = 10.0       # hari ARA: close >= prev * (1 + pct/100)
ACCUM_HEAVY_RVOL = 2.0          # multiplikator vs baseline volume POST-ARA (fallback: 20 hari pre-ARA / RVOL)
ACCUM_RVOL_PERIOD = 20          # jendela fallback pre-ARA & ambang double-ARA; periode display RVOL
ACCUM_DENSITY_PCT = 30.0        # GATE kepadatan hari heavy dlm jendela post-ARA (%) — WAJIB (validasi: 30-50%
                                #   punya edge sama ~+13pp b10; 30% = sinyal paling banyak utk edge yg sama)
ACCUM_MIN_HEAVY_DAYS = 2        # minimal jumlah hari heavy di jendela
ACCUM_MA20_DAYS = 20            # konfirmasi: close harus >= SMA(N) (di atas, bukan fresh cross)

# Auto-drop: threshold dihitung dari volatilitas saham biar setup bermakna per saham
RECOVERY_AUTO_SIGMA_MULT = 2.5     # threshold auto = mult x sigma_daily
RECOVERY_AUTO_MIN = 2.0            # floor (%)
# Cap sesuai batas Auto Rejection BEI TERBARU (SK Direksi Kep-00003/BEI/04-2025,
# efektif 8 April 2025): ARB (batas turun) diseragamkan FLAT 15% untuk semua
# tier harga. Karena setup recovery berbicara soal PENURUNAN harga, acuan yang
# relevan adalah ARB — jadi cap flat ~13% (margin di bawah 15% ARB) untuk
# seluruh tier. (ARB lama bertingkat 35/25/20 sudah tidak berlaku.)
RECOVERY_AUTO_CAP_UNDER_200 = 13.0     # harga < Rp 200 (ARB 15%)
RECOVERY_AUTO_CAP_200_TO_5000 = 13.0   # Rp 200 - <Rp 5000 (ARB 15%)
RECOVERY_AUTO_CAP_AT_5000 = 13.0       # harga >= Rp 5000 (ARB 15%)

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
SHORT_SELLING_LIST_FILE = os.path.join(CACHE_DIR, "short_selling_list.json")
