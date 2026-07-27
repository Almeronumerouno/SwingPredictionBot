# Risk Management & Trade Plan

| Item | Detail |
|------|--------|
| **Modul** | `backend/risk.py` |
| **Versi** | v0.2.0 |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Layer risk management menghitung Stop Loss, Take Profit, dan position sizing berdasarkan ATR dan modal. ATR sengaja dipisah dari Swing Score — Volatility tidak directional dan tidak bisa dibedakan bullish/bearish, sehingga tidak cocok sebagai komponen linear Swing Score.

## 2. Parameter

| Parameter | Value | Notes |
|-----------|-------|-------|
| Position sizing | 25% alokasi modal (fallback 50%) | Capital-based, bukan risk-based |
| Risk per trade | Bervariasi — informasional | Ditampilkan sebagai "Risiko aktual X%" |
| Stop Loss | entry ± ATR × **3.0** | Kalibrasi v0.2.0 |
| Take Profit | entry ± ATR × **2.5** | R:R ~1:0.83 |
| Lot size | 100 lembar | Konvensi IDX |
| Minimal capital | ~Rp 100,000 | Tergantung harga saham (1 lot termurah) |

### 2.1 Risk Level Adjustment

```python
mult = ATR_SL_MULTIPLIER  # 3.0
if risk_level == "tinggi":
    mult *= 0.8  # SL lebih ketat saat risiko tinggi
```

## 3. Position Sizing Logic

```python
cost_per_lot = entry_price * 100  # 1 lot = 100 lembar
for deploy_pct in (1.0,):         # 100% modal (25% → 100% sejak 18 Jul 2026)
    max_lots = int((capital * deploy_pct) // cost_per_lot)
    if max_lots >= 1:
        shares = max_lots * 100
        risk_pct = (per_share_risk * shares) / capital
        if risk_pct > 1%:
            note = f"Risiko: Rp {risk_amt:,} ({risk_pct*100:.1f}%)"
        return shares, note
return 0, None  # Tidak cukup modal untuk 1 lot
```

## 4. Trade Plan Output

| Field | Type | Description |
|-------|------|-------------|
| `direction` | string | BUY / SELL |
| `entry` | float | Harga entry (close terakhir) |
| `stop_loss` | float | entry ± ATR × 3.0 (× 0.8 jika risk tinggi) |
| `take_profit` | float | entry ± ATR × 2.5 |
| `shares` | int | Jumlah lembar (kelipatan 100) |
| `lots` | int | shares / 100 |
| `risk_reward_ratio` | float | reward / risk (rata-rata 0.83) |
| `note` | string | Peringatan jika risiko > 1% modal |

## 5. Identified Issues (Current)

| Issue | Impact | Proposed Solution |
|-------|--------|-------------------|
| R:R rata-rata 0.83 | Risk lebih besar dari reward | TP multiplier perlu dinaikkan (3.5× ATR?) |
| No trailing stop | Sering kehilangan profit setelah TP | Implementasi TP Trail (50% exit, 50% trailing) |
| No partial exit | Semua atau tidak sama sekali | Scale out 50/30/20 |
| Fixed multiplier | Tidak adaptif terhadap volatilitas | Dynamic ATR multiplier berdasarkan Volatility Regime |
| Single TP level | Harga sering nyaris TP lalu reversal | Multiple TP levels (T1, T2, T3) |

## 6. Proposed Improvements (Fase 7)

### 6.1 Partial Profit Taking (Scale Out)

| Stage | Aksi | Stop Management |
|-------|------|----------------|
| Entry | Full posisi | SL awal 3.0× ATR |
| T1 (+1.0× ATR) | Close **50%** | Pindah SL ke breakeven |
| T2 (+2.0× ATR) | Close **30%** | Trailing stop 0.5× ATR dari high |
| Sisa 20% | Biarkan running | Trail sampai kena atau timeout |

### 6.2 TP Trail Method

Begitu harga mencapai TP (2.5× ATR), exit 50%. Sisa 50% di-trail dengan stop 1.0× ATR di bawah harga tertinggi sejak entry.

### 6.3 Dynamic ATR Multiplier

```
ATR_SL_MULTIPLIER = base × vol_factor
vol_factor = 
  0.8 jika Volatility Regime = HIGH
  1.0 jika Volatility Regime = NORMAL  
  1.2 jika Volatility Regime = LOW
```

### 6.4 Circuit Breaker

Setelah 2 kerugian beruntun, posisi size dikurangi 50%. Reset setelah 1 winning trade.

## 7. Backtest Outcome Distribution (Current)

| Label | Count | Percentage |
|-------|-------|-----------|
| TP_FIRST | 57 | 40.4% |
| SL_FIRST | 36 | 25.5% |
| TIMEOUT | 48 | 34.0% |

Target dengan partial exit + trailing: **TP_HIT rate > 55%**.
