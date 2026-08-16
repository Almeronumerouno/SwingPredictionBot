# Audit Mendalam Ready To Fly & Recovery Engine — Versi Terbaru

**Project:** Swing Bot IDX  
**Scope:** Ready To Fly / Accumulation, Recovery Engine, Post-ARA/Post-Pump, Recovery Probability, Accumulation Density, Heavy Volume, SMA/Moving Average, Gate/Filtering, Scoring/Ranking, Backtest & Validation  
**Audit status:** Research + source-code audit, **tanpa perubahan kode**  
**Versi source yang diaudit:** `backend(3).zip`

---

# 1. Executive Summary

Versi terbaru **jauh lebih baik** dibanding versi sebelumnya. Perbaikan paling penting adalah penggunaan **empirical logistic recovery model**, adanya **Brier/reliability evaluation**, **walk-forward infrastructure**, **liquidity study**, **ranking study**, dan berbagai sanity check.

Namun, model belum dapat dianggap sepenuhnya production-trustworthy karena masih terdapat beberapa persoalan pada:

1. definisi event ARA/post-ARA;
2. semantic `ALMOST`;
3. temporal OOS split recovery calibration;
4. overlapping observations dan statistical dependence;
5. konsistensi definisi recovery target;
6. beberapa bug implementasi konkret pada `net_dist` dan local dataset;
7. survivorship/corporate-action handling;
8. pemilihan threshold yang masih sebagian heuristic;
9. validasi Ready To Fly yang belum sepenuhnya walk-forward/out-of-sample.

## Overall assessment

| Area | Status | Rating |
|---|---|---:|
| Recovery logistic | Konsep sudah jauh lebih benar | 7.5/10 |
| Recovery probability calibration | Belum cukup valid secara OOS | 5.5/10 |
| Accumulation logic | Reasonable heuristic detector | 7/10 |
| Heavy-volume logic | Useful feature, threshold masih heuristic | 6.5/10 |
| SMA20 gate | Matematis benar, role predictive terbatas | 6.5/10 |
| Post-ARA | Definisi event masih bermasalah | 4.5/10 |
| READY gate | Logic dasar reasonable | 7/10 |
| ALMOST gate | Semantic mismatch / bug | 4/10 |
| Ranking strength | Ada indikasi incremental value | 6.5/10 |
| Backtest infrastructure | Jauh membaik | 7.5/10 |
| OOS validation RTF/Recovery | Belum benar-benar bersih | 5/10 |
| Survivorship control | Belum terselesaikan | 4.5/10 |
| Probability interpretation | Harus diperketat | 5/10 |

### Overall

**Architecture: ~7/10**  
**Evidential/statistical validity: ~5.5–6/10**

Kesimpulan praktis:

> Project sudah tidak berada pada kondisi “formula ngawur”. Tetapi belum cukup kuat untuk menyatakan bahwa `READY` benar-benar predictive atau bahwa `Recovery Probability` sudah merupakan probability yang fully calibrated dan out-of-sample validated.

---

# 2. Bagian yang Sudah Benar / Patut Dipertahankan

## 2.1 Recovery tidak lagi bergantung pada pure GBM

Perubahan dari theoretical GBM/first-passage menuju **empirical logistic recovery model** adalah improvement besar.

Konsep saat ini:

\[
P_h = \sigma(a_h+b_h DD)
\]

dengan:

\[
\sigma(x)=\frac{1}{1+e^{-x}}
\]

serta drawdown berbasis recent peak.

### Penilaian

- Mathematical correctness: **BENAR**
- Output 0–1: **BENAR**
- Monotonic relationship terhadap drawdown: **reasonable**
- Lebih defensible daripada pure GBM: **YA**
- Sudah terbukti calibrated OOS: **BELUM**

**Rekomendasi:** pertahankan logistic sebagai baseline utama. Jangan diganti dengan model yang lebih kompleks sebelum validation layer diperbaiki.

---

## 2.2 Brier Score dan Reliability Evaluation

Kehadiran:

- AUC
- Brier score
- reliability analysis

merupakan improvement yang benar karena prediction probabilistik harus dinilai bukan hanya dari discrimination tetapi juga calibration.

Namun current split belum benar-benar temporal OOS sehingga angka calibration belum boleh dianggap final production calibration.

---

## 2.3 Walk-forward Infrastructure

Walk-forward engine memiliki struktur yang baik:

```text
TRAIN
↓
PURGE
↓
EMBARGO
↓
TEST
```

Ini patut dipertahankan.

Tetapi walk-forward tersebut terutama memvalidasi swing/backtest pipeline. Tidak otomatis berarti seluruh Ready To Fly/Recovery pipeline sudah OOS validated.

---

# 3. Formula Audit

| Component | Formula / Logic Saat Ini | Mathematical Correctness | Modelling Suitability | Evidence | Risk | Recommendation |
|---|---|---|---|---|---|---|
| Logistic recovery | \(P=\sigma(a+bDD)\) | ✅ | ✅ Baseline kuat | Empirical/statistical | Calibration split | Keep + revalidate OOS |
| GBM first passage | GBM/barrier style probability | ✅ | ⚠️ Kurang realistis untuk individual stock | Theoretical | Model misspecification | Diagnostic/baseline only |
| Drawdown 252 | \(DD=1-P/Peak_{252}\) | ✅ | ✅ Reasonable | Empirical/research-compatible | Window sensitivity | Keep + test horizons |
| DD clamp 0.85 | Clamp drawdown at 85% | ✅ | ⚠️ Tail information lost | Heuristic | Understates extreme loss | Re-test tail handling |
| Empirical recovery | Success / total events | ✅ | ✅ | Empirical | Small n, overlap | Add shrinkage + cluster inference |
| n >= 5 | Switch to empirical if n≥5 | ✅ | ❌ Too weak | Heuristic | Extreme variance | Wilson/Beta shrinkage |
| Heavy volume 2x | Volume ≥ 2 × baseline | ✅ | ⚠️ Candidate feature | Research supports high-volume effects, not exact 2x | Arbitrary threshold | Tune OOS |
| Accumulation density | k/window | ✅ | ⚠️ Descriptive | Empirical | Direction ignored without net_dist | Keep, label correctly |
| NetDist | Directional heavy-volume proportion | ⚠️ Alignment issue | ⚠️ | Practitioner/microstructure concept | Numerator/denominator mismatch | Fix implementation |
| SMA20 | Mean last 20 closes | ✅ | ✅ Confirmation | Broad TA evidence mixed | Lagging | Keep as confirmation |
| Strength | density × net_dist × decay | ✅ | ✅ Ranking heuristic | Project empirical | Overlap/threshold selection | Keep, validate OOS |
| Decay | exp(-days/2) | ✅ | ⚠️ Heuristic | Not proven optimal | Arbitrary τ | Validate |
| Day-5 cutoff | days≥5 → zero | ✅ | ❌ Artificial discontinuity | Heuristic | Boundary artifact | Remove/retest |
| READY | Gate conjunction | ✅ | ✅ Interpretable | Heuristic + empirical | Threshold sensitivity | Keep architecture |
| ALMOST | >=3 gates | ✅ arithmetic | ❌ Semantic mismatch | Implementation | May pass invalid setup | Fix immediately |
| +10% ARA | close_t ≥ 1.1 close_{t-1} | ✅ math | ❌ Not universal IDX ARA | Exchange rule mismatch | Wrong event classification | Implement actual ARA or rename |
| ADV20 | liquidity floor | ✅ | ⚠️ Operational filter | Execution logic | Not predictive itself | Keep as safety gate |

---

# 4. Recovery Model Audit

## 4.1 Current logistic model

Model:

\[
P_h = \sigma(\alpha_h + \beta_h DD)
\]

Dengan interpretasi bahwa semakin besar drawdown, recovery probability cenderung menurun.

### Mathematical correctness

**Benar.** Sigmoid menghasilkan output pada [0,1] dan tidak memerlukan clipping tambahan untuk probability.

### Modelling suitability

**Cukup baik sebagai baseline empirical model.**

Namun model hanya memakai drawdown sebagai feature utama. Itu membuatnya interpretable, tetapi belum berarti sufficient untuk predictive modelling.

Candidate features untuk tahap lanjut:

- drawdown duration;
- realized volatility;
- distance to SMA20/SMA50;
- relative volume;
- market regime;
- beta/relative strength terhadap IHSG;
- liquidity;
- post-event age.

Jangan menambah semua feature sekaligus. Tambahkan satu blok feature dan lakukan ablation/OOS testing.

---

# 5. Critical Finding — Recovery Calibration Split Belum Benar-Benar Temporal

Pada calibration script, data dari beberapa saham digabung kemudian di-split berdasarkan posisi baris sekitar 70/30.

Masalahnya: ini **bukan global chronological split**.

Yang dibutuhkan adalah:

```text
TRAIN
2019 ───────── 2024

PURGE / EMBARGO

TEST
2024 ───────── 2026
```

bukan:

```text
70% first rows of concatenated stocks
30% remaining rows
```

### Kenapa critical?

Karena temporal forecasting harus memastikan model tidak melihat kondisi periode yang lebih baru pada calibration yang disebut OOS.

### Priority

**CRITICAL**

### Fix

Gunakan cutoff date global atau walk-forward per horizon:

```text
train_end = T
purge = max_horizon
valid = T + purge → next cutoff
```

---

# 6. Critical Finding — Overlapping Recovery Events

Jika satu drawdown berlangsung 5–10 hari, event creation bisa menghasilkan banyak event pada hari-hari yang berurutan.

Contoh:

```text
Day 1  -5%
Day 2  -6%
Day 3  -7%
Day 4  -8%
Day 5  -9%
```

Bisa menghasilkan 5 event yang sangat berkorelasi.

Padahal secara ekonomi mungkin itu hanya **satu drawdown episode**.

### Dampak

- effective sample size terlalu besar;
- p-value terlalu optimistis;
- confidence interval terlalu sempit;
- AUC/Brier dapat tampak lebih stabil daripada kenyataan.

### Recommended

Gunakan salah satu:

1. episode deduplication;
2. minimum separation/cooldown antar event;
3. cluster inference berdasarkan stock;
4. block bootstrap.

Untuk recovery, lebih baik unit observasi adalah:

```text
stock × recovery episode
```

bukan setiap hari.

---

# 7. Critical Finding — Recovery Event Definition Tidak Konsisten

Engine saat ini memiliki beberapa konsep recovery yang berbeda:

- recovery ke prior peak;
- recovery ke previous close/reference;
- target berdasarkan future high.

Tetapi istilah `recovery_probability` dapat membuatnya tampak sebagai satu event yang sama.

### Ini harus dipisahkan

Gunakan nama eksplisit seperti:

```text
p_recover_prev_close_21d
p_recover_peak_21d
p_hit_plus_10_10d
```

Jangan memakai satu `recovery_probability` generik untuk event yang berbeda.

### Priority

**CRITICAL / HIGH**

---

# 8. n >= 5 Terlalu Sedikit untuk Empirical Probability

Current logic:

```python
if n_events >= 5:
    use empirical probability
```

Contoh:

```text
n = 5
success = 4
P = 80%
```

Padahal uncertainty sangat besar.

### Recommendation

Gunakan shrinkage:

\[
P = \frac{s+\alpha}{n+\alpha+\beta}
\]

atau gunakan Wilson lower/upper interval dan shrink ke global base rate jika sample kecil.

Lebih baik lagi:

```text
n kecil → global/base-rate prior
n sedang → partial shrinkage
n besar → empirical proportion lebih dominan
```

---

# 9. Drawdown Clamp 85%

Current clamp sekitar 85% berarti drawdown 85%, 90%, dan 95% dapat kehilangan perbedaan pada input model.

Ini penting karena recovery probability memang berubah di tail.

Research drawdown-recovery menunjukkan probabilitas recovery turun tajam pada drawdown yang sangat besar.

### Recommendation

Jangan langsung memilih angka clamp baru.

Lakukan:

```text
bucket 0–10%
10–20%
20–30%
...
80–90%
90%+
```

lihat sample size dan outcome terlebih dahulu.

Jika tail terlalu sparse, gunakan monotonic shrinkage, bukan arbitrary clamp.

---

# 10. Ready To Fly Audit

Current architecture pada prinsipnya bagus:

```text
eligibility/safety
+
quality gates
+
ranking strength
```

Saya **tidak merekomendasikan mengganti READY menjadi black-box ML**.

Lebih baik pertahankan interpretability.

---

# 11. Accumulation Density

Formula:

\[
density = \frac{k}{window}
\]

### Mathematical

✅ Benar.

### Modelling

⚠️ Descriptive, belum otomatis predictive.

Contoh:

```text
3 heavy-volume bullish days
```

dan:

```text
3 heavy-volume bearish days
```

dapat memiliki density sama.

Karena itu `directional heavy-volume pressure`/`net_dist` diperlukan sebagai feature tambahan.

### Terminology

Jangan menyebut `density` sebagai:

> probability of accumulation

atau:

> institutional accumulation probability

lebih tepat:

> accumulation activity density / event density.

---

# 12. Heavy Volume Days

Research mendukung gagasan bahwa unusually high volume dapat mengandung informasi mengenai subsequent return, tetapi evidence tidak universal dan exact threshold seperti 2x tidak terbukti sebagai angka optimal universal.

Karena itu:

```text
heavy volume = candidate predictive feature
```

✅

sementara:

```text
2x = research-proven optimal threshold
```

❌

### Status threshold 2x

**Heuristic / empirical candidate**.

### Recommendation

Test threshold hanya pada TRAIN:

```text
1.25x
1.5x
1.75x
2.0x
2.5x
3.0x
```

kemudian freeze parameter sebelum OOS test.

---

# 13. NetDist Alignment Bug

Ditemukan masalah alignment pada implementasi `net_dist`:

- numerator menggunakan directional information;
- denominator volume tidak selalu merepresentasikan observation set yang sama;
- first post-event day dapat masuk denominator tanpa direction yang sepadan.

Idealnya setiap volume observation memiliki direction eksplisit:

\[
direction_t = sign(C_t-C_{t-1})
\]

kemudian:

\[
NetDist =
\frac{\sum_t V_t I(direction_t>0)}{\sum_t V_t}
\]

atau gunakan signed volume proxy jika definisinya memang itu.

### Penting

Jangan menyebut metrik ini sebagai true institutional order flow. OHLCV hanya memberi proxy. Order-flow imbalance membutuhkan data microstructure yang lebih lengkap.

### Priority

**HIGH**

---

# 14. Strength Score

Current concept:

\[
Strength = Density \times NetDist \times Decay
\]

Saya **tidak menyarankan menggantinya dulu**.

Ini reasonable sebagai ranking heuristic.

Evidence terbaru dari project menunjukkan indikasi bahwa strength lebih baik daripada density-only untuk precision@K, tetapi jumlah query OOS masih belum cukup kuat untuk final claim.

### Classification

**Empirical ranking heuristic**

Bukan probability.

---

# 15. ALMOST Logic Bug

Current description mengarah pada:

```text
ALMOST = ≥3 of 4 gates
```

namun implementation aktual memiliki **5 gates**, misalnya:

```text
below
 density
 heavy
 above SMA
 liquidity
```

sementara logic tetap:

```python
gates_passed >= 3
```

Akibatnya saham dapat berstatus `ALMOST` walaupun `below` gagal.

Contoh:

```text
below        = False
 density     = True
 heavy       = True
 above_sma   = True
 liquidity   = True
```

Hasil sekarang dapat menjadi `ALMOST`, walaupun saham tidak memenuhi kondisi dasar post-event accumulation.

### Solusi architecture-friendly

Pisahkan:

### Safety / eligibility gates

```text
below-event
liquidity
valid data
```

### Quality gates

```text
density
heavy-volume
SMA confirmation
```

Kemudian:

```text
READY
= all safety + all quality

ALMOST
= all safety + 2/3 quality

NOT ELIGIBLE
= safety failure
```

### Priority

**CRITICAL**

---

# 16. Post-ARA Detection — +10% Bukan Universal ARA IDX

Current logic pada dasarnya:

```text
close_t >= 1.10 × close_{t-1}
```

Secara matematis valid sebagai large up move.

Tetapi ini tidak sama dengan definisi Auto Rejection Atas yang berlaku universal untuk seluruh saham IDX.

Aturan IDX membedakan batas berdasarkan kelompok/harga dan ketentuan pasar yang berlaku.

### Recommendation

Buat `event_detector`:

```text
large_upmove
ARA
post_pump
```

Jika data yang diperlukan untuk menentukan ARA aktual tidak tersedia, jangan menyebut event tersebut `ARA`.

Gunakan:

```text
POST_LARGE_UPMOVE
```

untuk threshold heuristic seperti +10%.

### Priority

**CRITICAL/HIGH**

---

# 17. Post-ARA Decay

Current:

\[
decay=e^{-days/2}
\]

dan kira-kira:

```text
days >= 5 → 0
```

Matematis sah, tetapi modelling-nya heuristic.

Ada discontinuity besar:

```text
Day 4 ≈ 13.5%
Day 5 = 0
```

Tidak ada alasan kuat bahwa biological/statistical process harus tiba-tiba nol pada hari ke-5.

### Recommendation

Tetapkan decay sebagai ranking freshness.

Jangan memperlakukannya sebagai probability.

Lakukan sensitivity test:

```text
τ = 1
τ = 2
τ = 3
τ = 5
```

dan bandingkan OOS.

---

# 18. SMA20 Audit

Formula:

\[
SMA_{20,t} = \frac{1}{20}\sum_{i=0}^{19} Close_{t-i}
\]

### Mathematical correctness

✅ Benar.

### Point-in-time

✅ Jika hanya memakai t dan historical bars sebelum t.

### Predictive role

Lebih tepat sebagai:

> trend confirmation / lagging state variable

bukan leading breakout predictor.

### Recommendation

**Keep.** Jangan dihapus hanya karena bukan leading indicator. Yang penting adalah menggunakan SMA20 sebagai confirmation/gate dan menguji incremental value-nya.

---

# 19. Threshold Audit

| Threshold | Classification | Evidence status |
|---|---|---|
| Density 30% | Heuristic / empirical | Perlu OOS |
| Heavy volume 2x | Heuristic | Exact threshold belum terbukti universal |
| ≥2 heavy days | Heuristic | Perlu OOS |
| Price ≥ SMA20 | Heuristic/technical confirmation | Evidence mixed |
| Decay τ=2 | Heuristic | Belum terbukti optimal |
| Day 5 = 0 | Heuristic | Terlalu discontinuous |
| Recovery P ≥ 0.68 | Heuristic unless locked from research | Validasi calibration wajib |
| Empirical n≥5 | Heuristic | Terlalu kecil |
| ADV floor | Operational | Bukan predictive evidence |
| ARA +10% | Incorrect semantic use | Harus diperbaiki |

---

# 20. Statistical & Backtest Audit

## 20.1 Look-ahead bias

Arsitektur terbaru sudah lebih sadar terhadap point-in-time, tetapi validation seluruh Ready To Fly belum sepenuhnya membuktikan bahwa parameter selection tidak menggunakan masa depan.

Yang harus dijaga:

```text
feature_t hanya berasal dari data ≤ t
label menggunakan > t
parameter hanya fit pada train
threshold freeze sebelum test
```

---

## 20.2 Data leakage

Risiko terbesar muncul ketika:

- threshold dipilih memakai seluruh dataset;
- calibration memakai seluruh history lalu dievaluasi pada bagian history yang sama;
- preprocessing/global normalization menggunakan future observations;
- event definitions dibuat dengan informasi pasca-event sebelum signal timestamp.

---

## 20.3 Survivorship bias

Adanya `delisted_bias_check.py` adalah langkah baik.

Tetapi keberadaan check belum berarti survivorship bias sudah terselesaikan.

Dataset perlu mempertahankan historical universe yang benar, termasuk:

- delisted;
- suspended;
- historical constituents;
- saham yang keluar/masuk universe.

---

## 20.4 Corporate actions

Pisahkan penggunaan:

### Raw prices
Untuk:

- execution;
- actual exchange event;
- ARA logic.

### Adjusted/split-adjusted series
Untuk:

- historical return;
- drawdown;
- momentum;
- SMA;
- recovery studies.

Tanpa policy ini, corporate action dapat menciptakan artificial drawdown/recovery.

---

# 21. Local Dataset Bug

Ditemukan potensi bug konkret pada assignment `previous`:

```python
previous=float(r[COL_OPEN - 1])
```

Jika `COL_OPEN = 0`, maka index menjadi `-1`, yang berarti kolom terakhir (volume), bukan previous close.

### Correct semantic

```python
previous = rows[i - 1, COL_CLOSE]
```

Selain itu, synthetic date seperti `2020-01-01 + i days` tidak merepresentasikan actual trading dates.

### Priority

**HIGH**

---

# 22. Probability Calibration

Probability 0–1 dari sigmoid belum otomatis merupakan calibrated probability.

Calibrated probability perlu memenuhi kondisi secara kasar:

\[
P(Y=1\mid \hat P \approx p) \approx p
\]

Karena itu evaluasi perlu mencakup:

- Brier score;
- log loss;
- reliability curve;
- calibration intercept;
- calibration slope;
- base-rate benchmark;
- temporal OOS calibration.

### Brier skill

Jangan hanya melaporkan:

```text
Brier = 0.12
```

bandingkan dengan:

```text
Brier(model)
vs
Brier(always predict base rate)
```

---

# 23. Baseline Comparison yang Wajib

RTF harus dibandingkan dengan baseline sederhana:

1. Drawdown-only.
2. Price > SMA20.
3. Volume > average/median.
4. Simple momentum.
5. Recovery-only.
6. Volume-only.
7. Random selection.
8. Current RTF.

Selain itu lakukan ablation:

```text
RTF
RTF - density
RTF - heavy volume
RTF - SMA
RTF - decay
RTF - liquidity
```

Tujuan utamanya adalah membuktikan **incremental predictive value**.

---

# 24. False Signal yang Harus Diaudit

## Distribution

Heavy volume tidak otomatis accumulation.

## Dead-cat bounce

Saham bisa memantul setelah downtrend panjang tanpa melanjutkan recovery.

## Temporary volume spike

Single-day abnormal volume dapat menjadi event liquidity/exit, bukan base building.

## Illiquidity

Volume spike di saham tipis bisa menghasilkan signal palsu walaupun ada minimum liquidity gate.

## Market-wide rally

Saham terlihat “recovery” hanya karena IHSG/risk-on market.

## Structural deterioration

SMA20 dan volume tidak mendeteksi perubahan fundamental atau structural deterioration.

---

# 25. Research Comparison

## High volume dan subsequent returns

Gervais, Kaniel, dan Mingelgrin menemukan bahwa unusually high trading volume dapat terkait dengan subsequent price appreciation. Ini mendukung volume sebagai **candidate feature**, tetapi tidak membuktikan threshold `2x` sebagai universal optimum.

## Cross-country evidence

Penelitian lintas negara juga menemukan volume-related return effects, tetapi kekuatan dan persistensinya tidak universal.

## Out-of-sample caution

Literature menunjukkan hubungan volume-return dapat melemah pada testing yang lebih ketat.

## Market microstructure

Cont, Kukanov, dan Stoikov menunjukkan bahwa **order-flow imbalance** lebih informatif untuk short-horizon price changes daripada raw volume semata. Ini mendukung penggunaan directional volume sebagai proxy, tetapi juga menunjukkan keterbatasan OHLCV-only implementation.

## Technical analysis

Literature technical analysis memberikan evidence mixed dan sangat rentan terhadap data snooping, market regime, biaya transaksi, dan parameter selection.

## Recovery / drawdown

Empirical drawdown-recovery research menunjukkan bahwa recovery probability menurun ketika drawdown semakin ekstrem, sehingga penggunaan drawdown sebagai feature memiliki dasar empiris. Tetapi probabilitas tersebut bergantung pada definisi event, universe, horizon, dan conditioning.

## Backtest overfitting

White, Bailey, dan penelitian terkait menunjukkan repeated model selection / multiple testing dapat membuat backtest terlihat jauh lebih baik daripada kemampuan out-of-sample sebenarnya.

---

# 26. Recommended Model

Architecture yang paling masuk akal untuk saat ini:

```text
                    Historical OHLCV
                           │
                  Point-in-time layer
                           │
            ┌──────────────┴──────────────┐
            │                             │
       Recovery Engine             Ready-To-Fly Engine
            │                             │
     drawdown / recovery           accumulation density
     empirical probability         heavy-volume behavior
                                  SMA / price structure
            │                             │
            └──────────────┬──────────────┘
                           │
                     Eligibility
                           │
                    READY / ALMOST
                           │
                        Ranking
                        Strength
                           │
                         Output
```

Prinsip utama:

```text
Probability ≠ Score ≠ Gate
```

Ketiganya sebaiknya tetap dipisahkan.

---

# 27. Recommended Recovery Formula

Untuk tahap sekarang:

\[
P_{recover,h} = \sigma(\alpha_h + \beta_h DD)
\]

dengan:

- horizon h berbeda untuk 5/10/21 hari atau horizon lain yang dipilih;
- drawdown point-in-time;
- temporal training;
- shrinkage untuk sample kecil;
- cluster/block-aware inference.

Jangan mengganti model ini sampai OOS evaluation membuktikan bahwa baseline gagal.

---

# 28. Future Model yang Lebih Cocok: Survival/Hazard

Jika logistic baseline sudah tervalidasi, model berikutnya yang paling masuk akal bukan langsung deep learning, tetapi **discrete-time survival / hazard model**.

Definisi hazard:

\[
h_t=P(T=t\mid T\ge t,X_t)
\]

dan cumulative recovery probability:

\[
P(T\le H)=1-\prod_{t=1}^{H}(1-h_t)
\]

Ini lebih natural untuk pertanyaan:

> “Kapan recovery terjadi?”

dibandingkan pure GBM first-passage.

Tetapi ini **optional future phase**, bukan prioritas sekarang.

---

# 29. Label Recovery / Trading yang Lebih Tepat

Pisahkan beberapa outcome:

### First-touch label

```text
future high reaches target
```

### Close-target label

```text
future close reaches target
```

### Executable trade label

```text
+TP before -SL
```

### Timeout

```text
neither target nor stop
```

Dengan demikian:

```text
Probability of touch
```

tidak disalahartikan sebagai:

```text
Probability of profitable trade
```

---

# 30. Priority Matrix

## 🔴 CRITICAL

- Fix true ARA definition / rename large-upmove event.
- Fix ALMOST safety gate semantics.
- Fix temporal split recovery calibration.
- Unify recovery event definitions.

## 🟠 HIGH

- Fix overlapping recovery events.
- Cluster/block bootstrap.
- Replace `n>=5` with shrinkage/Wilson.
- Fix `net_dist` alignment.
- Fix local dataset `previous` bug.
- Use actual trading dates.
- Establish raw vs adjusted data policy.
- Historical survivorship/universe handling.
- True temporal OOS threshold selection for RTF.

## 🟡 MEDIUM

- Re-test DD clamp.
- Re-test decay τ and hard cutoff.
- Heavy-volume baseline with robust median/percentile.
- Calibration slope/intercept.
- Market-relative features.
- Regime breakdown.

## 🟢 LOW

- ML complexity.
- Deep learning.
- HMM.
- NLP sentiment.
- Order book features.
- Feature explosion.

---

# 31. Validation Plan Setelah Perbaikan

## Phase A — Correctness tests

- Unit test ARA event detection.
- Unit test ALMOST/READY eligibility.
- Unit test net_dist.
- Unit test previous-close source.
- Unit test actual date handling.
- Unit test raw/adjusted price pathways.

## Phase B — Recovery temporal validation

Gunakan chronological split:

```text
TRAIN
2018–2022

VALIDATION
2023–2024

LOCKBOX
2025–2026
```

dengan purge/embargo berbasis maximum horizon.

## Phase C — Recovery metrics

Report:

- ROC-AUC;
- PR-AUC bila imbalance tinggi;
- Brier;
- Log Loss;
- calibration slope;
- calibration intercept;
- reliability;
- Brier skill vs base rate;
- CI;
- performance per drawdown bucket;
- performance per market regime.

## Phase D — RTF validation

Walk-forward threshold selection:

```text
Train
→ tune density/volume/decay
→ freeze
→ OOS test
→ roll forward
```

## Phase E — Ranking validation

Measure:

- precision;
- recall;
- precision@5;
- precision@10;
- lift;
- MAP@K bila relevan;
- confidence interval.

## Phase F — Trading outcome

Measure:

- expectancy;
- profit factor;
- TP_FIRST;
- SL_FIRST;
- TIMEOUT;
- MAE;
- MFE;
- maximum drawdown;
- Sharpe/Sortino bila horizon/strategy memungkinkan.

---

# 32. Walk-Forward Rule yang Harus Dipegang

Parameter tidak boleh dituning menggunakan periode OOS.

Jika mencoba:

```text
30%
40%
50%
```

maka pemilihan threshold dilakukan di TRAIN.

Setelah threshold dipilih:

```text
freeze parameter
↓
OOS test
```

Jika parameter dipilih ulang setelah melihat OOS result, periode tersebut bukan OOS lagi.

---

# 33. Final Verdict

## Apakah Ready To Fly layak dipercaya?

**Sebagai screener heuristic: YA, dengan batasan.**

**Sebagai statistically proven predictive system: BELUM.**

---

## Apakah Recovery Probability benar-benar probability?

**Mathematically: YA.**

**Sebagai calibrated forecasting probability yang telah terbukti OOS: BELUM.**

Masalah utama bukan sigmoid, tetapi:

- temporal split;
- event definition;
- overlap;
- small sample;
- survivorship;
- calibration validation.

---

## Bagian yang sudah bagus

- Empirical logistic recovery.
- Brier/reliability tooling.
- Walk-forward infrastructure.
- Separation antara gate dan ranking.
- Accumulation density sebagai interpretable feature.
- Directional heavy-volume concept.
- Strength score sebagai ranking heuristic.
- Liquidity guard.
- Explicit validation tooling.

---

## Bagian misleading / berisiko

- Calling +10% event “ARA”.
- `ALMOST` yang bisa pass tanpa below-event condition.
- Recovery probability yang dapat mencampur event definitions.
- Empirical probability dari n≥5.
- Row-level iid statistical inference pada overlapping events.
- Describing strength as probability.
- Describing heavy volume as institutional accumulation.
- Treating current calibration score as final OOS evidence.

---

# 34. Recommended TODO — Urutan Implementasi

## Phase 1 — Correctness

- [x] Fix `ALMOST` semantic logic.
- [x] Fix ARA/event terminology and actual ARA rules.
- [x] Fix `net_dist` numerator/denominator alignment.
- [x] Fix local dataset previous-close bug.
- [x] Replace synthetic dates with actual trading dates.
- [x] Establish raw vs adjusted price policy.

### ✅ Status Implementasi — Fase 1 selesai (13 Agustus 2026)

Semua 6 item fase 1 diimplementasikan pada source live (`backend/`; snapshot
yang diaudit = `backend.zip` 12-08-2026).

1. **ALMOST semantic** — `data_source/readytofly_scanner.py`: gate dipisah
   SAFETY (`below`, `liquidity`) vs QUALITY (`density`, `min_heavy`, `above_ma`).
   READY = semua safety + semua quality; ALMOST = semua safety + ≥2/3 quality.
   Sebelumnya `>=3 dari 5` bisa meloloskan ALMOST walau safety `below` gagal.
2. **Terminologi event** — `recovery.py` + `config.py`: event berthreshold +10%
   disebut **large upmove / POST_LARGE_UPMOVE** (heuristic), BUKAN ARA resmi BEI
   (bertingkat 35/25/20 & berubah per regulasi). Nama internal/API `*ara*`
   dipertahankan demi kompatibilitas. Docstring, reason, note, warning diubah.
3. **net_dist alignment** — `recovery.py`: arah dihitung eksplisit untuk SEMUA
   hari window (hari pertama dibandingkan thd close hari event), denominator penuh
   & sejajar numerator. Sebelumnya numerator `post_vol[1:]` vs denominator
   `post_vol_sum` (hari pertama ikut denominator tanpa direction).
4. **Previous-close bug** — `data_source/local_dataset.py`: `previous` =
   `rows[i-1, COL_CLOSE]` (sebelumnya `r[COL_OPEN-1]` = `r[-1]` = volume).
5. **Actual dates** — `data_source/local_dataset.py`: `make_local_bar` menerima
   daftar tanggal ISO nyata dari `npz["dates"]` (fallback sintetis utk pemanggil
   lama). Sebelumnya tanggal sintetis `2020-01-01 + i`.
6. **Raw vs adjusted policy** — sudah diterapkan & diverifikasi: `auto_adjust=False`
   di `yahoo_client.py`; `DailyBar.close`/`raw_close` = harga riil (basis event &
   gate RTF), `adj_close` = disesuaikan dividen/split (basis indikator/model).

**Hasil uji integritas (13-08-2026):**
- Scan 963 saham dgn `detect_accumulation`: 14 sinyal valid, 0 error.
- `net_dist` engine 0.3474 = hitung manual 0.3474 (alignment OK).
- `previous` fix & actual dates terverifikasi (AADI, `2024-12-05`).
- `python test_api.py`: exit=0, semua smoke test PASS.
- `tsc --noEmit`: bersih (exit=0).

---

## Phase 2 — Recovery statistics

- [x] Implement global chronological recovery split.
- [x] Add purge/embargo.
- [x] Deduplicate/cluster recovery episodes.
- [x] Implement stock/block bootstrap.
- [x] Replace `n>=5` hard switch with shrinkage.
- [x] Separate recovery target semantics.
- [x] Re-evaluate DD clamp.

### ⚠️ BUG DATA KRITIS DITEMUKAN & DIPERBAIKI (13 Agustus 2026) — prasyarat F2.1

Selama persiapan F2.1 ditemukan bahwa **`dates` di `universe_ohlcv.npz` tertukar
antar kode** (hanya ~3/642 kode yang konsisten dengan kalender trading IDX saat
diuji silang). Akar masalah: `_build_recovery_dataset.py` men-*append* `dates`
dalam urutan selesainya thread pool (`as_completed`), lalu `_save` menempelkannya
ke `dates_arr[i]` berdasarkan urutan itu — padahal `rows[i]`/`lens[i]` ditulis
per indeks kode. Akibatnya tanggal kode A bisa menempel ke kode B.

Dampak:
1. F2.1 (purge/embargo) TIDAK VALID bila memakai dates tersebut.
2. Fase 1 item 5 ("actual dates") memakai `npz["dates"]` via
   `local_dataset.py` → tanggal bar di runtime juga salah untuk sebagian besar
   saham (verifikasi Fase 1 lolos karena kebetulan AADI = kode indeks 0).

Perbaikan yang diterapkan:
- `_build_recovery_dataset.py`: `dates` kini **dict per indeks kode**
  (`dates[i] = bars[-nb:]`), `_save` menulis per indeks; kode tanpa data → `None`.
- Rebuild penuh universe: `python _build_recovery_dataset.py` → **OK 963/963,
  fetch_errors 0**, durasi ~84s (2026-08-13).
- Verifikasi pasca-rebuild: `len(dates) == lens` untuk **963/963 kode** (sebelumnya
  321 mismatch), AADI idx-0 mulai `2024-12-05` (cocok IPO, konsisten Fase 1),
  rentang kalender `2024-02-26 … 2026-08-13`.
- Backup npz lama: `data/universe_ohlcv.legacy-20260812.npz` (+ meta json).

**Catatan penting:** `recovery_model_params.json` (produksi) dihitung dari baris
OHLCV saja (`_collect_rows` tidak membaca dates) → **param produksi TIDAK
terpengaruh** oleh bug dates dan tidak diubah.

### ✅ Status Implementasi — F2.1 selesai (13 Agustus 2026)

**Script baru:** `backend/_fase2_temporal_split.py` (evaluasi saja; `params`
produksi TIDAK ditimpa). `_collect_rows` di `_calibrate_recovery_model.py`
diperluas: menerima `dates_list`, tiap observasi kini membawa
`code`, `date_s` (tanggal event), `date_e` (tanggal bar akhir label = `pos + h`).

**Desain:**
- **Cutoff global** = quantile `TRAIN_FRAC` (0.70) dari SELURUH tanggal baris
  dataset → `2025-11-24` (bukan per saham, bukan per posisi bar).
- **PURGE per observasi per horizon**: observasi train yg labelnya menembus
  cutoff (exact: `date_e > cutoff` via tanggal nyata `npz["dates"]`) dibuang.
- **EMBARGO**: test = observasi dgn `date_s > cutoff + 90 hari kalender`
  (~max horizon 63 hari trading). Observasi di rentang cutoff..embargo
  (`n_gap`) dibuang.
- **Dua evaluasi**: (A) refit logistic di train purged → test embargoed;
  (B) param PRODUKSI tanpa refit → test yg sama (jawaban "apakah param live
  masih kalibrasi di masa depan?").

**Hasil (cutoff 2025-11-24, embargo 90d, N total per h ≈ 222–275 rb obs):**

| h | n_train | n_test | rec_test | AUC refit=prod | Brier refit | Brier prod | overpred prod | n_purged |
|---|---|---|---|---|---|---|---|---|
| 1 | 131,354 | 96,924 | 1.0% | 0.9701 | 0.0079 | 0.0079 | +0.4% | 803 |
| 3 | 129,702 | 95,215 | 2.0% | 0.9386 | 0.0159 | 0.0157 | +1.0% | 2,455 |
| 5 | 128,057 | 93,509 | 2.7% | 0.9186 | 0.0223 | 0.0219 | +1.5% | 4,100 |
| 10 | 123,924 | 89,242 | 4.2% | 0.8855 | 0.0362 | 0.0349 | +2.8% | 8,233 |
| 21 | 114,843 | 79,778 | 6.8% | 0.8407 | 0.0637 | 0.0594 | +5.3% | 17,314 |
| 42 | 97,991 | 61,701 | 11.2% | 0.8018 | 0.1142 | 0.0994 | +10.1% | 34,166 |
| 63 | 81,701 | 43,583 | 14.5% | 0.7811 | 0.1667 | 0.1375 | +15.9% | 50,456 |

**Interpretasi:**
1. **Diskriminasi tetap kuat secara temporal**: AUC OOS murni (dilatih masa
   lalu, diuji masa depan) 0.78–0.97 — sinyal recovery tidak ilusi leakage.
   (AUC refit == AUC prod karena ranking AUC model univariat hanya bergantung
   pada distribusi dd, bukan kalibrasi.)
2. **Kalibrasi produksi menurun di masa depan (overpredict)**, parah pada
   drawdown menengah dan horizon panjang. Contoh h=21 bucket dd 0.05–0.10:
   pred=0.492 vs aktual=0.284 (dev −0.208); dd 0.10–0.15: pred=0.378 vs
   aktual=0.156 (−0.221). `overpred` naik monoton: +0.4% (h=1) → **+15.9%
   (h=63)**.
3. **Purge terbukti perlu**: tanpa purge, ~50 rb observasi h=63 (≈24% train)
   labelnya menembus cutoff — split posisi lama mengkontaminasi test.
4. `n_gap` 46,086/horizon dibuang = konsekuensi embargo 90d: test temporal
   hanya ~36–44% observasi.

**Arti praktis:** probabilitas recovery live saat ini over-optimistic untuk
perpindahan drawdown besar/panjang; P(recover) tidak boleh dibaca sebagai
kalibrasi future-OOS sebelum rekalibrasi (lihat Phase 4: calibration
intercept/slope) atau keputusan F2.5/F2.6.

**Output:** `backend/data/recovery_temporal_eval.json` (refit, production,
n_purged, n_gap per horizon + kalibrasi bucket produksi h=21).

### ✅ Status Implementasi — F2.2 selesai (13 Agustus 2026)

**Script baru:** `backend/_fase2_episodes.py` — dedup overlapping observations
ke **satu observasi per episode drawdown** (`dd>0` run kontigu, dari trailing
peak hingga close kembali ≥ peak).

**Temuan struktural:**
- **275 rb observasi** (F2.1) ternyata hanya **4.605 episode independen** —
  ukuran sampel efektif ~60× lebih kecil dari kelihatannya. Semua CI/AUC
  berbasis observasi-overlap membaca pseudo-repetisi (bukan bukti baru).
- Distribusi durasi episode: 745 episode durasi 1 bar (16%), 410 durasi 2,
  dst; episode terpanjang 336 bar.

**Dua pilihan "observasi representatif" per episode (uji sensitivitas):**

| h | AUC refit (first) | AUC refit (trough) | overpred prod (first) | overpred prod (trough) |
|---|---|---|---|---|
| 1 | 0.772 | 0.974 | −14.1% | −9.0% |
| 5 | 0.773 | 0.980 | −19.0% | −12.8% |
| 21 | 0.775 | 0.957 | −13.3% | −13.2% |
| 63 | 0.753 | 0.947 | −7.0% | −30.3% |

**Interpretasi (penting — koreksi narasi F2.1):**
1. **AUC tahan dedup** (0.75–0.98 tergantung rep): sinyal recovery bukan
   ilusi dari observasi berulang. Rep "trough" (bar dd terdalam) sangat
   diskriminatif karena bertanya "dari titik terparah, apakah kembali ke
   peak" — paling relevan utk model risiko.
2. **Kesimpulan kalibrasi F2.1 berbalik**: produksi bukan overpredict pada
   sampel independen — justru **underpredict** (overpred negatif −7% s/d
   −30%). Overprediksi +5.3%…+15.9% di F2.1 adalah **artefak overlap**:
   episode panjang (label-0 berulang) mendominasi sampel per-observasi.
   Contoh h=21, bucket dd 0.00–0.05 (rep=first): pred 0.635 vs aktual
   0.840 (dev +0.205 = underprediksi) — model meremehkan recovery pada
   awal drawdown karena kebanyakan observasi train berasal dari episode
   yang gagal pulih.
3. **Pengambilan keputusan utk produksi:** P(recover) live sekarang TIDAK
   over-optimistic seperti disimpulkan F2.1; arah bias sebenarnya bergantung
   komposisi drawdown (kalibrasi bersyarat). Rekalibrasi (Phase 4) wajib
   dilakukan pada sampel **episode-independen**, bukan per-observasi.
   Keputusan F2.5/F2.6 (target semantics, DD clamp) juga wajib dievaluasi
   di kerangka episode ini.

**Output:** `backend/data/recovery_episodes_eval_first.json` &
`recovery_episodes_eval_trough.json` (refit dedup, produksi di test dedup,
kalibrasi bucket h=21, stats episode per rep). Produksi TIDAK ditimpa.

### ✅ Status Implementasi — F2.3 selesai (13 Agustus 2026)

**Script baru:** `backend/_fase2_bootstrap.py` — uncertainty pada struktur
dependent/clustered (bukan IID), sesuai keputusan user.

**Desain:**
- **Level 1 (PRIMARY CI) — stock-cluster bootstrap**: unit resampling =
  SAHAM (dengan replacement) → seluruh episode stock terpilih dipertahankan
  → REFIT logistic `logit(P_h)=a_h+b_h·DD` → hitung AUC/Brier/beta/alpha.
  Distribusi `(a^b_h, b^b_h)` mencakup parameter estimation + sampling
  uncertainty. **TIDAK** sampling episode IID; **TIDAK** bootstrap angka final.
- **Level 2 (SENSITIVITY) — episode-block within-stock**: per saham resample
  episode miliknya sendiri (komposisi stock tetap, dependence intra-stock
  diguncang) → CI pembanding.
- **OOB (out-of-bootstrap)**: model yg difit di saham terpilih dievaluasi di
  episode dari saham yang TIDAK terpilih — menjawab "apakah bias kalibrasi
  konsisten across stocks?" (in-sample cal slope/intercept = tautologi,
  tidak dilaporkan sbg bukti).

**Hasil (B=1000, B_within=500, seed=42):**

| h | rep | AUC point | AUC OOB CI | β point | P(β<0) | overpred OOB CI |
|---|---|---|---|---|---|---|
| 1 | trough | 0.934 | [0.921, 0.946] | −29.4 | 100% | [−0.025, +0.025] |
| 1 | first | 0.836 | [0.818, 0.853] | −31.6 | 100% | [−0.027, +0.028] |
| 21 | trough | 0.953 | [0.944, 0.961] | −13.8 | 100% | [−0.021, +0.022] |
| 21 | first | 0.871 | [0.856, 0.886] | −22.1 | 100% | [−0.023, +0.025] |
| 63 | trough | 0.935 | [0.923, 0.948] | −10.3 | 100% | [−0.020, +0.020] |
| 63 | first | 0.877 | [0.861, 0.892] | −13.4 | 100% | [−0.019, +0.023] |

OOB cal_slope CI ≈ [0.81, 1.25] (mencakup 1); OOB cal_intercept CI ≈
[−0.39, +0.34] (mencakup 0) di semua horizon. Level 2 (within-stock): CI
hampir identik & sedikit lebih sempit drpd Level 1 (variance dominan antar
saham, tapi kecil).

**Interpretasi:**
1. **`β<0` ROBUST**: 100% replicate (semua horizon, kedua rep) → hubungan
   drawdown→recovery monoton negatif adalah bukti cross-stock yang kuat.
   Tidak ada saham individual yang membalikkan arah.
2. **AUC stabil & CI sempit** (±1–2pp), dan OOB ≈ in-sample → diskriminasi
   model bukan artefak saham tertentu.
3. **Kalibrasi: BELUM ADA bukti cross-stock utk rekalibrasi**. CI OOB dari
   bias kalibrasi (overpred/underpred) MENCANGKUP NOL di semua horizon —
   underprediksi yg terlihat di F2.2 (mis. dd 0–5%: pred 0.635 vs aktual
   0.840) TIDAK konsisten across stocks; bisa jadi didorong segelintir
   saham. **Keputusan F2.5/F2.6/Phase 4 DITAHAN** (sesuai instruksi):
   belum cukup evidence cross-stock utk rekalibrasi agresif.
4. Implikasi utk produksi: arah model aman, magnitude probabilitas masih
   perlu treatment kalibrasi nanti, tapi TIDAK mendesak & TIDAK boleh
   dilakukan dengan asumsi bias global.

**Output:** `backend/data/recovery_bootstrap_trough.json` &
`recovery_bootstrap_first.json` (point, CI stock-cluster, OOB, within-stock,
stock_stats per horizon + draws mentah utk h=1/21/63). Produksi TIDAK ditimpa.

### ✅ Status Implementasi — F2.4 selesai (13 Agustus 2026)

**Script baru:** `backend/_fase2_shrinkage.py` — mengganti HARD SWITCH
`n_events >= 5` di jalur sinyal produksi (recovery.py) dgn SHRINKAGE
empirical Bayes (Beta-Binomial).

**Masalah hard switch lama:**
- Rate mentah k/n utk n kecil sangat noisy (n=5: 2/5 vs 4/5 = beda 40pp);
  utk n sedikit sering ekstrem (0 atau 1) padahal populasi ~60%.
- Diskontinuitas tajam: n=4 → fallback model global, n=5 → rate mentah.
- Fallback model targetnya prior high, sinyal utama target previous close
  → saat switch, target berganti diam-diam.

**Solusi F2.4:**
- Prior Beta per (bucket drop × horizon) diestimasi OFFLINE dari train
  (cutoff 2025-11-24, purge date_e<=cutoff, embargo 90 hari):
  p0 = pooled rate antar-saham; m0 (pseudo-count) dari overdispersion:
  m0 = n̄/(overdisp−1)−1, clamp [1, 500]. Bucket drop = grid
  [2-3, 3-4, 4-5, 5-6.5, 6.5-8, 8-10, 10-13, 13-20]% (cakupan
  auto_drop_pct produksi 2.5σ clamp [2,13]); bucket < 20 saham → prior
  tetangga terdekat / global.
- Runtime produksi: `p_signal = (k + a0)/(n + a0 + b0)`, kontinu thd n;
  n=0 (tanpa event) → fallback model global (target prior peak, status quo);
  file params hilang → perilaku lama dipertahankan (backward compatible).
- Bucket p0 = 0.583 (d=5-6.5%, h=21) dengan m0 = 500 (homogen antar-saham
  di bucket ini → prior kuat) vs m0 global 9.39 (heterogen → prior lemah).

**Evaluasi OOS (test temporal, embargo 90, Brier tertimbang n_te):**

| h | Brier baseline (hard switch) | Brier shrinkage | MAD baseline | MAD shrinkage |
|---|---|---|---|---|
| 1 | 0.0465 | 0.0431 | 0.1596 | 0.1547 |
| 3 | 0.0850 | 0.0775 | 0.2281 | 0.2179 |
| 5 | 0.1009 | 0.0862 | 0.2498 | 0.2310 |
| 10 | 0.1111 | 0.0932 | 0.2692 | 0.2482 |
| 21 | 0.1041 | 0.0859 | 0.2561 | 0.2338 |
| 42 | 0.0999 | 0.0816 | 0.2481 | 0.2300 |
| 63 | 0.1417 | 0.1250 | 0.3042 | 0.2898 |

Shrinkage menang di SEMUA horizon (Brier −7% s/d −17%, MAD −5% s/d −9%);
h=21 (horizon sinyal) Brier 0.104 → 0.086 (−17%). Prior m0 ~4-9 pseudo-count
→ efektif utk saham dgn sedikit event, hampir tanpa efek utk saham dgn
banyak event (w = n/(n+m0) → 1).

**Perubahan produksi:** `config.py` (+RECOVERY_SHRINKAGE_PARAMS_FILE),
`recovery.py` (+_load_shrinkage_params, _shrunk_rate, blok sinyal baru:
basis `"empiris shrinkage (N event + prior beta-binomial)"`, p_min tetap
0.68 krn target previous close; fallback model → 0.5 krn target prior high;
exit_plan target = previous close utk shrinkage, prior high utk model —
konsisten dgn basis startswith("model") yg sudah ada). Field API tidak
berubah (empirical rate mentah tetap dilaporkan).

**Verifikasi:** test_api.py PASS semua; tsc --noEmit exit 0.

**Output:** `backend/data/recovery_shrinkage_params.json` (prior per
bucket+horizon, eval per bucket & agregat, kalibrasi shrinkage).
`recovery_model_params.json` TIDAK ditimpa.

### ✅ Status Implementasi — Dampak sinyal F2.4 (13 Agustus 2026)

Simulasi jalur produksi utk 879 saham (min bars 150) — `_fase2_shrinkage_impact.py`:

| Metrik | Baseline (hard switch) | F2.4 (shrinkage) |
|---|---|---|
| Basis empiris aktif | 561 (64%) | 818 (93%) |
| Model fallback (n=0) | ~318 | 61 (7%) |
| POTENTIAL | 202 (23%) | 117 (13%) |
| Flip POTENTIAL→WATCH | — | 124 (110 empiris, 14 model) |
| Flip WATCH→POTENTIAL | — | 39 (semua dari model) |
| Δp mean (sd) | — | +0.135 (0.266) |

- **110 flip POTENTIAL→WATCH = koreksi yang diinginkan**: rate mentah 1.000
  dgn n=5-8 (TRGU, AMMN, BCIC, BBCA, ...) kini 0.52-0.63 — persis kasus
  over-optimism yang memotivasi F2.4.
- **39 flip WATCH→POTENTIAL = perubahan target yang eksplisit**: semuanya
  berasal dari fallback model (target prior high, p≈0.00-0.03) yang kini
  dapat shrinkage (target previous close, p≈0.81-0.87) — saham super-volatile
  (drop 13%/hari) yang recovery ke close kemarin dalam 21 hari memang
  berkemungkinan tinggi; ini bukan bug, tapi konsekuensi pemisahan target.
- **Catatan diskriminasi**: AUC per-saham test = 0.51 utk baseline, shrinkage,
  DAN pooled-only (target previous close) — rate per-saham hampir tidak
  membedakan antar-saham. Yang punya daya pisah kuat adalah model
  dd_fraction (AUC 0.93-0.95, target prior high). Brier shrinkage unggul
  karena menekan noise (mendekati pooled yang stabil), bukan karena menambah
  diskriminasi. Implikasi desain: utk ranking antar-saham, model dd_fraction
  tetap aset utama; shrinkage memperbaiki LEVEL probabilitas sinyal.

### ✅ Status Implementasi — F2.5 & F2.6 selesai (13 Agustus 2026)

**F2.5 — Separate recovery target semantics (tanpa mengubah probabilitas):**
- Problem: sinyal memakai DUA target dengan threshold berbeda —
  shrinkage/empiris → previous close (p_min 0.68), fallback model → prior
  high (p_min 0.5). Konsumen API tidak bisa tahu target sinyal saat ini.
- Fix: field `target: "previous_close"` ditambahkan di tiap elemen
  `empirical[]`, dan field baru `signal_target: "previous_close" |
  "prior_high"` di response (set sesuai basis sinyal). API kompatibel
  (field baru opsional, default None).
- Hasil: konsumen API dapat membedakan makna P(recovery) tanpa menebak
  dari basis string.

**F2.6 — Re-evaluate DD clamp (keputusan: PERTAHANKAN 0.85):**
- Hanya 2.713/276.881 (0.98%) observasi dd yang > 0.85; q99 raw = 0.8481,
  max = 0.976. Clamp hampir tidak aktif — ekor atas datar.
- Sensitivitas refit temporal h=21 (clamp 0.85 vs 0.95 vs 1.00): parameter
  identik (a=0.8206, b=−9.16), AUC_te=0.8407, Brier_te=0.0637 utk ketiga
  skenario → clamp 0.85 tidak menghilangkan informasi yang material.
- Keputusan: pertahankan RECOVERY_MODEL_DD_CLAMP=0.85 (stabilitas numerik
  logit utk dd ekstrem tetap terjaga tanpa biaya kalibrasi).
- Output: `backend/data/recovery_dd_clamp_eval.json`.

**Perubahan produksi F2.5:** `api.py` (+target di RecoveryEmpirical,
+signal_target di RecoveryResponse), `recovery.py` (isi field). Verifikasi:
test_api.py PASS semua, tsc --noEmit exit 0, smoke test BBCA
(signal_target=previous_close, empirical[0].target=previous_close).

---

## Phase 3 — RTF validation

- [x] Implement true walk-forward threshold validation.
- [x] Test density thresholds in train only.
- [x] Test heavy-volume threshold in train only.
- [x] Test decay parameters in train only.
- [x] OOS evaluate strength.
- [x] Compare simple baselines.
- [x] Run ablation studies.

### ✅ Status Implementasi — Fase 3 selesai (15 Agustus 2026), eval-only

**Skrip (semua `_phase3_rtf_*.py`, produksi TIDAK diubah):**
- `_phase3_rtf_common.py` — evaluator per-baris historis (mirror `detect_accumulation`
  produksi persis: event +10% raw close, double-event anchor gap≤20, heavy baseline
  post-event mean → fallback pre-event 20d → fallback RVOL20, gates below/above_ma/
  likuiditas ADV20 point-in-time/min_heavy, `strength = density × (ndh|0.5) × decay`,
  decay `exp(-d/τ)` cutoff d≥5), label multihorizon (5/10/21/63) censor-aware,
  split walk-forward global, metrik lift/AUC/precision@K, bootstrap CI stock-cluster.
- `_phase3_rtf_wf.py` — tuning sequential & freeze (acceptance user #3):
  `density → heavy_rvol → min_heavy → decay_tau → decay_cutoff`, pemilihan HANYA di TRAIN.
- `_phase3_rtf_baseline.py` — baseline OOS: random, momentum 5d, momentum 10d, density-only.
- `_phase3_rtf_ablation.py` — ablasi gates & komponen strength (OOS).

**Protokol (acceptance user #1–#5):** cutoff global = quantile 0.70 → **tanggal absolut
`2026-01-23`**; purge horizon label maksimum 63 (sinyal train yang forward window
menembus cutoff dikeluarkan); embargo 90 hari kalender (test mulai `2026-04-23`);
train 206.280 baris / test 63.795 / gap 94.943; OOS tidak pernah dipakai memilih
konfigurasi; near-tie (tol lift 0.05, AUC 0.01) → prefer default (stabil/sederhana).

**Hasil tuning (TRAIN, metrik b10 horizon-10):**

| Dimensi | Grid | Pemenang | Catatan |
|---|---|---|---|
| density | 20/25/30/35/40/50 | **50.0** | lift 2.772 vs default 2.631 (n=1.673) |
| heavy_rvol | 1.5/1.75/2.0/2.5/3.0 | **2.0 (default)** | near-tie: 2.812 vs 2.772 (Δ0.040≤0.05) |
| min_heavy | 1/2/3 | **2 (default)** | 2.772 vs 2.772 (seri) |
| decay_tau | 1.0/1.5/2.0/3.0 | **2.0 (default)** | near-tie AUC: 0.5155 vs 0.514 (Δ0.001) |
| decay_cutoff | None/5/7/10 | None (AUC 0.5247 vs 0.514) | Δ0.011 > tol 0.01 |

**OOS (parameter frozen — pembandingan winner vs default):**

| Konfigurasi | n | b10 h10 | lift | b10 h21 | AUC(up1_21) |
|---|---|---|---|---|---|
| winner (density 50, cutoff None) | 366 | 0.1961 | 2.735 | 0.2656 | **0.3706** |
| **default produksi** (density 30, cutoff 5) | 872 | 0.1980 | 2.762 | 0.2804 | **0.4352** |

→ **Default produksi lebih robust di OOS** (lift & AUC lebih tinggi, n 2,4× lebih besar).
Tuning density 50/cutoff None overfit train; rekomendasi: **pertahankan default**.

**Baseline OOS (b10 h10):** kontrol 0.0717 (n=50.381) · random 0.0713 · **momentum 5d
0.2338** · **momentum 10d 0.2516** · density-only 0.1914 (n=619) · winner 0.1961.
→ Sinyal RTF punya edge nyata vs kontrol/random (lift ≈2,7×), namun baseline momentum
sederhana (top-N ret 5/10 hari) mengungguli — subset berbeda; kombinasi RTF+momentum
belum dieksplorasi (masuk Phase 5).

**Ablasi gates (OOS):** full n=306 b10 0.1961 · no_above_ma 0.2037 (gate MA sedikit
merugikan) · no_liq 0.1868 (gate liq membantu) · **no_below 0.3531 lift 4,92** (sinyal
di atas level event — sudah breakout — jauh lebih tinggi, tapi di luar mandat "beli di
konsolidasi") · mh_1 0.1946 (min_heavy 2 vs 1 nyaris sama).

**Ablasi strength (AUC up1_21, OOS, arm full):** full 0.3706 · density_only **0.4250** ·
ndh_only 0.3892 · decay_only 0.4111. → **perkalian density×ndh×decay justru menurunkan
ranking vs density-only** (berlawanan dengan klaim §35 Empirical lama; lihat koreksi).

**Output:** `backend/data/phase3_rtf_rows.npz` (+meta), `phase3_rtf_tune.json`,
`phase3_rtf_oos.json`, `phase3_rtf_baseline.json`, `phase3_rtf_ablation.json` —
masing-masing memuat `selection_metadata` (cutoff_date absolut, purge_horizon,
embargo_days, train/oos_signal_count, parameter_selection_order, default_config,
selected_config) dan `train_metrics` per kandidat.

> **Phase 3 selesai — eval-only — recommended configuration pending user acceptance.**
> Rekomendasi sementara: pertahankan config produksi (density 30, heavy 2.0, min_heavy 2,
> tau 2, cutoff 5); tuning tidak menghasilkan perbaikan OOS yang meyakinkan.

### ✅ Verdict user — 15 Agustus 2026 (dibaca kritis, bukan auto-ACCEPT)

**Keputusan:**
- ✅ **Phase 3 PASS — validation completed** (research process diterima).
- ❌ **No parameter promotion** — winner tuning (density 50, cutoff None) TIDAK di-promote.
- ✅ **Production config retained** — density 30, heavy 2.0, min_heavy 2, tau 2.0, cutoff 5,
  **UNCHANGED**. Alasan: bukan "30 terbukti optimal", tetapi **tidak ada evidence OOS yang
  cukup kuat untuk membenarkan perubahan dari default**.

**Alasan metodologis:**
1. **Default ≈ tuned di OOS** (Δ b10 hanya 0.2 pp: 0.198 vs 0.196) sementara default punya
   ~2,38× lebih banyak sinyal (872 vs 366) → tidak ada alasan empiris mengganti config.
2. **Selection noise:** konfigurasi dipilih di TRAIN; literatur backtest overfitting
   (White; Bailey/López de Prado) — makin banyak alternatif yang dicoba lalu dipilih,
   makin tinggi peluang "winner" hanyalah noise. **22 sequential candidates cukup;
   TIDAK dibuka Cartesian 6×5×3×4×4=1440.**
3. **density 50 = textbook in-sample improvement yang tidak bertahan OOS** → justru
   validasi bahwa protokol Phase 3 bekerja (mencegah auto-promotion yang salah).
4. **heavy 2 / min_heavy 2 / tau 2 dipertahankan** (default & near-tie) — tetap
   interpretable: 2× heavy volume, 2 heavy days, τ=2.
5. **Limitation objective tuning:** `lift_b10` = kemampuan mengidentifikasi top event
   incidence (event-ranking objective), **BUKAN trading expectancy**. Pemenang parameter
   hanya boleh disebut "best in-sample event-ranking candidate under predefined b10
   objective". Sebelum trading: TP_FIRST, SL_FIRST, TIMEOUT, expectancy, MAE/MFE,
   transaction cost, slippage harus diuji terpisah (Phase 4/5 lanjutan).
6. **Temuan utama = momentum mengalahkan RTF** (M5 23.4%, M10 25.2% vs RTF 19.6–19.8%
   pada b10 h10): RTF punya lift ≈2,7× vs random (≈7,1%) — bukan noise — tetapi **belum
   membuktikan incremental predictive power terhadap simple momentum**.
7. **AUC 0.371 (strength→up1_21, OOS) dibaca hati-hati:** ranking "berlawanan" dengan
   outcome (bukan "tidak informatif"). TAPI inverse relationship **TIDAK stabil**
   (lihat diagnostic di bawah) → **jangan membalik strength ke 1−strength** (post-hoc
   tuning berbasis OOS). Orientasi baru hanya boleh diuji sebagai hypothesis setelah
   stabilitas lintas TRAIN/OOS/stock/regime terbukti — dan ternyata tidak terbukti.
8. **Gate `below` costly untuk raw predictive rate** (tanpa below: b10 35,3% vs 19,6%)
   tetapi mengubah target strategy: tanpa gate model menangkap *breakout continuation*,
   bukan *pre-breakout accumulation/consolidation*. BUKAN bug; indikasi **dua strategy
   regimes** (A. pre-breakout/accumulation, B. breakout continuation) yang berpotensi
   menjadi dua signal type terpisah di Phase 5.

**Diagnostic stabilitas orientasi strength (15-08-2026, `_phase3_rtf_diag.py`, read-only):**

| Aspek | Hasil | Kesimpulan |
|---|---|---|
| TRAIN vs OOS, full→up1_21 | train **0.5247** (positif) vs OOS **0.3706** (inverse) | TIDAK stabil — inverse hanya OOS |
| TRAIN vs OOS, full→b10_21 | train 0.5667 vs OOS 0.5073 (positif keduanya) | stabil positif; inverse tidak berlaku utk b10 |
| full→b10_10 | train 0.55 vs OOS 0.5511 | stabil |
| Per-kuartal (proxy regime) | osilasi 0.43–0.57 tanpa pola inverse konsisten; density-only lebih stabil (0.50–0.54) | tidak ada regime dgn inverse konsisten |
| Per-kode, arm DEFAULT (n≥20) | 53–62 kode; median ≈ 0.500; frac_inverse ≈ frac_positif (0.48–0.50) | ranking intra-stock ≈ acak, bukan terbalik |
| Per-kode, arm density-50 | hanya 1 kode memenuhi n≥20 | tak dapat dievaluasi (data tipis) |

→ **Kesimpulan:** AUC 0.371 adalah artefak kombinasi (a) konfigurasi winner yang
overfit, (b) target up1 (pump cepat) yang karakternya beda dengan b10, (c) OOS pendek.
Strength **tidak** "terbalik secara inheren"; per-saham ia mendekati random (0.50).
**Hypothesis "inverse strength" TIDAK dilanjutkan.**

**Finding utama Phase 3 (final):**
1. Default ≈ tuned di OOS; default lebih robust + 2,38× signal coverage.
2. Momentum 5/10 lebih kuat daripada current RTF terhadap b10.
3. RTF tetap punya positive lift vs random (≈2,7×).
4. Strength ranking saat ini misaligned thd up1 di OOS tapi TIDAK stabil; ~random per-saham.
5. Removing `below` gate menaikkan predictive rate tetapi mengubah target strategy.
6. No config change justified.

## Phase 4 — Probability quality (checklist final user, 15 Agustus 2026)

**Prinsip:** Phase 4 = *probability quality audit + optional minimal recalibration*,
BUKAN model improvement. Evaluasi mengikuti calibration hierarchy
(calibration-in-the-large → intercept/slope → flexible curve → conditional),
semua diukur terhadap **production probability path** (logistic + shrinkage),
per **target × horizon**, dengan PIT integrity.

- [x] **P4.0 Freeze probability-quality evaluation protocol**
  - [x] Freeze target semantics per `signal_target`
  - [x] Freeze horizons
  - [x] Freeze production probability source/version
  - [x] Freeze episode representation
  - [x] Freeze chronological split + purge/embargo
  - [x] Freeze regime definition
  - [x] Freeze base-rate reference methodology
  - [x] Freeze bootstrap methodology
  - [x] Freeze acceptance criteria
  - [x] Record protocol metadata

### ✅ P4.0 selesai — protocol frozen (15 Agustus 2026) → `backend/data/phase4_protocol.json`

**Target dipisah per `signal_target` (F2.5):** `previous_close` (empirical +
shrinkage beta-binomial, drop frozen 5.0%) vs `prior_peak` (logistic drawdown
global, dd = clip(1−close/peak,0,0.85), peak lookback 252). **Horizons** [1,3,5,10,21,42,63].
**Version:** `recovery_shrinkage_params.json` (sha `d329fe1662b12f24`,
2026-08-13) & `recovery_model_params.json` (sha `abd9cedced0bae47`, 2026-08-12).
**Split:** konsisten Phase 3/F2.1 — cutoff absolut `2026-01-23`, purge horizon 63,
embargo 90 → dev = ≤cutoff (purged), validation = `2026-04-23`→akhir (dibuka Phase 3;
bukan final holdout). **Regime:** `regime.py regime_series` (ADX14<20 sideways;
close>SMA200 bull else bear; PIT-safe). **Base rate:** climatology dev per
(target,horizon), dilarang pakai validation prevalence. **Bootstrap:** stock-cluster
B=1000 seed=42 (primary), date-block B=500 seed=7 (sensitivity). **Acceptance:**
CI intercept ∋ 0, CI slope ∋ 1, BSS>0, curve tanpa deviation material di p≈0.68/0.5,
robust; INCONCLUSIVE bila CI lebar; HL test dilarang; ECE optional. **P4.7** hanya
bila miscalibration material; logistic intercept-only→intercept+slope; isotonic
sensitivity only; calibration window = 126 hari terakhir dev.

- [x] **P4.1 Audit frozen production probabilities**
  - [x] Verify point-in-time probability generation
  - [x] Separate evaluation by target and horizon
  - [x] Report n_stocks / n_episodes / n_events / n_non_events
  - [x] Report mean predicted probability
  - [x] Report observed event rate

### ✅ P4.1 selesai — audit production probability (PIT, `_phase4_p41_audit.py` → `phase4_p41_audit.json`)

Probabilities = persis jalur produksi (bukan model baru): `previous_close` =
empirical + shrinkage beta-binomial (PIT: n/hit dihitung hanya atas event yang
window-nya lengkap SEBELUM event t); `prior_peak` = logistic drawdown global.
Split dev/validation sesuai protocol. Hasil O/E (observed/expected) per horizon:

**prior_peak (logistic global) — dev agak underestimate, validation OVERESTIMATE:**

| h | dev O/E | validation O/E | val n |
|---|---|---|---|
| 1 | 1.04 | 0.73 | 64502 |
| 5 | 1.11 | 0.66 | 61087 |
| 21 | 1.18 | 0.49 | 47356 |
| 63 | 1.20 | 0.37 | 11161 |

**previous_close (shrinkage) — underestimate di dev (s/d 2.3×), bervariasi di val:**

| h | dev O/E | validation O/E |
|---|---|---|
| 1 | 2.34 | 2.06 |
| 10 | 1.34 | 1.28 |
| 21 | 1.29 | 1.23 |
| 63 | 1.18 | 0.85 |

**Interpretasi:** kedua target punya deviasi material dari observed — arahnya
berlawanan antar target, dan utk `prior_peak` memburuk parah di validation
(periode 2026-04→08 market belum pulih → recovery rate anjlok; model overestimate).
Validation pendek (h63 val n=11k vs dev 131k). Ini **menuntun ke P4.2 (slope/
intercept) & P4.6 (regime)**: dugaan sementara bukan global slope≠1 murni, tapi
pergeseran base-rate antar periode/regime. Dilarang menyesuaikan apa pun dari
validation sebelum P4.2–P4.4 kuantifikasi selesai.

- [x] **P4.2 Global calibration** (`_phase4_p42_calib.py` → `phase4_p42_calib.json`)
  - [x] Calibration-in-the-large / intercept
  - [x] Calibration slope
  - [x] 95% confidence intervals (asymptotic; cluster bootstrap di P4.5)
  - [x] Observed/Expected ratio
  - [x] No Hosmer-Lemeshow as primary test

### ✅ P4.2 selesai — prior_peak hampir calibrated di dev, overestimate di validation; previous_close underestimate konsisten

**prior_peak (logistic):** dev: intercept +0.03…+0.35, slope 0.90–0.96 (sedikit
underestimate, CI slope eksklusif <1 utk h≥3). Validation: intercept **negatif
signifikan** (−0.45…−1.37, CI eksklusif 0) dan slope >1 (1.17–1.65 utk h≥21) →
**overestimate material di validation**. Bukan slope≠1 global — pola konsisten
dengan pergeseran base-rate antar periode (lihat P4.6).

**previous_close (shrinkage):** dev: intercept positif (0.12–4.19) →
underestimate signifikan; slope tidak stabil antar horizon (0.59–4.93, CI lebar)
karena variasi logit(p̂) per saham kecil → fit noise. Validation: intercept
positif utk h1–h10 (CI eksklusif 0 utk h1), ≈0 utk h21/h42, negatif h63 (n kecil).

- [x] **P4.3 Flexible calibration / reliability** (`_phase4_p43_curve.py` → `phase4_p43_curve.json`)
  - [x] Smooth calibration curve (isotonic + grid 101)
  - [x] 95% CI (Wilson per quantile bin)
  - [x] Identity reference line
  - [x] Quantile-bin diagnostic table (20 bin)
  - [x] Calibration near production probability threshold
  - [x] ECE optional diagnostic only

### ✅ P4.3 selesai — region produksi: prior_peak p~0.5 h21: dev +0.07 (ok), validation −0.16 (material); previous_close p~0.68 h21: dev +0.07, val +0.05

Region sinyal (h=21): prior_peak p≈0.50 → acc 0.572 vs conf 0.499 (dev, sedikit
underestimate) tapi acc 0.335 vs conf 0.498 di validation (overestimate 16pp —
**material**). previous_close p≈0.68 → acc 0.708 vs conf 0.634 (dev) & 0.683 vs
0.634 (val) — underestimate kecil konsisten (n region kecil: 72/41). ECE: dev
prior_peak 0.015–0.077 (baik), h63 validation 0.192 (parah); previous_close ECE
0.13–0.18 semua split (buruk).

- [x] **P4.4 Proper probabilistic scoring** (`_phase4_p44_scores.py` → `phase4_p44_scores.json`)
  - [x] Brier Score
  - [x] Brier Skill Score vs pre-specified base-rate forecast (climatology DEV, BUKAN test prevalence)
  - [x] Brier decomposition: reliability / resolution / uncertainty
  - [x] Log Loss

### ✅ P4.4 selesai — previous_close BSS NEGATIF vs climatology (lebih buruk dari base-rate konstan); prior_peak BSS positif

**previous_close:** BSS dev −0.10…−0.16, validation −0.07…−0.10 (h1–h21) —
production shrinkage probabilities **lebih buruk dari sekadar climatology dev**.
Decomposition: loss didominasi REL (0.23–0.50) bukan RES (0.01–0.03) →
miscalibration, bukan kurang resolusi. **prior_peak:** BSS dev +0.16…+0.26,
validation +0.28…+0.51 — skill discrimination positif robust. LogLoss mengikuti.

- [x] **P4.5 Uncertainty / dependence** (`_phase4_p45_uncertainty.py` → `phase4_p45_uncertainty.json`)
  - [x] Stock-cluster bootstrap (primary, konsisten F2.3) — B=1000, seed=42, tanpa refit
  - [x] 1000+ bootstrap replicates
  - [x] CI untuk intercept / slope / Brier / BSS / O-E
  - [x] Optional date-block bootstrap sensitivity — B=500, seed=7, block 10 hari
  - [x] Report effective stock/episode counts

### ✅ P4.5 selesai — CI mengonfirmasi keputusan P4.4; date-block menunjukkan base rate time-varying

Cluster CI: previous_close BSS CI eksklusif negatif di dev (h1–h63) dan val
(h1–h21); prior_peak BSS CI eksklusif positif di kedua split; validation
intercept prior_peak CI eksklusif <0 (semua h). Date-block dev CI sangat lebar
(O/E 0.53–1.24 prior_peak) → base rate berfluktuasi antar blok tanggal; cluster
CI prior_peak dev O/E ∋ 1 (h1–h21) tapi val eksklusif <1.

- [x] **P4.6 Regime calibration** (`_phase4_p46_regime.py` → `phase4_p46_regime.json`)
  - [x] Evaluate predefined/PIT-safe regimes (ADX14<20 sideways; close>SMA200 bull; else bear)
  - [x] Report calibration per regime
  - [x] Report Brier/BSS per regime
  - [x] Flag insufficient-sample regimes (INSUFFICIENT, bukan forced conclusion)
  - [x] Do not tune regime definitions from results

### ✅ P4.6 selesai — deviasi antar regime MATERIAL: bull over-predicts, bear under-predicts (dev); validation bear parah

**prior_peak dev:** sideways O/E 0.53–0.95 (h≤21), bull 1.20–1.38 (overestimate),
bear 0.25–0.75 (underestimate) → spread 0.25 vs 1.38 antar regime. **Validation:**
bear 0.18–0.22, sideways 0.34–0.38, bull 0.84–1.00 (bull hampir well-calibrated).
BSS positif di semua regime (discrimination baik). **previous_close:** BSS negatif
di hampir semua regime × split (konsisten P4.4/P4.5); val h63 semua regime
INSUFFICIENT (n<500). Regime definitions TIDAK diubah dari hasil ini.

- [x] **P4.7 Conditional recalibration** (`_phase4_p47_recalib.py` → `phase4_p47_recalib.json`)
  - [x] Only execute if material miscalibration is demonstrated (P4.1–P4.6: ya, material)
  - [x] Separate temporal calibration window (126 trading hari terakhir dev, purged)
  - [x] Test intercept-only recalibration
  - [x] Test intercept+slope recalibration
  - [x] Compare against frozen production probability
  - [x] Do not use final holdout for calibration selection
  - [x] Isotonic only as optional sensitivity experiment

### ✅ P4.7 selesai — rekomendasi: intercept-only utk previous_close h1–h21; M0 frozen tetap utk sisanya

Eval di validation (Brier | O/E | ECE):

| target | h | M0 frozen | M1 intercept | M2 int+slope | M3 regime-int | M4 isotonic | pilih |
|---|---|---|---|---|---|---|---|
| previous_close | 1 | 0.193 / 2.06 / 0.121 | 0.178 / 1.03 / 0.031 | 0.178 / 1.02 / 0.034 | 0.178 / 1.01 / 0.029 | 0.178 / 1.01 / 0.022 | M4 (M1≈) |
| previous_close | 3 | 0.267 / 1.53 / 0.151 | 0.244 / 0.98 / 0.028 | 0.244 / 0.99 / 0.026 | 0.244 / 0.96 / 0.032 | 0.244 / 0.98 / 0.020 | M4 (M1≈) |
| previous_close | 5 | 0.275 / 1.45 / 0.164 | 0.248 / 0.96 / 0.031 | 0.248 / 0.96 / 0.029 | 0.249 / 0.95 / 0.032 | 0.248 / 0.96 / 0.026 | M2 (M1≈) |
| previous_close | 10 | 0.244 / 1.28 / 0.145 | 0.224 / 0.97 / 0.028 | 0.224 / 0.97 / 0.033 | 0.225 / 0.96 / 0.033 | 0.224 / 0.97 / 0.028 | M1 |
| previous_close | 21 | 0.215 / 1.23 / 0.134 | 0.200 / 0.94 / 0.050 | 0.200 / 0.94 / 0.050 | 0.204 / 0.93 / 0.060 | 0.200 / 0.93 / 0.052 | M4 (M1≈) |
| previous_close | 42 | 0.181 / 1.11 / 0.077 | 0.182 / 0.90 / 0.083 | 0.182 / 0.90 / 0.082 | 0.187 / 0.90 / 0.088 | 0.183 / 0.90 / 0.086 | M0 |
| previous_close | 63 | 0.243 / 0.85 / 0.112 | 0.295 / 0.72 / 0.255 | 0.294 / 0.72 / 0.252 | 0.301 / 0.71 / 0.262 | 0.295 / 0.72 / 0.255 | M0 |
| prior_peak | semua | — | semua transformasi LEBIH BURUK di validation | — | — | — | **M0 semua h** |

**Rekomendasi:** (1) previous_close h1–h21 → **M1 intercept-only** (sederhana,
stabil, selisih <0.001 dgn M2/M4; isotonic bukan kandidat produksi per protokol);
(2) previous_close h42/h63 → **pertahankan M0** (recalibration menurunkan
kualitas; O/E M0 sudah dekat 1); (3) **prior_peak semua h → pertahankan M0**
(recalibration semua transformasi menaikkan Brier di validation; deviasi =
regime-shift yang tak bisa dikoreksi transformasi statis — dikelola P4.6-aware,
BUKAN recalibration global). **Implementasi produksi MENUNGGU keputusan user.**

- [x] **P4.7b M1 impact audit — read-only, wajib sebelum holdout** (`_phase4_m1_impact_audit.py` → `phase4_m1_impact_audit.json`)

### ✅ P4.7b selesai — M1 aman secara calibration, TAPI gate 0.68 jenuh utk h21/h10 (temuan kritis)

Impact kandidat M1 (intercept-only, c per horizon dari P4.7) pada jalur sinyal
produksi (gate 0.68 → POTENTIAL; produksi TIDAK diubah):

| h | split | POT old→new | flip out (valid hilang) | flip in (valid baru) | netFP | precision | AUC |
|---|---|---|---|---|---|---|---|
| 21 | dev | 0 → 19.285 (100%) | 0 (0) | 19.285 (14.608) | +4.677 | — → 0.7575 | 0.5447 == 0.5447 |
| 21 | val | 0 → 4.892 (100%) | 0 (0) | 4.892 (3.563) | +1.329 | — → 0.7283 | 0.5428 == 0.5428 |
| 10 | dev | 26 → 4.832 (23%) | 0 (0) | 4.806 (3.480) | +1.326 | 0.808 → 0.724 | 0.5706 == 0.5706 |
| 10 | val | 7 → 2.426 (46%) | 0 (0) | 2.419 (1.703) | +716 | 0.571 → 0.704 | 0.5622 == 0.5622 |
| 3 | dev | 0 → 27 | 0 (0) | 27 (20) | +7 | — → 0.741 | 0.6015 == 0.6015 |
| 1,5 | dev/val | 0 → 0 | 0 | 0 | 0 | — | identik |

**Temuan kritis:** (1) M1 monotonic → **AUC & ranking identik** (bukti user), tidak
ada valid POTENTIAL terhapus (c>0 ⇒ p_new≥p_old). (2) Namun intercept positif
besar mengangkat SELURUH distribusi: utk h21, **semua event menembus 0.68** →
gate produksi kehilangan fungsi seleksi (POTENTIAL = 100% populasi); h10 melonjak
23–46%. (3) Precision dev h10 turun 0.808→0.724 (gate longgar), val naik
0.571→0.704. (4) M1 memperbaiki *level* probability (O/E→1, ECE↓, Brier↓ dari
P4.7) — tetapi **bukan koreksi seleksi pada gate 0.68**.

**Implikasi kebijakan:** p_min 0.68 TETAP FROZEN utk holdout (keputusan user).
Gate alternatif BUKAN research question sebelum holdout. Holdout wajib mencatat
operational impact (POTENTIAL/WATCH counts, flips) M0 vs M1 secara paralel.

- [x] **P4.8 Final locked holdout** — metodologi & harness FROZEN (lihat bawah); execution ⏳ WAIT
  - [x] Reserve genuinely untouched future/date block — **TIDAK tersedia saat ini** (status: pending)
  - [x] Apply purge/embargo
  - [x] Freeze methodology before opening holdout
  - [x] Freeze calibration choice / baseline / regime / metric definitions
  - [ ] Run holdout once — **WAIT: genuinely unseen data belum ada**
  - [ ] Report final PASS / FAIL / INCONCLUSIVE — setelah RUN ONCE
  - [x] Bila data untouched tidak tersedia → status **pending genuinely unseen future
        data** (TIDAK membajak Phase 3 OOS yang sudah dibuka)

### ⏳ P4.8 — status: **pending genuinely unseen future data**

### ✅ P4.8 harness siap (15-08-2026) — metodologi frozen, menunggu data

Metodologi lengkap di-freeze (lihat checklist P4.8 di atas): purge/embargo per
horizon (`date_s + h <= tanggal data terakhir`), config FROZEN di
`data/phase4_holdout_config.json` (M1 candidate c per horizon, base-rate reference
climatology dev, seeds B=1000/42 cluster + B=500/7 date-block, p_min 0.68,
acceptance rules 1–8, hash snapshot params produksi), calibration choice M1 h1–21
/ M0 h42–63 & prior_peak / isotonic sensitivity-only. Sisa: **Run holdout once**
dan **Report final PASS/FAIL/INCONCLUSIVE** — WAIT hingga genuinely unseen data.

**Harness:** `backend/_phase4_holdout.py` (read-only; ABORT bila hash params
produksi berubah; INCONCLUSIVE bila n < 300 / n_events < 30 — **project-specific
minimum evidence rule, BUKAN statistical universal minimum**; selftest ditandai
SELF_TEST, bukan bukti). Jalankan:
`python _phase4_holdout.py --cutoff <YYYY-MM-DD data unseen mulai>` → output
`data/phase4_holdout_report.json` (dua layer: probability quality M0 vs M1 +
operational impact POTENTIAL/WATCH/flips/precision/FP + verdict per rule).

**Field wajib per cell di report (supaya INCONCLUSIVE bisa dijelaskan):**
n_total, n_events, n_non_events, n_stocks, n_episodes, ci_width (Brier/BSS/
intercept/slope), p_ref_frozen, mean_p, observed_rate. **Brier decomposition
(REL−RES+UNC) = DIAGNOSTIC only, BUKAN acceptance gate** (estimasi finite-sample
bisa biased — Ferro 2012). Metric utama: Brier, BSS, calibration slope/intercept,
reliability curve. LogLoss dipertahankan (hukuman keras utk p ekstrem yang
sistematis gagal).

**⚠️ Self-test TIDAK PERNAH menjadi evidence P4.8.** Self-test (mode
`--selftest`, output ditandai `SELF_TEST`) hanya membuktikan harness logic
bekerja — bukan model/calibration bekerja. Hasil selftest (mis. h21→FAIL rule 7,
h3→FAIL rule 8, h10→PASS di data dev) adalah artefak verifikasi harness dan
dihapus setelah dipakai; tidak boleh dikutip sebagai hasil holdout.

**M1 = FROZEN CANDIDATE — dilarang diubah setelah holdout dibuka.** Begitu
intercept M1 diubah berdasarkan hasil holdout, holdout selesai menjadi holdout.
Bila M1 ditolak di holdout (saturation/poor calibration) → buat Phase 4.9/5.1
baru dengan data development berikutnya; TIDAK mengutak-atik hasil holdout.

**Run sequence (persis, saat data baru tersedia):**
```text
new genuinely unseen data
        ↓ 1. verify date cutoff
        ↓ 2. verify production parameter hash (harness ABORT otomatis bila berubah)
        ↓ 3. verify no accidental contamination
        ↓ 4. RUN ONCE
        ↓ 5. phase4_holdout_report.json
        ↓ 6. PROMOTE / REJECT / INCONCLUSIVE
```
Setelah RUN ONCE: **dilarang rerun dengan konfigurasi berbeda.** Bila hasil
INCONCLUSIVE, status tetap INCONCLUSIVE — dilarang menggeser cutoff supaya
sample cukup.

**Acceptance rules (dari user, di config):** 1) calibration improvement survives
(O/E lebih dekat 1) · 2) Brier improves · 3) BSS tidak deteriorate (margin 1pp) ·
4) LogLoss tidak materially deteriorate (+0.01) · 5) calibration curve improves
(ECE + max bin diff) · 6) AUC/ranking unchanged (<1e-6, wajib identik utk M1
monotonic) · 7) operational selectivity acceptable (POTENTIAL share ≤ 0.50) ·
8) tidak driven by satu stock/regime (top-1 share < 0.5; n_stocks ≥ 10; regime
tidak collapse). Verdict per h: PASS semua → PROMOTE; ada FAIL → REJECT;
tanpa FAIL tapi INCONCLUSIVE → INCONCLUSIVE. **M1 dipromosikan HANYA bila semua
h1–21 PASS — selectivity jenuh (POTENTIAL ≈ semua saham) = REJECT walaupun
Brier lebih baik.** Base-rate reference TETAP climatology dev (bukan prevalence
holdout).

### 🧾 Keputusan user (15-08-2026) — status final Phase 4

```text
P4.0–P4.7 ✅ completed (research)
P4.7b ✅ M1 impact audit completed (read-only)

previous_close h=1–21:
    M1 (intercept-only / recalibration-in-the-large) = CANDIDATE
    - evidence kuat perbaikan calibration (O/E→1, Brier↓~8%, ECE 0.12–0.16→0.03–0.05)
    - monotonic → AUC & ranking IDENTIK (bukan predictor baru, hanya calibration layer)
    - TIDAK dipromosikan ke production sebelum Final Locked Holdout
    - M0 tetap ACTIVE di production sementara

previous_close h=42–63:
    M0 = KEEP (recalibration terbukti menurunkan kualitas validation)

prior_peak semua h:
    M0 = KEEP (validation miscalibration = regime/base-rate shift, bukan static
    calibration distortion; static calibrator hanya akan cocok dengan validation
    period → TIDAK dijustifikasi)

Isotonic (M4) = sensitivity analysis SAJA, bukan production candidate
    (fleksibilitas berlebih, risiko overfit dgn calibration sample kecil;
     M1 ≈ M4 tanpa kompleksitas non-monotonic)

p_min = 0.68 : TIDAK diubah (frozen utk holdout)
```

**Terminologi (audit history):** M1 = **intercept recalibration /
recalibration-in-the-large** — `logit(p_new) = α + logit(p_old)` — BUKAN "new
probability model". Recovery Engine tidak diubah substantif; yang berubah hanya
calibration layer (bila di-promote).

**Validation set kini berstatus research/evaluation set** (sudah dipakai utk
memilih M1) → bukan final evidence; holdout berikutnya harus genuinely untouched.

### ✅ Acceptance test M1 sebelum promotion (dari user, di-freeze utk holdout)

| Test | Requirement |
|---|---|
| Calibration intercept | membaik |
| Calibration slope | tidak memburuk |
| Brier | membaik |
| BSS | membaik |
| O/E | mendekati 1 |
| Reliability curve | lebih dekat identity |
| AUC | tidak turun |
| Signal count | dilaporkan |
| POTENTIAL/WATCH flips | seluruhnya dicatat |
| Regime behavior | tidak collapse |
| Final holdout | **wajib** |

### Holdout plan (metodologi frozen)

1. **Probability quality:** Brier, BSS (vs climatology dev), calibration
   intercept/slope, reliability, LogLoss — M0 vs M1 (previous_close h1–21),
   M0 only (lainnya).
2. **Operational impact:** POTENTIAL count, WATCH count, READY/ALMOST unchanged,
   recovery signal flips — M0 vs M1 paralel; p_min 0.68 frozen; AUC tidak boleh
   turun; regime behavior tidak collapse.
3. Holdout dibuka SEKALI setelah genuinely unseen data tersedia.

Belum ada blok data masa depan yang genuinely untouched: validation 2026-04-23→
sekarang sudah berulang kali dibuka (Phase 3 OOS + seluruh P4.2–P4.7) sehingga
statusnya temporal validation, bukan holdout. Holdout hanya boleh dibuka SEKALI
setelah metodologi & keputusan kalibrasi (termasuk rekomendasi P4.7) di-freeze.
Tidak ada indikasi data baru tersedia saat ini.

### ✅ Phase 4 — CLEAR (methodology DONE & LOCKED, verdict user 15-08-2026)

**Phase 4 (probability quality) dinyatakan selesai metodologinya.** Tidak ada
reason utk: menambah metric baru; mengubah M1; mengubah `p_min=0.68`; menguji gate
baru; membuka ulang validation; menjalankan calibration method baru. Satu-satunya
pekerjaan tersisa = **genuine Final Locked Holdout (P4.8 execution, RUN ONCE)**.

```text
P4.0 ✅  P4.1 ✅  P4.2 ✅  P4.3 ✅  P4.4 ✅  P4.5 ✅  P4.6 ✅  P4.7 ✅
P4.7b ✅ (M1 impact audit)   P4.8 harness ✅ (frozen + selftest verified)
P4.8 execution ⏳ WAIT (genuinely unseen future data)

Production state (TIDAK ADA perubahan):
    previous_close h1–21 → M0 ACTIVE · M1 = FROZEN CANDIDATE
    previous_close h42/63 → M0
    prior_peak semua h → M0
    p_min = 0.68 → FROZEN
```

**Artefak:** `backend/data/phase4_protocol.json` (P4.0) · `phase4_p41_audit.json` …
`phase4_p47_recalib.json` (P4.1–P4.7) · `phase4_m1_impact_audit.json` (P4.7b) ·
`phase4_holdout_config.json` (frozen) · `backend/_phase4_holdout.py` (harness).
Semua script: `backend/_phase4_*.py`. Hasil holdout akan masuk
`phase4_holdout_report.json` → PROMOTE / REJECT / INCONCLUSIVE.

**Urutan bila data baru tersedia (persis, RUN ONCE):** verifikasi cutoff →
verifikasi hash params produksi (harness ABORT otomatis bila berubah) → verifikasi
no contamination → RUN ONCE → report → verdict. Dilarang rerun dengan konfigurasi
berbeda; INCONCLUSIVE tetap INCONCLUSIVE (tidak menggeser cutoff).

## Phase 5 — RTF × Short-Horizon Return Incremental Value (checklist final user, 15 Agustus 2026)

**Pertanyaan Phase 5:**

> Apakah RTF memberikan informasi tambahan SETELAH kita sudah mengetahui
> short-horizon return M5/M10?

**Bukan:** "bagaimana membuat score baru yang lebih bagus". Karena itu
**tidak ada perubahan production, tidak ada tuning parameter, dan Phase 4
locked holdout TIDAK boleh disentuh.**

**Terminologi:** M5/M10 = **short-horizon return baseline**, BUKAN classic
momentum anomaly — literatur classic momentum memakai horizon jauh lebih
panjang; short-horizon return dapat menunjukkan momentum MAUPUN reversal
tergantung horizon/liquidity.

**Model:** M0 = Momentum5 · M1 = RTF (production definition frozen) ·
M2 = RankAvg(M5, RTF) · M3 = Momentum10 · M4 = RankAvg(M10, RTF).
Random baseline = universe tanggal SAMA + K SAMA (per date, bukan satu
random global). Density-only = DIAGNOSTIC saja (Phase 3: density-only >
full strength di beberapa ranking test), BUKAN M6 production candidate.

### ✅ P5.0 Freeze & Safety Check — PASS (15-08-2026)

- [x] Protocol Phase 5 dibuat → `backend/data/phase5_protocol.json` (FROZEN)
- [x] Production RTF config hash disimpan (config.py sha `85351777724228cb…`)
- [x] Dataset snapshot/hash → `data/phase5_snapshot_universe_ohlcv.npz`
      (sha `284B40C7B92B7C26B823A7C50C477FC6AE553DF250B76423C4C7DD21D0CB8FB2`,
      963 kode, 526.169 rows, 2024-02-26 → 2026-08-13; kolom
      [open, high, low, close, adj, vol]; seri RAW utk M5/M10/label)
- [x] Cutoff date disimpan — `2026-01-23` (global chronological, policy F2/F3)
- [x] Purge horizon disimpan — `21` (max label horizon)
- [x] Embargo disimpan — `90` hari → OOS mulai `2026-04-23`
- [x] Phase 4 holdout boundary disimpan — data setelah 2026-08-13 (belum ada);
      Phase 5 WAJIB pakai SNAPSHOT (bukan live npz) → kontaminasi mustahil
- [x] Phase 4 locked holdout dikecualikan
- [x] M1 recalibration candidate TIDAK dipakai (di luar scope Phase 5)
- [x] `p_min=0.68` tidak disentuh
- [x] `config.py` production tidak akan ditulis (script Phase 5 read-only)
- [x] Verifier: `backend/_phase5_p50_freeze.py` → `data/phase5_p50_check.json`
      **VERDICT: PASS** (snapshot hash OK · config hash OK · nilai RTF config
      OK density=30/heavy=2.0/min_heavy=2/tau=2.0/cutoff=5 · split OK)

**Bila hash berbeda → STOP, jangan lanjut ke P5.1.**

### P5.1 Dataset

- [ ] Build point-in-time dataset (`code, date, close, m5, m10, rtf_score,
      rtf_density, eligible, b10_h10, b10_h21, up1_h21, regime,
      liquidity_group, episode_id`)
- [ ] Pastikan dates nyata
- [ ] Pastikan raw/adjusted policy konsisten (raw utk semua feature & label)
- [ ] Hitung M5 = Close_t/Close_{t-5} − 1
- [ ] Hitung M10 = Close_t/Close_{t-10} − 1
- [ ] Ambil RTF production score (definition frozen; tanpa tuning)
- [ ] Attach labels (b10_h10 = PRIMARY, b10_h21 = SECONDARY, up1_h21 = DIAGNOSTIC)
- [ ] Attach regime (`regime_series` existing; jangan define ulang)
- [ ] Attach liquidity group (ADV20 existing: liquid = adv_vol ≥ 500.000 &
      adv_val ≥ 250.000.000; less-liquid = sisanya eligible; TANPA threshold baru)
- [ ] Exclude Phase 4 locked holdout (otomatis: snapshot berakhir 2026-08-13)
- [ ] Validate no feature > t (tidak ada future feature)
- [ ] Acceptance: tidak ada future feature · tidak ada locked-holdout row ·
      tidak ada duplicate code/date

### ✅ P5.1 Dataset — PASS (15-08-2026)

- [x] Build point-in-time dataset (`code, date, open/high/low/close/adj/vol,
      m5, m10, rtf_score, rtf_density, rtf_ready, rtf_anchor, rtf_window, ep,
      b10_h10, b10_h21, up1_h21, regime, liquidity_group, eligible`)
      → `backend/data/phase5_dataset.npz` (hash `F8FC56CF…E5EB8518`)
- [x] Pastikan dates nyata (dates actual, strictly increasing utk semua kode;
      len(dates[i]) == lens[i])
- [x] Pastikan raw/adjusted policy konsisten (raw close utk M5/M10/label;
      adjusted hanya diagnostic)
- [x] Hitung M5 = Close_t/Close_{t-5} − 1 (raw, point-in-time, unit test exact)
- [x] Hitung M10 = Close_t/Close_{t-10} − 1 (unit test exact)
- [x] Ambil RTF production score (definition frozen density=30/heavy=2.0/
      min_heavy=2/tau=2.0/cutoff=5 via cache `phase3_rtf_rows.npz`
      sha `3F094435…E34EC2`, source == snapshot; tanpa tuning)
- [x] Attach labels (b10_h10 = PRIMARY, b10_h21 = SECONDARY, up1_h21 =
      DIAGNOSTIC; level = close_t, definisi Phase 3; NaN = censored, BUKAN 0)
- [x] Attach regime (`regime_series` existing, point-in-time; ADX NaN →
      UNKNOWN(-1); tanpa threshold baru)
- [x] Attach liquidity group (ADV20 existing: liquid = adv_vol ≥ 500.000 &
      adv_val ≥ 250.000.000; less-liquid = sisanya eligible; TANPA threshold
      baru; ADV20 < 5 bar → UNKNOWN)
- [x] Exclude Phase 4 locked holdout (snapshot berakhir 2026-08-13; holdout
      contamination = 0)
- [x] Validate no feature > t (future feature violations = 0; no global
      aggregate — semua feature lokal per kode)
- [x] Acceptance: 0 duplicate code/date · 0 future-feature · 0 holdout ·
      17/17 acceptance criteria PASS · unit test 0 fail

**Hasil dataset (526.129 rows):** m5 valid 521.514 · m10 valid 516.899 ·
rtf_score valid 365.018 (post-event) · rtf_ready 6.050 · b10_h10 valid
516.899 (events 164.725) · b10_h21/up1_h21 valid 506.756 · censored h10 9.230 /
h21 19.373 · eligible 271.055 (584 tanggal) · regime UNKNOWN 11.997 ·
liquidity UNKNOWN 3.692 · liquid 271.055 / less-liquid 251.382.

### P5.2 Split

- [ ] Global chronological split (policy F2/F3 — BUKAN split baru demi Phase 5)
- [ ] Purge berdasarkan max label horizon (21)
- [ ] Embargo 90 hari
- [ ] Simpan train/oos counts
- [ ] Verifikasi Phase 4 holdout tetap tidak tersentuh

### ✅ P5.2 Split — PASS (15-08-2026)

- [x] Global chronological split (policy F2/F3 — BUKAN split baru demi Phase 5);
      dataset hash `F8FC56CF…` diverifikasi vs protocol (freeze P5.1)
- [x] Purge berdasarkan max label horizon (21 trading days — label_end_h21 ≤
      cutoff; BUKAN 63 F2, karena target Phase 5 = b10_h10/b10_h21/up1_h21)
- [x] Embargo 90 hari kalender (GAP = 2026-01-24..2026-04-22; OOS inclusive ≥
      2026-04-23)
- [x] Simpan train/oos counts (4 partisi: TRAIN 384.862 · PURGED 19.215
      (overlap 19.215, censored 0) · GAP 50.334 · OOS 71.718)
- [x] Verifikasi Phase 4 holdout tetap tidak tersentuh — overlap 0, status
      jujur **NOT_PRESENT_IN_SNAPSHOT** (bukan SAFE)
- [x] Checks A–F: max(train) ≤ cutoff · semua train label_end ≤ cutoff ·
      min(oos) ≥ 2026-04-23 · partisi disjoint (6 pasang = 0) · holdout 0 ·
      duplicate (code,date) 0 · future-feature/label violations 0
- [x] Label availability: OOS h10 valid 62.488 (censored 9.230) · h21 valid
      52.345 (censored 19.373) — censored TIDAK masuk metric
- [x] Per-date OOS: 81 tanggal signal · 3 tanggal insufficient_k10
      (eligible < 10 → tidak memaksa top-10) · 0 tanggal tanpa kandidat RTF
- [x] Balance: train 915 kode / OOS 923 kode; signal dates train 427 / OOS 81;
      events OOS h10 20.593 / h21 23.096 → `backend/data/phase5_split.json`
- [x] TIDAK ada model selection (cutoff/purge/embargo/horizon tetap frozen;
      OOS kecil pun tidak menggeser cutoff)

### P5.3 Baselines

- [ ] M0 = Momentum5 (rank M5 per date → Top-5/Top-10 → b10_h10, b10_h21, up1_h21)
- [ ] M1 = RTF-only (production frozen: density=30, heavy=2.0, min_heavy=2,
      tau=2.0, cutoff=5; tanpa tuning)
- [ ] M3 = Momentum10
- [ ] Random baseline (universe tanggal SAMA + K SAMA, per date)
- [ ] Density-only diagnostic (BUKAN M6 production candidate)

### ✅ P5.3 Baselines — PASS (15-08-2026)

- [x] M0=M5 & M3=M10: formula exact Phase 3 (raw close), diverifikasi manual
      acak (2 kode × 2 t, err < 1e-6) — BUKAN momentum asumsi, empirical baseline
- [x] M1=RTF: production `rtf_score`, config frozen diverifikasi vs config.py
      (density=30, heavy=2.0, min_heavy=2, tau=2.0, cutoff=5)
- [x] RTF-ranked subset = stock dgn `rtf_score > 0` (arm/ndh aktif): OOS
      1.007 kandidat / 79 tanggal (score 0 = 63.609 — episode tanpa arm aktif,
      nilai sah evaluator BUKAN konversi NaN→0; NaN = 7.102 non-signal);
      0 baris NaN/≤0 masuk top-K; n_eligible vs n_rtf_rankable dipisah
- [x] Random: per-date Uniform(U_t,K), seed 42 frozen (protocol), verifikasi
      deterministik (regenerate identik); sanity only
- [x] Density-only diagnostic (`rtf_density > 0`, 60.823 kandidat OOS): BUKAN
      M6, tanpa tuning density
- [x] Ranking cross-sectional PER TANGGAL; K hanya {5,10}; U_t SAMA utk semua
      model; insufficient dates dicatat (RTF K5: 10 tanggal, K10: 36) tanpa
      memaksa top-K
- [x] no future information (dataset P5.1 audited) · no Phase 4 holdout ·
      no parameter tuning · top5/top10 count per date valid (0 duplikat)

**Tabel baseline (OOS, pooled, ranking ELIGIBLE-ONLY):**

| Model | K | n_dates | n_selected | b10_h10 | lift | b10_h21 | up1_h21 |
|-------|---|--------:|-----------:|--------:|-----:|--------:|--------:|
| M5    | 5 | 81 | 405 | **0.6176** | 1.87 | 0.6756 | 0.5284 |
| M5    |10 | 81 | 800 | 0.5458 | 1.66 | 0.6163 | 0.5161 |
| RTF   | 5 | 79 | 353 | 0.5607 | 1.70 | 0.6454 | 0.4542 |
| RTF   |10 | 79 | 561 | 0.5613 | 1.70 | 0.6448 | 0.5038 |
| M10   | 5 | 81 | 405 | 0.5847 | 1.77 | 0.6400 | 0.5067 |
| M10   |10 | 81 | 800 | 0.5630 | 1.71 | 0.6356 | 0.5356 |
| Random| 5 | 81 | 405 | 0.3944 | 1.20 | 0.5000 | 0.5133 |
| Random|10 | 81 | 800 | 0.3857 | 1.17 | 0.4949 | 0.5068 |
| Density| 5 | 81 | 402 | 0.5157 | 1.57 | 0.5878 | 0.4628 |
| Density|10 | 81 | 793 | 0.5448 | 1.65 | 0.6289 | 0.5189 |

⚠️ **KOREKSI METODOLOGIS (15-08-2026, setelah P5.4):** P5.3 awal meranking &
memilih top-K atas SEMUA baris tanggal (eligible + non-eligible; OOS hanya
55% eligible = 39.616/71.718). Dilanggar P5.3.6. Diperbaiki di sumber:
ranking & top-K kini ELIGIBLE-ONLY; cache `phase5_oos_ranks.npz` hash baru
`97A361D3…`; P5.4 & P5.5 di-rerun dari cache baru (angka di atas FINAL).
Base rate OOS (eligible): b10_h10 0.3296 · b10_h21 0.4412 · up1_h21 0.4481.
Catatan: M5 K5 > M10 K5 > RTF K5 (h10) = hasil EMPIRIS IDX, bukan universal
law; density-only < strength. Output: `data/phase5_baseline.json` +
`data/phase5_oos_ranks.npz` (input P5.4–P5.8). PASS ≠ menang.

### ✅ P5.4 Dependency Audit — PASS (15-08-2026)

- [x] Input = cache P5.3 (`phase5_oos_ranks.npz`), hash diverifikasi cocok
      (`10D923FC…`) — TIDAK rebuild ranking; protocol hash cocok
- [x] Spearman RTF vs M5 & RTF vs M10 PER TANGGAL (primary), intersection
      `U_t^{RTF∩M}` (rank_rtf > 0 & rank_m > 0); pairwise missing handled;
      NaN & score-0 tidak ikut, tidak di-zero; ranks unik → Spearman = Pearson
      pada ranks (monotonic, selaras dgn rank-normalization P5.5)
- [x] Overlap@5/@10 = |TopK_RTF ∩ TopK_M|/K (K tetap) + Jaccard diagnostic;
      pooled correlation hanya SECONDARY (ρ M5 0.12 / M10 0.43 — jangan dibaca
      sebagai primary)
- [x] Distribusi bins (ρ<0 / 0–0.25 / 0.25–0.5 / 0.5–0.75 / ≥0.75) — visual
      diagnostic, BUKAN threshold keputusan
- [x] Regime & liquidity breakdown: existing definitions, UNKNOWN tetap
      UNKNOWN; modus-date utk overlap + **cell-rho** (pairwise per date×segment)
      utk dependency segment — tanpa membuat regime baru
- [x] TIDAK ada model selection/config modification; holdout untouched

**Hasil (OOS, date-level primary; median) — cache FINAL `97A361D3…`:**

| Pasangan | ρ median | Q25 | Q75 | Overlap@5 | Overlap@10 | n_pairs/date |
|----------|---------:|----:|----:|----------:|-----------:|-------------:|
| RTF vs M5 | **0.10** | −0.21 | 0.40 | 0.4 | 0.4 | 8 (1–64) |
| RTF vs M10 | **0.04** | −0.36 | 0.29 | 0.2 | 0.2 | 8 (1–64) |

Bins ρ RTF-M5: negatif 29 · 0–0.25: 20 · 0.25–0.5: 15 · 0.5–0.75: 8 · ≥0.75: 4
(76 tanggal valid; 2 zero-pairs, 5 insuf rho; RTF top-K tak lengkap sering —
median kandidat RTF 8/date < 10 → overlap dibaca hati-hati).

**Regime (median ρ date-level):** bear (64 tgl) M5 **0.03** / M10 **−0.02** —
dependency ≈ 0 · sideways (15 tgl) 0.42 / 0.32 · bull (2 tgl) 0.57 / 0.39 —
**INSUFFICIENT** (jangan disimpulkan). Cell-rho konsisten (bear 0.23/0.13,
sideways 0.26/−0.02, bull 0.39/0.40).

**Liquidity:** OOS didominasi liquid (modus-date 81/81; cell-rho liquid 0.10/0.04);
segment less-liquid tidak punya ≥2 pairs per tanggal → **INSUFFICIENT** di OOS —
independence per segment liquidity belum bisa disimpulkan.

**Interpretasi (qualitative, BUKAN keputusan):**
- Dependency RTF–M5/M10 **rendah** (Case B potensial): RTF tampak membawa
  informasi berbeda dari recent-return baseline. Baselines P5.3 > random
  (RTF 0.561, M5 0.618, M10 0.585 vs random 0.394) → combination layak diuji
  P5.5, tapi **belum ada kesimpulan** sampai ΔPrecision/ΔLift + CI (P5.7/P5.8).
- Indikasi dependency conditional regime (Case D: ≈0 di bear, lebih tinggi di
  sideways/bull) = hypothesis utk future — BELUM boleh regime-specific
  weighting.
- Output: `data/phase5_dependency.json`

### P5.5 Combination

- [ ] Rank-normalisasi cross-sectional: r_i = (N_t − Rank_i)/(N_t − 1) →
      top = 1, bottom = 0; N=1 ditangani aman
- [ ] rank_m5, rank_m10, rank_rtf; verify range 0..1
- [ ] M2 = RankAvg(M5, RTF); M4 = RankAvg(M10, RTF) — equal weight
- [ ] Tanpa weight optimization (dilarang 60/40, 70/30, 80/20)

### ✅ P5.5 Rank Normalization & Combination — PASS (15-08-2026)

- [x] Input = cache P5.3 FINAL (`97A361D3…`); cache/dataset/snapshot hash
      cocok vs protocol; TIDAK rebuild ranking
- [x] r_i,t = (N_t − Rank_i,t)/(N_t − 1), best→1, worst→0; N_t==1 →
      insufficient_rank_universe (NaN, bukan inf) — unit test lulus
- [x] M2 = RankAvg(M5, RTF) & M4 = RankAvg(M10, RTF) — equal weight saja
      (tanpa 60/40/70/30/80/20; tanpa tuning K/threshold/fitting)
- [x] r_rtf hanya utk kandidat rankable (score > 0); missing → **NaN, bukan 0**
      (tanpa implicit penalty); verifikasi 0 baris NaN/≤0 di top-K
- [x] Re-rank per tanggal atas score kombinasi; U_t^{combined} =
      U_momentum ∩ U_RTF; |U| < K → **partial_k** (K_filled dicatat);
      |U| == 0 → insufficient_k; TIDAK fallback ke saham tanpa RTF
- [x] Common-universe sensitivity (M0 vs M2, M3 vs M4): ranking DIHITUNG
      ULANG dlm U_common (fix: rank global bukan subset → negatif; diperbaiki
      dgn rerank-in-subset) — sensitivity ONLY, bukan production
- [x] Sanity: rank & score ∈ [0,1] · no NaN/inf di selection · no duplicate
      (code,date) · same date-based ranking · K {5,10} · unit test exact
      (r_m5=1.0 + r_rtf=0.0 → M2=0.5) · holdout untouched · no config modif
- [x] n_eligible / n_m5 / n_m10 / n_rtf / n_combined / n_common per tanggal
      disimpan (comparability M5 besar vs M2 kecil tidak disembunyikan)

**Statistik kombinasi:** M2/M4: partial_k K5 = 22 tanggal, K10 = 55;
insufficient_k K5 = 5, K10 = 5 (tanggal dgn kombinasi kosong). n_rtf_rankable
median 8/tanggal → kombinasi sering partial — dibawa ke P5.6 sbg K_filled,
TIDAK dipaksa jadi Top-K penuh.
Output: `data/phase5_combination_ranks.npz` (hash `B8960C51…`) +
`data/phase5_combination.json`. TIDAK ada evaluasi performa di P5.5.

### P5.6 OOS Evaluation

- [x] Precision@5, Precision@10
- [x] Lift@5, Lift@10
- [x] AUC
- [x] n_dates, n_selected, n_events
- [x] Primary: b10_h10 · Secondary: b10_h21 · Diagnostic: up1_h21

**Status: PASS (15-08-2026).** Cache final P5.3/P5.5 diverifikasi
(97A361D3…/B8960C51…); split/protocol cocok; holdout tidak disentuh;
censored label dikeluarkan; partial-K memakai K_filled (tidak diam-diam ÷ K).

**Tabel utama (OOS, native; Precision h10; base rate 0.3554):**

| Model | K | dates | filled | pooled | daily-mean | lift | AUC |
|-------|--:|------:|-------:|-------:|-----------:|-----:|----:|
| M5 | 5 | 71 | 353 | **0.6176** | 0.6197 | **1.738** | 0.437 |
| M5 | 10 | 71 | 698 | 0.5458 | 0.5435 | 1.536 | 0.437 |
| RTF | 5 | 69 | 305 | 0.5607 | 0.5220 | 1.578 | 0.504 |
| RTF | 10 | 69 | 481 | 0.5613 | 0.5156 | 1.579 | 0.504 |
| M2 (M5+RTF) | 5 | 66 | 302 | 0.5894 | 0.5669 | 1.659 | 0.562 |
| M2 (M5+RTF) | 10 | 66 | 478 | 0.5649 | 0.5391 | 1.590 | 0.562 |
| M10 | 5 | 71 | 354 | 0.5847 | 0.5852 | 1.645 | 0.467 |
| M10 | 10 | 71 | 698 | 0.5630 | 0.5615 | 1.584 | 0.467 |
| M4 (M10+RTF) | 5 | 66 | 302 | 0.5762 | 0.5548 | 1.621 | 0.542 |
| M4 (M10+RTF) | 10 | 66 | 478 | 0.5669 | 0.5406 | 1.595 | 0.542 |
| Random | 5 | 71 | 355 | 0.3944 | 0.3944 | 1.110 | — |
| Random | 10 | 71 | 700 | 0.3857 | 0.3858 | 1.085 | — |
| Density | 5 | 71 | 351 | 0.5157 | 0.5157 | 1.451 | 0.588 |
| Density | 10 | 71 | 692 | 0.5448 | 0.5444 | 1.533 | 0.588 |

**Incremental (h10, native):**

| Pair | K | ΔPrec pooled | ΔPrec daily | ΔLift | dates >/=/< |
|------|--:|-------------:|------------:|------:|------------:|
| M2−M0 | 5 | −0.028 | −0.053 | −0.079 | 15/20/31 (66) |
| M2−M0 | 10 | +0.019 | −0.004 | +0.054 | 28/6/32 (66) |
| M4−M3 | 5 | −0.009 | −0.030 | −0.024 | 23/17/26 (66) |
| M4−M3 | 10 | +0.004 | −0.021 | +0.011 | 26/8/32 (66) |

→ K5: kombinasi **lebih buruk** (daily mean negatif, fraction dates condong
M2<M0). K10: pooled sedikit positif tapi daily mean negatif & fraction
seimbang — belum ada bukti improvement.

**Common-universe (h10; universe identik):**

| Pair | K | ΔPrec pooled | ΔPrec daily |
|------|--:|-------------:|------------:|
| M2−M5 | 5 | +0.007 | +0.006 |
| M2−M5 | 10 | −0.002 | −0.002 |
| M4−M10 | 5 | +0.010 | +0.009 |
| M4−M10 | 10 | 0.000 | 0.000 |

→ Improvement native K10 (pooled +0.019/+0.004) **HILANG di common universe**
(≈0/−0.002) → sebagian besar berasal dari **universe selection**
(coverage RTF 1.9%), BUKAN signal combination. Finding penting.

**AUC (diagnostic ranking, BUKAN primary):** M5 0.437 · M10 0.467 (< 0.5 —
raw momentum vs full eligible universe; tidak dipakai utk trading) · RTF 0.504
· M2 0.562 · M4 0.542 · Density 0.588. AUC tidak sejalan dgn Precision@K
(exactly kenapa bukan primary).

**Coverage (eligible OOS 39.616):** M5 99.9% · M10 99.9% · RTF 1.93% (764) ·
M2/M4 1.92% (761). Kombinasi memilih dari universe jauh lebih kecil —
dilaporkan, tidak disembunyikan.

**Per-date stability (K5, h10):** median 0.6 semua model; IQR 0.4;
daily mean M5 0.620 > M2 0.567 > M10 0.585 > M4 0.555 > RTF 0.522.

**Regime (pooled h10; date-level modus):** bear (64 tgl) — M5 0.642, M2 0.603
(Δ −0.039), M10 0.584, M4 0.587 (Δ +0.003); sideways (15 tgl) — M2 Δ −0.064,
M4 Δ −0.078; bull (2 tgl) INSUFFICIENT. Tidak ada regime-specific winner.

**Liquidity:** seluruh seleksi OOS liquid (n less-liquid = 0) →
less-liquid INSUFFICIENT; baris liquid = tabel utama.

**Verdict sementara (BELUM final — tunggu CI P5.7):** M2/M4 **tidak**
mengalahkan M0/M3 pada Precision/Lift (K5 negatif; K10 pooled margin positif
kecil namun daily mean negatif dan common-universe ≈ 0). RTF standalone
(lift 1.58) > random (1.11) tapi < M5 (1.74)/M10 K5 (1.65). Output:
`data/phase5_oos_eval.json`.

### P5.7 Incremental Value (bagian PALING penting — bukan cuma absolute precision)

- [x] ΔPrecision M2−M0 (contoh: M5 25.2% → M5+RTF 27.4% → Δ = +2.2pp)
- [x] ΔLift M2−M0
- [x] ΔPrecision M4−M3
- [x] ΔLift M4−M3

**Status: PASS (15-08-2026) — verdict: REDUNDANT (no incremental value).**

Stock-cluster bootstrap B=1000, seed=42; 667 stocks eligible OOS; CI
percentile 95%; point estimates reproduce P5.6 exactly (verifikasi otomatis);
semua CI termasuk 0.

**ΔPrecision pooled (h10; CI [2.5%, 97.5%]):**

| Pair | K | point | CI | verdict |
|------|--:|------:|----|---------|
| M2−M0 | 5 | −0.028 | [−0.104, +0.048] | includes 0 |
| M2−M0 | 10 | +0.019 | [−0.041, +0.082] | includes 0 |
| M4−M3 | 5 | −0.009 | [−0.101, +0.084] | includes 0 |
| M4−M3 | 10 | +0.004 | [−0.070, +0.077] | includes 0 |

**ΔLift pooled (h10):** semua includes 0 (M2−M0 K5 −0.079 [−0.295, +0.132];
K10 +0.053 [−0.116, +0.233]; M4−M3 K5 −0.024; K10 +0.011).

**Common-universe (wajib; universe identik) — ΔPrecision pooled (h10):**

| Pair | K | point | CI |
|------|--:|------:|----|
| M2−M5 | 5 | +0.007 | [−0.039, +0.040] |
| M2−M5 | 10 | −0.002 | [−0.022, +0.021] |
| M4−M10 | 5 | +0.010 | [−0.050, +0.032] |
| M4−M10 | 10 | +0.000 | [−0.026, +0.019] |

→ Semua includes 0, point ≈ 0. Gain native K10 (+1.9pp, CI includes 0) hilang
di common universe → **universe-selection effect**, bukan complementary
signal. Per P5.7.15: CI includes 0 + point kecil = **REDUNDANT**.

**Absolute CI (h10, K5):** M0 0.618 [0.560, 0.673] · M1 0.561 [0.475, 0.638]
· M2 0.589 [0.504, 0.665] · M3 0.585 [0.508, 0.661] · M4 0.576 [0.490, 0.652]
(tumpang tindih kuat — tidak ada model unggul secara robust).

**AUC CI (h10, diagnostic):** M0 0.437 [0.422, 0.456] & M3 0.467 [0.447, 0.484]
→ di bawah 0.5 (raw momentum vs full eligible universe; diagnostic saja).
M1 0.504 [0.497, 0.510] · M2 0.562 [0.488, 0.633] · M4 0.542 [0.467, 0.623]
→ includes 0.5.

**Diagnostics:** n_unique_stocks 667 · top_stock_share_rows 0.002 ·
effective_stocks 564 — tanpa konsentrasi mencolok; top-K tersebar 96–141
stocks (top share 2.5–4.9%). n_valid=1000 semua metric; n_invalid=0.

**Date-block sensitivity (subsample 63% tanggal tanpa replacement, B=500,
seed=7):** semua CI includes 0; konsisten dgn stock-cluster (K5 cenderung
negatif, K10 ≈ 0). Perbedaan kecil stock vs date → tidak ada konflik
conclusion.

**Kesimpulan P5.7:** TIDAK ada bukti incremental value RTF di atas M5/M10
(CI ΔPrecision & ΔLift semua includes 0, native maupun common). Apparent
K10 gain = universe selection. **TIDAK ada perubahan architecture.**
Output: `data/phase5_bootstrap.json`.

### P5.8 Uncertainty (stock-cluster bootstrap, F2.3) — ✅ tercakup oleh P5.7

- [x] B = 1000, seed = 42; resample STOCK (semua observasi milik stock),
      BUKAN row IID
- [x] CI Precision@5 · Precision@10 · Lift · AUC
- [x] CI ΔPrecision · CI ΔLift — **paling penting: menguji incremental value**
      → verdict REDUNDANT (lihat blok P5.7)

### P5.8 Final Interpretation — VERDICT

**VERDICT: REDUNDANT / NO INCREMENTAL VALUE ESTABLISHED** ✅

**Phase 5 — RTF × Short-Horizon Return Incremental Value**

1. RTF standalone retains positive predictive association versus random
   (RTF K5 56.07% vs random 39.44%; Lift RTF ≈ 1.58).
2. M5/M10 are competitive or stronger standalone baselines
   (M5 K5 61.76% · M10 K5 58.47% · M5 K10 54.58% · M10 K10 56.30%).
3. Rank-average combinations M5+RTF and M10+RTF do not produce robust OOS
   improvement (M2 K5 58.94%, M4 K5 57.62% — di bawah baseline K5).
4. Stock-cluster bootstrap confidence intervals (B=1000, seed=42) untuk
   ΔPrecision dan ΔLift semua include zero (native maupun common-universe).
5. Date-block sensitivity (B=500, seed=7) memberikan kesimpulan sama.
6. Native K10 gains (M2−M0 +1.9pp pooled) hilang di common-universe
   (−0.2pp, CI includes 0) → **universe/eligibility selection**, bukan
   complementary signal information.
7. Tidak ada evidence yang membenarkan RTF sbg additive ranking component
   di atas M5/M10.
8. **Production RTF UNCHANGED** — Phase 5 adalah incremental-value study,
   bukan alasan retune RTF (density 30 · heavy 2 · min_heavy 2 · tau 2 ·
   cutoff 5 tetap; config.py hash `85351777…` diverifikasi ulang di P5.9).
9. **RTF TIDAK boleh dideskripsikan useless** — ia mempertahankan standalone
   signal association; yang tidak terbukti adalah incremental value
   conditional on M5/M10.
10. Hypothesis masa depan (RTF-as-filter, breakout-continuation below ON/OFF)
    membutuhkan research phase terpisah dengan protocol baru — TIDAK boleh
    di-claim retrospectif dari Phase 5.

**Tiga evidence yang membentuk verdict (bukan cuma CI includes zero):**

```
Low dependency (P5.4: ρ M5 0.10 / M10 0.04)   → orthogonal ≠ useful
+ standalone RTF edge (56.1% vs random 39.4%)
+ no incremental gain on common universe
────────────────────────────────────────────────
= REDUNDANT — RTF membawa informasi berbeda, tetapi informasi tersebut
  belum terbukti menambah predictive value setelah short-horizon return
  sudah diketahui; native improvement terutama berasal dari RTF's
  restrictive universe (coverage 1.9% eligible).
```

**Batasan verdict (wajib dicatat):**
- Phase 5 hanya menguji `RTF | M5` dan `RTF | M10` dgn rank-average
  combination — BUKAN semua konsep RTF. Two-strategy diagnostic
  (below ON/OFF) = separate hypothesis, REMAINS UNRESOLVED.
- AUC (M2/M4 > 0.5 vs M0/M3 < 0.5) BUKAN counterargument: AUC mengukur
  ranking discrimination across all thresholds; Precision@K mengukur
  kualitas bagian ranking yang dipakai deployment. Keduanya menjawab
  pertanyaan berbeda — tidak ada contradiction.
- Historical OOS Phase 5 TIDAK boleh dipromosikan menjadi final holdout.

**Rekomendasi production:**
- TIDAK memakai M5+RTF / M10+RTF sebagai production ranking.
- Arsitektur: M5/M10 = primary candidate ranking; **RTF = secondary
  technical context** (bukan "confirmation" probabilistic — belum
  dibuktikan). RTF tetap dipertahankan di UI sebagai konteks teknikal.
- TIDAK otomatis mengganti ranking production menjadi M5/M10 berdasarkan
  Phase 5 — keputusan ranking architecture terpisah dari research verdict.

### P5.9 Final Audit — ✅ Phase 5 COMPLETE

- [x] P5.0 protocol frozen
- [x] P5.1 dataset PASS (526.129 rows; hash F8FC56CF…)
- [x] P5.2 split PASS (TRAIN 384.862 / PURGED 19.215 / GAP 50.334 / OOS 71.718)
- [x] P5.3 baseline PASS (final eligible-only; cache 97A361D3…)
- [x] P5.4 dependency PASS (ρ 0.10/0.04; overlap@5 0.4/0.2)
- [x] P5.5 combination PASS (cache B8960C51…)
- [x] P5.6 OOS evaluation PASS (phase5_oos_eval.json)
- [x] P5.7 bootstrap PASS (phase5_bootstrap.json; verdict REDUNDANT)
- [x] P5.8 interpretation PASS (verdict REDUNDANT / NO INCREMENTAL VALUE)
- [x] Phase 4 holdout untouched (mtime 13:33 sebelum Phase 5; status
      NOT_PRESENT_IN_SNAPSHOT; overlap 0; P4.8 tetap WAIT)
- [x] production config unchanged (config.py hash `85351777…` cocok dgn
      protocol; diverifikasi ulang P5.9)
- [x] no parameter promotion (tidak ada weight/param di-promote ke production)
- [x] no post-hoc tuning (satu-satunya perubahan = bug fix metodologi
      eligible-only di sumber P5.3, didokumentasikan, bukan tuning)
- [x] all hashes recorded: snapshot 284B40C7… · dataset F8FC56CF… ·
      config 85351777… · RTF cache 3F094435… · rank cache 97A361D3… ·
      combination cache B8960C51… · eval json 0793804F… ·
      bootstrap json (tercatat di file)
- [x] all dev bugs documented: (1) P5.3 ranking non-eligible → eligible-only
      fix (material, rerun chain); (2) P5.5 common-universe rank global →
      rerank-in-subset; (3) P5.6 flag kolom M2/M4 dibaca dari cache salah →
      fixed + validasi vs P5.3 & spot-check; (4) P5.7 common delta sempat
      hanya precision absolut → fixed + point match P5.6
- [x] final verdict documented (P5.8 block di atas)

**Phase 5 COMPLETE — Verdict: REDUNDANT / NO INCREMENTAL VALUE ESTABLISHED.**
Production unchanged. P4.8 holdout: WAIT (genuinely unseen data).

### 🔒 FREEZE POINT (15-08-2026) — Phase 5 closed, no further research implementation

**Status project:**

```text
F2 ✅ Recovery statistical integrity
F3 ✅ Fundamental risk-context only
F4 ✅ Probability quality methodology frozen
    P4.8 = WAIT · M1 = frozen candidate · p_min 0.68 = FROZEN
F5 ✅ RTF × M5/M10 incremental study → Verdict REDUNDANT · No production change
```

**Jangan disentuh (frozen):** P4.8 Final Locked Holdout = WAIT · M1 candidate =
tetap candidate · p_min = 0.68 FROZEN · RTF config = UNCHANGED (density 30,
heavy 2, min_heavy 2, tau 2, cutoff 5) · Phase 4 holdout = UNTOUCHED.

**Tidak membuka Phase 6** (menambah indikator) sebelum final holdout — hasil
Phase 5 (orthogonal ≠ useful) tidak membenarkan membuka model-selection loop
lagi. Pertanyaan "apakah seluruh production ranking architecture perlu
diganti" adalah evaluasi terpisah, BUKAN dijawab oleh verdict Phase 5.

**Satu-satunya open item — P4.8 RUN ONCE**, hanya setelah data genuinely
unseen tersedia, dengan urutan tetap:

```text
verify cutoff
→ verify production hash
→ verify no contamination
→ RUN P4.8 ONCE
→ PROMOTE / REJECT / INCONCLUSIVE
```

Baru setelah verdict P4.8 ada dasar untuk memutuskan perubahan architecture
production.

- [ ] Regime SUDAH ada (bull/bear/sideways) — jangan define ulang setelah result
- [ ] Per regime: precision@5, precision@10, lift, ΔPrecision, signal count,
      CI bila sample cukup; sample terlalu sedikit → INSUFFICIENT

### P5.10 Liquidity Analysis

- [ ] Liquid group vs less-liquid group (classification existing, tanpa threshold baru)
- [ ] M0–M4 comparison + ΔPrecision per group

### P5.11 Ablation

- [ ] Momentum5 · RTF full · RTF density · Momentum5 + RTF full ·
      Momentum5 + RTF density · Momentum10 · Momentum10 + RTF full
- [ ] Tujuan: apakah incremental value benar-benar berasal dari RTF, dan apakah
      bagian yang berguna sebenarnya hanya density?
- [ ] JANGAN mengulang gate ablation Phase 3 (sudah pernah dilakukan)

### P5.12 Two-Strategy Diagnostic

- [ ] Strategy A = Pre-breakout / accumulation (below ON)
- [ ] Strategy B = Breakout continuation (below OFF)
- [ ] Bandingkan b10, up1, precision, regime
- [ ] **Tidak ada perubahan production**; kalau menarik → phase khusus baru

### P5.13 Final Interpretation

- [ ] A Incremental: M2 > M0 & M4 > M3 + CI incremental mendukung → RTF complementary
- [ ] B Redundant: M2 ≈ M0 & M4 ≈ M3 (CI overlap / Δ tidak jelas) → tidak ada
      incremental value
- [ ] C Harmful: M2 < M0 & M4 < M3 secara robust → RTF mengganggu
- [ ] D Regime-specific: mis. Bull helpful / Bear harmful → jangan paksa satu
      global conclusion
- [ ] E Inconclusive: sample/CI terlalu lemah → tidak ada config change

### P5.14 Final Audit

- [ ] Phase 4 holdout tetap unopened
- [ ] Production config unchanged
- [ ] No M1 recovery candidate used
- [ ] No threshold tuning (p_min 0.68 untouched)
- [ ] No momentum window tuning
- [ ] No rank-weight tuning
- [ ] Same universe per date
- [ ] No future features
- [ ] Cluster CI complete
- [ ] Primary/secondary target evaluated · regime checked · liquidity checked
- [ ] Dependency documented · ablation documented · final interpretation documented
- [ ] Update audit doc §34 · record artifacts · user ACCEPT / REJECT decision

**Urutan eksekusi PERSIS P5.0 → P5.14. Jangan lompat ke combination sebelum
P5.2 (split) dan P5.4 (dependency) selesai.**

## Phase 5 (lama, superseded) — optional future model

- [x] ~~Discrete-time survival/hazard.~~ (ditunda — kompleksitas tidak dijustifikasi)
- [x] ~~Market-relative features.~~ (masuk evaluasi kombinasi Phase 5 baru bila relevan)
- [x] ~~Regime conditioning.~~ (diteliti sebagai diagnostic; tanpa inverse strength)
- [x] ~~Additional nonlinear modelling only if justified by OOS.~~ (hanya setelah M0–M4)

---

# 35. Research Classification

## Research-backed

- High-volume activity can contain information about subsequent returns, but effect is context-dependent.
- Volume-return relationships can weaken OOS.
- Order-flow imbalance is more informative than raw volume for some short-horizon price movements.
- Drawdown size is associated with decreasing probability of recovery to prior highs.
- Calibration must be evaluated using proper probabilistic metrics/reliability.
- Multiple testing and repeated backtest selection can cause severe overfitting.

## Empirical

- Current accumulation density appears useful in project data.
- Current strength ranking appears to add some incremental ranking value over density-only.
- Current logistic recovery shows promising discrimination on available data.
- ⚠️ **Koreksi 15-08-2026 (Phase 3 OOS):** strength penuh `density×ndh×decay` TIDAK
  menambah nilai ranking vs density-only pada OOS yang tidak tersentuh (AUC 0.371 vs
  0.425, n arm kecil). Klaim "strength menambah value atas density-only" kini hanya
  berlaku di TRAIN, bukan OOS.
- ⚠️ **Koreksi 15-08-2026 (Phase 3 OOS):** baseline momentum 5/10 hari (ret terakhir)
  mengungguli sinyal RTF pada b10 horizon-10 (0.234/0.252 vs 0.196). Edge RTF vs
  kontrol nyata (lift ≈2,7×) tapi momentum sederhana adalah pesaing kuat; kombinasi
  keduanya belum diuji (Phase 5).
- ⚠️ **Koreksi 15-08-2026 (diagnostic orientasi):** AUC(strength→up1_21)=0.371 di OOS
  TIDAK berarti strength "terbalik secara inheren" — orientasi tidak stabil (train
  positif 0.525; per-kuartal osilasi 0.43–0.57; per-kode median ≈0.50 seimbang; b10
  tetap positif stabil 0.507–0.567). Inverse hanya muncul utk target up1 di OOS pendek
  dgn konfigurasi winner overfit. Hypothesis "inverse strength" tidak dilanjutkan.

## Heuristic

- 30% density threshold.
- 2× heavy volume.
- 2 heavy days.
- SMA20 confirmation.
- Decay τ=2.
- Day-5 zero cutoff.
- Recovery probability threshold.
- n≥5 empirical switch.

## Speculative / must not be overstated

- Heavy volume == institutional accumulation.
- +10% == ARA.
- Strength == probability.
- READY == probability of breakout.

---

# 36. Final Recommendation

**Jangan redesign model.**

Tahap terbaik sekarang adalah memperbaiki **correctness dan validation**, bukan menambah kompleksitas.

Urutan paling penting:

1. **Fix ARA definition.**
2. **Fix ALMOST gate.**
3. **Fix temporal OOS recovery calibration.**
4. **Fix overlapping-event statistics.**
5. **Fix net_dist dan local dataset bugs.**
6. **Pisahkan recovery probability definitions.**
7. **Run true walk-forward OOS untuk RTF thresholds dan ranking.**

Jika tujuh langkah ini sudah selesai dan edge masih konsisten pada untouched OOS data, baru model layak dinaikkan ke tahap survival/hazard atau model nonlinear.

---

# 37. Research References

Referensi inti yang digunakan untuk justifikasi audit:

1. Gervais, S., Kaniel, R., & Mingelgrin, D. H. — *The High-Volume Return Premium*.
2. Cont, R., Kukanov, A., & Stoikov, S. — *The Price Impact of Order Book Events* / order-flow imbalance research.
3. White, H. — *A Reality Check for Data Snooping*.
4. Bailey, D. H. et al. — research on *Probability of Backtest Overfitting*.
5. Bailey / López de Prado et al. — research on multiple testing, backtest overfitting, and Deflated Sharpe Ratio.
6. Research on probabilistic forecast calibration, reliability diagrams, Brier score, calibration slope/intercept.
7. Morgan Stanley Investment Management — empirical study of stock drawdown/recovery behavior using a large historical equity universe.
8. IDX/OJK market rules/documentation concerning Auto Rejection and price limits.
9. Quantitative finance literature on technical analysis, data snooping, transaction costs, and out-of-sample robustness.

---

# Final Statement

Versi terbaru adalah **substantial improvement** dan architecture dasarnya layak dipertahankan.

Namun status yang paling tepat saat ini adalah:

> **RTF = promising, interpretable heuristic/empirical detector yang belum final OOS validated.**
>
> **Recovery Probability = mathematically valid empirical probability model yang belum cukup kuat untuk disebut fully calibrated production probability.**

Fokus perbaikan berikutnya harus pada **correctness → point-in-time integrity → event definitions → statistical dependence → walk-forward validation → calibration**, bukan menambah kompleksitas model.

---

# 38. Fase 3 — Fundamental Risk Context (keputusan user, 13 Agustus 2026)

## 38.1 Keputusan arsitektur (user, setelah membaca F2 7/7)

- **Fundamental = secondary risk/context layer, BUKAN predictor utama** untuk horizon 1–21 hari.
  Justifikasi: studi 2025 di *Journal of International Financial Markets, Institutions and Money*
  (technical info lebih kuat untuk horizon pendek; accounting info lebih berguna untuk horizon
  lebih panjang & turnover lebih rendah); momentum relevan di horizon pendek.
- **Pilihan: A (source audit) SEKARANG → C (fundamentals.py + risk flags + endpoint) setelah A lolos.**
  **B (IDX/PDF → parser → SQLite) DITOLAK sekarang** — butuh ticker/period_end/announcement_date/
  source_date/value/restated?/currency/unit; tanpa announcement date, historical fundamental
  backtest tidak aman. B baru masuk akal jika project bergeser jadi fundamental research engine.
- **Constraint yang dibawa dari F2 ke seluruh F3**:
  > setiap fundamental value wajib punya `available_at`; tanpa itu, fundamental TIDAK boleh
  > masuk backtest/predictive score.
- **Tidak ada penalty otomatis** (PER ekstrem / laba negatif / market cap kecil ≠ penalty —
  "small cap = rawan bandar" bukan hukum statistik universal).
- **UNKNOWN tetap UNKNOWN** — missing data jangan diubah menjadi "bad fundamental".
- **Tidak ada penggabungan ke skor** pada tahap pertama. Output terpisah:
  `ready_score`, `recovery_probability`, `fundamental_quality`, `fundamental_flags`
  (contoh target: BBCA READY=82, Recovery 21d=71%, Quality=GOOD, Flags=NONE — bukan FINAL SCORE=84.7).

### Desain yang disepakati

- `fundamental_status`: HEALTHY / NEUTRAL / RISK / UNKNOWN
- `risk_flags`: NEGATIVE_EARNINGS, HIGH_LEVERAGE, EXTREME_VALUATION, LOW_COVERAGE
- Prioritas lapangan: 1) negative earnings (risk context → extra scrutiny pada recovery signal,
  bukan don't-buy); 2) Debt/Equity (structural risk — high leverage + large drawdown + weak recovery
  punya interpretasi ekonomi lebih masuk akal); 3) ROE (profitability/quality context);
  4) PER — hati-hati (earnings≈0, negatif, cyclical, one-off) → deskriptif saja sampai bukti OOS;
  5) PBV — valuation context saja.
- `fundamental_age_days` wajib disimpan bersama nilai, plus `period_end` dan `available_at` terpisah:
  contoh Q1: period_end=2026-03-31, available_at=2026-05-15 → signal 2026-04-20 TIDAK boleh pakai Q1.
  (Sama prinsipnya dengan recovery label.)
- **Uji incremental OOS (gate F3.7, bukan otomatis)**: M0 = RTF+Recovery; M1 = M0+flags;
  M2 = M0+raw ratios; M3 = M0+quality composite. Bandingkan OOS: AUC, PR-AUC, Brier, Calibration,
  Precision@K, Lift, Expectancy, Max DD. M1≈M0 → fundamental tidak masuk scoring, tetap tampil
  sebagai risk context (itu hasil riset yang valid).

### Roadmap F3 — status final (keputusan user, 13 Agu 2026)

```text
F3.1 ✅ Fundamental source audit                    (selesai, 38.2)
F3.2 ✅ Point-in-time / availability-date validation (selesai, 38.3)
F3.3 ✅ fundamentals.py                              (selesai, 38.4)
F3.4 ✅ fundamental risk flags                       (ACCEPTED 17/17, 38.5)
F3.5 ✅ API/UI exposure                              (browser smoke test 9/9 PASS, 38.6-38.7)
F3.6 ⏸️ OOS incremental-value test                   (NOT FEASIBLE with Yahoo — no valid PIT dataset, 38.7)
F3.7 🚫 ONLY IF evidence exists: risk integration    (NO-GO, 38.7)
```

Detail per fase: 38.2–38.7. Status fase final + arsitektur: 38.7.

---

## 38.2 ✅ Status F3.1 — Fundamental source audit (selesai, 13 Agustus 2026)

Sumber yang diaudit: **Yahoo Finance via yfinance 1.5.1** (pola resmi proyek — `yahoo_client.py`),
sampel acak **10 kode** dari universe (seed=42): OMED, BEBS, AKRA, ROCK, DUCK, DAYA, COAL, BLTA, RIMO, BBRM.
Script: `backend/_fase3_source_audit.py` → `data/fundamental_source_audit.json` (log: `data/fase3_source_audit2.log`).

### Hasil — snapshot coverage (info Yahoo)

| Field | Coverage | Catatan |
|---|---|---|
| PER (trailingPE) | 8/10 | MISS di BEBS, COAL (laba negatif → PER memang tak terdefinisi) |
| PBV (priceToBook) | 10/10 | |
| ROE (returnOnEquity) | 8/10 | MISS DUCK, RIMO |
| Debt/Equity | 8/10 | MISS DUCK, RIMO; **BBCA = None (bank)** |
| Market Cap | 10/10 | **RIMO = 0.0** (data tidak valid) |
| EPS (trailingEps) | 7/10 | |
| Net Income | 8/10 | |
| Revenue | 8/10 | |

Ekstrem yang terlihat: BLTA PBV=11333, BBRM PBV=19167 (book value ≈ 0 → PBV meledak),
DAYA DER=209.7, AKRA DER=33.3 — **wajib ada guard nilai ekstrem di F3.4**, bukan penalty.

### Hasil — point-in-time metadata (inti audit)

1. **`available_at` (earningsTimestamp) hanya 1/10** (AKRA), dan nilainya **tidak sinkron**:
   info `earningsTimestampEnd`=2025-07-28, padahal `earnings_dates` AKRA menunjukkan announcement
   2026-07-23, 2026-04-24, 2025-10-22, 2025-07-27. → earningsTimestamp di info TIDAK bisa dipakai
   sebagai available_at.
2. **`earnings_dates` historis: 2/10** (AKRA lengkap 2025–2026; BLTA cuma 2007–2010 = saham bermasalah).
   Sisanya tidak tersedia. EPS actual/estimate semua None → hanya tanggal, bukan nilai.
3. **`fundamentals-timeseries` (data historis Yahoo): 404 di semua varian** (query1/query2, semua
   nama field) — endpoint ini tidak tersedia untuk publik. yfinance 1.5.1 juga tidak punya method-nya.
4. **`income_stmt` / `balance_sheet` kuartalan: TERSEDIA** (5–6 kolom, 38–45 baris) TAPI:
   - **hanya period_end sebagai kolom, TANPA available_at per periode** → tidak memenuhi constraint F3;
   - ada **gap kuartal** (BBCA: 2026-06-30, 2026-03-31, 2025-12-31, 2025-06-30, 2025-03-31 —
     **2025-09-30 hilang**); gap bisa karena saham tidak wajib lapor kuartal tertentu (emisien IDX);
   - `earningsChart.quarterly` memberi EPS aktual 4 kuartal terakhir (BBCA: 117/115/119/121) tanpa tanggal announcement per kuartal.

### Kesimpulan F3.1 (jujur)

- **Snapshot fundamental real-time TERSEDIA dan layak** untuk risk-context layer (F3.3–F3.5):
  coverage PER/PBV/ROE/DER/MCap 8–10/10 dengan session cookie+crumb (`fc.yahoo.com` + `getcrumb`),
  `available_at` harus diambil dari `earnings_dates` bila tersedia, sisanya fallback estimasi
  period_end + lag, atau UNKNOWN.
- **Data historis point-in-time TIDAK tersedia dari Yahoo** untuk backtest: tidak ada available_at
  per periode historis, earnings_dates coverage 20%, fundamentals-timeseries 404, statement kuartalan
  ada gap tanpa announcement date.
- **Dampak ke roadmap**: F3.6 (uji incremental OOS M0–M3) **tidak dapat dijalankan dengan integritas
  point-in-time dari sumber ini** — persis risiko leakage yang dihindari constraint user.
  F3.3–F3.5 tetap jalan (risk context real-time dengan disiplin available_at); F3.6 ditunda sampai
  sumber dengan announcement date historis ditemukan, atau dinyatakan tidak feasible (hasil riset
  valid: fundamental tidak masuk scoring sampai terbukti incremental).
- **Guard yang sudah teridentifikasi untuk F3.4**: nilai ekstrem PBV/DER (book value ≈ 0),
  marketCap = 0, PER tak terdefinisi untuk laba negatif → semua jadi UNKNOWN/deskriptif, bukan penalty.

### Detail teknis audit

- Session wajib: `requests.Session` + User-Agent browser + seed cookie `fc.yahoo.com` + crumb
  `https://query1.finance.yahoo.com/v1/test/getcrumb` → diteruskan ke `yf.Ticker(code+".JK", session=s)`.
  Tanpa ini → `YFRateLimitError` (429) beruntun.
- Endpoint yang diuji: `quoteSummary` (info + earnings + calendarEvents) OK; `fundamentals-timeseries`
  404; `get_income_stmt(freq='quarterly')` OK.
- Data age saat audit (2026-08-13): semua period_end terbaru = 2026-06-30 (Q2 2026) → laporan Q2
  sudah lewat batas rilis khas IDX (~akhir Juli) → usia data ~14 hari untuk Q2 yang sudah diumumkan.

### Next: F3.2 — validasi availability-date per kode

Verifikasi per kode apakah `earnings_dates` tersedia; kalau tidak → skema fallback bertingkat:
(1) earnings_dates → (2) period_end + lag default (mis. T+45) → (3) UNKNOWN. Wajib dicatat per kode
di metadata agar F3.6 (bila nanti ada sumber historis) tidak pernah memakai nilai tanpa available_at.

---

## 38.3 ✅ Status F3.2 — Point-in-time / availability-date validation (selesai, 13 Agu 2026)

Script: `backend/_fase3_pit_validation.py` → `data/fundamental_pit_validation.json`
(log: `data/fase3_pit_validation.log`). Sample 50 kode acak (seed=42) dari universe 963.
`earningsTimestampEnd` TIDAK dipakai sebagai primary PIT source (hanya observasi inkonsistensi).

### Tiga status availability (dipertahankan sampai storage F3.3)

| Status | availability_source | is_observed | pit_safe |
|---|---|---|---|
| observed | `earnings_dates` | true | **true** (satu-satunya yang boleh masuk M1) |
| assumed | `conservative_lag` (period_end + lag) | false | false |
| unknown | `unknown` (available_at=null) | false | false |

UNKNOWN tetap UNKNOWN — dilarang mengisi unknown → period_end+lag demi dataset penuh.

### Hasil per field (n=50)

| Field | observed | assumed | quote | unknown |
|---|---|---|---|---|
| EPS / Net Income / Revenue / ROE / D/E | 3 | 41 | 0 | 6 |
| PER / PBV / Market Cap | 0 | 0 | 50 | 0 |

- **observed = 3/50 (6%)**: AKRA (lag 23d, Q2 2026), MDKA (lag 90d, Q1 2026), JPFA (lag 136d, Q1 2026).
- **assumed = 41/50 (82%)**: period_end ada, earnings_dates tidak ada → conservative lag.
- **unknown = 6/50 (12%)**: period_end missing (DUCK, RIMO, UNIT, PURE, TRAM, GOLL) → available_at=null.
- **Snapshot fields 50/50**: source `quote`, is_observed=true (nilai BENAR-BENAR diamati saat fetch),
  TETAPI `pit_safe=false` + note "no historical PIT" — tidak pernah dipakai sebagai PIT backtest.
- Semua report-based field (EPS..D/E) berbagi tanggal announcement yang sama dari laporan yang sama,
  tapi dihitung per field — bisa beda bila restatement/beda lag resmi.

### Temuan metodologis penting (bukan sekadar hasil)

1. **earningsTimestampEnd tidak sinkron (terkonfirmasi)**: AKRA tsEnd=2025-07-28 vs earnings_dates
   aktual 2026-07-23 (selisih ~1 tahun). MDKA/JPFA kebetulan cocok. → justifikasi user benar:
   earningsTimestampEnd BUKAN primary PIT source.
2. **earnings_dates Yahoo mengandung JADWAL masa depan** (MDKA: baris 2026-09-24 = jadwal rilis Q3,
   belum terjadi, dan tsEnd ikut tercemar). → sanity check wajib filter baris masa depan:
   `max(past_dates)` bukan `max(all)`. Bug ini ditemukan & diperbaiki di F3.2 (MDKA rejected→accepted).
3. **Sanity check accepted/rejected** (sesuai desain user): min 1 baris; available_at > period_end
   (menolak BLTA: 2010-04-16 vs period_end 2026-06-30 — earnings_dates basi); available_at ≤ hari ini+2d
   (menolak jadwal masa depan); lag ≥ 1 hari.
4. **Coverage observed sangat rendah (6%)** → implikasi F3.6: **M1 (observed-only) hampir pasti tidak
   feasible karena sample terlalu kecil** — dan itu sendiri hasil riset yang valid. M2 (observed+assumed)
   mungkin secara teknis, tapi dengan is_observed=false tidak pernah menjadi "PIT ground truth".

### Policy lag (config.py — ASUMSI konservatif, bukan fakta market)

```python
FUNDAMENTAL_LAG_DAYS_BY_MONTH = {3: 90, 6: 60, 9: 90, 12: 150}   # Q1/Q2/Q3/Q4
FUNDAMENTAL_LAG_DEFAULT_DAYS = 150
FUNDAMENTAL_EARNINGS_MIN_ROWS = 1
FUNDAMENTAL_AVAILABLE_FUTURE_TOLERANCE_DAYS = 2
```

Buffer sengaja longgar: salah arah yang aman = LEBIH TUA (tidak bocor), bukan lebih baru (look-ahead).

### Konsistensi dengan batas F3.1 (ditegaskan user)

- Snapshot PER/PBV/ROE/D/E/MCap → diteruskan ke F3.3 sebagai **current risk context** (quote, pit_safe=false).
- Historical PER_t/PBV_t/ROE_t/D/E_t → **TIDAK dipaksakan jadi PIT** hanya karena period_end tersedia.
- Kalau historical PIT tidak tersedia dengan integritas cukup → **fundamental tidak masuk predictive score** (F3.6).

### Next: F3.3 — fundamentals.py

```text
snapshot fundamentals (quote, saat ini)
        +
availability metadata (observed/assumed/unknown per field)
        +
UNKNOWN-safe behavior
        ↓
fundamentals.py → {code, period_end, available_at, availability_source,
                   availability_is_observed, age_days, values{...}}
```

---

## 38.4 ✅ Status F3.3 — fundamentals.py (selesai, 13 Agu 2026)

File: `backend/fundamentals.py` (baru, pure data layer). Test: `backend/_fase3_fundamentals_smoke.py`
→ **126 PASS / 0 FAIL** (log `data/fase3_fundamentals_smoke.log`). Existing tests tetap PASS:
`test_api.py` EXIT=0 (log `data/fase3_test_api_after.log`), `test_real_data.py` EXIT=0.

### Contract yang diimplementasikan

```text
fetch -> normalize -> validate -> attach metadata -> return
```

- `get_fundamentals(code)` → `FundamentalSnapshot(code, as_of, fields{...}, fetch_errors)`
- Setiap field: `FundamentalField` dengan `value, period_end, available_at,
  availability_status, availability_source, is_observed, pit_safe,
  snapshot_only, historical_pit_available, note`
- Report fields (`eps, net_income, revenue, roe, debt_equity`): berbagi tanggal
  announcement laporan (observed bila earnings_dates accepted, assumed bila period_end
  ada + conservative lag, unknown bila period_end None).
- Snapshot fields (`per, pbv, market_cap`): `availability_status="quote"`,
  `is_observed=true` (nilai benar-benar diamati saat fetch), TAPI `pit_safe=false`,
  `snapshot_only=true`, `historical_pit_available=false` — tidak pernah PIT backtest.
- `pit_safe=true` HANYA untuk observed (satu-satunya yang boleh masuk M1 di F3.6).

### Guard yang diimplementasikan (sesuai contract user)

| Guard | Perilaku |
|---|---|
| `finite(value)` | NaN/inf/-inf → None |
| D/E < 0 | None + note "tidak bermakna ekonomis" |
| PER bila EPS ≤ 0 | None + note "EPS <= 0 -> PER not meaningful" (tidak pernah -12.7) |
| PBV bila book value ≤ 0 | None + note "book value <= 0 -> PBV not meaningful" (BLTA/BBRM case) |
| Market Cap ≤ 0 | None + note (RIMO case: 0.0) |
| UNKNOWN | value=None, available_at=None — **tidak pernah di-coerce ke 0** |
| Fetch total gagal | snapshot valid dgn semua field unknown + fetch_errors (tanpa exception) |

### Verifikasi nyata (3 tipe saham, acceptance test user)

- **AKRA** (lengkap + observed): status report=observed, ROE pit_safe=true,
  available_at > period_end (2026-07-23 > 2026-06-30), PER snapshot_only.
- **BEBS** (parsial, laba negatif): ROE negatif & EPS negatif **dipertahankan** (bukan 0),
  PER=None (raw Yahoo None utk laba negatif; guard unit test membuktikan note utk kasus
  raw non-None + EPS≤0).
- **RIMO** (UNKNOWN/extreme): marketCap 0.0 → None + note; field tanpa data → unknown-safe.

### Isolasi yang diverifikasi

- `risk.py`, `api.py`, `recovery.py` tetap importable; `RECOVERY_SIGNAL_P_MIN` tidak berubah.
- fundamentals.py TIDAK mengubah score/signal/API — murni data layer (risk logic menunggu F3.4).
- `earnings_dates` rejection dicatat di `fetch_errors` (transparan, bukan silent).

### Catatan desain (dari F3.2, dipertahankan)

- Coverage observed ~6% adalah **temuan riset, bukan bug** — tidak ada pelonggaran policy.
- Metadata assumed TIDAK dihapus — ia perkiraan conservative policy, bukan invalid.
- Snapshot fields ditandai eksplisit `historical_pit_available=false` — tidak ada
  pretensi bisa dipakai historical backtest.

## 38.5 ✅ Status F3.4 - fundamental_risk.py (selesai, 13 Agu 2026)

### Contract yang diimplementasikan (keputusan user, 13 Agu 2026)

- **Bukan score, bukan predictor, bukan penalty** — risk-CONTEXT classifier
  "bodoh tapi jujur". `READY 82 + RISK` dimungkinkan (context, bukan hukuman).
- Nama file **`fundamental_risk.py`** (bukan `risk.py` — file existing yang
  dipakai api/recovery TIDAK ditimpa; verifikasi di smoke test).
- Output: `fundamental_health` (HEALTHY|NEUTRAL|RISK|UNKNOWN), `data_quality`
  (GOOD|PARTIAL|LOW — **terpisah dari health**), `flags`, `reasons`
  (human-readable per flag), `coverage` (counts + ratio), `context`
  (market_cap — konteks, BUKAN flag; anti double-count dengan liquidity engine).

### Aturan per flag

- **NEGATIVE_EARNINGS**: EPS < 0 OR Net Income < 0. EPS=None → UNKNOWN (bukan
  flag). PER negatif tidak pernah trigger (F3.3 sudah null-kan PER tak bermakna).
- **HIGH_LEVERAGE**: D/E > `FUNDAMENTAL_FLAG_DER_HARD_EXTREME` (150.0, heuristic
  guard di config.py — bukan universal danger threshold; DAYA 209.7 trigger).
- **EXTREME_VALUATION**: PER > 100 OR PBV > 20 (guard sangat ekstrem; ROCK PER=106,
  BLTA PBV=11333 trigger). PER=None karena EPS≤0 TIDAK jadi flag ini — domainnya
  NEGATIVE_EARNINGS (BEBS: PER=None + NEGATIVE_EARNINGS, bukan EXTREME_VALUATION).
- **LOW_COVERAGE**: coverage ratio < 0.60 atas REPORT_FIELDS, weight
  observed=1.0, assumed=0.5, unknown=0.0. **Data-quality dimension, bukan
  probability** — counts observed/assumed/unknown dilaporkan apa adanya
  (keputusan user: laporkan counts, tanpa weighted score tambahan di luar ini).
- Hierarchy health (hindari HEALTHY jadi default): ratio < 0.25 → UNKNOWN;
  else material flag → RISK; else ratio ≥ 0.80 → HEALTHY; else NEUTRAL.
- `data_quality`: GOOD ≥ 0.80, PARTIAL ≥ 0.40, LOW < 0.40. Semua assumed = 0.5
  → NEUTRAL + PARTIAL (assumed ≠ observed, tidak boleh jadi HEALTHY).

### Verifikasi nyata + acceptance test user (66/66 PASS)

| Kode | health | quality | flags | coverage | arti |
|------|--------|---------|-------|----------|------|
| AKRA | HEALTHY | GOOD | — | 1.00 | observed penuh, tanpa flag |
| BEBS | RISK | PARTIAL | NEGATIVE_EARNINGS | 0.50 | laba negatif nyata; PER None bukan valuation flag |
| RIMO | UNKNOWN | LOW | LOW_COVERAGE | 0.00 | data minim nyata; UNKNOWN ≠ RISK |

- Kasus sintetis: normal/assumed/negatif-leverage/ekstrem/partial/unknown,
  extreme 1e300 tidak crash, semua flag punya reason, threshold ada di config.
- **Isolasi**: `RECOVERY_SIGNAL_P_MIN` (0.68) & `RECOVERY_MODEL_P_MIN` (0.5)
  tidak berubah; `risk.py` existing masih importable; api/recovery tidak disentuh.
- Regresi: `test_api.py` selesai tanpa FAIL, `test_real_data.py` selesai normal.

### Next: F3.5 — integrasi ke api.py (fundamental_status + fundamental_flags
terpisah dari skor, tanpa penalty)

## 38.6 ✅ Status F3.5 - integrasi api.py (selesai, 13 Agu 2026, auto DONE + REPORT)

### Yang diimplementasikan

- `api.py` meng-import `fundamental_risk`; `analyze_stock()` memanggil
  `assess_fundamental_risk(kode)` dan menambahkan **3 field top-level baru**
  (bukan nested di score — TERPISAH dari skor):
  - `fundamental_status`: HEALTHY | NEUTRAL | RISK | UNKNOWN
  - `fundamental_flags`: `[{flag, reason}, ...]` (human-readable)
  - `fundamental_meta`: `{data_quality, coverage, context, fetch_errors}`
- **Tanpa penalty**: `score_result` tidak disentuh sama sekali; hanya
  short_selling gate (existing) yang memodifikasi recommendation, dan itu
  pre-existing. Verified: score dict punya kunci original persis
  (`valid/swing_score/components/recommendation/confidence/risk_level/
  prob_continuation/prob_reversal/regime`) — tidak ada kunci fundamental.
- **Fetch fundamental tidak boleh merusak endpoint**: seluruh assessment
  dibungkus try/except → gagal fetch ⇒ `fundamental_status="UNKNOWN"` +
  `fetch_errors` transparan (bukan RISK, bukan error 500).

### Verifikasi (30/30 PASS, fetch nyata)

| Kode | fundamental_status | flags | meta |
|------|--------------------|-------|------|
| AKRA | HEALTHY | — | data_quality=GOOD, coverage 1.00 |
| BEBS | RISK | NEGATIVE_EARNINGS + reason | terpisah dari score |
| RIMO | skip (data harga < min — delisted; perilaku existing, bukan F3.5) |

- Catatan: `score.valid=False` untuk BEBS adalah perilaku EXISTING dari
  scoring.py line 172-173 (NaN indicator pada data tipis) — tidak ada kaitannya
  dengan F3.5; blok fundamental hanya menambah field response.
- Regresi: `test_api.py` [DONE] tanpa FAIL, `test_real_data.py` selesai normal,
  smoke F3.4 66/66 PASS.

### Bug yang ditemukan & diperbaiki (response_model filter)

- Smoke awal hanya memanggil `analyze_stock()` langsung → field fundamental
  ADA. Tapi endpoint HTTP `/analisis/{kode}` memakai `response_model=
  AnalisisResponse` (Pydantic) yang BELUM punya field fundamental → FastAPI
  **diam-diam memfilter** field tersebut dari response (status=None).
- Perbaikan: tambah `FundamentalFlagResponse`, `FundamentalCoverageResponse`,
  `FundamentalMetaResponse` + 3 field opsional di `AnalisisResponse`.
- Verifikasi HTTP final (server nyata): AKRA → HEALTHY/[] /GOOD,
  BEBS → RISK/[NEGATIVE_EARNINGS]/PARTIAL, BBCA → HEALTHY/[]/GOOD.
  Skor tidak berubah (AKRA 43.6 HOLD, BBCA 55.7 HOLD).

### Trade-off yang dicatat (untuk F3.6/optimasi nanti)

- Setiap `/analisis` kini fetch fundamental tambahan ke Yahoo (network
  ~1-3 detik, tanpa cache). Diterima untuk integrasi pertama; cache snapshot
  (mis. TTL 24 jam per kode) adalah optimasi terpisah — bukan kewajiban F3.5.

## 38.7 ✅ Status F3.5 final + F3.6 verdict (ditutup 13 Agu 2026)

### F3.5 — API/UI exposure: TERTUTUP (browser smoke test 9/9 PASS)

- Browser smoke test nyata (Playwright, server user yang berjalan):
  - `/saham/AKRA` → kartu "Fundamental Context" tampil, badge **HEALTHY**,
    disclaimer "TIDAK memengaruhi skor", card Swing Score tetap tampil.
  - `/saham/BEBS` → kartu tampil, badge **RISK**, flag **Laba Negatif**,
    card Swing Score tetap tampil.
- Screenshot: `Temp/opencode/f36_AKRA.png`, `f36_BEBS.png`.
- Tidak ada perubahan skor/rekomendasi yang teramati di UI.

### F3.6 — PIT incremental-value test: NOT FEASIBLE dengan sumber Yahoo

- Verdict resmi: **not feasible / no valid PIT dataset** — BUKAN eksperimen
  yang tidak dilakukan. Historical PIT Yahoo hampir pasti tidak cukup untuk
  menjalankan F3.6 secara integritas (lihat F3.1/F3.2: historical_pit_
  available=false, observed hanya ~6%, earnings_dates rejection).
- Konsisten dengan prinsip Fase 2: **tidak ada evidence ≠ evidence bahwa
  fundamental tidak berguna.** Fundamental tetap risk-context layer dan
  tidak menyentuh score.
- F3.7 (fundamental → score adjustment): **NO-GO** sampai ada sumber
  historical fundamental yang benar-benar point-in-time.

### Status fase final (keputusan user, 13 Agu 2026)

```text
F3.1 ✅ Source audit
F3.2 ✅ PIT validation
F3.3 ✅ Data layer
F3.4 ✅ Risk flags            (ACCEPTED, 17/17)
F3.5 ✅ API/UI exposure       (browser smoke test 9/9 PASS)
F3.6 ⏸️ PIT incremental test  ← NOT FEASIBLE with Yahoo
F3.7 🚫 NO-GO                 ← tidak ada evidence incremental PIT
```

### Arsitektur final

```text
Technical / Price / Volume
        │
        ├── Ready To Fly
        ├── Recovery
        └── Swing Score
                  │
                  ▼
             Signal / Rank

Fundamentals
        │
        ├── HEALTHY
        ├── NEUTRAL
        ├── RISK
        └── UNKNOWN
                  │
                  ▼
          Risk Context Only
```

Sehat karena: predictive engine terlindungi dari data non-PIT; fundamental
tetap informatif; UNKNOWN dihormati; tidak ada double-count market cap/
liquidity; tidak ada hidden penalty; threshold fundamental tidak di-tune
dengan backtest.

### Detail implementasi UI (F3.6 code — terverifikasi via browser smoke test)

- `frontend/types/api.ts`: tipe `FundamentalFlag`, `FundamentalCoverage`,
  `FundamentalContext` + 3 field opsional di `AnalisisResponse`.
- `frontend/app/saham/[kode]/page.tsx`: kartu **"Fundamental Context"** di bawah
  grid Score Cards — badge status (HEALTHY/NEUTRAL/RISK/UNKNOWN + sub-teks),
  badge data quality (GOOD/PARTIAL/LOW), daftar flag dgn label Indonesia
  (Laba Negatif / Leverage Tinggi / Valuasi Ekstrem / Data Minim) + reason
  human-readable, market cap sebagai konteks (bukan flag), fetch_errors
  transparan. Teks eksplisit: "Konteks risiko fundamental — TIDAK memengaruhi
  skor".
- Verifikasi teknis: `tsc --noEmit` bersih, `next build` sukses (7 routes).

### Acceptance criteria F3.4 (checklist user — SEMUA TERVERIFIKASI)

| Kriteria | Status |
|----------|--------|
| HEALTHY / NEUTRAL / RISK / UNKNOWN | PASS (smoke 66/66) |
| NEGATIVE_EARNINGS (EPS<0 OR NI<0; EPS=None → UNKNOWN; PER<0 tidak trigger) | PASS |
| HIGH_LEVERAGE (DER > hard_extreme 150.0, config, risk guard bukan predictive) | PASS |
| EXTREME_VALUATION (PER>100 OR PBV>20, guard sangat ekstrem, heuristic) | PASS |
| LOW_COVERAGE (weighted observed=1.0/assumed=0.5/unknown=0; counts dilaporkan) | PASS |
| no score penalty | PASS (RECOVERY_SIGNAL_P_MIN tetap, score keys original) |
| no READY/ALMOST modification | PASS (recovery.py/risk.py tidak disentuh) |
| UNKNOWN != RISK | PASS (RIMO → UNKNOWN + LOW_COVERAGE, bukan RISK) |
| missing != zero | PASS (EPS/D/E None dipertahankan None) |
| negative EPS handled correctly | PASS (BEBS EPS -0.84; PER=None bukan valuation flag) |
| invalid PBV handled correctly | PASS (F3.3 guard → None, tidak crash) |
| invalid D/E handled correctly | PASS (F3.3 guard → None, bank case) |
| extreme values don't crash | PASS (1e300 test) |
| every flag has human-readable reason | PASS (reasons per flag, non-empty) |
| data quality exposed separately | PASS (data_quality GOOD/PARTIAL/LOW terpisah) |
| thresholds reside in config.py | PASS (6 konstanta FUNDAMENTAL_*) |
| tests cover normal/extreme/unknown cases | PASS (sintetis + nyata AKRA/BEBS/RIMO) |

### Catatan penutup (F3.7 & optimasi)

- **F3.7 (fundamental → score adjustment): NO-GO** sampai ada evidence
  PIT fundamental historical yang valid & OOS test. Threshold F3.4 DILARANG
  di-tuning via backtest (anti data-snooping, konsisten dgn Fase 2).
- Optimasi opsional (bukan kewajiban): cache snapshot fundamental per kode
  (TTL ~24 jam) utk mengurangi latensi /analisis.


---

## 35. P6 - Production Integrity & Execution Audit (15 Agustus 2026)

Audit eksternal (C1-C16, rating ~6.5/10 research maturity) diverifikasi ke kode
aktual: C1/C5/C7 = VALID (split posisi bar bocor, entry close[i], end_d=today),
C2/C6/C8-C16 = PARTIAL/VALID (CI delta-method+scale, tanpa slippage, skip window
diam-diam, survivorship, ARA terminology). Seluruh remediation P6.1-P6.7 dikerjakan
sesuai instruksi user; hasil di bawah. **Tidak ada perubahan production ranking
M5/M10; RTF config UNCHANGED; p_min 0.68 FROZEN; P4.8 tetap WAIT.**

### P6.0 Web research (grounding metodologi)

- **Purge/embargo** (de Prado, AFML ch.7): buang train obs yang label span-nya
  overlap test span + buffer embargo; overlap = [t0, t1] ∩ [T0, T1] ≠ ∅.
- **Shumway (1997)** "The Delisting Bias in CRSP Data" (J. Finance): delisting
  return hilang utk delist negatif = bias material; studi pasar berkembang
  (India smallcap, 2025): ~4.9pp annual overstatement.
- **Backtrader**: market order dieksekusi di next bar open + slippage (slip_open);
  close-order = tanpa slippage. Konvensi defensible utk entry.
- **Cluster inference** (MacKinnon-Nielsen-Webb 2025): WCLU-S bootstrap / jackknife
  t(G-1) > CV1; untuk logit produksi → cluster bootstrap saham (konsisten F2.3).

### P6.1 (C1) - Split global kronologis + purge + embargo [SELESAI]

Script baru _phase6_p61_calibrate.py (calibrator lama _calibrate_recovery_model.py
tidak disentuh; output file baru data/recovery_model_params_p6.json).

- Cutoff = tanggal ke-70% rentang global = **2025-11-24** (bukan posisi bar).
- TRAIN = obs dgn date_e < cutoff - embargo(5 hari kalender); PURGED = obs yg
  labelnya menembus cutoff; TEST = obs dgn date_s >= cutoff (window penuh).
- Hasil h=21: n_train=110.728, **n_purged=19.782** (obs bocor dibuang),
  n_test=127.588, episode train 2.760 / test 2.233, AUC_test **0.847**
  (lama 0.83 di split bocor), Brier 0.095.
- **TEMUAN PENTING - kalibrasi OOS bersih (h=21) OVERPREDICT**: deviasi prediksi
  vs aktual di TEST bersih: bucket 0.05-0.10 → −0.089; 0.10-0.15 → **−0.147**;
  0.15-0.25 → **−0.107**; 0.25-0.40 → −0.039. Model produksi lama overpredict
  recovery di periode Nov-2025 s/d Agu-2026; klaim config lama "deviasi OOS
  <= 0.03" diukur pada split posisi yang bocor = TIDAK valid.

### P6.2 (C2) - Cluster bootstrap CI (saat produksi) [SELESAI]

- CI = cluster bootstrap SAHAM (resample 963 saham, refit logistic, percentile
  90%, B=500, seed 42) — menggantikan delta-method + scale ad-hoc.
- Disimpan di params sebagai ci_cluster.<h> (grid dd 0.05-0.80 + tabel
  prob_ci_low/high); ci_bootstrap legacy = None.
- ecovery.py ecovery_model_probs() di-update: prioritas ci_cluster
  (interpolasi), fallback delta+scale utk params lama (backward compat).
- Contoh h=21 dd=0.15: p=0.366, CI (0.349, 0.384) — CI sempit & masuk akal.
- **Catatan**: params P6 memberi probabilitas LEBIH TINGGI dari params lama di
  dd sama (h=21 dd=0.15: 0.366 vs 0.324; dd=0.05: 0.590 vs ~0.5x) → perubahan
  perilaku sinyal fallback jika di-switch (lihat keputusan tertunda di bawah).

### P6.3 (C7) - Completed-bar policy [SELESAI]

- data_source/yahoo_client.py: last_completed_idxs_session() = sesi IDX
  terakhir yg SUDAH selesai (WIB-aware: <16:00 WIB → hari kerja sebelumnya;
  weekend → mundur). Default etch_trading_info (tanpa target_date) kini
  memakai sesi completed, bukan date.today().
- Hard guard: bar dgn tanggal > end_d DIBUANG (partial bar / data delayed).
- Heuristik tanpa kalender libur IDX (keterbatasan sumber) — didokumentasikan;
  saat Senin libur tetap benar (mundur ke Jumat).

### P6.4 (C5/C6/C16) - Sensitivitas eksekusi backtest [SELESAI]

acktest.py: + entry_mode (close|open) + slippage_bps (buy naik, sell
turun) di BacktestConfig + CLI. Grid 5 saham liquid (BBCA BMRI ASII TLKM BBNI,
length 500) -> data/phase6_execution_sensitivity.json:

| entry + slippage | trades | WR | avg ret | avg sharpe |
|---|---|---|---|---|
| close + 0bps (lama) | 75 | 47.3% | **−5.24%** | −0.13 |
| open + 0bps | 79 | 49.3% | **−15.17%** | −0.31 |
| open + 25bps | 77 | 48.1% | −18.24% | −0.41 |
| open + 50bps | 81 | 46.2% | −31.82% | −0.85 |
| open + 100bps | 81 | 45.3% | −37.35% | −1.02 |

**Kesimpulan C5/C6 terbukti material**: asumsi eksekusi mengubah hasil drastis
(−5% → −37%); hasil backtest lama (close-entry, tanpa slippage) = optimis.
Sensitivitas ini WAJIB dilaporkan berdampingan dengan klaim PnL.

### P6.5 (C4) - Survivorship [SELESAI]

data/phase6_survivorship.json (menggabungkan delisted_ohlcv.npz + meta + bias
check existing):

- Universe live 963 kode; delisted 31 seeds (16 dgn data, 15 tanpa data).
- **0 saham delisted punya bar di window OOS Phase 5** (semua berakhir <=
  2025-07-23 < cutoff 2025-11-24) → OOS precision tidak tercemar langsung.
- Model produksi overpredict recovery pada saham yg akhirnya delisted
  (h=21: pred 0.126 vs aktual 0.072, overpred +0.054; h=63: +0.144) — konsisten
  Shumway; dampak refit parameter kecil (delta rel b terbesar 0.0013 h=63).
- Label wajib: **"survivorship-limited backtest"** — hasil berlaku utk saham
  yang bertahan; probabilitas recovery saham berisiko delisting cenderung
  overestimasi.

### P6.6 (C8/C9) - Transparansi skip window walk-forward [SELESAI]

- un_walk_forward(..., return_meta=True) → meta {windows_total, evaluated,
  skipped, skip_reasons {no_train_fit, under_min_trades, oos_error}, skip_log
  [{window_id, reason, n_trials}]}; default tetap return list (non-breaking).
- Report CLI/JSON menampilkan wf_meta. Smoke test BBCA+BMRI --local:
  8 windows total, 8 evaluated, 0 skipped, 36 param sets. P(skip|regime)
  tersedia via skip_log utk analisis lanjut.

### P6.7 (C10-C15) - Claims audit & terminology [SELESAI]

- Klaim "split temporal 70/30" stale dihapus dari config.py & recovery.py
  docstring → diganti deskripsi P6.1 (script baru).
- ARA → user-facing alias **large_upmove_date / large_upmove_ref_price /
  prev_large_upmove_*** ditambahkan di RecoveryAccumulation,
  ReadyToFlyEntryResponse, builder readytofly, dan dict recovery.py — istilah
  benar (ARA resmi BEI bertingkat 35/25/20, threshold kami heuristic +10%),
  field lama dipertahankan utk backward compat frontend.
- Score ≠ probability: sudah terdokumentasi (skor ranking RTF = density x
  net_dist_heavy x decay; probabilitas hanya dari model recovery/base rate).

### Refresh dataset universe (15-08-2026)

_build_recovery_dataset.py dijalankan ulang: 963 kode, OK=962 (CNTX delisted
tetap gagal), **max date 2026-08-14** (921 saham punya bar 14/8; sebelumnya
828 @13/8). Snapshot Phase 5 (phase5_snapshot_universe_ohlcv.npz) TIDAK
disentuh. Artinya: store riset kini punya 14/8 → fondasi utk P4.8 kelak
(label h10/h21 butuh 10-21 hari trading setelah sinyal → layak akhir Agu/awal Sep).

### KEPUTUSAN TERTUNDA - menunggu user

1. **Switch params produksi ke recovery_model_params_p6.json?**
   - Pro: P6.1 menghapus split bocor; klaim kalibrasi jadi valid.
   - Kontra: model P6 LEBIH OPTIMIS (kalibrasi OOS bersih overpredict di
     bucket 0.10-0.25, dev −0.15); sinyal fallback POTENTIAL berubah; ini
     perubahan production → melanggar spirit freeze point tanpa persetujuan.
   - Backup params lama tersedia utk revert.
2. Jika switch disetujui: _validate_recovery.py dijalankan ulang utk memastikan
   pipeline produksi sehat sebelum dipakai.
3. Kalibrasi OOS jelek di params P6: opsi lanjut (belum dikerjakan, butuh
   keputusan): (a) terima & dokumentasikan sebagai regime-sensitivity,
   (b) kalibrasi ulang (isotonic/Platt) pada test bersih — hati-hati
   data-snooping, (c) tunggu data baru utk re-evaluasi kalibrasi.

### P6.9 - Promote params P6 + re-evaluate calibration [SELESAI, keputusan user 15-08-2026]

Keputusan user: **switch params produksi ke params P6 (correctness fix, bukan
parameter optimization)** — mempertahankan params lama = mempertahankan model
yang fit dengan validation procedure yang sudah dinyatakan tidak valid.

Urutan eksekusi:

1. Backup params lama -> data/recovery_model_params_pre_p6_backup.json (14.424
   bytes, hash lama ABD9CEDC... tetap tersimpan utk revert).
2. ecovery_model_params.json <- params P6 (hash baru
   **F495252969AF96CF6A0732659FD0F9A98BA78ECD879A23F566334B9C963FEAA1**).
3. Smoke tests: recovery_model_probs pakai ci_cluster (h21 dd=0.15 -> p=0.366,
   CI 0.349-0.384); fallback legacy tetap jalan (backup params -> p=0.324,
   delta+scale); shrinkage params terpisah tidak tersentuh; import/compile OK.
4. API smoke test nyata: /recovery/BBRI HTTP 200, alias baru
   large_upmove_date/large_upmove_ref_price tampil di response (P6.7 field).
5. Cache Phase 4 di-rebuild (--force): prior_peak kini memakai params P6.

Re-evaluasi kalibrasi (_phase6_p69_recalib.py -> data/phase6_p69_recalib.json):
calibration window = 126 hari trading terakhir DEV P6 (purged), evaluasi di
TEST BERSIH P6 (cutoff 2025-11-24), BSS ref = frozen base rate (bukan prevalence
VAL). Per target x horizon diuji M0 raw / M1 intercept-only / M2 slope+intercept
(sensitivity), plus diag slope/intercept di VAL dan Case C (saturation p_min 0.68):

| Layer | Hasil VAL | Keputusan |
|---|---|---|
| previous_close h1 | M0 B=0.190 O/E=2.03 -> M1 c=0.911 B=0.176 O/E=0.96, sat68 ~0 | **M1 baru** |
| previous_close h3 | M0 0.265/1.52 -> M1 c=0.738 0.244/0.95 | **M1 baru** |
| previous_close h5 | M0 0.271/1.40 -> M1 c=0.739 0.250/0.94 | **M1 baru** |
| previous_close h10 | M1 B turun TAPI **Case C**: sat68 1.7%->30.5% | **M0** (veto) |
| previous_close h21 | M1 B turun TAPI **Case C**: sat68 0%->**100%** (gate mati total) | **M0** (veto) |
| previous_close h42/63 | M1 memperburuk Brier (over-shrink O/E 0.86-0.89) | **M0** |
| prior_peak h1-63 (layer P6) | M1 tidak membantu (Brier ~sama); h42-63 intercept ~0, masalah SLOPE (diag VAL 1.36-1.55, O/E 0.59-0.64) | **M0 P6 raw semua h** |

Catatan: M1 baru = intercept-only (monotonic -> AUC/ranking identik M0, rule 6
P4.8 tetap berlaku). Case C h10/h21 konsisten acceptance_rules.overall P4.8:
"M1 TIDAK boleh dipromosikan bila operational selectivity rusak WALAUPUN Brier
lebih baik". Temuan kalibrasi temporal prior_peak h42-63 (O/E 0.59-0.64) =
problem slope bukan intercept -> intercept recalibration tidak menyelesaikan;
dokumentasikan, bukan keputusan holdout.

### P6.10 - Re-freeze P4.8 holdout methodology [SELESAI, 15-08-2026]

data/phase4_holdout_config.json di-re-freeze (holdout TIDAK dibuka; ini
perbaikan methodology sebelum final experiment):

- production_params_snapshot.recovery_model_params.json -> hash P6 baru
  (harness ABORT kalau params bergeser diam-diam; hash lama di-backup).
- m1_candidate DIREVISI: previous_close **h1/3/5** (c = 0.9112 / 0.7382 /
  0.7387, source P6.9). M1 lama (P4.7, h1-21) INVALID: diturunkan dari layer
  pre-P6; h10/21 veto Case C; h42/63 M0; prior_peak M0 semua h.
- decision_reference diperbarui dengan catatan re-freeze.

Verifikasi harness (_phase4_holdout.py --selftest --cutoff 2025-11-01, output
data/phase4_holdout_report_selftest_p6.json, DITANDAI SELF_TEST - bukan bukti):

- Hash params match config: PASS (ABORT sebelumnya krn hash salah dicatat -
  diperbaiki).
- M1 baru: h1 8/8 rules PASS (brier CI M1 [0.172,0.181] vs M0 [0.184,0.197]
  non-overlap, O/E CI M1 [0.924,0.995]); h5 8/8 PASS; h3 7/8 (rule 8 FAIL:
  hanya 24 POTENTIAL -> n_stocks_potential < 10 di selftest window; dievaluasi
  ulang di holdout final, bukan blocker).
- h10/21/42/63 + prior_peak semua: M0_ONLY sesuai config.
- Bootstrap CI stock-cluster B=1000 + date-block B=500 jalan di semua blok.

**Status production pasca-P6.9/P6.10:**

`	ext
P6 params = ACTIVE (hash F4952529...)
M1 = candidate previous_close h1/3/5 (c baru P6.9) · p_min 0.68 FROZEN
prior_peak = M0 P6 raw · P4.8 holdout = WAIT (genuinely unseen data)
`

**Standar reporting backtest (keputusan user, P6.4):** primary = next-open +
realistic slippage; sensitivity = next-open 0/25/50/100bps; legacy close+0bps
hanya historical comparison. **Survivorship wording:** direct OOS contamination
tidak teramati di window Phase 5, tapi historical-universe completeness tetap
unresolved (bukan "solved").

### P6.11 - Keputusan FINAL user (15-08-2026): freeze point pasca-P6, STOP sampai P4.8

**Keputusan user: jangan lakukan perubahan apa pun sebelum P4.8.** Menahan diri
dari perubahan = bagian dari metodologi, bukan kurangnya pekerjaan.

**Wording resmi (dipakai di seluruh doc mulai sekarang):**

- P6 params = **methodologically corrected production parameters** (bukan
  "final optimal parameters" — alasan ACTIVE = perbaikan proses estimasi yang
  sebelumnya tidak valid temporal, bukan karena Brier/AUC lebih baik).
- M1 h1/3/5 = **frozen recalibration candidate pending final locked holdout**
  (bukan "validated" — dipilih menggunakan development/validation evidence).
- Probability calibration ≠ decision calibration: M1 memperbaiki kalibrasi
  (h10: POTENTIAL share 30.5%; h21: 100%) tapi menghancurkan selectivity gate
  -> gate saturation = VETO (sudah benar, bukan mengejar Brier lebih rendah).
- p_min = 0.68 **FROZEN. Jangan diubah** untuk "menyelamatkan" M1 — itu tuning
  baru yang merusak fungsi holdout sebagai final evidence.

**Interpretasi selftest (bukan bukti):**

- Selftest h3 rule 8 FAIL (24 POTENTIAL di selftest window) **bukan model
  failure**; rule 8 dievaluasi di genuine holdout. Bila h3 INSUFFICIENT di
  holdout -> verdict **INCONCLUSIVE** (bukan geser cutoff, bukan longgarkan rule).

**P4.8 = satu tembakan:**

`	ext
Phase 4 -> P6 corrected probability layer -> P6.10 frozen config
        -> genuinely unseen data -> RUN ONCE
`

Dilarang: holdout -> lihat hasil -> ubah M1 -> rerun (holdout berhenti menjadi
holdout; repeated OOS/model-selection cycles meningkatkan false-discovery risk).

**TIDAK ada research phase baru** (semua ditolak user sampai holdout): isotonic
lagi, M1 h10/h21 dipaksa, tune p_min, regime-specific calibration, CPCV,
tambah recovery features, tambah RTF features, ML. P6 sudah menjawab gap
correctness paling kritis. Brier decomposition tetap diagnostic saja.

**Status final (freeze point pasca-P6):**

`	ext
F2  ✅ Statistical integrity
F3  ✅ Fundamental risk context
F4  ✅ Probability-quality framework
F5  ✅ RTF incremental-value study -> REDUNDANT
P6  ✅ Production integrity corrections
P6.9 ✅ Corrected params ACTIVE
P6.10 ✅ Holdout methodology RE-FROZEN
P4.8 ⏳ WAIT (genuinely unseen data; label h10/h21 matang ~akhir Agu/awal Sep)

Recovery params   = P6 ACTIVE (hash F4952529...) · old = BACKUP ONLY
shrinkage         = ACTIVE · cluster CI = ACTIVE
target semantics  = FROZEN · DD clamp 0.85 = FROZEN
M1                = previous_close h1/3/5 candidate (c 0.9112/0.7382/0.7387)
previous_close h10-63 = M0 · prior_peak semua h = M0
p_min             = 0.68 FROZEN
RTF config        = UNCHANGED · RTF ranking role = secondary technical context
Fundamentals      = risk context only
`

Verdict P4.8 kelak dibaca sebagai: **validation terhadap seluruh probability
stack terbaru** (P6 recovery estimation + M1 candidate + p_min frozen) sebagai
satu production probability pipeline.

---

# 39. TODO Tambahan — Production Integrity & Execution Audit (P7)

> Catatan: Semua TODO di bawah ini adalah tambahan. Seluruh isi, keputusan,
> prioritas, roadmap, dan TODO pada §0–§7 di atas tetap dipertahankan tanpa
> perubahan.
>
> (Catatan metodologi: sumber Reddit/GitHub yang ditemukan selama riset —
> script indikator "volume breakout" TradingView, dsb. — sengaja tidak dikutip
> sebagai evidence di atas karena tidak menyertakan validasi walk-forward/OOS
> yang bisa diverifikasi, sesuai instruksi untuk tidak memperlakukan sumber
> komunitas setara bukti akademik.)

## Recommended Execution Order — P7

P7.1 Backtest Temporal Integrity → P7.2 Portfolio-Level Aggregation →
P7.3 Realistic Execution Standard → P7.4 Production Calibration/Provenance
Guard → P7.5 Recovery Episode/Dependence Sensitivity → P7.6 Corporate-Action
Integrity → P7.7 Survivorship/Historical Universe Integrity → P7.8 Embargo
Sensitivity → P7.9 Walk-Forward Selection Transparency → P7.10 Stale
Methodology/Legacy Guard → P7.11 Base-Rate Artifact Integrity → P7.12
Probability CI Semantics → P7.13 Final Holdout Pre-Registration → P7.14 Final
Claims Audit → **P4.8 FINAL LOCKED HOLDOUT — RUN ONCE**

## Important scope rule

P7 tidak berarti semua item otomatis harus mengubah production. Untuk item yang
berbentuk sensitivity/research (P7.5, P7.6, P7.8, P7.9), hasil negatif atau null
dapat menjadi alasan yang valid untuk **tidak** mengubah architecture.

Tujuan P7 adalah: memperbaiki validity dan mengetahui apakah assumption
tertentu benar-benar consequential, **bukan** membuat model semakin kompleks.

## Checklist Status P7 (di-update setiap progres)

- [x] P7.1 — Backtest Temporal Integrity [CRITICAL] — selesai 16-08-2026
- [x] P7.2 — Portfolio-Level Backtest Aggregation [CRITICAL] — selesai 16-08-2026
- [ ] P7.3 — Realistic Execution Standard [CRITICAL]
- [ ] P7.4 — Production Calibration / Parameter Provenance Guard [CRITICAL]
- [ ] P7.5 — Recovery Episode / Dependence Sensitivity [HIGH]
- [ ] P7.6 — Corporate-Action Integrity [HIGH]
- [ ] P7.7 — Survivorship / Historical Universe Integrity [HIGH]
- [ ] P7.8 — Embargo Sensitivity [MEDIUM/HIGH]
- [ ] P7.9 — Walk-Forward Selection Transparency [MEDIUM]
- [ ] P7.10 — Stale Methodology / Legacy Guard [MEDIUM]
- [ ] P7.11 — Base-Rate Artifact Integrity [MEDIUM]
- [ ] P7.12 — Probability CI Semantics [MEDIUM]
- [ ] P7.13 — Final Holdout Pre-Registration [CRITICAL]
- [ ] P7.14 — Final Claims Audit [HIGH]

## Detail TODO P7

### P7.1 — Backtest Temporal Integrity [CRITICAL]

Audit backtest.py untuk memastikan seluruh metadata keputusan pada trade entry
memakai signal state t-1 ketika entry dilakukan pada open_t.

**TEMUAN (16-08-2026):** Entry path memakai `recs[i-1]` (benar — sinyal bar
i-1), TETAPI seluruh metadata keputusan diambil dari bar EKSEKUSI i:
`atr_val[i]`, `_risk_level(atr_val, i)`, `gate[i]`, `rvol[i]`,
`signals["trend"/"momentum"/"volume"/"price_action"][i]`, `swing_scores[i]`
(entry_score). Untuk entry_mode="open", ATR/komponen bar i BELUM tersedia saat
open i (bar i belum selesai) → **current-bar leakage pada SL, TP, risk_level,
confidence, entry_score, breakeven trigger, trailing stop**.

**FIX:** Decision timestamp = close bar sinyal (i-1). Semua metadata keputusan
diambil dari bar i-1: `atr_val[i-1]`, `_risk_level(atr_val, i-1)`,
`gate[i-1]`, `rvol[i-1]`, komponen & swing_score `[i-1]`. Harga eksekusi tetap
bar i (`open_[i]` utk mode open, `close[i]` utk mode close) — itu konvensi
eksekusi, bukan metadata keputusan. Exit path sudah benar sejak audit #7
(`recs[i-1]` utk REVERSAL; SL/TP pakai high/low bar i — legal karena posisi
sudah terbuka sejak open i).

**Unit test:** `backend/test_temporal_integrity.py` — 3 test yang SECARA
EKSPLISIT gagal bila bar eksekusi bocor (entry_score ≠ score bar sinyal,
SL/TP ≠ ATR[i-1], risk_level/confidence ≠ state i-1):
- Sebelum patch: 2/3 FAIL (banyak bukti leakage: entry_score 38.6 vs 34.6, SL
  1042.55 vs 1043.72, dll)
- Sesudah patch: 3/3 PASS (data sintetis deterministik, tanpa network)

**Regression (data real, entry_mode=open, slippage 25bps, 5 saham):**
- BBCA: 7→8 trades, ret 12.88%→4.12%, sharpe 0.79→0.40 (SL/TP & exit berubah
  karena metadata kini dari bar sinyal — dampak integrity, bukan tuning)
- BBRI: ret −5.73%→−4.62%, sharpe −0.14→−0.08, trades tetap 10
- ASII: ret 22.26%→23.88%, trades tetap 9
- TLKM: ret −3.72%→−3.36%, trades tetap 6
- KOKA: ret 5.29%→6.21%, trades tetap 6
- Tidak ada error; tidak ada parameter yang diubah (hanya indexing metadata).

**Audit seluruh field Trade dataclass:** entry_date/exit_date/entry_price/
exit_price = harga & tanggal eksekusi (legal); stop_loss/take_profit = kini
dari ATR[i-1]; return_pct/holding_days/exit_reason = hasil; entry_score/
confidence/risk_level = kini dari bar sinyal. Tidak ada field tersisa yang
memakai bar eksekusi utk keputusan.

**Verifikasi "bukan tuning performa":** diff hanya mengubah `[i]` → `[i-1]`
pada 7 lokasi metadata entry + komentar. Tidak ada konstanta/parameter yang
diubah.

- [x] Pastikan ATR, risk_level, SL, TP, entry_score, confidence, regime, dan
      seluruh execution metadata yang memengaruhi trade berasal dari informasi
      yang memang tersedia pada decision timestamp.
- [x] Untuk entry_mode="open": gunakan state/ATR dari t-1, bukan ATR bar entry t.
- [x] Tambahkan unit test yang secara eksplisit gagal apabila execution-bar
      high/low/close/ATR bocor ke parameter trade yang sudah dieksekusi pada open_t.
- [x] Audit seluruh field pada Trade dataclass untuk kemungkinan current-bar leakage.
- [x] Re-run backtest regression setelah patch.
- [x] Verifikasi bahwa perubahan hanya memperbaiki temporal integrity dan
      bukan tuning performa.
- [x] Acceptance: tidak ada feature/metadata dari bar t yang digunakan untuk
      menentukan trade yang sudah dieksekusi pada open_t.

### P7.2 — Portfolio-Level Backtest Aggregation [CRITICAL]

**TEMUAN (16-08-2026):** `walkforward.py main()` menghitung portfolio metrics
dengan cara yang salah secara metodologis:
1. `oos_total_return = sum(return_pct per trade)` — return portfolio ≠ sum
   return trade (tanpa compound, tanpa waktu, tanpa modal).
2. `oos_sharpe = mean(oos_sharpe per window)` — mean dari Sharpe per window,
   bukan Sharpe dari portfolio return series.
3. `windows = len(set(window_id))` — window_id TIDAK unik global
   (`build_windows` memulai dari 1 utk TIAp saham); 3 saham × 4 window
   dilaporkan sbg 4 window, padahal 12.
4. Max DD dihitung dari trade return berurutan (bukan equity curve harian
   dengan cash/positions).

**FIX — modul baru `backend/portfolio.py`:**
- `build_portfolio_series(events, prices, capital, max_positions, fee_buy_pct,
  fee_sell_pct, lot_size)` — simulasi deterministic dari SATU chronological
  series: per hari exit → entry → mark-to-market. Posisi per code dgn shares
  bertanda (short didukung, gross collateral tanpa margin call — model
  eksplisit). Notional per posisi = capital/max_positions (default 3) →
  exposure ≤ ~100%. Slippage SUDAH di harga eksekusi (diterapkan backtest);
  fee dihitung engine (fee_buy_pct/fee_sell_pct asimetris, audit fix #14).
- Semua metric dari series: Sharpe, Sortino (downside std), max DD kronologis,
  CAGR, turnover (Σ notional / avg equity), total cost, avg exposure,
  peak_positions, skipped_events (entry gagal krn modal < 1 lot — transparan,
  tidak crash).
- `events_from_wf_results(results)` — konversi WFResult → PortfolioEvent
  (direction 'BUY'/'SELL' → ±1).
- walkforward.py: windows = `len(set((code, window_id)))`; oos_total_return/
  oos_sharpe/oos_max_dd = portfolio metrics; tambah `portfolio_metrics`
  (sortino, cagr, turnover, total_cost, n_days, avg_exposure, peak_positions,
  skipped_events) + `portfolio_series` (full series, reproducibility).
  Win rate tetap trade-level (deskripsi distribusi trade, bukan portfolio
  return). Per-window results tetap tersedia di `results`.

**Verifikasi:**
- Sanity test sintetis 3/3 PASS: (A) compound sequential — 2×+10% berturut
  = +19.9% (BUKAN 20% sum), equity 1.199.000, sharpe cocok formula;
  (B) entry di-skip krn modal < 1 lot → skipped_events=1, tidak crash;
  (C) 2 posisi paralel max_positions=2 → +10%, peak 2, exposure rata-rata
  0.5 (hari exit: posisi ditutup pagi → exposure 0).
- Run walk-forward lokal (BBCA, BBRI, ASII; train 252 / test 63, min-trades 1):
  12 windows (benar; sebelumnya salah lapor 4), 50 trade OOS, portfolio:
  return −3.92%, CAGR −1.71%, Sharpe −0.11, Sortino −0.09, max DD 13.21%,
  turnover 31.3, cost Rp 693.602, 585 hari, avg exposure 29.4%, peak 3.
  (Catatan: angka historical yg dilaporkan dgn metode lama TIDAK sebanding —
  wajib re-run bila dibandingkan.)

- [x] Pisahkan per-stock/per-window metrics dari portfolio-level metrics.
- [x] Bangun chronological portfolio equity curve.
- [x] Aggregate cash, positions, entries, exits, fees, slippage, dan exposure
      berdasarkan timestamp.
- [x] Hitung portfolio daily return dari equity curve.
- [x] Hitung Sharpe dari satu portfolio return series, bukan mean dari Sharpe
      per window.
- [x] Hitung Sortino dari portfolio return series.
- [x] Hitung maximum drawdown dari chronological equity curve.
- [x] Hitung CAGR/annualized return dari equity curve.
- [x] Hitung turnover.
- [x] Hitung total transaction cost.
- [x] Jangan menggunakan sum(trade_return_pct) sebagai portfolio return.
- [x] Jangan menggunakan mean(window_sharpe) sebagai portfolio Sharpe.
- [x] Pastikan window_id unik secara global atau diganti dengan (stock, window_id).
- [x] Acceptance: portfolio metrics dapat direproduksi dari satu chronological
      equity/cash/position series.

### P7.3 — Realistic Execution Standard [CRITICAL]

**IMPLEMENTASI (16-08-2026) — `backend/backtest.py`:**
1. **next-open = PRIMARY**: `BacktestConfig.entry_mode` default berubah
   `"close"` → `"open"` (eksekusi open bar berikutnya utk sinyal close t-1).
   `"close"` tetap tersedia utk komparasi historis saja.
2. **Baseline slippage**: default `slippage_bps` 0.0 → **25.0** (satu sisi,
   buy naik / sell turun, diterapkan pada harga entry & exit). Sensitivity
   0/25/50/100 bps tetap dieksplorasi secara eksplisit via param (P6.4).
3. **Gap-through-stop audit**: SUDAH benar sejak P6.4 — exit di `open_[i]`
   bila gap melewati stop (`min(SL, open)` BUY-SL, `max(TP, open)` BUY-TP,
   dst.). Tidak mengasumsikan harga intraday lebih baik.
4. **Intrabar ambiguity SL vs TP**: SL dicek LEBIH DULU daripada TP pada bar
   yang sama (SL-first, konservatif) — kini didokumentasikan di docstring.
5. **Conservative rules documentation**: paragraf P7.3 di docstring modul —
   SL-first, gap-through di open, breakeven tidak same-bar, trailing pakai
   atr_entry, REVERSAL exit di close (legacy konservatif), net-of-fees.
6. **Spread/impact proxy**: slippage_bps = proxy gabungan spread + market
   impact satu sisi (didokumentasikan; data bid/ask harian tidak tersedia di
   dataset — proxy eksplisit, bukan asumsi silent).
7. **ADV/participation constraint + partial-fill stress test**: field baru
   `max_adv_fraction` (0 = off). Bila aktif: notional trade dibandingkan dgn
   ADV20 (volume i-21..i-2 — informasi tersedia saat decision di close i-1,
   tidak memakai bar eksekusi); entry melebihi fraksi ADV di-SKIP dan
   dihitung di `BacktestMetrics.skipped_adv_entries` (baru).
8. **Net-of-fees headline**: return_pct, equity curve, total_return, sharpe,
   max_dd SUDAH net fee asimetris (audit fix #14) + slippage. total_fees
   tetap dilaporkan terpisah. Headline = NET.
9. **Legacy close+0bps = historical comparison only**: konvensi reporting
   P6.4 dipertahankan — hasil legacy hanya utk perbandingan, bukan headline.

**Verifikasi:**
- `test_temporal_integrity.py` tetap 3/3 PASS dgn default baru (open/25bps).
- ADV constraint teruji: BBCA (likuid) — 0 entry di-skip (notional ≪ ADV,
  wajar); KOKA (illiquid) cap 0.1% → 151 entry di-skip (32→8 trades, ret
  −81.5%→−35.7%); cap 0.02% → 187 skip (0 trade, ret 0); BBYB cap 0.1% →
  35 skip. Stress test berfungsi & transparan (counter di metrics).
- **Catatan dampak**: default baru mengubah hasil SEMUA backtest/walk-forward
  yang memakai default (sebelumnya close/0bps) — angka historical tidak
  sebanding; re-run wajib sebelum perbandingan apa pun.

- [x] Jadikan next-open sebagai primary research execution mode untuk signal
      yang tersedia pada close t-1.
- [x] Tetapkan satu baseline slippage yang realistis untuk primary evaluation.
- [x] Tetap simpan sensitivity 0 / 25 / 50 / 100 bps.
- [x] Audit gap-through-stop.
- [x] Audit intrabar ambiguity ketika SL dan TP sama-sama tersentuh dalam satu bar.
- [x] Dokumentasikan rule konservatif untuk ambiguous bars.
- [x] Tambahkan spread/impact proxy bila data memungkinkan.
- [x] Tambahkan participation/partial-fill stress test.
- [x] Tambahkan ADV/notional participation constraint untuk posisi besar.
- [x] Report PnL net-of-fees-and-slippage sebagai headline trading result.
- [x] Pertahankan legacy close + 0bps hanya sebagai historical comparison,
      bukan primary result.
- [x] Acceptance: hasil utama tidak bergantung pada execution convention yang
      optimistic.

### P7.4 — Production Calibration / Parameter Provenance Guard [CRITICAL]

**IMPLEMENTASI (16-08-2026):**
1. **`_calibrate_recovery_model.py` = LEGACY**: docstring ditandai
   "LEGACY / NOT FOR PRODUCTION". Hard guard di `main()`: menulis ke
   `recovery_model_params.json` produksi DITOLAK (exit 1, pesan REFUSED)
   kecuali `--allow-prod-write` eksplisit (tidak disarankan). Output tetap
   bisa disimpan ke path lain via `--out`.
2. **Provenance metadata** ditambahkan ke `recovery_model_params.json`
   (blok `provenance`): source_script (_phase6_p61_calibrate.py),
   calibration_version (P6.1), protocol frozen P6 (teks lengkap), dataset,
   n_codes (963), **dataset_hash** (sha256 universe_ohlcv.npz =
   d60aac04...), cutoff_date (2025-11-24), purge_rule, embargo_days (5),
   created_at, **parameter_hash** (sha256 canonical blok horizons =
   ea9c4124...), **locked: true**, locked_since.
   - Diverifikasi: seluruh isi model (horizons, base_rate_table, split_info,
     dll.) IDENTIK sebelum/sesudah — hanya metadata ditambahkan.
   - **PENTING (traceability)**: hash FILE berubah F495252969... →
     **1adb085eb2b8cfc9ae3b5584460f08b3ffa9db5b08fae14b29ad183d1323ef33**
     karena penambahan provenance; parameter model TIDAK berubah
     (diverifikasi via parameter_hash + diff JSON). Backup pre-P7.4:
     %TEMP%\opencode\recovery_model_params.pre_p74.json.
3. **Hard guard di `recovery.py`** (`_load_recovery_model_params`): produksi
   wajib punya `provenance.locked == True`, source_script, parameter_hash,
   dan hash ulang blok horizons harus cocok — kalau tidak: model recovery
   TIDAK dipakai (return None + pesan REFUSED ke stderr; API tetap jalan
   tanpa model, konservatif). Helper baru `_params_hash()`.
4. **Backup immutable**: `recovery_model_params_pre_p6_backup.json` dan
   `recovery_model_params_p6.json` di-set READ-ONLY (attrib +R, Windows).
5. **Smoke tests (semua PASS)**:
   - `_load_recovery_model_params()` memuat OK dgn provenance valid;
     modifikasi tak sah (a=999 + hash palsu) TERDETEKSI via hash mismatch.
   - `_calibrate_recovery_model.py` tanpa flag → REFUSED, exit 1, tidak
     menulis apa pun.
   - `recovery_model_probs(0.20)` → 7 horizon, CI cluster bootstrap utuh.
   - `import api` OK; `build_recovery_analysis` OK (jalur API recovery).

- [x] Tandai _calibrate_recovery_model.py sebagai LEGACY / NOT FOR PRODUCTION
      atau cegah script tersebut menulis production params.
- [x] Pastikan hanya calibrator yang telah disetujui dapat menulis
      recovery_model_params.json.
- [x] Tambahkan provenance metadata pada production params: source script,
      dataset hash, cutoff date, purge, embargo, calibration version,
      creation timestamp, parameter hash.
- [x] Tambahkan hard guard pada recovery.py bila metadata/provenance production
      tidak cocok dengan protocol frozen.
- [x] Pastikan backup legacy params tetap immutable/read-only.
- [x] Re-run API/recovery smoke tests setelah guard diterapkan.
- [x] Acceptance: tidak ada jalur legacy yang dapat secara tidak sengaja
      meng-overwrite production recovery parameters dengan methodology lama.

### P7.5 — Recovery Episode / Dependence Sensitivity [HIGH]

**IMPLEMENTASI (16-08-2026)** — script `_p75_episode_sensitivity.py`,
output `data/phase7_p75_episode.json` (B=100, seed 42). Estimator
episode-representative = 1 obs per episode drawdown (bar TROUGH = argmax
dd; definisi episode F2.2, run kontigu dd>0 dari trailing peak 252),
target/split/purge/embargo IDENTIK dgn produksi (cutoff 2025-11-24
diverifikasi sama dgn params produksi; 4.4–4.6 rb episode per horizon;
durasi episode median 15 hari; obs per episode ~58–60).

**Hasil OOS (test bersih):**
- Brier mentah: daily lebih baik h<=10 (0.016 vs 0.088 … 0.063 vs
  0.074), episode lebih baik h>=21 (0.071 vs 0.095 … 0.050 vs 0.182).
  TIDAK fair langsung — populasi berbeda (base rate episode jauh lebih
  tinggi: mean_p 0.26–0.82 vs 0.02–0.43).
- Brier Skill Score vs base rate: EPISODE LEBIH TINGGI DI SEMUA h
  (0.565/0.652/0.697/0.704/0.709/0.710/0.399 vs daily
  0.234/0.241/0.239/0.232/0.202/0.127/0.035).
- Calibration: episode c_int positif (0.27–1.24 = under-predict low-end),
  daily c_int negatif (−0.15..−1.00 = over-predict low-end); slope episode
  lebih dekat 1 utk h<=21.
- Stock-cluster bootstrap diff Brier (episode−daily), CI90 sangat ketat:
  h<=10 diff POSITIF (episode lebih buruk, 0% resamples), h>=21 diff
  NEGATIF (episode lebih baik, 100%). Perbedaan bukan noise, tapi
  komposisi populasi: episode estimator menang di saham dgn BANYAK
  episode (Brier 0.11–0.19 → 0.03–0.11), daily menang di saham
  few-episode (mayoritas universe; median episode per stock = 1).

**KEPUTUSAN: PRODUCTION TETAP DAILY-EVENT ESTIMATOR (TIDAK DIGANTI).**
Alasan (sesuai aturan P7.5 — jangan ganti hanya karena point estimate
berbeda; butuh incremental OOS evidence):
1. Semantik sinyal berbeda: produksi memberi estimasi per-baris setiap
   hari drawdown (user butuh P "hari ini"), episode estimator hanya
   menjawab "di titik trough" — mengubah arti output sinyal.
2. Brier mentah di horizon sinyal utama h1–h21: daily menang h<=10,
   kalah h=21 — bukti campur, bukan incremental evidence yang jelas.
3. Episode estimator sensitif thd komposisi sampel (menang hanya di
   saham many-episode = minoritas); daily lebih robust di mayoritas
   universe.
Hasil negatif/null utk promotion = alasan valid TIDAK mengubah
produksi (scope rule P7). Catatan riset lanjutan (non-production):
episode-weighted training atau conditioning trough bisa dieksplorasi
jika sinyal harian tetap dibutuhkan.

- [x] Bandingkan current daily-event recovery estimator vs episode-representative
      estimator.
- [x] Gunakan definisi episode yang sudah dipakai F2.2 agar tidak membuat event
      definition baru.
- [x] Gunakan target semantics yang sama.
- [x] Gunakan split temporal + purge/embargo yang sama.
- [x] Gunakan stock-cluster bootstrap.
- [x] Bandingkan: probability level, Brier, Brier Skill, calibration intercept,
      calibration slope, reliability.
- [x] Analisis sensitivity terhadap jumlah episode per stock.
- [x] Jangan mengganti production estimator hanya karena point estimate berbeda;
      promotion harus membutuhkan incremental OOS evidence.
- [x] Acceptance: keputusan daily-event vs episode estimator dibuat berdasarkan
      evidence OOS, bukan preferensi modelling.

### P7.6 — Corporate-Action Integrity [HIGH]

**IMPLEMENTASI (16-08-2026)** — script `_p76_corporate_action.py`,
output `data/phase7_p76_corporate_action.json`. Deteksi CA = lompatan
faktor f = raw_close/adj_close antar bar (>1% material; >5% split/
bonus/rights/dividen besar) pada 963 saham universe.

**Audit (raw vs adj):**
- 988 CA events di 365 saham; 274 big (>5%); median jump 3.28%,
  p95 9.40%.
- State drawdown: dd_raw > 5% di 88.4% bar vs dd_adj 86.9%
  (perbedaan ~1.6pp = efek CA). State error |dd_raw - dd_adj| > 5%:
  13.728 bar (4.63%), terkonsentrasi di saham dgn banyak event
  (MPMX, CLPI, BSSR, BJTM, CFIN...).
- **CA-artifact drawdown signal** (dd_raw > 5% TAPI dd_adj < 1%):
  hanya 603 bar (0.20% bars valid); episode drawdown murni artifact:
  7 dari 4.609 (0.15%). Dampak sinyal kecil.
- **Bias probabilitas KONSERVATIF, bukan overestimasi**: pada bar
  CA-artifact, P(h21) raw mean 0.521 vs counterfactual adj 0.687 —
  0/603 bar ter-overestimasi >5pp. Model raw mengukur target "kembali
  ke peak raw" (level pra-CA) yang memang lebih sulit tercapai.
- Re-test RTF/ARA policy: ARA raw >= +9.9% = 2.649 bar; ARA PALSU di
  adjusted (adj>=9.9% tapi raw<9.9%) = 12 bar — konfirmasi keputusan
  raw (kasus DUTI terdokumentasi di recovery.py: adjusted bisa bikin
  ARA palsu).

**PERUBAHAN PRODUKSI (minimal, defensif):**
- `recovery.py`: helper `_detect_corporate_action()` — deteksi lompatan
  faktor adj >2% dalam ~5 bar terakhir; flag **ca_note** ditambahkan di
  `build_recovery_analysis` (ada di response walau valid=False / data
  pendek). `api.py`: field `ca_note: str | None` di RecoveryResponse.
- Acceptance P7.6 terpenuhi: corporate action TIDAK dapat menciptakan
  artificial recovery signal TANPA TERDETEKSI (0.2% bar artifact kini
  ter-flag di jalur analisis user).

**POLICY FINAL (data contract, universe_meta.json note diperbarui):**
- RAW (raw_close) = basis eksekusi & event semantics: entry/exit
  backtest, deteksi ARA, gate RTF, % change harian, params recovery
  P6.1 (basis_harga raw) — PERTAHANKAN, konsisten semua jalur.
- ADJ (adj_close) = referensi statistik historis & deteksi CA saja;
  TIDAK dipakai jalur produksi mana pun.
- CA material dideteksi & di-flag via ca_note (konteks, bukan sinyal).
- Tidak mengganti pipeline ke Adj Close (verifikasi definisi
  adjustment Yahoo diperlukan utk itu; DUTI case membuktikan adjusted
  bermasalah utk event detection).

- [x] Identifikasi saham/period yang memiliki split, bonus, rights, atau
      corporate action material.
- [x] Bandingkan recovery state menggunakan raw price vs
      corporate-action-normalized price.
- [x] Audit apakah artificial drawdown/recovery dapat muncul dari corporate action.
- [x] Tentukan policy eksplisit: raw price untuk execution/event semantics;
      normalized series untuk historical statistical state bila diperlukan.
- [x] Jangan mengganti seluruh pipeline ke Adj Close tanpa memverifikasi definisi
      adjustment.
- [x] Re-test drawdown, recovery target, RTF event, dan SMA policy terhadap
      corporate-action cases.
- [x] Dokumentasikan policy final di data-contract.
- [x] Acceptance: corporate action tidak dapat menciptakan artificial recovery
      signal tanpa terdeteksi.

### P7.7 — Survivorship / Historical Universe Integrity [HIGH]

**IMPLEMENTASI (16-08-2026)** — P6.5 dijalankan ulang (`_phase6_p65_
survivorship.py` -> `phase6_survivorship.json`) + audit tambahan
(`_p77_survivorship_extra.py` -> `data/phase7_p77_survivorship.json`).

**Angka kunci:**
- Universe live 963 kode vs delisted 31 seeds (16 dgn data, 15 tanpa;
  sumber SahamOK/IDXChannel/CNBC — IDX API resmi tidak dapat diakses
  Cloudflare 403/503). Delisted fraction universe = 3.1%.
- **Direct OOS contamination = 0**: semua bar delisted berakhir SEBELUM
  window OOS (>= 2025-11-24) — evaluasi OOS TIDAK terkontaminasi;
  sisanya murni survivorship limitation (bias Shumway-style):
  overpred model produksi pada saham delisted h=21 +0.054, h=63 +0.144;
  refit universe+delisted: delta b relatif max 0.0013 (h=63) — dampak
  parameter kecil.
- **RTF khusus delisted (baru)**: 15 saham delisted dgn >= 150 bar,
  27 episode ARA total → **0 sinyal akumulasi valid** (semua gagal gate:
  data pendek / di bawah level event / dll). RTF tidak menghasilkan
  sinyal dari saham yang akhirnya delisted — bias survivorship RTF
  minimal.
- **Suspensi (baru)**: universe 38.109 bar volume=0 di 910/963 saham
  (136 saham suspensi panjang >= 20 bar); episode drawdown overlap
  zero-vol = 232/4.609 (5.0%). Bar suspensi tetap dipakai state
  recovery (close flat -> dd menanjak tanpa volume) — dampak kecil,
  limitation didokumentasikan; 53 saham universe data pendek (< 260
  bar) otomatis di-skip model recovery.
- **IPO entry dates (baru)**: npz window = 2024-02-27..2026-08-14
  (900 bar); 962/963 saham mulai dari awal window — data availability
  != listing date; tanggal IPO resmi tidak tercatat (limitation).
- Label resmi: "survivorship-limited backtest" (config.py + P6.5).

**KEPUTUSAN**: tidak ada perubahan produksi. Klaim performa universe-
wide tetap "survivorship-limited" (BUKAN unbiased). Keterbatasan
didokumentasikan: coverage delisted parsial, missing delisting return
(gap_ok=False), suspensi, IPO date tidak tersedia.

- [x] Tambahkan historical universe membership bila source memungkinkan.
- [x] Masukkan delisted securities ke historical evaluation sesuai availability.
- [x] Tangani delisting date/reason.
- [x] Tangani suspended stocks secara eksplisit.
- [x] Tangani IPO entry dates.
- [x] Dokumentasikan missing delisting return sebagai limitation jika tidak
      tersedia.
- [x] Jalankan ulang survivorship test khusus RTF.
- [x] Pisahkan: direct OOS contamination vs broader survivorship limitation.
- [x] Acceptance: klaim universe-wide performance tidak disebut unbiased bila
      historical membership belum lengkap.

### P7.8 — Embargo Sensitivity [MEDIUM/HIGH]

**IMPLEMENTASI (16-08-2026)** — `_p78_embargo_sensitivity.py` ->
`data/phase7_p78_embargo.json`. Cutoff FROZEN (2025-11-24) & purge
label-overlap FROZEN; hanya embargo 5/10/20 hari kalender divariasikan.

**Hasil (test bersih, identik utk ketiga embargo):**
- AUC test TIDAK berubah: h1 0.9576 ... h63 0.8025 (semua varian).
- Brier test TIDAK berubah material: max |ΔBrier| vs embargo 5 =
  0.0008 (embargo 10), 0.0036 (embargo 20).
- Calibration intercept/slope nyaris identik (embargo 10: c_int
  -0.157 vs -0.155; slope 0.967 vs 0.968 di h1).
- Fitted params: embargo 10 max |Δa| 0.016, |Δb| 0.046; embargo 20
  max |Δa| 0.057, |Δb| 0.287 (h1 b=-30.9 -> rel < 1%).
- Sampel: embargo 5 train h1 127.213 / purge 3.297; embargo 20
  train 118.122 / purge 12.388 (train mengecil ~7%, test SAMA
  karena test = date_s >= cutoff).

**KEPUTUSAN: FINAL EMBARGO = 5 HARI (dipertahankan, status quo).**
Alasan (stability/integrity, BUKAN profit): (1) metrik OOS identik di
semua varian -> embargo lebih panjang tidak memberi perbaikan
stabilitas; (2) embargo 5 = sampel train terbesar & buffer minimal
yang sudah mencakup ~3 hari trading; (3) parameter terstabil. Dicatat
sebelum final holdout (P4.8): embargo final = 5 hari kalender.

- [x] Evaluate embargo 5 calendar days.
- [x] Evaluate embargo 10 calendar days.
- [x] Evaluate embargo 20 calendar days.
- [x] Pertahankan cutoff dan purge tetap frozen.
- [x] Bandingkan: AUC, Brier, calibration intercept, calibration slope, fitted
      parameters, sample size.
- [x] Pilih embargo final sebelum final holdout.
- [x] Catat alasan pemilihan secara reproducible.
- [x] Jangan memilih embargo berdasarkan profit OOS.
- [x] Acceptance: final embargo dipilih berdasarkan stability/statistical
      integrity, bukan performance cherry-picking.

### P7.9 — Walk-Forward Selection Transparency [MEDIUM]

**IMPLEMENTASI (16-08-2026)** — `_p79_walkforward_transparency.py` ->
`data/phase7_p79_walkforward.json`. Re-run walk-forward (train 252 /
test 63, purge 10 + embargo 10, grid 36 kandidat) pada BBCA/BBRI/ASII/
TLKM dgn return_meta=True + metadata seleksi per window disimpan.

**Hasil:**
- Total candidate trials per window: 36 (konstan, dari WF_OPT_GRID
  3x3x2x2) — tercatat per window di per_window_log.
- Windows: 16 total, 16 evaluated, **0 skipped** (skip rate 0.0%);
  alasan: kandidat pada train 252 bar selalu >= WF_OPT_MIN_TRADES=10
  di saham liquid ini; skip_reasons kosong.
- Breakdown regime (train slice ±10%): down 8 (0 skip), sideways 5
  (0 skip), up 3 (0 skip) — tidak ada window yang ter-skip di regime
  manapun pada sampel ini; breakdown liquidity: median avg-vol per
  saham dicatat (skipped = n/a krn 0 skip).
- Parameter-selection frequency: mode share (kandidat sama menang) =
  37.5% — pemenang paling sering: adx_gate_ceiling=15,
  atr_sl_multiplier=2.0, rvol_breakout_confirm=1.2,
  swing_buy_threshold=68 (6/16 window).
- Parameter stability antar-window berturut-turut: 37.5% (6/16 pasang
  memilih kombinasi identik) — seleksi cukup bervariasi per window;
  konsisten dgn grid kecil yg di-optimasi per window di data train.
- Selection metadata FULL disimpan (per window: winner params,
  train_sharpe/trades, OOS sharpe/return/win rate, regime, avg vol)
  utk audit tanpa aggregate Sharpe tunggal.

- [x] Report total candidate trials per window.
- [x] Report parameter-selection frequency.
- [x] Report parameter stability antar-window.
- [x] Report skipped-window rate.
- [x] Breakdown skipped windows by regime.
- [x] Breakdown skipped windows by liquidity/universe availability.
- [x] Quantify how often the same candidate wins.
- [x] Simpan full selection metadata untuk audit.
- [x] Jangan menambahkan CPCV/PBO/DSR sebelum evidence menunjukkan kebutuhan.
- [x] Acceptance: selection process dapat diaudit tanpa mengandalkan satu
      aggregate Sharpe number.

### P7.10 — Stale Methodology / Legacy Guard [MEDIUM]

**IMPLEMENTASI (16-08-2026):**
- Grep seluruh source: klaim "70/30" hanya tersisa di konteks yang
  sudah diklarifikasi — config.py:186 annotation (P6.1 menggantikan
  split bar 70/30 yang bocor), `_calibrate_recovery_model.py` (LEGACY
  banner P7.4 + guard --allow-prod-write), `_fase2_*`/`_validate_
  recovery.py`/`_bootstrap_recovery.py` (riset historis berkonteks
  fase). Tidak ada methodology competing yang tampak production-valid.
- `_reliability.py`: ditambah banner **LEGACY-METHODOLOGY (P7.10)** —
  script memakai split temporal 70/30 pre-P6; produksi = P6.1
  (chronological cutoff 70% tanggal + purge label-overlap + embargo 5);
  hasil 12-Agu-2026 = riset historis utk audit kalibrasi.
- `gorengan.py`: klaim "memperkirakan probabilitas" utk Gorengan Risk
  Score (heuristic composite 0-100) diperbaiki -> "mengukur risiko,
  BUKAN probabilitas terkalibrasi" (score tidak dideskripsikan sbg
  probability).
- User-facing terminology: api.py sudah pakai `large_upmove_*` (P6.7
  C14); istilah internal "ARA" selalu disertai klarifikasi "BUKAN
  definisi ARA resmi BEI" (config.py:278, recovery.py:486).
- swing_score di api.py: tidak pernah dideskripsikan sebagai
  probability (hanya `float | None` + recommendation). recovery_model
  score = probabilitas terkalibrasi (sah — beda jalur).

- [x] Grep seluruh source untuk klaim lama 70/30, position split, atau
      performance claim sebelum P6.
- [x] Tandai script lama sebagai LEGACY bila masih dipertahankan.
- [x] Hapus/annotate stale performance claims yang tidak lagi valid.
- [x] Pastikan developer-facing comments mengarah ke methodology P6 terbaru.
- [x] Pastikan user-facing terminology large_upmove_* digunakan, bukan ARA legacy.
- [x] Pastikan score tidak pernah dideskripsikan sebagai probability.
- [x] Acceptance: tidak ada dua methodology competing yang sama-sama tampak
      production-valid.

### P7.11 — Base-Rate Artifact Integrity [MEDIUM]

**IMPLEMENTASI (16-08-2026):**
- Audit `recovery_model_params.json`: runtime (recovery.py) HANYA
  membaca blok `horizons.<h>.a` & `.b` (recovery_model_probs =
  logistic(a + b*dd)); `_params_hash` = sha256 canonical COMPACT
  (separators=(",",":")) dari blok horizons — diverifikasi cocok dgn
  provenance.parameter_hash `ea9c41244210...`. HASH FILE (seluruh
  file) berubah 1adb085e... -> **992CC0CB32D138067DBE211F9B3DE2D13B462E5B88DFB0DE80671B64D10970D3**
  hanya karena metadata P7.11 ditambahkan; kontrak P7.4 (parameter_
  hash blok horizons + locked) TIDAK berubah — verified match.
- `base_rate_table` = statistik FULL-HISTORY (semua bar, semua saham,
  tanpa split — build_base_rate_table di _calibrate_recovery_model.
  py) — **diagnostic-only, TIDAK pernah dibaca runtime** (cek grep:
  tidak ada referensi di recovery.py/api.py).
- `ci_cluster` = cluster bootstrap (resample saham) dari TRAIN split
  saja (fit ulang di train; percentile 90%) — bukan full-history.
- `auc_test/brier_test/calibration/n_*_test` di blok horizons =
  diagnostic OOS, tidak dibaca runtime.
- **Source-mask ditambahkan ke artifact** (P7.11, hash horizons
  tidak berubah — verified 67caef.../compact ea9c4124...):
  `base_rate_table_meta` = {scope: full_history_diagnostic_only,
  used_by_runtime: false, runtime_uses: [horizons.<h>.a, .b]} dan
  `runtime_contract` = {reads: {horizons: [a, b]}, diagnostic_only:
  [base_rate_table, ci_cluster, auc_*, brier_test, calibration,
  n_*_test, rec_rate]}.
- Acceptance terpenuhi: tidak ada statistik future-derived/
  full-history yang masuk jalur probabilitas produksi (a, b dari
  TRAIN; cluster CI dari TRAIN). Smoke: load OK, probs OK.

- [x] Audit base_rate_table pada recovery_model_params_p6.json.
- [x] Pastikan statistik yang dapat memengaruhi runtime hanya berasal dari
      TRAIN/development.
- [x] Pisahkan diagnostic statistics full-history dari production parameter
      statistics.
- [x] Jika base_rate_table tidak digunakan runtime, tandai jelas sebagai
      diagnostic-only.
- [x] Tambahkan source-mask metadata bila artifact menyimpan statistik penelitian.
- [x] Acceptance: tidak ada future-derived statistic yang dapat diam-diam masuk
      ke production probability path.

### P7.12 — Probability CI Semantics [MEDIUM]

**IMPLEMENTASI (16-08-2026):**
- `recovery_model_probs` sekarang mengekspos metadata CI per horizon:
  `ci_method` = "cluster_bootstrap_90pct" (primary; fallback legacy
  "delta_method_90pct_legacy" hanya utk params pra-P6), `ci_level` = 90,
  `ci_scope` = "parameter/estimation uncertainty antar-saham (cluster
  bootstrap) — BUKAN prediction interval".
- Docstring `recovery_model_probs` di-update: CI = ESTIMATION/PARAMETER
  uncertainty (ketidakpastian a,b antar-saham), bukan prediction
  interval; dilarang disebut "chance range".
- `api.py::RecoveryProbability`: field `ci_method`, `ci_level`,
  `ci_scope` ditambahkan (pass-through otomatis; verifikasi pydantic
  OK). Tidak ada istilah "chance range"/misleading di API.
- Stock-cluster bootstrap tetap PRIMARY uncertainty method (P6.2,
  precomputed grid + interpolasi linear; delta method = legacy).
- Acceptance: pengguna dapat membedakan point probability (`p_hit`)
  dari uncertainty estimate (`ci_low/ci_high` + scope) secara jelas.

- [x] Tambahkan metadata ci_method.
- [x] Tambahkan ci_level.
- [x] Tambahkan ci_scope.
- [x] Jelaskan bahwa CI adalah estimation/parameter uncertainty, bukan prediction
      interval.
- [x] Pastikan UI/API tidak menyebut CI sebagai "chance range" atau istilah yang
      misleading.
- [x] Pastikan stock-cluster bootstrap tetap menjadi primary uncertainty method.
- [x] Acceptance: pengguna dapat membedakan point probability dari uncertainty
      estimate secara jelas.

### P7.13 — Final Holdout Pre-Registration [CRITICAL]

**IMPLEMENTASI (16-08-2026)** — dokumen `backend/data/phase7_p713_
preregistration.json` (protocol **P4.8-protocol-v3.0**) + update
`phase4_holdout_config.json` (production_params_snapshot → hash file
aktual 992CC0CB... dgn catatan P7.4/P7.11; parameter_hash blok
horizons ea9c4124... tetap match — hard guard P7.4 PASS). Semua
keputusan dikunci SEBELUM P4.8 RUN ONCE:
- Cutoff rule frozen: `--cutoff YYYY-MM-DD` argumen saat run (tanggal
  mulai data genuinely unseen), exclude semua date_s < cutoff, purge
  date_s + h <= last date; RUN ONCE, dilarang geser cutoff / rerun
  methodology lain.
- Production params hash frozen: file 992CC0CB...; shrinkage
  D329FE16...; locked=True; parameter_hash ea9c4124... match.
- M1 candidate frozen: previous_close h1/3/5, c = 0.9112/0.7382/
  0.7387 (h10/h21 veto Case C; h42/63 = M0; prior_peak M0 semua h).
- p_min = 0.68 FROZEN (P6.11).
- Brier reference frozen: climatology DEV (<= 2026-01-23, purged) —
  dilarang prevalence holdout sebagai reference.
- Bootstrap seeds frozen: primary B=1000 seed 42 (stock-cluster),
  sensitivity B=500 seed 7 (date-block 10 hari).
- Acceptance rules frozen: 8 rules + overall PROMOTE/REJECT/
  INCONCLUSIVE (operational selectivity < 0.50).
- Embargo final = 5 hari (P7.8) dicatat utk seluruh evaluasi.
- Verification: hash code/config 7 file kunci dicatat; dataset
  snapshot d60aac04... (universe) + ede45b8a... (delisted); no
  contamination (delisted di OOS = 0, P7.7); holdout BELUM dibuka;
  selftest = DEV-only, bukan evidence; probability source stabil
  (P7.4/P7.11).
- Harness RUN-ONCE: phase4_holdout_config.json run_discipline + ABORT
  bila hash params berubah (PIT-integrity).

- [x] Freeze exact holdout cutoff rule/date.
- [x] Freeze production params hash.
- [x] Freeze M1 candidate parameters.
- [x] Freeze p_min=0.68.
- [x] Freeze Brier reference/base-rate.
- [x] Freeze bootstrap seeds.
- [x] Freeze acceptance rules.
- [x] Verify no contamination.
- [x] Verify no test run has touched holdout.
- [x] Verify code/config hash.
- [x] Verify dataset snapshot/hash.
- [x] Record final protocol version.
- [x] Mark harness as RUN-ONCE.
- [x] Do not move cutoff to increase sample size.
- [x] Do not rerun with different methodology after seeing result.
- [x] Acceptance: P4.8 becomes a genuinely one-shot final evidence experiment.

### P7.14 — Final Claims Audit [HIGH]

**IMPLEMENTASI (16-08-2026)** — `backend/data/phase7_p714_claims.json`
(11 klaim diaudit, C01–C11) + perbaikan README.md:
- **README**: klaim backtest Fase 6 (win rate 55.3%, Sharpe 0.24,
  +0.41%) di-annotate **LEGACY** — eksekusi close+0bps pre-P7.1 fix;
  metode recovery di-update ke P6.1 (split kronologis + purge +
  embargo 5, provenance hash); CI di-update ke cluster bootstrap +
  semantics P7.12 (estimation uncertainty, bukan prediction
  interval); validasi OOS di-update (periode eksak ≤ 2026-08-14 +
  angka P6.1).
- Separations tercatat: screening vs profitability; discrimination
  (AUC) vs calibration (Brier/slope/ECE); probability quality vs
  decision utility (P4.8 final_verdict); RTF standalone vs
  incremental value.
- Klaim C01 (RTF 3.4x) = research-backed dgn batasan konteks; C03
  = ANNOTATED-LEGACY; C10 = pending P4.8; C11 (gorengan
  "probabilitas") = FIXED P7.10.
- Aturan global: klaim performa wajib OOS period; PnL wajib
  konvensi eksekusi; universe-wide wajib survivorship limitation;
  probabilistik wajib metodologi CI; RTF tidak diklaim "useless"
  dari Phase 5; M5/M10 tidak diklaim "universally superior".

- [x] Separate: research-backed claims / empirical project findings / heuristic
      assumptions / unsupported-speculative claims.
- [x] Separate screening usefulness from executable profitability.
- [x] Separate discrimination from calibration.
- [x] Separate probability quality from decision utility.
- [x] Separate standalone RTF association from incremental value.
- [x] Do not claim RTF is "useless" based solely on Phase 5.
- [x] Do not claim M5/M10 is universally superior momentum.
- [x] State exact OOS period for every performance claim.
- [x] State execution convention for every PnL claim.
- [x] State survivorship limitations for every universe-wide claim.
- [x] State uncertainty/CI methodology for every probabilistic claim.
- [x] Acceptance: every major claim in README/audit/API documentation can be
      traced to a valid evidence source.
