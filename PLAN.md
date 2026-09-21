# Swingbot IDX — Execution Plan v0.3.0

## Ringkasan

Target: **naikkan win rate** lewat precision entry, tuning threshold bertahap, dan validasi OOS.
Bukan nambah trade count — precision-recall trade-off: threshold lebih tinggi → false positive turun.

## Prinsip Utama

- **Regime = bobot + sizing**, bukan hard gate. ADX non-directional, cocok buat konteks, bukan larangan.
- **Walk-forward wajib** untuk setiap perubahan parameter — purge + embargo cegah leakage.
- **Satu perubahan per eksperimen** — kalau diubah 10 hal sekaligus, tidak tahu mana yang beneran ngefek.
- **Precision dulu, recall belakangan** — kurangi false positive, biarkan trade count turun wajar.

## 10 Langkah (Status & Eksekusi)

### Langkah 1 — Bekukan Baseline — [x] SELESAI

Ambil satu konfigurasi stabil sebagai pembanding:

| Parameter | Value | Notes | Status |
|-----------|-------|-------|:------:|
| `LONG_ONLY_MODE` | `False` | SELL tetap entry signal (58% WR) | ✅ Aktif |
| `ATR_TP_MULTIPLIER` | `2.5` | Baseline; 3.0 diuji terpisah | ✅ Aktif |
| Bear `allow_new_longs` | `True` | Bukan blok mutlak | ✅ Aktif |
| Regime | bobot + sizing only | Bukan gate izin entry | ✅ Aktif |

### Langkah 2 — Walk-Forward Wajib — [x] SELESAI

Sudah ada `backend/walkforward.py` (461 baris, fully functional). Output:

- Concat OOS trade dari seluruh (saham × window)
- Win rate, TP_HIT, SL_HIT, Sharpe, Max DD, total trade, Sortino, CAGR, AUC-ROC
- Parameter stability antar window via hyperparameter grid train/test

### Langkah 3 — Samakan Sumber Parameter — [x] SELESAI

**Satu source of truth:** `config.py`

| File | Yang dicek | Status |
|------|-----------|:------:|
| `config.py` | Default global — TP, threshold, sizing, regime | ✅ Selesai |
| `backtest.py` | `BacktestConfig` baca dari config.py, override cuma saat kalibrasi | ✅ Selesai |
| `risk.py` | Baca config, bukan simpan versi sendiri | ✅ Selesai |
| `api.py` | Pastikan output trade plan pakai nilai dari risk.py | ✅ Selesai |

### Langkah 4 — Entry Filter (Precision) — [x] DIUJI & TERINTEGRASI

Heuristik breakout & konfirmasi volume sudah terintegrasi:
- `close > donchian_upper` & `RVOL >= 1.5` — terintegrasi di Price Action score (`scoring.py` & `backtest.py`)
- `ADX gate ceiling 20` — menekan trend & momentum jika pasar sideways
- `_price_stagnation_gate` — membatalkan sinyal BUY/SELL jika pergerakan harga stagnan
- Hard 3-of-4 confluence filter diuji; kombinasi skor linier + regime multiplier terbukti lebih stabil

### Langkah 5 — Tuning Threshold — [x] SELESAI

Perubahan kecil berbasis rezim di `regime.py`:

| Regime | Threshold | Status |
|--------|:---------:|:------:|
| Bull | 72 (dari 75) | ✅ Aktif di `regime.py` |
| Sideways | 68 (dari 70) | ✅ Aktif di `regime.py` |
| Bear | 70 (dari None — baru) | ✅ Aktif di `regime.py` |

**File:** `backend/config.py`, `backend/regime.py`

### Langkah 6 — Regime = Bobot + Sizing — [x] SELESAI

| Regime | Trend | Mom | Vol | PA | Size | Status |
|--------|:-----:|:---:|:---:|:--:|:----:|:------:|
| Bull | 0.35 | 0.25 | 0.15 | 0.25 | 100% | ✅ Aktif |
| Sideways | 0.15 | 0.15 | 0.25 | **0.45** | 50% | ✅ Aktif |
| Bear | 0.20 | **0.30** | 0.25 | 0.25 | 25% | ✅ Aktif |

Bear tetap boleh entry kalau confluence kuat — size kecil, bukan larangan.

### Langkah 7 — Risk Quick Wins (S1B + S1C) — [x] DIUJI & DIPUTUSKAN

**S1B — TP 3.0 (Eksperimen terpisah)**
- TP multiplier 3.0 → R:R 1:1
- Diuji via walk-forward; hasil OOS menunjukkan TP 2.5 memiliki hit-rate dan kestabilan lebih tinggi (TP 3.0 trade count dan win rate tertekan saat bear market). **Keputusan:** Baseline 2.5 dipertahankan.

**S1C — Breakeven Trigger 1.0 ATR**
- Logika lengkap diimplementasikan di `backtest.py:L579-590`.
- Hasil pengujian pada level 1.0, 1.2, 1.5, dan 2.0 ATR menunjukkan breakeven stop justru mendegradasi WR dan TP_HIT (karena whipsaw candle normal). **Keputusan:** Sengaja dinonaktifkan (`BREAKEVEN_TRIGGER = 999.0`).

### Langkah 8 — LONG_ONLY_MODE (Final) — [x] DIUJI & SENGAJA NONAKTIF

- Logika tersedia di `config.py`, `backtest.py`, dan `risk.py`.
- Karena sinyal SELL terbukti memiliki Win Rate 58% konsisten lintas rezim, short/exit signal tetap dipertahankan sebagai sinyal aktif (`LONG_ONLY_MODE = False`).

### Langkah 9 — Walk-Off: TP 2.5 vs TP 3.0 — [x] SELESAI

Hasil evaluasi out-of-sample:
- TP 2.5: TP_HIT 41.2%, SL_HIT 24.4%, Avg R:R 0.83, Total trade 221.
- TP 3.0: TP_HIT 35.4%, SL_HIT 26.5%, Avg R:R 1.0, Total trade 223.
- **Pemenang:** TP 2.5 dipilih karena TP_HIT lebih tinggi (+5.8%) dan SL_HIT lebih rendah (-2.1%).

### Langkah 10 — Fine-Tune Regime Weights (Final) — [x] SELESAI

- Bobot rezim di `regime.py` telah disetel: Sideways PA ditingkatkan ke 0.45, Bear momentum 0.30, Bull trend 0.35.
- Evaluasi berjalan memuaskan dan stabil di baseline v0.3.0.

## Urutan Edit File

```
1. backend/config.py        — baseline fix
2. backend/walkforward.py   — sudah ada, jadi mandatory gate
3. backend/regime.py        — threshold + bobot (hard gate sudah dihapus)
4. backend/scoring.py       — entry confluence filter
5. backend/risk.py          — sizing + breakeven
6. backend/backtest.py      — compute_signals + confluence
7. backend/api.py           — output konsisten
8. README.md / PRD.md       — update dokumentasi
```

## Target Metrik

| Metrik | v0.2.0 | Target v0.3.0 |
|--------|:------:|:-------------:|
| Win rate | 49-55% | >50% OOS |
| TP_HIT | 40-45% | >38% OOS |
| R:R | 0.83 | 0.83-1.0 |
| Sharpe | 0.24 | >0.30 OOS |
| Max DD | 5.94% | <6% |
| Trade count | 150-220 | >100 |
