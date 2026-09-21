# Product Overview — Swingbot IDX

| Item | Detail |
|------|--------|
| **Product Name** | Swingbot IDX |
| **Version** | 0.3.0-wip |
| **Status** | Fase 7 (Production Readiness) — Sprint 1 berjalan |
| **Last Updated** | 21 September 2026 |

## 1. Ringkasan

Swing trading signal generator untuk Bursa Efek Indonesia (IDX). Sistem mengambil data pasar dari IDX (1 call = seluruh pasar), menghitung indikator teknikal Wilder-class, menghasilkan Swing Score 0-100 dari 4 komponen dengan ADX gating, dan menyusun trade plan (SL/TP/sizing) berbasis ATR.

## 2. Mengapa Ini Dibutuhkan

- Rata-rata investor ritel IDX tidak punya alat analisis teknikal yang terstruktur
- Data IDX tersebar dan sulit diakses — sistem mengkonsolidasi 2 endpoint IDX + Yahoo Finance
- Scoring kuantitatif menghilangkan bias subjektif dalam membaca indikator
- Risk management terintegrasi (posisi sizing, SL/TP) melindungi modal

## 3. Perubahan dari Rencana Awal

Awalnya direncanakan bot Telegram. Diubah menjadi **dashboard web** (FastAPI + Next.js) karena:
- Dashboard web lebih kaya secara visual (chart, tabel, warna)
- Lebih mudah diakses via browser tanpa instalasi
- Bisa dikembangkan jadi platform multi-user

## 4. Goals & Objectives

### 4.1 Tujuan Utama

1. **Menyediakan analisis teknikal otomatis** untuk seluruh saham IDX
2. **Memberikan sinyal trading objektif** (BUY/SELL/HOLD) berbasis data
3. **Mengintegrasikan risk management** (SL, TP, posisi sizing)
4. **Akses cepat via web dashboard** dalam 2 klik dari gainers ke detail

### 4.2 Success Metrics

| Metrik | Target v0.3.0 | Current (v0.2.0) |
|--------|:-------------:|:-----------------:|
| Waktu scrape seluruh pasar | < 1 menit (IDX) | ~3 detik (IDX) |
| Waktu analisis per saham | < 3 detik | ~1-2 detik |
| Cakupan saham | Seluruh IDX (~900 emiten) | ~900 emiten |
| Win Rate (mid-big cap liquid) | **>60%** | 55.3% |
| Alpha vs B&H | **>+8%** | +5.38% |
| Sharpe Ratio | **>0.50** | 0.24 |
| TP_HIT rate | **>55%** | 40.4% |
| R:R rata-rata | **>1.2** | 0.83 |
| Max DD | **<5%** | 5.94% |

## 5. Target Audience

| Segmen | Kebutuhan | Prioritas |
|--------|-----------|-----------|
| **Investor ritel individu** | Analisis cepat, rekomendasi jelas, risk management | Primary |
| **Trader swing pemula** | Panduan entry/exit, sizing aman, edukasi indikator | Secondary |
| **Analis / research house** | Data mentah indikator, screening cepat | Tertiary |

## 6. Fase Pengembangan

| Fase | Deskripsi | Status |
|------|-----------|--------|
| 0 | Setup & Validasi Data Source | **100%** |
| 1 | Layer Indikator (`indicators.py`) | **100%** |
| 2 | Normalisasi & Scoring (`scoring.py`) | **100%** |
| 3 | Risk & Trade Plan (`risk.py`) | **100%** |
| 4 | API Layer (`api.py`, FastAPI) | **100%** |
| 5 | Frontend Dashboard (Next.js) | **100%** |
| 6 | Testing & Refinement (Backtest + Kalibrasi) | **100%** |
| **7** | **Production Readiness** | **Dalam pengerjaan** |

### Sprint Plan Fase 7

| Sprint | Item | Status |
|--------|------|--------|
| S1A | Walk-forward harness skeleton | **✅ Selesai** (`walkforward.py`, 461 baris, fully functional) |
| S1B | Fix R:R — TP multiplier 3.0 | **Ditangguhkan** (baseline 2.5 dipertahankan, belum ada bukti OOS 3.0 lebih baik) |
| S1C | Breakeven stop (1.0 ATR) | **✅ Tested & Disabled** (degrades TP_HIT & WR; tested 1.0/1.2/1.5/2.0) |
| S1D | Long-only mode (SELL advisory) | **✅ Tested & Kept Off** (SELL validated 58% WR — tetap aktif sebagai entry signal) |
| S2 | Rekonsiliasi sizing + validasi OOS | **✅ Selesai** (reconciled to all-in, `POSITION_SIZING_MODE="all_in"`) |
| S3 | Regime detection + adaptive weights | **✅ Selesai** (`regime.py` — SMA200+ADX, 3 profiles, adaptive weights/sizing) |
| S4+ | Scale-out, trailing, ML | **Ditunda** |

## 7. Hasil Backtest v0.2.0 (Baseline)

### Parameter Optimal (Kalibrasi 243 combo × 19 saham)

| Parameter | Default | Kalibrasi |
|-----------|:-------:|:---------:|
| ADX gate ceiling | 25 | **20** |
| Swing buy threshold | 65 | **75** (experimental) |
| ATR SL multiplier | 1.5 | **3.0** |
| ATR TP multiplier | 2.5 | **3.0** (v0.3.0) |
| RVOL window | 20 | **10** |
| RVOL breakout confirm | 2.0 | **1.5** |

### Performa 19 Mid-Big Cap Liquid (Des 2025 — Jul 2026)

| Metrik | v0.2.0 | Target S1-S2 | Target S3 |
|--------|:------:|:------------:|:---------:|
| Win Rate | 55.3% | 55-58% | >60% |
| Total Return | +0.41% | +1-3% | >5% |
| Alpha vs B&H | +5.38% | +6-7% | >+8% |
| Sharpe Ratio | 0.24 | 0.30-0.40 | >0.50 |
| Max Drawdown | 5.94% | <5.5% | <5% |

### Outcome Distribution (141 sinyal, 20 saham)

| Label | Jumlah | Persentase |
|-------|--------|-----------|
| TP_FIRST | 57 | **40.4%** |
| SL_FIRST | 36 | **25.5%** |
| TIMEOUT | 48 | **34.0%** |

## 8. Catatan Penting

- **BUY belum tervalidasi** edge independen lintas rezim (bullish WR 70.6% → bearish 27.3%)
- **SELL tervalidasi** (~58% WR konsisten 2 rezim) — long-only mode tersedia tapi sengaja OFF (SELL tetap entry signal)
- **Micro-cap gainers tidak cocok** — sistem optimal di saham likuid mid-big cap
- **Fees sudah dimodelkan** — `FEE_BUY_PCT=0.18%`, `FEE_SELL_PCT=0.28%` (termasuk PPh Final 0.1%)
- **Walk-forward validation sudah tersedia** (`walkforward.py`) — prasyarat untuk semua perubahan parameter baru
