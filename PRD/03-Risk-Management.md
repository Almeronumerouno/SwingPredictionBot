# Risk Management & Trade Plan

| Item | Detail |
|------|--------|
| **Modul** | `backend/risk.py` |
| **Versi** | v0.4.0-wip |
| **Last Updated** | 7 Agustus 2026 |

## 1. Ringkasan

Layer risk management menghitung Stop Loss, Take Profit, dan position sizing berdasarkan ATR dan modal. ATR sengaja dipisah dari Swing Score — Volatility tidak directional dan tidak bisa dibedakan bullish/bearish, sehingga tidak cocok sebagai komponen linear Swing Score.

## 2. Parameter

| Parameter | Value | Notes |
|-----------|-------|-------|
| Position sizing | **Risk-based** (bukan full deploy) | `risk_budget = capital × 1% × regime_mult` |
| Risk per trade | Bull **1.0%**, Sideways **0.5%**, Bear **0.25%** | Risk budget per regime = `RISK_PER_TRADE_PCT × position_pct` |
| Stop Loss | entry ± ATR × **3.0** | Kalibrasi v0.2.0 (× 0.8 jika risk tinggi) |
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

**v0.4.0:** Risk-based sizing menggantikan full-deployment. Ukuran posisi ditentukan agar **max loss saat kena stop = risk budget**, bukan "deploy semua modal". Regime multiplier (`profile.position_pct`, single source of truth dari `regime.py`) dipakai sebagai risk multiplier:

- **Bull**: risk budget = capital × 1% × **1.0** = 1.0% modal
- **Sideways**: capital × 1% × **0.5** = 0.5% modal
- **Bear**: capital × 1% × **0.25** = 0.25% modal

Saat ATR lebar (stop jauh), risk budget otomatis memaksa posisi kecil — bukan full deploy. Safety net: posisi tidak boleh melebihi `capital × regime_mult` (no leverage).

```python
per_share_risk = abs(entry - stop_loss)
deploy_capital = capital * regime_mult            # capital dialokasikan
risk_budget = deploy_capital * risk_pct           # e.g. 10jt × 1% = 100rb
lots = int(risk_budget / per_share_risk) // 100   # floor ke lot
# cap: tidak boleh > capital × regime_mult / entry (no leverage)
shares = lots * 100
```

Contoh: modal 10jt, entry @1.000, SL @970 (risk/share 30) → Bull: 100.000/30 = 33 lot = 0.99% modal at risk. Dengan sizing lama (full deploy) saham ini masuk 100 lot = 300.000 risk (3%).

Formulanya identik di `risk.py` (live) dan `backtest.py:_calc_shares_by_risk` (validation) sehingga live == backtest.

## 4. Trade Plan Output

| Field | Type | Description |
|-------|------|-------------|
| `direction` | string | BUY / SELL (SELL hanya advisory jika long-only) |
| `entry` | float | Harga entry (close terakhir) |
| `stop_loss` | float | entry ± ATR × 3.0 (× 0.8 jika risk tinggi) |
| `take_profit` | float | entry ± ATR × 3.0 |
| `shares` | int | Jumlah lembar (kelipatan 100) — 0 jika tidak cukup untuk 1 lot |
| `lots` | int | shares / 100 |
| `risk_reward_ratio` | float | reward / risk (1:1) |
| `risk_per_trade_pct` | float \| None | **BARU v0.4.0** — actual risk % dari modal (di frontend tampil sebagai "Risiko per Trade") |
| `note` | string | Ringkasan risiko aktual (dari `risk.py`) |

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

Setelah base sizing direkonsiliasi (Sprint 2), sizing bervariasi per regime. **v0.4.0:** regime multiplier sekarang **risk multiplier** (bukan position multiplier):

| Regime | Risk per Trade | Posisi saat SL 3% |
|--------|:------------:|:-----------------:|
| Bull | 1.0% | ~1/3 modal |
| Sideways | 0.5% | ~1/6 modal |
| Bear | 0.25% | ~1/12 modal |

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
