# Risk Management & Trade Plan

| Item | Detail |
|------|--------|
| **Modul** | `backend/risk.py` |
| **Versi** | v0.3.0-wip |
| **Last Updated** | 27 Juli 2026 |

## 1. Ringkasan

Layer risk management menghitung Stop Loss, Take Profit, dan position sizing berdasarkan ATR dan modal. ATR sengaja dipisah dari Swing Score — Volatility tidak directional dan tidak bisa dibedakan bullish/bearish, sehingga tidak cocok sebagai komponen linear Swing Score.

## 2. Parameter

| Parameter | Value | Notes |
|-----------|-------|-------|
| Position sizing | 100% dari capital input user | Capital-based (frontend CapitalControl handle input) |
| Risk per trade | Bervariasi — informasional | Ditampilkan sebagai "Risiko aktual X%" |
| Stop Loss | entry ± ATR × **3.0** | Kalibrasi v0.2.0 |
| Take Profit | entry ± ATR × **3.0** | v0.3.0: dinaikkan dari 2.5 (R:R 1:1) |
| Breakeven trigger | entry + ATR × **1.0** | Saat profit 1 ATR, SL pindah ke entry |
| Lot size | 100 lembar | Konvensi IDX |
| Minimal capital | ~Rp 100,000 | Tergantung harga saham (1 lot termurah) |

### 2.1 Risk Level Adjustment

```python
mult = ATR_SL_MULTIPLIER  # 3.0
if risk_level == "tinggi":
    mult *= 0.8  # SL lebih ketat saat risiko tinggi
```

## 3. Position Sizing Logic

Kode menggunakan 100% dari capital yang di-input user. Ini sengaja — frontend CapitalControl sudah memberikan kendali penuh ke user, backend tidak perlu memotong lagi.

```python
cost_per_lot = entry_price * 100  # 1 lot = 100 lembar
for deploy_pct in (1.0,):         # 100% modal
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
| `direction` | string | BUY / SELL (SELL hanya advisory jika long-only) |
| `entry` | float | Harga entry (close terakhir) |
| `stop_loss` | float | entry ± ATR × 3.0 (× 0.8 jika risk tinggi) |
| `take_profit` | float | entry ± ATR × 3.0 |
| `shares` | int | Jumlah lembar (kelipatan 100) — 0 jika SELL + long-only |
| `lots` | int | shares / 100 |
| `risk_reward_ratio` | float | reward / risk (1.0) |
| `note` | string | Peringatan jika risiko > 1% modal, atau mode long-only aktif |

## 5. Long-Only Mode

Kebanyakan retail IDX tidak punya akses short-selling.

```
LONG_ONLY_MODE = True  (config.py, default)

Saat mode aktif:
  - SELL signal → tidak ada trade plan (trade_plan = None)
  - SELL tetap tampil di scoring sebagai sinyal exit/advisory
  - Validation note: "Mode long-only aktif. SELL advisory — sinyal keluar
    jika sudah memiliki posisi, bukan sinyal short entry."
```

## 6. Sprint 1 (v0.3.0) — Quick Win

### 6.1 Fix R:R Ratio

TP multiplier dinaikkan dari 2.5 ke **3.0** → R:R 1:1.

Dampak teoritis:
- Trade plan R:R = 1:1 (seimbang)
- Expected Value naik dari 0.04 ATR menjadi 0.106 ATR per trade
- TP hit rate mungkin turun (target lebih jauh), tapi tiap TP lebih berarti

### 6.2 Breakeven Stop Rule

Begitu harga menyentuh entry + 1.0 ATR, SL otomatis dipindah ke entry price.

- Melindungi modal setelah profit tercapai
- Tidak menambah downside risk
- Parameter tunggal: `BREAKEVEN_TRIGGER = 1.0`

## 7. Sprint 3 — Regime-Dependent Position Sizing

Setelah base sizing direkonsiliasi (Sprint 2), sizing bervariasi per regime:

| Regime | Position Size |
|--------|:------------:|
| Bull | 100% |
| Sideways | 50% |
| Bear | 25% |

## 8. Roadmap Sprint (S1-S4)

| Sprint | Item | Parameter Baru | Dependensi |
|--------|------|:--------------:|------------|
| **S1A** | Walk-forward harness | 0 | — |
| **S1B** | Fix R:R (TP 3.0) | 1 | S1A |
| **S1C** | Breakeven stop (1.0 ATR) | 1 | S1A |
| **S1D** | Long-only mode | 0 | — |
| **S2** | Rekonsiliasi sizing + validasi S1 | 0 | S1A–D |
| **S3** | Regime detection + adaptive weights | 2-3 | S2 |
| **S4+** | Full scale-out, trailing, ML | banyak | S3 |

## 9. Backtest Outcome Distribution (v0.2.0 Baseline)

| Label | Count | Percentage |
|-------|-------|-----------|
| TP_FIRST | 57 | 40.4% |
| SL_FIRST | 36 | 25.5% |
| TIMEOUT | 48 | 34.0% |

**Target v0.3.0:** TP_HIT > 50% (S1-S2), > 55% (S3), > 60% (S4+).
