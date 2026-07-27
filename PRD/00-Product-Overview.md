# Product Overview — Swing Bot IDX

| Item | Detail |
|------|--------|
| **Product Name** | Swing Bot IDX |
| **Version** | 0.2.0 |
| **Status** | Fase 6 (Testing & Refinement) selesai. Memasuki Fase 7 (Production Readiness) |
| **Last Updated** | 27 Juli 2026 |

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

| Metrik | Target | Current (v0.2.0) |
|--------|--------|-----------------|
| Waktu scrape seluruh pasar | < 1 menit (IDX) | ~3 detik (IDX) |
| Waktu analisis per saham | < 3 detik | ~1-2 detik |
| Cakupan saham | Seluruh IDX (~900 emiten) | ~900 emiten |
| Win Rate (mid-big cap liquid) | >55% | 55.3% |
| Alpha vs B&H | >+5% | +5.38% |
| Sharpe Ratio | >0.20 | 0.24 |
| TP_HIT rate | >50% | 40.4% |

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
| **7** | **Production Readiness (target)** | **0%** |

## 7. Hasil Backtest Final (v0.2.0)

### Parameter Optimal (Kalibrasi 243 combo × 19 saham)

| Parameter | Default | Kalibrasi |
|-----------|:-------:|:---------:|
| ADX gate ceiling | 25 | **20** |
| Swing buy threshold | 65 | **70** (experimental: 75) |
| ATR SL multiplier | 1.5 | **3.0** |
| RVOL window | 20 | **10** |
| RVOL breakout confirm | 2.0 | **1.5** |

### Performa 19 Mid-Big Cap Liquid (Des 2025 — Jul 2026)

| Metrik | Default | Kalibrasi |
|--------|:-------:|:---------:|
| Win Rate | 35.6% | **55.3%** |
| Total Return | -1.92% | **+0.41%** |
| Alpha vs B&H | +0.86% | **+5.38%** |
| Sharpe Ratio | -0.72 | **0.24** |
| Max Drawdown | 5.25% | **5.94%** |
| Beat B&H | — | **13/19 (68%)** |

### Outcome Distribution (141 sinyal, 20 saham)

| Label | Jumlah | Persentase |
|-------|--------|-----------|
| TP_FIRST | 57 | **40.4%** |
| SL_FIRST | 36 | **25.5%** |
| TIMEOUT | 48 | **34.0%** |

## 8. Catatan Penting

- **BUY belum tervalidasi** edge independen lintas rezim (bullish WR 70.6% → bearish 27.3%)
- **SELL tervalidasi** (~58% WR konsisten 2 rezim)
- **Micro-cap gainers tidak cocok** — sistem optimal di saham likuid mid-big cap
- **Fees & slippage belum dimodelkan** — return overstate ~2-5%
- **Look-ahead minor**: S/R levels pakai full history (efek kecil)
- **Walk-forward validation belum dilakukan** — parameter optimal mungkin overfit
