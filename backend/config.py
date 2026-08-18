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
# NOTE: bobot komponen TIDAK di sini - single source of truth = regime.py
# (RegimeProfile.weights, identik 0.15/0.15/0.25/0.45 utk semua regime saat ini).
# Hasil kalibrasi bobot berbasis data (_calibrate_scoring.py, 150 saham IDX,
# split temporal, AUC-ROC utk forward return 1d & 5d, Agu 2026):
#   - Bobot heuristik sekarang: AUC test ~0.48-0.50 = tidak lebih baik dari
#     koin utk memprediksi arah return 1-5 hari (fitur yang dipakai hampir
#     tidak informatif sebagai leading signal jangka pendek).
#   - Logistic fit: AUC test 0.509 (h=5) tapi 0.487 (h=1) - TIDAK stabil
#     lintas horizon. Koefisien momentum konsisten NEGATIF (rsi/mfi tinggi
#     terkait return lebih buruk), volume & price_action mendekati nol.
#   - KEPUTUSAN: bobot produksi DIPERTAHANKAN (delta kecil, tidak robust).
#     Riset fitur baru lebih bernilai daripada re-weight komponen lama;
#     target 150-300 trade resolved utk melatih Outcome Score (lihat PLAN).
ADX_GATE_CEILING = 20
RVOL_WINDOW = 10
RVOL_BREAKOUT_CONFIRM = 1.5
SWING_BUY_THRESHOLD = 72
SWING_SELL_THRESHOLD = 35
# Status validasi (backtest_calibrate.py, 36 kombinasi x 5 saham, Agu 2026):
#   - OOS 63 hari terakhir: Sharpe NEGATIF utk SEMUA kombinasi (market bearish,
#     MaxDD ~24%), trade OOS cuma 3-4/saham -> statistik lemah, TIDAK ada
#     rekomendasi konklusif. Threshold 68/72/76 setara (beda noise), SL 2.0 vs
#     3.0xATR tidak konklusif -> parameter produksi DIPERTAHANKAN.
#   - Sinyal RECOMMENDED tandingan terbaik (train) = adx 25, buy 68, sl 2.0,
#     rvol 1.5 (train sharpe 0.22) — masih in-sample, belum layak produksi.
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

# Model recovery EMPIRIS global (pengganti GBM yang menyesatkan):
# P(hit prior high / "par") = 1/(1 + exp(a_t + b_t*dd_fraction)),
# dd_fraction = 1 - harga/prior_peak, prior_peak = max(close) trailing
# RECOVERY_PEAK_LOOKBACK_DAYS hari trading. Parameter a_t, b_t per horizon
# dikalibrasi OFFLINE dari universe_ohlcv.npz (963 saham IDX) dan disimpan
# di RECOVERY_MODEL_PARAMS_FILE.
#  - P6.1 (Agu 2026): split GLOBAL KRONOLOGIS (cutoff 70% tanggal) + purge
#    label-overlap + embargo (bukan split posisi bar lama 70/30 yang bocor;
#    _phase6_p61_calibrate.py). CI = cluster bootstrap saham (P6.2).
#  - Basis harga mentah (konsisten jalur produksi).
#  - KETERBATASAN DATA (VALID#1): dataset ~3.5 tahun (2023-2026, 900 bar per
#    saham) dari Yahoo = saham yang MASIH AKTIF (survivorship bias; saham
#    delisted tidak masuk, sehingga P(recover) bisa overestimate). Estimasi
#    delisting IDX ~3-5% per tahun — dampak kecil tapi jangan diabaikan saat
#    menerjemahkan probabilitas ke keputusan. Perlu data >10 tahun + saham
#    delisted untuk menghilangkan bias ini sepenuhnya.
#  - P6.5 (Agu 2026): backtest & kalibrasi = "survivorship-limited"
#    (lihat data/phase6_survivorship.json).
RECOVERY_PEAK_LOOKBACK_DAYS = 252     # prior high = max(close) trailing N hari trading
RECOVERY_MODEL_P_MIN = 0.5            # sinyal fallback model: P(hit prior peak <= 21d) >= 50%
RECOVERY_MODEL_DD_CLAMP = 0.85        # clamp dd_fraction ke [0, 0.85]
RECOVERY_MODEL_PARAMS_FILE = "data/recovery_model_params.json"

# F2.4 (Agu 2026): shrinkage Beta-Binomial pengganti hard switch n>=5.
# Prior per (bucket drop, horizon) diestimasi offline dari universe_ohlcv.npz
# (_fase2_shrinkage.py) -> data/recovery_shrinkage_params.json.
# p_shrunk = (k + a0)/(n + a0 + b0); kalau file tidak ada, perilaku lama
# (hard switch n>=5) dipertahankan sebagai fallback.
RECOVERY_SHRINKAGE_PARAMS_FILE = "data/recovery_shrinkage_params.json"

# F3.2 (Agu 2026): kebijakan availability-date fundamental.
# PERHATIAN: ini ASUMSI KONSERVATIF, BUKAN fakta market.
# `period_end + lag` BUKAN tanggal publikasi yang teramati. Setiap nilai yang
# memakai jalur ini WAJIB ditandai availability_source="conservative_lag" dan
# availability_is_observed=false. Jalur observed (earnings_dates) selalu didahulukan.
#
# Lag per bulan period_end mengikuti batas pelaporan OJK/IDX + buffer:
#   - Q1 (Mar): batas akhir Mei  (~61 hari)  -> 90
#   - Q2 (Jun): batas akhir Juli (~31 hari)  -> 60
#   - Q3 (Sep): batas akhir Nov  (~62 hari)  -> 90
#   - Q4 (Des): batas akhir Apr  (~120 hari) -> 150
# Buffer sengaja longgar: salah arah yang aman adalah LEBIH TUA (tidak bocor),
# bukan lebih baru (look-ahead). M1/M2 (observed-only vs observed+assumed) di F3.6
# akan membandingkan kedua jalur.
FUNDAMENTAL_LAG_DAYS_BY_MONTH = {3: 90, 6: 60, 9: 90, 12: 150}
FUNDAMENTAL_LAG_DEFAULT_DAYS = 150       # fallback jika bulan period_end di luar 1-12

# F3.2: aturan accepted/rejected earnings_dates (sanity check sebelum dipakai
# sebagai availability_source="observed"):
#   - minimal 1 baris earnings_dates
#   - available_at harus SETELAH period_end (laporan tidak mungkin diumumkan
#     sebelum periode berakhir) — menolak earningsTimestampEnd yang tidak sinkron
#   - available_at harus <= hari ini + toleransi (jangan jadwalkan masa depan)
#   - lag (available_at - period_end) harus >= 1 hari (bukan tanggal yang sama)
FUNDAMENTAL_EARNINGS_MIN_ROWS = 1
FUNDAMENTAL_AVAILABLE_FUTURE_TOLERANCE_DAYS = 2

# F3.4 (Agu 2026): threshold risk flags fundamental — **HEURISTIC, bukan
# research-backed, BUKAN hasil tuning backtest**. Fungsinya hanya risk GUARD,
# bukan predictive threshold. Dilarang tuning dengan backtest (data-snooping,
# masalah yang sama seperti Fase 2). Threshold baru bisa diuji OOS HANYA bila
# suatu hari historical PIT fundamental tersedia (F3.6).
#
# HIGH_LEVERAGE: DER > hard extreme. F3.1 menemukan DAYA DER=209.7 (kebutuhan
# extreme guard), TAPI DER=2/3 BUKAN universal danger (industri/bank berbeda) —
# jadi guard sengaja ekstrem. BBCA (bank) debtToEquity=None di Yahoo -> unknown,
# bukan flag.
FUNDAMENTAL_FLAG_DER_HARD_EXTREME = 150.0
# EXTREME_VALUATION: PER/PBV > threshold SANGAT ekstrem (valuation tidak
# comparable lintas sektor; ekstrem bisa = overvaluation ATAU growth pricing
# ATAU earnings/book sementara terdistorsi). Bukan penentu fair value.
# F3.1: ROCK PER=106, BLTA PBV=11333, BBRM PBV=19167.
FUNDAMENTAL_FLAG_PER_EXTREME = 100.0
FUNDAMENTAL_FLAG_PBV_EXTREME = 20.0
# Coverage (data-quality, bukan probability): observed=1.0, assumed=0.5,
# unknown=0.0 atas REPORT_FIELDS (5 field).
#   ratio < COVERAGE_UNKNOWN  -> UNKNOWN (data tidak cukup utk klasifikasi apa pun)
#   ratio < COVERAGE_LOW      -> flag LOW_COVERAGE + data_quality LOW
#   ratio >= COVERAGE_HEALTHY -> memenuhi syarat HEALTHY (bila tanpa material flag)
FUNDAMENTAL_COVERAGE_UNKNOWN = 0.25
FUNDAMENTAL_COVERAGE_LOW = 0.40
FUNDAMENTAL_COVERAGE_HEALTHY = 0.80

# Accumulation ("siap terbang": ARA = puncak distribusi/dump, lalu volume besar
# sambil harga masih stagnant + konfirmasi SMA20).
# Baseline volume = mean SELURUH hari post-ARA sebelum hari berjalan (jendela
# akumulasi itu sendiri, tanpa hari ARA & tanpa hari ini — anti-self-referencing,
# anti-look-ahead), bukan 20 hari pre-ARA. ACCUM_DENSITY_PCT = GATE WAJIB
# (tanpa gate density, edge hilang total — lihat validasi _validate_accum4.py).
# ACCUM_HEAVY_RVOL = knob sensitivitas (2.0x; turunkan ~1.5-1.8x bila lonjakan
# banyak yang kelewat).
# Validasi FINAL (_validate_accum4.py, 915 saham IDX, 800 hari, anti look-ahead,
# baseline post-ARA + gate density): density >= 30% → b10 = 18.4% (n=8092) vs
# kontrol (di bawah ARA tanpa sinyal) 5.4% (n=217521) → edge ~3.4x, p < 1e-16;
# density >= 40% → b10 18.6%; TANPA gate density → b10 8.7% (= kontrol, p~1).
# Versi lama (baseline pre-ARA, density>=40%): b10 16.8% vs 5.9% (n=2958).
## ---- Ready To Fly: event pemicu akumulasi ----

# Event pemicu: "large upmove" (close >= prev * (1 + pct/100)) pada harga RIIL
# (raw_close). Threshold +10% ini HEURISTIC — BUKAN definisi ARA resmi BEI
# (yang bertingkat 35/25/20 per tier harga dan berubah sesuai peraturan, mis.
# SK BEI Apr 2025 menyeragamkan ARB 15%). Karena sistem tidak membaca aturan
# ARA aktual per harga, event ini disebut POST_LARGE_UPMOVE; istilah internal
# "ara" (nama variabel/field API) dipertahankan demi kompatibilitas (audit v2 §16).
ACCUM_ARA_RISE_PCT = 10.0       # ambang large upmove: close >= prev * (1 + pct/100)
ACCUM_RVOL_PERIOD = 20          # jendela fallback pre-ARA & ambang double-ARA; periode display RVOL
ACCUM_DENSITY_PCT = 30.0        # GATE kepadatan hari heavy dlm jendela post-ARA (%) — WAJIB (validasi: 30-50%
                                #   punya edge sama ~+13pp b10; 30% = sinyal paling banyak utk edge yg sama)
ACCUM_MIN_HEAVY_DAYS = 2        # minimal jumlah hari heavy di jendela
ACCUM_HEAVY_RVOL = 2.0          # ambang volume "heavy" = x lipat baseline post-ARA (knob sensitivitas)
ACCUM_MA20_DAYS = 20            # konfirmasi: close harus >= SMA(N) (di atas, bukan fresh cross)

# Gate anti-repetisi (riset forensik Agu 2026, dataset Jul-Agu n=456, definisi
# b10 high-based 10 hari): pola RTF mentah yang valid 4+ hari berturut-turut
# TANPA expansion win-rate-nya membusuk drastis (hari ke-4+: 42.7% vs hari
# 1/2/3: 57.9%/56.9%/63.4%) — aktivitas besar berulang tanpa respons harga =
# kemungkinan distribusi berkedok akumulasi (stale), bukan absorption.
# Sinyal di hari RTF_MAX_STREAK_DAYS+1 berturut-turut di-invalidasi
# (detect_accumulation(..., apply_streak_gate=True), dipakai jalur produksi
# scanner + API; default False = perilaku lama, klaim 18.4% tetap atribut
# definisi lama). Eksperimen: 456->332 sinyal, 54.4%->58.7% (+4.3pp), stabil
# Juli (+5.3) & Agu (+2.6); HIT dipertahankan 195/248 (79%); 71/208 miss
# dibuang; hanya 3/82 saham unik HIT hilang total (BBRM, LUCK, RISE);
# bootstrap 5k: mean +4.31pp, CI95 [-1.17, +9.61], P(gain>0)=94%. n kecil —
# wajib validasi ulang dataset penuh (800 hari) sebelum klaim resmi baru.
RTF_MAX_STREAK_DAYS = 3         # maks hari sinyal berturut-turut (termasuk hari ini)

# Gate likuiditas (rombak TODO, riset Agu 2026): ADV 20 hari point-in-time,
# hari ARA di-buang (volume ARA = antrean beli, bukan likuiditas keluar).
# Uji base rate B10 (universe 963, 12-Agu-2026): prima 0.3176 (n=825) vs
# floor-BEI 0.3040 (n=375) vs terfilter 0.3063 (n=493) -> z<0.6 semua, jadi
# likuiditas TIDAK prediktif; gate = floor eksekusi, bukan filter kualitas.
#   - gate wajib: tier (b) margin BEI (Rp250jt + 500rb lbr/hari) - floor
#     operasional: dapat dieksekusi tanpa impact harga utk swing 10-50jt.
#   - "prima" (1jt lbr + Rp1M/hari) hanya jadi flag display, BUKAN gate
#     (memfilter 50% sinyal tanpa manfaat prediktif).
ACCUM_ADV_WINDOW = 20           # jendela ADV (hari trading)
ACCUM_ADV_MIN_BARS = 5          # minimal bar valid utk menghitung ADV
ACCUM_MIN_ADV_VOL = 500_000     # floor: min rata-rata volume harian (lembar)
ACCUM_MIN_ADV_VAL = 250_000_000  # floor: min rata-rata nilai harian (Rp)
ACCUM_PRIMA_ADV_VOL = 1_000_000     # flag display "likuiditas prima" (lembar)
ACCUM_PRIMA_ADV_VAL = 1_000_000_000  # flag display "likuiditas prima" (Rp)

# Penalti kesegaran post-ARA (MED#5 + riset decay): w(d) = exp(-d/tau),
# cutoff keras d >= ACCUM_DECAY_CUTOFF_DAYS. Dipakai utk RANKING strength,
# bukan gate. Dasar: efek negatif ARA hanya di d+1 (netral sejak d>=2);
# literatur reversal IDX half-life 1-2 hari (tau ~2.0).
ACCUM_DECAY_TAU = 2.0
ACCUM_DECAY_CUTOFF_DAYS = 5

# DEFINISI FORMULA (MED#7 — referensi tunggal, konsisten antar modul):
#   - dd_fraction = 1 - close/prior_peak, prior_peak = max(close) trailing
#     RECOVERY_PEAK_LOOKBACK_DAYS, clamp [0, RECOVERY_MODEL_DD_CLAMP].
#     Target recovery = "menyentuh prior peak dalam h hari trading".
#   - net_dist (volume-weighted, recovery.py) = (sum_vol_up - sum_vol_dn) /
#     total_vol seluruh bar post-ARA, range [-1, 1].
#   - net_dist_heavy (definisi TODO audit) = (#heavy-day dgn Close > Open) /
#     (#heavy-day), range [0, 1]. Heavy = volume >= ACCUM_HEAVY_RVOL x
#     baseline post-ARA point-in-time. Dua-duanya dikirim API (komplementer).
#   - sma_gap_pct (RTF) = (close - SMA20)/SMA20 kontinu; SMA20 = simple mean
#     rolling 20 bar point-in-time (bukan exponential).
#   - momentum (audit) = close[i]/close[i-N] - 1.
# Hasil verifikasi data IDX 2026 (_validate_squeeze/_validate_post_ara/
# _baseline_compare): squeeze volatilitas BUKAN leading signal (OR<1);
# efek buruk post-ARA hanya di d+1 lalu netral d>=5; momentum murni tetap
# baseline terkuat; deep-drawdown tanpa model hampir tanpa edge.

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
# Kalibrasi empiris (_threshold_tuning.py, Top 10 Gainers 10 hari, Jul 2026,
# 94 saham): base rate dump = 70.2%; precision hampir FLAT 65-78% di semua
# threshold score (F1 max 76.5 @ 51-54, precision 77.8% @ 84+ dgn n=18).
# Kesimpulan: skor gorengan TIDAK diskriminatif utk memprediksi dump — level
# bersifat deskriptif/peringatan, bukan filter. Jangan jadikan cutoff tunggal.
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
