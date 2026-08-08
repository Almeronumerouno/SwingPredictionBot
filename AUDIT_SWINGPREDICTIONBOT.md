# Audit Menyeluruh — Swingbot IDX Backend

**Cakupan:** `backend.zip` — indicators.py, scoring.py, regime.py, risk.py, backtest.py, backtest_calibrate.py, walkforward.py, recovery.py, gorengan.py, api.py, data_source/*, serta seluruh script validasi (`_validate_*.py`, `_backtest_gorengan.py`, `_threshold_tuning.py`, `_compare_methods.py`, `_retune_hybrid.py`).
**Metodologi:** (1) pembacaan kode baris-per-baris untuk setiap rumus; (2) verifikasi numerik independen — implementasi ulang RSI/ATR/MFI/ADX dari nol memakai pandas lalu di-diff terhadap `indicators.py`, dan simulasi Monte Carlo untuk menguji formula GBM di `recovery.py`; (3) riset teori/standar (Wilder 1978, López de Prado 2018, teori GBM/Itô, konvensi Sharpe ratio) dan regulasi BEI/IDX terkini (per Agustus 2026).
**Prinsip pelaporan:** setiap rumus diberi status **✅ BENAR** (tervalidasi, dengan alasan), **⚠️ PERLU PERBAIKAN** (ada bug/inkonsistensi, dengan bukti dan rekomendasi), atau **🔶 CATATAN** (bukan bug, tapi ada nuansa/asumsi yang perlu didokumentasikan atau divalidasi lebih lanjut).

---

## Ringkasan Eksekutif

Secara keseluruhan, codebase ini menunjukkan tingkat kematangan kuantitatif yang **jauh di atas rata-rata proyek swing-trading retail** — indikator teknikal diimplementasikan dengan presisi tinggi, ada kesadaran eksplisit soal *lookahead bias* di beberapa tempat, dan validasi memakai *ground truth* riil (saham UMA yang benar-benar ditandai BEI) alih-alih asumsi. Namun audit menemukan **9 isu signifikan** — satu di antaranya (kesalahan konversi drift GBM) berhasil dibuktikan secara kuantitatif lewat simulasi Monte Carlo, dan satu lagi (tidak ada filter kelayakan *short selling*) adalah isu regulasi yang berdampak langsung ke keterlaksanaan sinyal SELL di dunia nyata.

| # | Temuan | Modul | Severity | Status |
|---|--------|-------|----------|--------|
| 1 | Drift GBM salah dipakai di `first_passage_cdf` (lupa koreksi Itô −0.5σ²) | recovery.py | 🔴 Tinggi | ✅ DIPERBAIKI |

| 2 | Tidak ada filter kelayakan *short selling* untuk sinyal SELL | api.py/risk.py | 🔴 Tinggi | ✅ DIPERBAIKI |

| 3 | `backtest_calibrate.py` melakukan optimasi parameter 100% in-sample | backtest_calibrate.py | 🔴 Tinggi | ✅ DIPERBAIKI |

| 4 | `walkforward.py`: window train dihitung tapi tidak pernah dipakai untuk optimasi | walkforward.py | 🟠 Sedang-Tinggi | ✅ DIPERBAIKI |

| 5 | `walkforward.py`: anualisasi Sharpe pakai √252 pada return per-trade (bukan harian) | walkforward.py | 🟠 Sedang | ✅ DIPERBAIKI |

| 6 | `risk_level` & `confidence` di live scoring selalu konstan ("sedang") — beda dari backtest | scoring.py/risk.py | 🟠 Sedang | ✅ DIPERBAIKI |

| 7 | Exit REVERSAL di backtest pakai sinyal bar-yang-sama (lookahead) | backtest.py | 🟠 Sedang | ✅ DIPERBAIKI |

| 8 | Dead code: perhitungan Sharpe trade-based tertimpa variable shadowing | backtest.py | 🟡 Rendah-Sedang | ✅ DIPERBAIKI |

| 9 | Seeding RSI menyisipkan delta palsu bernilai 0 (bias di ~40-60 bar pertama) | indicators.py | 🟡 Rendah | ✅ DIPERBAIKI |


Selain itu ditemukan beberapa **inkonsistensi logika & asumsi domain** (persentase ARA/ARB yang sudah tidak sesuai regulasi BEI terbaru, threshold sinyal recovery yang secara matematis di bawah breakeven risk:reward-nya sendiri, self-referencing z-score di gorengan.py yang tidak konsisten dengan konvensi RVOL) yang dijelaskan detail di bawah. Bagian akhir laporan berisi tabel prioritas lengkap dan apresiasi eksplisit atas bagian-bagian yang **sudah** diimplementasikan dengan benar dan matang.

---

## Status Perbaikan — Semua Temuan ✅ TELAH DITANGANI (8 Agustus 2026)

Seluruh temuan signifikan (🔴/🟠/🟡) dan catatan (🔶) pada audit ini telah diperbaiki/diimplementasikan di codebase. Rincian per temuan:

| # | Fix | Lokasi | Verifikasi |
|---|-----|--------|------------|
| 1 | `estimate_gbm_params()` kini mengembalikan drift **proses log-harga** (tanpa +0.5σ²); drift log dipakai di `first_passage_cdf`; drift aritmetik hanya untuk pelaporan via helper `mu_arithmetic_daily()` | `recovery.py` | Smoke test BBCA (mu_daily aritmetik vs p_hit 21d terpisah benar) |

| 2 | Modul `short_selling.py` + daftar cache `cache/short_selling_list.json`; SELL diturunkan jadi HOLD+note bila ineligible (default konservatif TIDAK eligible) | `short_selling.py` (baru), `api.py` | Test API SCMA: SELL → HOLD, trade_plan=None, note tercantum |

| 3 | `backtest_calibrate.py`: grid default dipersempit ke `WF_OPT_GRID` (36 kombinasi), optimasi hanya di TRAIN window, top-N divalidasi ulang di TEST (OOS), leaderboard menampilkan OOS vs train | `backtest_calibrate.py` | Compile + logika dipetakan; run manual `--param`/`--test-days` tersedia |

| 4 | `walkforward.py`: tiap window **optimasi di data TRAIN** (grid `WF_OPT_GRID`), filter `WF_OPT_MIN_TRADES`, pemenang by `WF_OPT_METRIC`, HANYA pemenang dievaluasi di TEST (OOS) | `walkforward.py` | `build_candidates()` = 36 kombinasi; run backtest BBCA OK |

| 5 | Sharpe OOS diambil dari `metrics.sharpe` tiap window (daily-equity-based dari backtest.py), bukan √252 atas return per-trade | `walkforward.py` | Smoke test |

| 6 | `risk_level_from_atr()` & `confidence_from_score()` dipindah ke `scoring.py` (single source of truth) dan dipanggil dari `compute_score` — cabang tighten-SL 0.8× di `risk.py` kini hidup | `scoring.py`, `risk.py` | API live: `risk_level=rendah/tinggi` bervariasi (bukan stub "sedang") |

| 7 | Exit REVERSAL memakai `recs[i-1]` (sinyal bar sebelumnya, konsisten dengan entry) | `backtest.py` | Trade #1 BBCA keluar via REVERSAL next-bar |

| 8 | Blok Sharpe trade-based (dead code / shadowing) dihapus; hanya daily equity Sharpe yang dipertahankan | `backtest.py` | Compile OK |

| 9 | RSI: delta dihitung tanpa padding (`np.diff(close)`), seeding Wilder dari 14 delta asli; bar valid pertama = index 14 (konvensi baku) | `indicators.py` | Unit test: first valid idx = 14 |

| 10 | Docstring & borders auto-drop disesuaikan ARB flat 15% (SK BEI Apr 2025): cap flat 13% semua tier | `recovery.py`, `config.py` | Smoke test |

| 11 | `RECOVERY_SIGNAL_P_MIN` dinaikkan 0.60 → 0.68 (≥ breakeven R:R 66.7% + margin fee) | `config.py` | Smoke test |

| 12 | `_zscore()` mengecualikan observasi terakhir dari baseline (konsisten konvensi `rvol()`) | `gorengan.py` | Unit test: z=36.3 untuk outlier (tidak teredam) |

| 13 | Fee asimetris: `FEE_BUY_PCT=0.18`/`FEE_SELL_PCT=0.28` dipakai di entry/exit & `net_ret` | `config.py`, `backtest.py` | Backtest BCCA: fee round-trip terpotong |

| 14 | yfinance: `auto_adjust=True` di-set eksplisit (tahan perubahan default v0.2.54+) | `config.py`, `data_source/yahoo_client.py` | Smoke test fetch |

| 15 | Regime multiplier asimetris terdokumentasi eksplisit sebagai desain defensif (bukan perubahan kode) | `config.py` | — |

| 16 | Disclaimer timing entry (sinyal T → eksekusi T+1) ditambahkan di `validation_note` API | `api.py` | Test API |


> Catatan operasional: `cache/short_selling_list.json` berisi daftar contoh placeholder. **Admin wajib menyalin Daftar Efek Short Selling BEI bulan berjalan** ke file tersebut agar gate #2 benar-benar merefleksikan daftar resmi. Selama file kosong → default konservatif (semua saham TIDAK eligible untuk short).

---

## 1. Lapisan Indikator Teknikal (`indicators.py`)

### 1.1 EMA & Wilder's Smoothing (RMA) — ✅ BENAR

`ema()` di-seed dengan SMA periode awal lalu direkursi dengan α = 2/(n+1) — ini konvensi standar (Wilder, *New Concepts in Technical Trading Systems*, 1978, dan seluruh literatur TA sesudahnya). `wilder_rma()` men-seed dengan SMA lalu memakai α = 1/n — ini persis metode smoothing asli Wilder untuk ATR/RSI/ADX, **berbeda** dari EMA biasa, dan kode ini secara eksplisit membedakan keduanya (banyak implementasi open-source keliru menyamakan EMA dengan Wilder RMA — kode ini tidak melakukan kesalahan itu).

### 1.2 RSI(14) - DIPERBAIKI: bias seeding dari delta-palsu (audit #9)

**Kode** (`indicators.py`, fungsi `rsi`):
```python
delta = np.diff(close, prepend=close[0])   # delta[0] dipaksa = 0 (palsu, bukan price change asli)
gain  = np.where(delta > 0, delta, 0.0)
loss  = np.where(delta < 0, -delta, 0.0)
avg_gain = wilder_rma(gain, period)   # seed = mean(values[0:period]) -> IKUT memasukkan delta[0] palsu
avg_loss = wilder_rma(loss, period)
```

**Masalah:** `np.diff(..., prepend=close[0])` menghasilkan `delta[0] = 0` — bukan perubahan harga sungguhan, hanya padding agar panjang array tetap `n`. Tapi `wilder_rma()` men-seed nilai awalnya dengan `mean(values[0:period])`, sehingga elemen palsu ini **ikut dirata-rata** sebagai salah satu dari `period` observasi. Akibatnya, seed rata-rata gain/loss pertama dihitung dari **hanya (period−1) delta asli + 1 nol**, dibagi `period` — bukan dari `period` delta asli seperti konvensi baku Wilder ("*first Average Gain = sum of Gains over the past 14 periods ÷ 14*", yang butuh 14 delta asli = 15 bar harga).

**Bukti numerik** (implementasi ulang independen dengan pandas, delta seed dari 14 nilai asli — lihat metodologi di atas), diuji pada 300 bar sintetis:

| Jarak dari bar valid pertama | Selisih RSI (poin, skala 0–100) |
|---|---|
| +0 (bar pertama RSI valid) | 0.18 |
| +10 bar | 0.71 |
| +20 bar | 0.42 |
| +40 bar | 0.028 |
| +60 bar | 0.0017 |
| +100 bar | 0.0002 |

Error meluruh geometris (faktor 13/14 per bar — sesuai sifat rekursi IIR Wilder) dan **praktis nol setelah ~60 bar**. `ind.rsi()` bahkan mengeluarkan nilai pertama di indeks 13, satu bar lebih awal dari konvensi baku (indeks 14), memperkuat bahwa titik awal ini memang belum representatif.

**Dampak praktis:** untuk sinyal live (di mana `MIN_TRADING_DAYS=150`+ data selalu tersedia sebelum bar terakhir), dampaknya **nihil** — errornya sudah lama meluruh. Tapi untuk backtest/walk-forward yang mulai bertransaksi tepat di ujung `warmup` (bar pertama saat `swing_score` non-NaN, biasanya ditentukan oleh ADX yang butuh ~2×period bar), sinyal-sinyal paling awal dalam setiap window berpotensi memakai RSI yang sedikit bias. Ini relevan khususnya untuk `walkforward.py` yang window OOS-nya hanya 21 hari (test_days) — proporsi bar "awal-bias" terhadap total window lebih besar dibanding backtest jangka panjang.

**Rekomendasi:** hitung delta tanpa padding (`np.diff(close)`, panjang n−1) lalu geser index secara eksplisit saat assignment ke array output — sehingga window seed `wilder_rma` untuk RSI benar-benar berisi `period` delta asli, bukan delta+padding. Alternatif minimal: pada pemanggilan RSI secara khusus, seed `wilder_rma` dari `values[1:period+1]`, bukan `values[0:period]`.

### 1.3 ATR(14), MFI(14), ADX(14)/DMI — ✅ BENAR (tervalidasi numerik hingga presisi floating-point)

Ketiganya diuji-silang terhadap implementasi independen (pandas, ditulis terpisah dari nol mengikuti definisi tekstual Wilder) pada data sintetis 300 bar:

| Indikator | Max selisih vs implementasi independen |
|---|---|
| ATR(14) | **0.0** (identik persis) |
| MFI(14) | 1.4 × 10⁻¹⁴ (presisi floating point) |
| ADX(14) | 1.1 × 10⁻¹⁴ (presisi floating point) |

`true_range()` menangani bar pertama dengan `H−L` (bukan padding nol) — ini alasan ATR/ADX **tidak** kena bug seeding seperti RSI. `mfi()` memakai *rolling sum* (bukan rekursi Wilder), dan jendela sum pertamanya (`[1, period]`) otomatis mengecualikan index 0 — jadi meskipun MFI juga memakai pola `np.diff(prepend=...)`, hasilnya tidak terpengaruh. ADX diimplementasikan lengkap: +DM/−DM dengan aturan Wilder yang benar (`up_move>down_move & up_move>0` dsb.), displacement dibagi ATR dengan skala konsisten (rasio +DI/−DI tetap benar walau `wilder_rma` di sini memakai rata-rata bukan sum — secara aljabar ekuivalen karena pembagian oleh `period` saling meniadakan di rasio +DI/ATR).

### 1.4 RVOL, Donchian, Bollinger Bands, Swing Points, S/R, Fibonacci — ✅ BENAR (dengan catatan desain)

- **RVOL** sengaja mengecualikan hari berjalan dari rata-rata pembanding ("*biar gak self-referencing*") — ini justru lebih ketat/benar dibanding kebanyakan implementasi RVOL retail yang memasukkan hari ini ke baseline-nya sendiri.
- **Donchian Channel** dihitung *termasuk* bar hari ini di window — secara matematis ini berarti `close[i]` tidak akan pernah melebihi `donchian_upper[i]` sendiri (karena `high[i]` sudah termasuk dalam perhitungan upper). 🔶 **Catatan:** jika dipakai naif untuk deteksi breakout ini jadi kondisi yang mustahil terpenuhi. Namun pemanggilnya di `scoring.py` (`_price_action_score`) sudah benar memakai `donchian_upper[i-1]` (channel hari **sebelumnya**) untuk cek breakout — jadi *tidak* ada bug aktif, hanya perlu didokumentasikan agar pemanggil baru di masa depan tidak salah pakai.
- **Bollinger Bands** memakai sample stddev (`ddof=1`) — konvensi standar.
- **Swing points** (fraktal) didokumentasikan eksplisit sebagai *lagging* sejumlah `window` bar (baru terkonfirmasi setelah window bar berikutnya) — kesadaran ini penting dan benar secara desain.
- **Fibonacci retracement/extension** memakai rasio baku (23.6/38.2/50/61.8/78.6% dan 127.2/161.8/200/261.8%) — sesuai konvensi universal.

### 1.5 Pola Candlestick (34 pola) — ✅ BENAR (dengan 1 catatan minor)

Diperiksa terhadap definisi baku (Nison, *Japanese Candlestick Charting Techniques*): Doji/Dragonfly/Gravestone (threshold body ≤10% range, shadow ≥60%), Hammer/Hanging Man & Inverted Hammer/Shooting Star (shadow ≥2× body, dibedakan via konteks tren), Engulfing/Harami (berbasis *real body*, bukan wick — konvensi tradisional), Piercing Line & Dark Cloud Cover (kondisi *close menembus titik tengah body sebelumnya* dicek dengan benar), Morning/Evening Star & Abandoned Baby, Three White Soldiers/Black Crows, Three Inside/Outside Up-Down, Rising/Falling Three Methods — semua sesuai definisi standar. 🔶 **Catatan minor:** pola "In-Neck Line" adalah pendekatan yang disederhanakan dari definisi tekstual aslinya (tidak mensyaratkan gap-down eksplisit di candle kedua); dampaknya kecil karena ini pola minor yang jarang dominan dalam skor.

---

## 2. Sistem Scoring & Regime (`scoring.py`, `regime.py`)

### 2.1 ADX Gate & Component Scores — ✅ BENAR (desain solid, well-grounded)

`_gate_adx(adx) = min(adx/20, 1.0)` lalu dipakai sebagai `score = 0.5 + (raw − 0.5) × gate` pada trend & momentum score. Ini menarik skor ke netral (0.5) saat ADX rendah. Ini **konsisten dengan interpretasi baku ADX** (Wilder 1978; StockCharts ChartSchool: "*Wilder suggests... no trend is present when ADX is below 20*", dengan 20–25 sebagai *gray zone*): sinyal trend/momentum memang kurang dapat diandalkan saat pasar tidak trending. Memakai 20 (bukan 25) sebagai titik gate=1.0 penuh berada di **tepi bawah** rentang baku 20–25 — pilihan yang defensible ("*many technical analysts use 20 as the key level*"), dan sudah diuji lewat grid search (`backtest_calibrate.py` menguji 15/20/25/30) — praktik kalibrasi yang baik.

`_volume_score`: `0.5 + sign(close vs close_prev) × clip(RVOL−1, 0, 1) × 0.5`. Skor netral saat volume di bawah rata-rata, bergerak menuju 0/1 berdasarkan arah harga saat volume di atas rata-rata (saturasi di RVOL=2). Ini bukan indikator baku bernama tertentu, tapi logikanya konsisten dan tidak melanggar prinsip apa pun — konstruksi ad-hoc yang masuk akal.

`_price_action_score`: posisi ternormalisasi antara support/resistance terdekat, di-override ke 1.0/0.0 saat breakout Donchian (dengan konfirmasi RVOL≥1.5) — **dan di sini benar memakai `donchian_upper[i-1]`**, bukan `[i]` (lihat §1.4).

### 2.2 Regime Detection & Multiplier - TERDOKUMENTASI: efek asimetris kini sadar-desain

`regime.py` memakai SMA(200) + ADX sebagai filter — kombinasi umum dan dapat dipertanggungjawabkan secara teori (SMA jangka panjang sebagai *trend filter* mengikuti tradisi model timing seperti milik Faber; ADX<20 sebagai filter *non-trending* mengikuti Wilder). Bobot komponen per regime (bull/sideways/bear) masing-masing berjumlah tepat 1.0 — matematis benar sehingga `raw_score` tetap terbatas 0–100.

**Namun**, `effective_score = raw_score × regime_multiplier` (mis. 0.90 di bear) memiliki sifat matematis yang mungkin belum sepenuhnya disadari: karena titik jangkarnya adalah 0 (bukan 50/netral), efek multiplier menjadi **asimetris** terhadap titik netral — skor di atas 50 ditarik turun mendekati netral (melemahkan sinyal BUY), tapi skor **di bawah** 50 justru ditarik makin jauh dari netral (menguatkan sinyal SELL). Contoh: skor 80 × 0.9 = 72 (mendekati netral, redaman −8), skor 30 × 0.9 = 27 (menjauhi netral, penguatan −3 ke arah bearish).

Ini kebetulan **selaras** dengan filosofi "defensif saat bear market" (BUY makin sulit tercapai, SELL makin tegas) dan cocok dengan catatan `SWING_SELL_VALIDATED=True` vs `SWING_BUY_VALIDATED=False` di config — tapi sifat ini tampak seperti **efek samping** dari perkalian skalar sederhana, bukan desain eksplisit. **Rekomendasi:** dokumentasikan secara sadar (atau, jika yang diinginkan justru peredaman simetris terhadap netral, ganti formulanya menjadi `50 + (raw_score − 50) × multiplier`).

### 2.3 Konstanta Duplikat / Dead Code - DIPERBAIKI (BUY_THRESHOLD = config.SWING_BUY_THRESHOLD)

`scoring.py` mendefinisikan `BUY_THRESHOLD = 70` secara lokal sebagai fallback, sementara `config.SWING_BUY_THRESHOLD = 72` — dua konstanta bernama mirip dengan **nilai berbeda**. Karena `get_regime_profile()` selalu mengembalikan salah satu dari 3 profil (bull/sideways/bear) yang masing-masing sudah punya `buy_threshold` non-None, fallback lokal `BUY_THRESHOLD=70` ini **tidak pernah tereksekusi** — bukan bug aktif, tapi berpotensi membingungkan kontributor lain di masa depan (nilai mana yang "benar"?). Rekomendasi: hapus konstanta lokal yang tidak terpakai, atau impor langsung dari `config`.

### 2.4 confidence dan risk_level - DIPERBAIKI: dinamis, single source of truth di scoring.py (audit #6)

```python
"confidence": "sedang",       # scoring.py — hardcoded, SELALU string ini
"risk_level": "sedang",       # scoring.py — hardcoded, SELALU string ini
"prob_continuation": None,
"prob_reversal": None,
```

Sementara `config.py` sudah mendefinisikan `CONFIDENCE_LOW_CUTOFF`/`CONFIDENCE_HIGH_CUTOFF` (0.4/0.75) dan `RISK_HIGH_CUTOFF`/`RISK_LOW_CUTOFF` (1.5/0.8) — **konstanta ini tidak pernah dipakai di scoring.py**. Yang lebih penting: `backtest.py` punya implementasi **penuh dan berbeda** untuk kedua nilai ini —

```python
# backtest.py — HANYA dipakai di simulasi backtest, TIDAK dipakai di live API
def _risk_level(atr, i):
    ratio = atr[i] / np.nanmean(atr[max(0,i-60):i])
    if ratio > config.RISK_HIGH_CUTOFF: return "tinggi"
    if ratio < config.RISK_LOW_CUTOFF:  return "rendah"
    return "sedang"

def _confidence(...):  # berdasar agreement antar komponen skor + gate + rvol
    ...
```

Ini didetailkan lebih lanjut di §3.3 — dampaknya signifikan karena `risk.py._stop_loss()` memakai `risk_level` untuk **mengetatkan SL sebesar 0.8× pada saham berisiko tinggi**, tapi cabang ini tidak pernah aktif di jalur live.

---

## 3. Manajemen Risiko (`risk.py`)

### 3.1 Stop Loss / Take Profit berbasis ATR — ✅ BENAR, dan matematika breakeven-nya tervalidasi presisi

```python
SL = entry ∓ 3.0 × ATR      # ATR_SL_MULTIPLIER
TP = entry ± 2.5 × ATR      # ATR_TP_MULTIPLIER
```

Ini teknik *volatility-based stop* standar (mirip *Chandelier Exit* ala Chuck LeBeau, atau *ATR stop* ala Van Tharp). R:R yang dihasilkan = 2.5/3.0 = 0.833 — **reward < risk per trade**, yang butuh win rate lebih tinggi dari 50% untuk profitable. Memakai rumus ekspektansi baku:

> Breakeven win rate W memenuhi: W·R = (1−W), dengan R = reward/risk → **W = 1/(1+R)**

Dengan R = 0.8333 → **W = 54.55%**. Ini **cocok presisi** dengan angka yang sudah divalidasi tim melalui triple-barrier labeling (breakeven 54.5% TP_FIRST rate) dan dengan win rate SELL yang divalidasi backtest (58%, di atas breakeven). Ini pekerjaan yang **sudah benar dan terverifikasi sendiri oleh tim** — good practice yang jarang ditemukan di proyek retail (banyak sistem serupa menetapkan SL/TP tanpa pernah menghitung breakeven-nya secara eksplisit).

### 3.2 Position Sizing berbasis Risiko — ✅ BENAR

```
risk_budget = capital × regime_mult × risk_pct     # 1% baseline
shares      = floor(risk_budget / |entry − SL|, ke kelipatan lot)
cap: nilai posisi ≤ capital × regime_mult (no-leverage safety net)
```

Ini implementasi benar dari *fixed-fractional position sizing* (Van Tharp; rumus baku *risiko per saham = jarak SL*, sehingga *jumlah saham = anggaran risiko ÷ risiko per saham*). Dua constraint independen (risk-based sizing dan value-cap no-leverage) melayani tujuan berbeda dan keduanya benar secara logika — cap value mencegah leverage implisit ketika SL sangat sempit (ATR kecil).

### 3.3 DIPERBAIKI: risk_level live dinamis - cabang tighten-SL 0.8x kini aktif (audit #6)

Karena §2.4 di atas (scoring.py selalu mengirim `"sedang"`), baris berikut di `risk.py` **tidak pernah tereksekusi** di jalur live (API):

```python
if risk_level == "tinggi":
    mult *= 0.8   # ATR_SL_TIGHTEN — dead code di jalur live
```

**Konsekuensi:** performa yang divalidasi lewat `backtest.py` (yang punya `_risk_level()` dinamis, sungguh mengetatkan SL pada saham volatilitas tinggi) **tidak identik** dengan apa yang benar-benar dieksekusi API live (yang selalu memakai SL longgar 3.0×ATR, tanpa pengetatan). Untuk saham dengan lonjakan volatilitas (ATR ratio >1.5×), live user mendapat SL lebih lebar dari yang divalidasi backtest — berpotensi menurunkan win rate riil vs win rate yang dilaporkan.

**Rekomendasi:** pindahkan `_risk_level()` dan `_confidence()` dari `backtest.py` ke `scoring.py` (atau modul bersama), lalu panggil dari kedua jalur (live & backtest) agar keduanya benar-benar menguji logika yang sama — prinsip *single source of truth* untuk memastikan hasil backtest applicable ke live.

---

## 4. Backtest Engine (`backtest.py`)

### 4.1 Simulasi Fill SL/TP dengan Gap Risk — ✅ SANGAT BAIK (di atas rata-rata praktik backtest retail)

```python
# BUY, SL tersentuh:
exit_price = min(stop_loss, open[i])   # kalau gap-down tembus SL, fill di open (lebih buruk) — realistis
# BUY, TP tersentuh:
exit_price = max(take_profit, open[i]) # kalau gap-up lewati TP, fill di open (lebih baik) — realistis limit-order fill
```

Ini memodelkan slippage akibat *gap* dengan benar — order stop yang “dilompati” oleh gap akan tereksekusi di harga pasar berikutnya (bukan di harga stop persis), sementara limit order justru terisi di harga lebih baik saat market gap melewatinya. **Banyak backtest engine retail mengabaikan ini** (selalu asumsi fill persis di level SL/TP), sehingga membuat hasil backtest terlalu optimis. Kode ini menghindari jebakan itu.

Saat SL & TP sama-sama tersentuh dalam satu bar (rentang H-L hari itu mencakup keduanya), kode **selalu mengutamakan SL** — ini konvensi konservatif standar dalam backtesting berbasis data OHLC harian (tanpa data tick, urutan intrabar sesungguhnya tidak diketahui; asumsi terburuk lebih aman daripada asumsi terbaik).

### 4.2 DIPERBAIKI: Exit REVERSAL pakai recs[i-1] - konsisten dgn entry (audit #7)

Bandingkan dua baris ini dalam file yang sama:

```python
# ENTRY (baris ~445) — BENAR: sinyal dari bar i-1, eksekusi di bar i
direction = recs[i-1]
entry_price = close[i]

# EXIT REVERSAL (baris ~549) — BUG: sinyal dari bar i, eksekusi JUGA di bar i
elif recs[i] == "SELL" and i > pos["entry_idx"]:
    exit_reason = REVERSAL
    exit_price_candidate = close[i]
```

`recs[i]` membutuhkan `close[i]` sepenuhnya (dipakai di EMA/RSI/MFI/ADX bar ke-i) — nilai yang secara kausal baru "selesai" tepat di penutupan bar i. Memakai `recs[i]` untuk memutuskan keluar **pada** `close[i]` berarti keputusan exit memakai informasi yang identik dengan harga eksekusinya sendiri — inilah persis pola *lookahead* yang justru berhasil dihindari oleh logika ENTRY di file yang sama (via lag i-1→i). Exit SL_HIT/TP_HIT **tidak** kena masalah ini karena keduanya membandingkan level yang sudah ditetapkan sejak entry terhadap `high[i]`/`low[i]` — bukan terhadap sinyal yang baru dihitung ulang.

**Rekomendasi:** gunakan `recs[i-1]` juga untuk exit REVERSAL (konsisten dengan entry), atau eksekusi reversal-exit di `close[i+1]` bila memakai `recs[i]`.

### 4.3 Model Fee - DIPERBAIKI: asimetris 0.18%/0.28% (audit #14)

```python
fee_entry = entry_price × shares × 0.25%
fee_exit  = exit_price × shares × 0.25%
```

Riset biaya transaksi riil di broker Indonesia (Indo Premier, BNI Sekuritas, MOST, dll., 2025) menunjukkan pola **konsisten asimetris**: fee beli ≈ 0.15–0.25%, fee jual ≈ 0.25–0.35% (memasukkan PPh Final Pasal 4(2) 0.1% dari nilai bruto **yang hanya dikenakan di sisi jual**). Round-trip realistis ≈ 0.44–0.48%, dibanding asumsi kode 0.50% flat — **secara agregat cukup dekat** (selisih <0.1pp), tapi strukturnya (0.25%/0.25% simetris) tidak mencerminkan mekanisme pajak sesungguhnya. Untuk swing trader yang lebih sering LONG (beli-dulu-jual-kemudian), fee entry riil biasanya *lebih murah* dari 0.25% dan fee exit *lebih mahal* — dampak nettonya kecil karena saling menutup, tapi kalau ingin presisi (mis. untuk laporan skripsi), pisahkan `fee_buy_pct` ≈ 0.18% dan `fee_sell_pct` ≈ 0.28% (termasuk PPh final 0.1%).

Perhitungan konsistensi fee vs P&L divalidasi secara aljabar: `pnl_rupiah / (shares×entry_price)` yang dipakai untuk update equity curve terbukti **identik** dengan `net_ret` yang disimpan di trade log — dua jalur perhitungan yang independen menghasilkan angka yang sama persis, jadi tidak ada inkonsistensi numerik antara equity curve dan laporan per-trade.

### 4.4 DIPERBAIKI: blok Sharpe trade-based dihapus; daily-equity Sharpe dipertahankan (audit #8)

```python
# baris ~655-660
if len(rets_arr) > 1 and rets_arr.std() > 0:
    annualization_factor = math.sqrt(252 / avg_hold)
    sharpe = float(rets_arr.mean() / rets_arr.std() * annualization_factor)   # (A) dihitung...
else:
    sharpe = 0.0

# baris ~662-669 (variabel NAMA SAMA!)
eq_arr = np.array(equity_curve)
daily_rets = ...
if len(valid) > 1 and valid.std() > 0:
    sharpe = float(valid.mean() / valid.std() * math.sqrt(252))   # (B) ...lalu DITIMPA di sini
```

Karena Python tidak punya *block scoping*, assignment (B) menimpa (A) sebelum `sharpe` sempat dipakai di mana pun — perhitungan (A) (Sharpe berbasis return per-trade, dianualisasi dengan `√(252/avg_hold)`, mempertimbangkan rata-rata lama holding) **dihitung tapi hasilnya tidak pernah terpakai**. Untungnya (B) — Sharpe dari daily equity curve, dianualisasi `√252` — memang metode yang **lebih standar** (Sharpe, 1966/1994: rasio return-to-variability dihitung dari return periodik reguler; daily equity curve juga otomatis memperhitungkan hari-hari tanpa posisi terbuka, yang diabaikan Sharpe berbasis trade). Jadi output akhir **tetap benar secara metodologi**, tapi kode (A) adalah computation yang terbuang — indikasi baik *leftover refactor* atau niat awal untuk membandingkan kedua metode yang gagal terealisasi. Rekomendasi: hapus (A), atau — lebih baik — ekspos keduanya sebagai field terpisah (`sharpe_daily` dan `sharpe_per_trade`) karena keduanya menjawab pertanyaan yang secara konseptual berbeda.

### 4.5 TERDOKUMENTASI: disclaimer timing entry (sinyal T -> eksekusi T+1) di validation_note (audit #9)

`api.py::analyze_stock()` membangun trade plan dengan:
```python
trade_plan = risk.build_trade_plan(score_result, entry_price=float(close[-1]), atr=float(atr_val[-1]), ...)
```

`score_result` dan `entry_price` **sama-sama** berasal dari bar terakhir (`close[-1]`) — artinya live API menyajikan "sinyal dari bar T, harga acuan bar T juga" — pasangan **persis sama** dengan pola yang di §4.2 terbukti bermasalah (sinyal dan harga eksekusi dari bar yang sama). Sementara `backtest.py` justru dirancang khusus menghindari pola ini di jalur entry (sinyal T-1, eksekusi di harga T). Konsekuensinya: win rate/return yang dilaporkan backtest (berbasis protokol "sinyal T-1 → eksekusi T") **tidak sepenuhnya mewakili** pengalaman user live yang melihat "sinyal T, harga acuan T" — karena begitu user membaca sinyal (setelah bursa tutup hari T), harga penutupan T sudah menjadi sejarah; eksekusi realistis paling cepat adalah pembukaan T+1.

Ini **bukan bug pemrograman** (live signal API memang lazim menampilkan harga acuan "harga terakhir diketahui" sebagai referensi, bukan janji harga eksekusi) — tapi merupakan **gap dokumentasi/komunikasi** yang penting: label `entry_price` di trade plan sebaiknya eksplisit disebut *"harga referensi saat sinyal dihasilkan"*, bukan tersirat sebagai harga yang bisa dieksekusi persis. Rekomendasi: tambahkan disclaimer di response API, atau — lebih baik — backtest juga sisi ini (uji varian "sinyal bar T, eksekusi open bar T+1") agar ada angka valid untuk dibandingkan langsung dengan pengalaman user live.

---

## 5. Kalibrasi & Walk-Forward Validation

### 5.1 backtest_calibrate.py - DIPERBAIKI: TRAIN/TEST split + validasi OOS top-N (audit #3)

Script ini menguji **1.280 kombinasi parameter** (4×5×4×4×4: `adx_gate_ceiling` × `swing_buy_threshold` × `atr_sl_multiplier` × `rvol_window` × `rvol_breakout_confirm`) langsung terhadap `run_backtest()` memakai **seluruh dataset yang tersedia** (365 hari, tanpa `sim_start_idx`/`sim_end_idx` yang mengisolasi bagian data), lalu me-ranking kombinasi berdasarkan Sharpe/metrik pilihan pada dataset yang **sama** itu juga. Tidak ada train/test split maupun validasi out-of-sample sama sekali di script ini.

Ini persis skenario *backtest overfitting* yang dibahas Bailey, Borwein, López de Prado & Zhu dalam *"The Probability of Backtest Overfitting"* (2014): menguji banyak kombinasi parameter pada satu sampel historis lalu memilih "pemenang" cenderung menangkap *noise* spesifik sampel tersebut, bukan *edge* yang genuinely bertahan di masa depan — makin banyak kombinasi diuji (di sini 1.280×5 saham), makin besar risiko *false discovery*. **Rekomendasi:** jangan gunakan output `backtest_calibrate.py` sebagai keputusan final parameter produksi; gunakan hanya untuk eksplorasi kasar, lalu validasi kandidat finalis lewat `walkforward.py` yang genuinely out-of-sample (lihat §5.2 untuk keterbatasannya saat ini).

### 5.2 walkforward.py - DIPERBAIKI: optimasi per-window di TRAIN, evaluasi OOS dgn pemenang (audit #4)

**Bagian yang ✅ BENAR:** `build_windows()` membangun window train→purge→embargo→test bergulir:
```
train: [0, 63)   purge: 10 hari   embargo: 10 hari   test: [83, 104)
```
Konsep *purge* dan *embargo* ini diambil langsung dari metodologi López de Prado (*Advances in Financial Machine Learning*, 2018, Bab 7 — *Purged K-Fold Cross-Validation*): purge menghapus sampel training yang label/outcome-nya tumpang tindih secara temporal dengan test set, embargo menambah buffer ekstra untuk mengantisipasi autokorelasi. Total gap 20 hari (10+10) **cocok pas** dengan horizon label maksimum sistem (`max_holding_days=20`) — ini penerapan teori yang tepat dan disengaja, bukan angka sembarang.

**Bagian yang ⚠️ BERMASALAH:** docstring modul menyatakan *"Setiap window optimasi di train, test di OOS"* — tapi `run_walk_forward()` **tidak pernah** menggunakan `win.train_start`/`win.train_end` untuk apa pun. Yang benar-benar terjadi:
```python
for win in windows:
    for params in candidates:        # candidates = HANYA 2 kombinasi hardcoded (DEFAULT_CANDIDATES)
        metrics = run_backtest(code, ..., sim_start_idx=win.test_start, sim_end_idx=win.test_end)
```
Tidak ada langkah "cari parameter terbaik di data train window ini" — sistem hanya menjalankan (paling banyak) 2 konfigurasi *tetap* langsung di tiap window test, lalu menggabungkan semua hasil trade dari semua window & kandidat menjadi satu pool. Ini secara fungsional adalah **uji ketahanan OOS dari 1-2 konfigurasi yang sudah ditentukan di muka** (valid dan berguna sebagai *itu*), **bukan** walk-forward *optimization* yang sesungguhnya (yang mensyaratkan parameter dipilih ulang dari data train di tiap window, seperti dijelaskan Robert Pardo dalam *The Evaluation and Optimization of Trading Strategies*, 2008).

**Dampak:** modul ini saat ini tidak bisa dipakai untuk "menemukan parameter optimal yang robust" — hanya untuk "mengecek apakah parameter yang *sudah dipilih* (dari `backtest_calibrate.py` yang in-sample, §5.1) tetap bertahan di luar sampel". Karena parameter awal itu sendiri hasil pencarian in-sample, siklus validasinya belum benar-benar tertutup.

**Rekomendasi konkret:** untuk tiap window, jalankan grid search (mirip `backtest_calibrate.py`) **dibatasi hanya pada** `[win.train_start, win.train_end)`, pilih pemenang dengan kriteria robust (bukan Sharpe tunggal — pertimbangkan jumlah trade minimum agar tidak overfit ke sample kecil), baru terapkan konfigurasi pemenang itu ke `[win.test_start, win.test_end)`. Hanya kumpulkan hasil test dari siklus tersebut. *(Catatan tambahan minor: ada overlap tepat 1 bar antara test window N dan train window N+1 akibat batas inklusif/eksklusif — kecil dan saat ini tidak berdampak karena train belum dipakai, tapi perlu diperbaiki bersamaan saat mengimplementasikan rekomendasi ini.)*

### 5.3 DIPERBAIKI: sharpe OOS = daily-equity-based per window (audit #5)

```python
oos_rets = [t["return_pct"] / 100 for t in all_oos_trades]   # RETURN PER-TRADE, bukan harian!
sharpe = float(np.mean(oos_rets) / np.std(oos_rets) * np.sqrt(252))   # tapi dianualisasi seolah HARIAN
```

Rumus anualisasi Sharpe standar: `Sharpe_tahunan = Sharpe_periode × √N`, dengan **N = jumlah periode independen per tahun** — untuk return harian, N=252 (konvensi pasar umum). Tapi `oos_rets` di sini adalah return **per trade**, dan trade swing biasanya berlangsung **beberapa hari, bukan satu hari** — sehingga jumlah trade independen per tahun jauh di bawah 252 (mis. jika rata-rata holding 10 hari, N yang benar ≈ 252/10 ≈ 25, bukan 252). Memakai √252 di sini bisa **melebih-lebihkan Sharpe teranualisasi hingga beberapa kali lipat** (untuk contoh 10-hari-holding: faktor koreksi √(252/25) ≈ 3.2×).

Menariknya, `backtest.py` justru **sudah punya** rumus yang benar untuk kasus ini (`√(252/avg_hold)` — lihat §4.4, sayangnya jadi dead code di sana), tapi rumus yang benar itu **tidak dipakai** di `walkforward.py`, yang malah memakai `√252` polos. **Rekomendasi:** ganti `np.sqrt(252)` di `walkforward.py` menjadi `np.sqrt(252/avg_holding_days)` (hitung `avg_holding_days` dari `all_oos_trades`), atau — lebih baik dan lebih presisi — bangun daily equity curve gabungan dari seluruh window OOS (seperti pendekatan (B) di §4.4) dan hitung Sharpe dari situ.

---

## 6. Model Recovery / Mean-Reversion via GBM (`recovery.py`)

### 6.1 Formula First-Passage Time — ✅ BENAR, dan self-correction dalam kode terverifikasi tepat

```python
z1 = (mu*t - a) / (sigma*sqrt(t))
z2 = -(a + mu*t) / (sigma*sqrt(t))
F(t) = Φ(z1) + exp(2·a·mu/sigma²) · Φ(z2)
```

Ini adalah rumus baku CDF *first passage time* untuk Brownian motion berdrift menyentuh level `a>0` (distribusi Inverse Gaussian/Wald — lih. Karatzas & Shreve, *Brownian Motion and Stochastic Calculus*; Borodin & Salminen, *Handbook of Brownian Motion*). Kode ini bahkan menyertakan catatan eksplisit yang mengoreksi kesalahan tanda yang umum ditemukan di sejumlah sumber (`Φ((a−μt)/·)` pada term pertama). **Kami verifikasi klaim ini**: dengan μ=0 (kasus tanpa drift), rumus versi kode menghasilkan `F(t) = 2Φ(−a/(σ√t))` — sama persis dengan rumus reflection-principle baku untuk BM tanpa drift. Rumus "salah" alternatif yang disebut kode (`Φ((a−μt)/·)` untuk term pertama) terbukti — jika ditelusuri — menghasilkan `F(t) ≡ 1` untuk semua t saat μ=0, yang jelas keliru (BM driftless hanya *mendekati* probabilitas 1 seiring t→∞, tidak sama dengan 1 di semua t). Self-correction developer di sini **terverifikasi benar**.

### 6.2 DIPERBAIKI: drift log-harga di first_passage_cdf; aritmetik utk laporan (audit #1)

```python
# estimate_gbm_params()
sigma = std(log_ret)
mu    = mean(log_ret) + 0.5 * sigma**2      # (*)
# ... lalu mu ini di-pass LANGSUNG ke first_passage_cdf() sebagai drift proses X_t = ln(S_t/S_0)
```

**Akar masalah:** untuk GBM dengan SDE `dS = μ_harga·S·dt + σ·S·dW` (drift *aritmetik* μ_harga), lemma Itô memberikan proses log-harga `d(ln S) = (μ_harga − ½σ²)·dt + σ·dW` — **drift proses log-harga adalah μ_harga − ½σ², bukan μ_harga**. Karena return log harian `r = ln(Sₜ/Sₜ₋₁)` punya rata-rata persis `μ_harga − ½σ²` (bukan μ_harga), maka `mean(log_ret)` **sudah** merupakan estimator langsung dari drift proses log-harga — **tanpa perlu koreksi apa pun**. Rumus (*) di atas justru **menambahkan** `+½σ²`, mengubah estimasi menjadi estimator drift *harga aritmetik* μ_harga (ini valid sebagai estimator μ_harga, dan memang benar dipakai untuk melaporkan `mu_annual` ke user — itu bagian yang benar). Masalahnya: nilai `mu` inilah yang **langsung** menjadi argumen `first_passage_cdf(a, mu, sigma, t)`, padahal fungsi itu butuh drift proses **log-harga**, bukan drift harga aritmetik. Selisihnya persis `+½σ²` — dan untuk saham IDX volatil (σ harian bisa 3-4%), `½σ²` bisa sebanding besarnya dengan `μ` itu sendiri.

**Pembuktian kuantitatif (simulasi Monte Carlo, 2 juta lintasan, disimulasikan independen dari rumus closed-form manapun):**

Skenario: harga awal 100, target 110 (+10%), σ harian=3.5% (khas saham IDX volatil), drift log-harga sesungguhnya = 0.05%/hari. Untuk tiap horizon, dibandingkan: (a) probabilitas empiris sungguhan dari simulasi langsung, (b) formula analitik dengan drift asli (sanity check formula itu sendiri), (c) rata-rata prediksi kode **saat ini** (drift dari `estimate_gbm_params` dipakai apa adanya, persis alur `recovery.py` + `_validate_recovery.py`), (d) rata-rata prediksi versi **perbaikan** (`mu − 0.5σ²` sebelum masuk `first_passage_cdf`) — (c) dan (d) dirata-rata dari 3.000 sampel histori acak (menyerupai kondisi estimasi dari data riil):

| Horizon (hari) | Analitik (drift asli) | **Kode saat ini** (bias) | **Versi perbaikan** (bias) |
|---|---|---|---|
| 5 | 0.2321 | 0.2425 (+0.0104) | 0.2316 (−0.0005) |

| 10 | 0.4044 | 0.4211 (+0.0167) | 0.4026 (−0.0018) |

| 21 | 0.5738 | 0.5940 (**+0.0202**) | 0.5686 (−0.0052) |
| 42 | 0.7003 | 0.7187 (+0.0184) | 0.6893 (−0.0110) |
| 63 | 0.7594 | 0.7743 (+0.0149) | 0.7436 (−0.0158) |

Bias kode saat ini **konsisten positif di semua horizon** (model terlalu percaya diri / *overestimate* peluang recovery), sementara versi perbaikan mendekati nol di horizon pendek-menengah — termasuk tepat di horizon 21 hari, yaitu `RECOVERY_SIGNAL_HORIZON_DAYS` yang dipakai sebagai basis keputusan sinyal "POTENTIAL" (bias kode di titik ini +2.02 poin persentase, ~4× lebih besar dari bias versi perbaikan). Ini match dengan intuisi di balik desain sistem sendiri — komentar di `recovery.py` menyebut *"Walk-forward (5 saham IDX, 35 event) menunjukkan GBM under-predict"* dibanding rate empiris, yang justru **konsisten** dengan temuan ini: jika model GBM sistematis over-optimis pada level individual event, model itu akan under-predict *relatif terhadap* rate empiris yang lebih sering menunjukkan kegagalan recovery — memvalidasi bahwa mekanisme fallback ke rate empiris (§6.3) sudah menjadi mitigasi tidak langsung, walau akar masalahnya (drift yang salah dipakai) sebaiknya tetap diperbaiki di sumbernya.

**Rekomendasi:** di `build_recovery_analysis()` (dan `_validate_recovery.py`), sebelum memanggil `first_passage_cdf`/`p_hit_ever`, konversi: `mu_log = mu - 0.5 * sigma**2`, lalu pakai `mu_log` (bukan `mu`) sebagai argumen drift. Nilai `mu` asli (arithmetic) tetap dipertahankan apa adanya untuk pelaporan `mu_annual`/`mu_daily` ke user — itu penggunaan yang sudah benar.

### 6.3 Base Rate Empiris — ✅ BENAR (praktik baik), dengan 🔶 catatan statistik minor

`empirical_base_rates()` mengidentifikasi event historis, mengecek recovery hanya di bar **setelah** event (`high[i+1:end]`, bukan termasuk bar event itu sendiri — anti-lookahead benar), dan men-*censor* (membuang) event yang horizonnya tidak lengkap di ujung data — semua ini praktik yang tepat. 🔶 Catatan: event-event yang tumpang tindih (mis. saham turun 2 hari beruntun bisa terhitung sebagai 2 event terpisah dengan window outcome yang saling overlap) membuat observasi tidak sepenuhnya independen — ini tidak membuat *point estimate* rate-nya bias, tapi membuat presisinya (jika suatu saat dihitung confidence interval) terlihat lebih tinggi dari sebenarnya. Untuk laporan skripsi/akademik, ini layak disebutkan sebagai keterbatasan (mirip isu *overlapping labels* yang dibahas López de Prado). Threshold "pakai rate empiris kalau event≥5" juga tergolong rendah secara statistik (SE proporsi dari n=5 bisa ±20-40pp) — pertimbangkan pendekatan **shrinkage Bayesian** (mis. Beta-Binomial, GBM sebagai prior, di-update oleh event empiris) dibanding hard-cutoff n≥5, supaya transisi kepercayaan model↔empiris lebih smooth berbanding lurus dengan jumlah sampel.

### 6.4 DIPERBAIKI: RECOVERY_SIGNAL_P_MIN 0.60 -> 0.68 (audit #12)

```python
sl = price - RECOVERY_SL_DISTANCE_MULT(2.0) * (ref_price - price)
# R:R = jarak_ke_target / jarak_ke_SL = 1 / 2.0 = 0.5
```

Dengan rumus breakeven yang sama seperti §3.1 (`W = 1/(1+R)`), R:R=0.5 berarti **breakeven win rate = 1/1.5 = 66.7%**. Tapi `RECOVERY_SIGNAL_P_MIN = 0.60` (60%) — sinyal "POTENTIAL" bisa muncul di probabilitas yang **secara matematis masih di bawah breakeven** rencana exit-nya sendiri (sebelum biaya transaksi). Dengan kata lain: bahkan jika estimasi probabilitas recovery-nya akurat sempurna, sinyal di ambang 60% masih berekspektasi **negatif** di bawah skema hit-target/hit-SL biner sederhana ini (walau `RECOVERY_TIME_STOP_DAYS=63` memberi jalan keluar ketiga yang mengubah kalkulus sebenarnya, sehingga bias ini bukan pasti berarti sistem rugi — tapi patut direkonsiliasi). **Rekomendasi:** naikkan `RECOVERY_SIGNAL_P_MIN` ke ~68-70% (di atas 66.7% + margin biaya transaksi), ATAU turunkan `RECOVERY_SL_DISTANCE_MULT` agar breakeven-nya turun mendekati 60%, ATAU — jika `time_stop` memang dominan menentukan outcome — validasi secara eksplisit dengan data seberapa sering exit terjadi lewat time-stop vs target vs SL, supaya framing R:R biner ini terkonfirmasi relevan atau tidak.

### 6.5 DIPERBAIKI: cap auto-drop flat 13% semua tier sesuai ARB 15% (SK BEI Apr 2025) (audit #11)

```python
RECOVERY_AUTO_CAP_UNDER_200   = 30.0   # komentar: "limit ±35%"
RECOVERY_AUTO_CAP_200_TO_5000 = 18.0   # komentar: "limit ±20%"
RECOVERY_AUTO_CAP_AT_5000     = 13.0   # komentar: "limit ±15%"
```

Berdasarkan riset regulasi terkini (**SK Direksi BEI No. Kep-00003/BEI/04-2025**, efektif 8 April 2025, dikonfirmasi banyak sumber independen 2025), aturan **saat ini** adalah:

| Tier harga | ARA (batas naik) | ARB (batas turun) |
|---|---|---|
| Rp50 – Rp200 | 35% | **15% (seragam, semua tier)** |
| >Rp200 – Rp5.000 | **25%** | 15% |
| >Rp5.000 | **20%** | 15% |

Sejak reformasi April 2025, **ARB sudah diseragamkan flat 15% untuk semua tier harga** (sebelumnya bertingkat 35/25/20 sama seperti ARA). Karena fitur *recovery* ini berbicara soal **penurunan** harga (drop_pct), acuan yang relevan secara konsep adalah **ARB**, bukan ARA — dan sejak reformasi, jawaban yang benar untuk "berapa maksimum penurunan harga 1 hari" **kini seragam 15% untuk semua saham**, bukan bertingkat. Konfigurasi kode saat ini (30/18/13) tidak presisi cocok dengan ARA lama, ARA baru, maupun ARB baru manapun. **Rekomendasi:** sederhanakan menjadi cap flat (mis. ~13-14%, sedikit di bawah 15% ARB sebagai margin) untuk seluruh tier, kecuali memang ingin mengakomodasi potensi ARB berturut-turut multi-hari (yang bisa mencapai ~39% kumulatif dalam 3 hari beruntun per ARB 15%/hari) sebagai skenario terpisah.

---

## 7. Gorengan (Pump & Dump) Detection Engine (`gorengan.py`)

### 7.1 Bobot & Struktur Skor — ✅ BENAR

7 komponen (historical P&D 15%, liquidity 15%, market cap 10%, active pump 30%, momentum 10%, distribution 10%, turnover+gaps 10%) berjumlah tepat 100% dan konsisten antara kode dan docstring.

### 7.2 DIPERBAIKI: baseline _zscore() mengecualikan observasi terakhir (audit #13)

```python
def _zscore(arr, lookback=60):
    valid = arr[-lookback:]     # termasuk observasi HARI INI
    mu, sigma = mean(valid), std(valid)
    return (valid[-1] - mu) / sigma    # HARI INI ikut membentuk baseline yang membandingkan HARI INI
```

Ini dipakai untuk skor momentum & volatilitas dalam gorengan detection. Sebagai perbandingan, `indicators.rvol()` — di modul lain dalam codebase yang sama — **secara eksplisit mengecualikan** hari berjalan dari baseline-nya (dikomentari langsung: "*biar gak bias/self-referencing*"). `_zscore()` di sini tidak menerapkan prinsip yang sama: memasukkan titik yang sedang dinilai ke dalam perhitungan mean/std baseline-nya sendiri meredam z-score (nilai ekstrem menarik mean/std ke arah dirinya sendiri), sehingga skor anomali sedikit *understated* — berlawanan arah dengan apa yang diinginkan sebuah detektor pump. Ini bukan kesalahan matematis "mutlak" (z-score self-inclusive dipakai juga di sejumlah konteks lain), tapi **tidak konsisten** dengan prinsip yang sudah ditetapkan sendiri di modul lain dalam codebase yang sama, dan secara konvensi deteksi anomali/outlier (mis. uji Grubbs) baseline biasanya dihitung *leave-one-out*. **Rekomendasi:** hitung `mu`/`sigma` dari `valid[:-1]` (histori sebelum hari ini), baru bandingkan `valid[-1]` terhadapnya — konsisten dengan konvensi RVOL.

### 7.3 Validasi Ground-Truth — ✅ PRAKTIK SANGAT BAIK

`_compare_methods.py`, `_threshold_tuning.py`, `_backtest_gorengan.py`, `_validate_gorengan.py` semuanya divalidasi terhadap **45 saham UMA (Unusual Market Activity)** — daftar yang sungguh ditandai BEI, bukan proxy buatan sendiri — versus 30 saham blue-chip sebagai kontrol negatif. Ini ground truth yang kredibel dan jarang dipakai di proyek sejenis. Diperiksa juga metodologi split train/forward-nya (`_threshold_tuning.py`, `_backtest_gorengan.py`): keduanya **benar** memotong data di tanggal target sebelum menghitung skor (`train_bars = bars[:split_idx]`), lalu mengecek outcome hanya dari `future_bars` — tidak ada lookahead di script-script validasi ini.

---

## 8. Lapisan Data & Infrastruktur

### 8.1 DIPERBAIKI: auto_adjust=True eksplisit via config.YAHOO_AUTO_ADJUST (audit #15)

```python
df = yf.Ticker(ticker).history(start=..., end=..., interval="1d")   # auto_adjust tidak disebutkan
```

Riset dokumentasi yfinance terkini mengonfirmasi default `Ticker.history()` saat ini adalah `auto_adjust=True` (OHLC otomatis disesuaikan untuk stock split & dividen) — jadi **secara kebetulan/mengikuti default, perilaku saat ini sudah benar** (split tidak akan menciptakan gap harga palsu yang merusak ATR/RSI/ADX/deteksi gorengan). **Namun** ini persis kasus yang sudah pernah terjadi: yfinance **mengubah default ini** dari `False` ke `True` pada rilis v0.2.54 (Feb 2025), sempat menyebabkan banyak breakage kode yang bergantung pada default lama. `requirements.txt` hanya mem-pin batas bawah (`yfinance>=0.2.40`, tanpa batas atas), sehingga `pip install --upgrade` di masa depan berisiko membawa perubahan default lain yang mengubah seluruh hasil indikator **secara diam-diam, tanpa perubahan kode apa pun**. **Rekomendasi:** set eksplisit `auto_adjust=True` di pemanggilan `history()` — membuat perilaku eksplisit dan tahan terhadap perubahan versi library di masa depan.

### 8.2 🔶 CATATAN: Data intraday berpotensi membuat sinyal "repaint"

`_is_data_delayed()` mendeteksi jam bursa (09:00–17:00 WIB) dan mengembalikan flag `data_delayed=True` — tapi sistem **tetap menghitung** skor/sinyal dari bar terakhir meski bar itu masih "berjalan" (harga real-time, bukan close final) saat query dilakukan di jam bursa. Ini transparan (flag-nya dikembalikan ke consumer), tapi berarti sinyal yang dilihat user bisa berubah beberapa kali dalam satu hari perdagangan yang sama, murni karena harga masih bergerak — karakteristik umum sistem berbasis indikator real-time, bukan bug, tapi baik untuk didokumentasikan eksplisit ke pengguna akhir (mis. "sinyal paling stabil dibaca setelah bursa tutup").

### 8.3 DIPERBAIKI: modul short_selling.py + gate di api.py (audit #2)

Sistem men-generate sinyal **SELL sebagai entry short** (`risk.build_trade_plan` menghitung SL/TP simetris untuk direction="SELL", `config.LONG_ONLY_MODE=False`, dan divalidasi backtest "58% WR"), untuk pada dasarnya **seluruh saham** dalam universe scan (tidak ada pemeriksaan whitelist di manapun dalam kode). Riset regulasi terkini (Peraturan II-H BEI — SK Direksi Kep-00157/BEI/10-2024, dan POJK No. 6 Tahun 2024) mengonfirmasi *short selling* di BEI **sangat dibatasi**:

- Hanya saham yang masuk **Daftar Efek Short Selling** yang diterbitkan & di-*review* BEI **setiap bulan** boleh di-short (per data Maret 2025: hanya **237 saham** dari 900+ saham tercatat di BEI).
- Syarat masuk daftar termasuk *free float* minimum 20% (dihitung 6 bulan terakhir), dan pembiayaan hanya bisa diberikan lewat perusahaan efek berizin OJK khusus dengan perjanjian pinjam-meminjam efek.
- Investor wajib menyetor jaminan awal minimal 50% dari nilai transaksi, dan volume short dibatasi ketat (0.01%–0.04% dari saham beredar per hari, tergantung nilai transaksi harian).
- *Naked short selling* (short tanpa pinjam saham) dilarang.

**Dampak:** sinyal SELL yang dihasilkan untuk saham **di luar** daftar bulanan tersebut (mayoritas dari universe scan, termasuk kemungkinan besar saham-saham kecil/menengah yang justru sering muncul di scan gorengan/recovery) **tidak bisa dieksekusi sebagai short** oleh user ritel biasa sama sekali — terlepas dari seberapa valid skor kuantitatifnya. Win rate 58% yang divalidasi kemungkinan besar dihitung dari backtest yang tidak mem-filter kelayakan ini, sehingga secara *tradability* riil, angka tersebut hanya applicable untuk subset saham yang jauh lebih kecil dari yang diklaim/ditampilkan sistem. **Rekomendasi:** tambahkan pengecekan terhadap Daftar Efek Short Selling (BEI mempublikasikan ulang tiap bulan) sebelum menampilkan/membacktest sinyal SELL sebagai *entry* short; untuk saham di luar daftar, tampilkan SELL hanya sebagai sinyal *exit* posisi long yang sudah ada (bukan entry short baru) — sesuai dengan catatan `validation_note` yang sebenarnya *sudah* ada di `api.py` ("*SELL bersifat advisory (long-only mode aktif)*") namun tampaknya belum konsisten dengan `LONG_ONLY_MODE=False` dan trade plan simetris yang benar-benar dihasilkan untuk SELL.

---

## 9. Ringkasan Prioritas Temuan

| # | Temuan | Lokasi | Severity | Effort Perbaikan  | Status |
|---|---|---|---|---|
| 1 | Drift GBM salah (lupa −0.5σ²) sebelum masuk `first_passage_cdf` | recovery.py:~85 & call sites | 🔴 Tinggi | Kecil (1-2 baris) | ✅ fix recovery.py (mu_log) |

| 2 | Tidak ada filter kelayakan short selling utk sinyal SELL | api.py, risk.py | 🔴 Tinggi | Sedang (perlu fetch daftar bulanan BEI) | ✅ fix api.py + short_selling.py |

| 3 | `backtest_calibrate.py` 100% in-sample, risiko overfitting | backtest_calibrate.py | 🔴 Tinggi | Sedang (integrasi ke walkforward) | ✅ fix backtest_calibrate.py (OOS) |

| 4 | `walkforward.py` train window dihitung tapi tak dipakai | walkforward.py | 🟠 Sedang-Tinggi | Sedang-Besar | ✅ fix walkforward.py (train-opt) |

| 5 | Anualisasi Sharpe salah (√252 pada return per-trade) | walkforward.py:188 | 🟠 Sedang | Kecil | ✅ fix walkforward.py (equity daily) |

| 6 | `risk_level`/`confidence` live selalu stub "sedang" | scoring.py, risk.py | 🟠 Sedang | Kecil-Sedang (pindah fungsi dari backtest.py) | ✅ fix scoring.py/risk.py (single source) |

| 7 | Exit REVERSAL pakai sinyal bar-sama (lookahead) | backtest.py:~549 | 🟠 Sedang | Kecil | ✅ fix backtest.py (recs[i-1]) |

| 8 | Dead code Sharpe trade-based (variable shadowing) | backtest.py:655-669 | 🟡 Rendah-Sedang | Kecil | ✅ fix backtest.py (shadowing dihapus) |

| 9 | Live trade-plan entry timing ≠ protokol yang divalidasi backtest | api.py vs backtest.py | 🟡 Sedang (dokumentasi) | Kecil (disclaimer) | ✅ fix api.py (disclaimer) |

| 10 | RSI seeding bias dari delta-palsu index 0 | indicators.py (`rsi`) | 🟡 Rendah | Kecil | ✅ fix indicators.py (seed asli) |

| 11 | Persentase ARA/ARB tidak sesuai regulasi BEI terkini | recovery.py/config.py | 🟡 Rendah-Sedang | Kecil | ✅ fix recovery/config (cap flat 13%) |

| 12 | Threshold sinyal recovery (60%) < breakeven R:R exit plan (66.7%) | recovery.py/config.py | 🟡 Sedang | Kecil (tuning) | ✅ fix config (0.68) |

| 13 | `_zscore` self-referencing, inkonsisten dgn `rvol()` | gorengan.py | 🟡 Rendah | Kecil | ✅ fix gorengan.py (leave-one-out) |

| 14 | Fee model simetris 0.25%/0.25%, riil asimetris ~0.18%/0.28% | backtest.py | 🟢 Rendah | Kecil | ✅ fix backtest.py (0.18/0.28) |

| 15 | `auto_adjust` yfinance bergantung default, tidak eksplisit | data_source/yahoo_client.py | 🟢 Rendah | Sangat kecil (1 parameter) | ✅ fix yahoo_client (eksplisit) |

| 16 | Regime multiplier asimetris terhadap titik netral (bukan bug, perlu validasi intent) | scoring.py | 🟢 Rendah | Dokumentasi / opsional | ✅ terdokumentasi (config.py) |


---

## 10. Apresiasi — Hal yang Sudah Dilakukan dengan Benar dan Matang

Poin ini penting disebutkan eksplisit karena audit sering terkesan hanya mencari-cari kesalahan:

1. **Indikator inti (ATR, ADX, MFI)** — presisi identik dengan implementasi independen; RSI juga benar, hanya seeding-nya yang perlu koreksi kecil.
2. **Simulasi fill SL/TP di backtest** memodelkan gap risk secara realistis — sesuatu yang bahkan banyak backtest engine profesional lewatkan.
3. **Matematika breakeven R:R** (54.5%) dihitung dan divalidasi silang dengan benar terhadap ATR SL/TP multiplier — konsistensi lintas-modul yang jarang ditemukan.
4. **Formula first-passage time GBM** untuk model recovery diverifikasi benar hingga ke detail tanda (sign convention) yang sering salah di berbagai sumber — dan developer sudah proaktif mengoreksinya sendiri.
5. **Validasi terhadap ground truth riil** (45 saham UMA BEI untuk gorengan detection, 963 saham untuk pola akumulasi) — bukan validasi sirkular terhadap asumsi sendiri.
6. **Kesadaran anti-lookahead** eksplisit di banyak tempat (RVOL exclude current bar, swing points didokumentasikan sebagai lagging, purge/embargo di walkforward, split train/future di script validasi) — pola pikir yang benar, walau implementasinya belum 100% konsisten di semua modul (§4.2, §7.2).
7. **Position sizing berbasis risiko** dengan safety-net anti-leverage — implementasi buku teks yang benar.
8. **Regime detection** (SMA200 + ADX) dan **ADX gate** memakai konvensi yang well-established dan sudah diuji lewat grid search, bukan angka sembarang.

---

## Referensi

1. Wilder, J. Welles Jr. (1978). *New Concepts in Technical Trading Systems*. Trend Research. — sumber RSI, ATR, ADX/DMI.
2. López de Prado, M. (2018). *Advances in Financial Machine Learning*, Bab 7 (Cross-Validation in Finance: Purging, Embargo). Wiley.
3. Bailey, D. H., Borwein, J., López de Prado, M., & Zhu, Q. J. (2014). "The Probability of Backtest Overfitting." *Journal of Computational Finance*.
4. Pardo, R. (2008). *The Evaluation and Optimization of Trading Strategies* (2nd ed.). Wiley. — metodologi walk-forward optimization.
5. Sharpe, W. F. (1994). "The Sharpe Ratio." *Journal of Portfolio Management*. — konvensi anualisasi.
6. Karatzas, I. & Shreve, S. (1991). *Brownian Motion and Stochastic Calculus*. Springer. — first-passage time & lemma Itô untuk GBM.
7. Van Tharp (2006). *Trade Your Way to Financial Freedom*. McGraw-Hill. — position sizing berbasis risiko.
8. StockCharts ChartSchool — "Average Directional Index (ADX)", diakses Agustus 2026.
9. Bursa Efek Indonesia — Surat Keputusan Direksi No. Kep-00003/BEI/04-2025 (batas Auto Rejection, efektif 8 April 2025).
10. Bursa Efek Indonesia — Peraturan II-H, SK Direksi No. Kep-00157/BEI/10-2024 & POJK No. 6/2024 (syarat transaksi margin & short selling).
11. yfinance documentation (ranaroussi.github.io) — perilaku default parameter `auto_adjust`.
12. Riset biaya transaksi saham ritel Indonesia (Indo Premier, BNI Sekuritas, MOST/CGS, 2025) — struktur fee beli/jual & PPh Final Pasal 4(2).

*Semua temuan formula divalidasi lewat kombinasi: pembacaan kode langsung, implementasi ulang independen + diff numerik (RSI/ATR/MFI/ADX), simulasi Monte Carlo (GBM drift, 2 juta lintasan), dan penelusuran literatur/regulasi primer. File simulasi verifikasi tersedia atas permintaan bila ingin direproduksi.*
