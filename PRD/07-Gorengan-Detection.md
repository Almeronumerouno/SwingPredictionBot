# Gorengan Detection Engine — Pump & Dump Risk Assessment

| Item | Detail |
|------|--------|
| **Modul** | `backend/gorengan.py` |
| **Versi** | v1.0 |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Gorengan Detection Engine menghitung Gorengan Risk Score (0-100) yang memperkirakan probabilitas sebuah saham menunjukkan karakteristik pump-and-dump ("saham gorengan"). Ini BUKAN sinyal buy/sell — ini layer risk assessment yang memperingatkan user.

## 2. Komponen Scoring (7 Faktor + Bonus)

| Komponen | Bobot | Deskripsi |
|----------|-------|-----------|
| Historical P&D Profile | 15% | Rekam jejak pump & dump di masa lalu (1 tahun) |
| Liquidity Risk | 15% | Saham tidak likuid (median daily value 60 hari) |
| Market Cap | 10% | Ukuran perusahaan (data shares) |
| **Active Pump** | **30%** | Short-term: RVOL spike + momentum 5d/10d + ATR expansion |
| Mid Momentum (20d) | 10% | Return searah 20 hari (Z-score) |
| Distribution Risk | 10% | Pola distribusi (dump behavior) |
| Turnover + Gaps | 10% | Turnover ratio + gap-up beruntun |
| Board Flag (bonus) | +10 | Saham di papan Pemantauan Khusus BEI |

## 3. Level Threshold

| Score | Level | Interpretasi |
|-------|-------|-------------|
| > 65 | EXTREME | Karakteristik P&D sangat kuat — hindari |
| > 45 | HIGH | Beberapa indikator manipulasi — hati-hati |
| > 20 | MEDIUM | Tanda spekulatif — waspada |
| ≤ 20 | LOW | Perilaku harga relatif normal |

## 4. Active Pump Detection (Bobot 30%)

Menggunakan **raw thresholds** (BUKAN time-series Z-score) karena Z-score kalah sama saham dengan baseline volatile tinggi (BHAT, NEST).

### 4.1 RVOL Spike

| Threshold | Score |
|-----------|-------|
| RVOL > 5.0 | 100 |
| RVOL > 3.0 | 70 |
| RVOL > 1.5 | 30 |
| Peak RVOL 14d > 5.0 | 70 |
| Peak RVOL 14d > 3.0 | 50 |

### 4.2 Short Momentum (5d & 10d Return)

| 5d Return | Score | 10d Return | Score |
|-----------|-------|------------|-------|
| > 25% | 100 | > 35% | 100 |
| > 12% | 70 | > 18% | 70 |
| > 7% | 40 | > 10% | 40 |
| > 3% | 20 | > 5% | 20 |

### 4.3 ATR Expansion (5d vs 14d)

| Ratio | Score |
|-------|-------|
| > 3.0 | 100 |
| > 2.0 | 70 |
| > 1.5 | 40 |

## 5. Validation Results

**Tested against 45 BEI UMA stocks (Jun-Jul 2026):**

| Method | HIGH+ | MEDIUM+ |
|--------|-------|---------|
| **Gorengan Engine** | **48.9%** | **95.6%** |
| Z-score only | 2.9% | 70.6% |

## 6. Output

```json
{
  "score": 72.3,
  "level": "HIGH",
  "factors": {
    "historical_pump_dump_risk": 0.0,
    "liquidity_risk": 60.0,
    "market_cap_risk": 100.0,
    "active_pump": 100.0,
    "mid_momentum": 40.0,
    "distribution_risk": 80.0,
    "turnover_gaps": 100.0
  },
  "warnings": [
    "Market cap kecil — sangat mudah disetir bandar",
    "Aktivitas pump terdeteksi: volume melonjak",
    "Turnover 18.5% float dalam sehari",
    "3x gap-up dalam 5 hari"
  ],
  "explanation": "Skor gorengan 72/100 — HIGH."
}
```

## 7. Future Improvements

- [ ] **Volume Profile analysis** — bedakan genuine breakout (HVN) vs pump (LVN)
- [ ] **Cross-sectional anomaly ranking** — bandingkan RVOL/return terhadap seluruh pasar
- [ ] **Social media sentiment** — FinBERT untuk deteksi koordinasi sosial
- [ ] **Order flow imbalance** — jika data tick-level tersedia
- [ ] **UMA monitoring** — auto-track saham di pemanatauan khusus BEI
- [ ] **ML classifier** — CatBoost dengan imbalance-aware optimization (referensi: 0.97 AUC-ROC)
