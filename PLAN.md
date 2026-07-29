# Swing Bot IDX — Execution Plan v0.3.0

## Ringkasan

Target: **naikkan win rate** lewat precision entry, tuning threshold bertahap, dan validasi OOS.
Bukan nambah trade count — precision-recall trade-off: threshold lebih tinggi → false positive turun.

## Prinsip Utama

- **Regime = bobot + sizing**, bukan hard gate. ADX non-directional, cocok buat konteks, bukan larangan.
- **Walk-forward wajib** untuk setiap perubahan parameter — purge + embargo cegah leakage.
- **Satu perubahan per eksperimen** — kalau diubah 10 hal sekaligus, tidak tahu mana yang beneran ngefek.
- **Precision dulu, recall belakangan** — kurangi false positive, biarkan trade count turun wajar.

## 10 Langkah (Urut — Jangan Lompat)

### Langkah 1 — Bekukan Baseline

Ambil satu konfigurasi stabil sebagai pembanding:

| Parameter | Value | Notes |
|-----------|-------|-------|
| `LONG_ONLY_MODE` | `False` | SELL tetap entry signal |
| `ATR_TP_MULTIPLIER` | `2.5` | Baseline; 3.0 diuji terpisah |
| Bear `allow_new_longs` | `True` | Bukan blok mutlak |
| Regime | bobot + sizing only | Bukan gate izin entry |

### Langkah 2 — Walk-Forward Wajib

Sudah ada `backend/walkforward.py`. Output minimal:

- Concat OOS trade dari seluruh (saham × window)
- Win rate, TP_HIT, SL_HIT, Sharpe, Max DD, total trade
- Parameter stability antar window

### Langkah 3 — Samakan Sumber Parameter

**Satu source of truth:** `config.py`

| File | Yang dicek |
|------|-----------|
| `config.py` | Default global — TP, threshold, sizing, regime |
| `backtest.py` | `BacktestConfig` baca dari config.py, override cuma saat kalibrasi |
| `risk.py` | Baca config, bukan simpan versi sendiri |
| `api.py` | Pastikan output trade plan pakai nilai dari risk.py |

### Langkah 4 — Entry Filter (Precision)

BUY hanya valid jika **minimal 3 dari 4** ini terpenuhi:

- `close > donchian_upper` — breakout konfirmasi
- `RVOL >= 1.5` — volume mendukung
- `ADX >= 15` — tren cukup kuat
- `ADX naik dari bar sebelumnya` — momentum positif

Opsional (untuk filter lebih ketat):

- `EMA fast > EMA slow` — tren searah
- `RSI >= 45` — tidak oversold
- `MFI >= 45` — tidak outflow berat

**File:** `backend/scoring.py`, `backend/backtest.py` (`compute_signals`)

### Langkah 5 — Tuning Threshold

Perubahan kecil, bukan lompatan besar:

| Regime | Threshold |
|--------|:---------:|
| Bull | 72 (dari 75) |
| Sideways | 68 (dari 70) |
| Bear | 70 (dari None — baru) |

**File:** `backend/config.py`, `backend/regime.py`

### Langkah 6 — Regime = Bobot + Sizing

| Regime | Trend | Mom | Vol | PA | Size |
|--------|:-----:|:---:|:---:|:--:|:----:|
| Bull | 0.35 | 0.25 | 0.15 | 0.25 | 100% |
| Sideways | 0.15 | 0.15 | 0.25 | **0.45** | 50% |
| Bear | 0.20 | **0.30** | 0.25 | 0.25 | 25% |

Bear tetap boleh entry kalau confluence kuat — size kecil, bukan larangan.

### Langkah 7 — Risk Quick Wins (S1B + S1C)

**S1B — TP 3.0 (Eksperimen terpisah)**
- TP multiplier 3.0 → R:R 1:1
- Diuji via walk-forward, bukan langsung ganti default
- Banding: TP 2.5 vs TP 3.0 → pilih yang OOS lebih stabil

**S1C — Breakeven Trigger 1.0 ATR**
- Setelah profit 1 ATR, SL pindah ke entry
- Mengurangi trade yang sempat benar lalu balik rugi
- 1 parameter, mudah divalidasi

### Langkah 8 — LONG_ONLY_MODE (Final)

Setelah entry filter + risk quick win stabil, baru uji:

- `LONG_ONLY_MODE = True` → SELL jadi advisory, short entry ditiadakan
- Scoring tetap hitung SELL — informasional
- Validasi: apakah win rate naik (karena short dihilangkan) atau turun (karena trade berkurang)

### Langkah 9 — Walk-Off: TP 2.5 vs TP 3.0

Dua kandidat final, diadu via walk-forward OOS:

| Metrik | TP 2.5 | TP 3.0 |
|--------|:------:|:------:|
| Win rate | ? | ? |
| TP_HIT | 41.2% | 35.4% |
| SL_HIT | 24.4% | 26.5% |
| Avg R:R | 0.83 | 1.0 |
| Sharpe | ? | ? |
| Max DD | ? | ? |
| Total trade | 221 | 223 |

Pilih yang win rate tertinggi, trade count masih wajar, max DD tidak meledak.

### Langkah 10 — Fine-Tune Regime Weights (Final)

Hanya jika langkah 1-9 sudah jalan dan win rate masih kurang:
- Identifikasi komponen paling sering false positive
- Sideways noise tinggi? Turunkan PA dari 0.45 ke 0.35-0.40
- Bull ketinggalan? Naikkan trend weight sedikit

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
