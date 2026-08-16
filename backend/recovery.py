"""
recovery.py - Mean reversion: probabilitas harga balik ke level sebelumnya.

Modul ini menghitung peluang harga saham kembali ke previous close dalam
horizon 1 hari sampai 3 bulan, untuk saham yang baru gap-down / turun
tajam X%.

Pendekatan:
  1. Base rate empiris per-saham: dari histori harga saham itu sendiri,
     berapa persen kejadian "turun X% dari previous close" yang akhirnya
     recovery (high menyentuh level referensi) dalam horizon yang sama.
     - basis sinyal UTAMA (target: previous close).
  2. Model recovery EMPIRIS GLOBAL (logistic drawdown, kalibrasi offline
     dari 963 saham IDX, target: prior high / "par" = max(close) trailing
     252 hari): P(hit par dalam h hari) = 1/(1 + exp(a_h + b_h*dd_fraction)).
     - fallback sinyal kalau base rate per-saham < 5 event, diekspos di
       response sebagai field "model" (probs per horizon + dd_fraction).
     - kalibrasi: python _calibrate_recovery_model.py -> 
       data/recovery_model_params.json. Hasil h=21: AUC test 0.83,
       Brier 0.118, deviasi OOS <= 0.03 utk dd >= 5%.
  3. First-passage time GBM (CDF Inverse Gaussian / Wald) - DEPRECATED:
     bisa memberi P>0.9 utk drop kecil saat drift tinggi, padahal empiris
     ~30-70% (menyesatkan). Fungsi tetap ada utk kompatibilitas tapi tidak
     dipakai lagi di jalur sinyal/response (gbm = None).

Ini bukan rekomendasi beli - murni estimasi probabilitas, bukan jaminan.
Exit plan (target/time-stop/stop-loss) sifatnya informasional saja.

Dependensi: numpy dan math (stdlib).
"""

from __future__ import annotations

import hashlib
import math
import os
import json

import numpy as np
from typing import Optional

import numpy as np

import config
import indicators as ind


# ---------------------------------------------------------------------------
# Distribusi normal (via erf, stdlib - tanpa scipy)
# ---------------------------------------------------------------------------

def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _log_normal_cdf(x: float) -> float:
    """log(Phi(x)) yang stabil untuk x sangat negatif (hindari underflow)."""
    if x < -8.0:
        # Asymptotic expansion: log Phi(x) ~= -x^2/2 - log(-x) - 0.5*log(2*pi)
        return -0.5 * x * x - math.log(-x) - 0.5 * math.log(2.0 * math.pi)
    if x >= 0:
        return math.log(_normal_cdf(x))
    return math.log1p(-_normal_cdf(-x))


# ---------------------------------------------------------------------------
# Estimasi parameter GBM
# ---------------------------------------------------------------------------

def estimate_gbm_params(
    close: np.ndarray,
    mu_lookback: int = config.RECOVERY_MU_LOOKBACK_DAYS,
    sigma_lookback: int = config.RECOVERY_SIGMA_LOOKBACK_DAYS,
) -> tuple[float, float]:
    """
    Estimasi drift harian (mu_log) dan volatilitas harian (sigma) dari log-return.

    mu_log = rata-rata log-return sepanjang mu_lookback hari terakhir. Ini
        sudah merupakan drift proses log-harga apa adanya: untuk GBM
        dS = mu_harga*S*dt + sigma*S*dW, lemma Ito memberi
        d(ln S) = (mu_harga - 0.5*sigma^2)*dt + sigma*dW, sehingga
        mean(log_ret) memang estimasi drift log-harga, bukan drift harga
        aritmetik. Jangan tambahkan +0.5*sigma^2 di sini - itu akan
        mengubahnya jadi drift harga aritmetik dan membuat estimasi di
        first_passage_cdf over-optimis.
    sigma = std log-return sepanjang sigma_lookback hari terakhir (ddof=1).

    Returns (mu_daily_log, sigma_daily); (0.0, 0.0) kalau data tidak cukup.
    Untuk drift harga aritmetik (dipakai di pelaporan), pakai mu_arithmetic_daily().
    """
    close = np.asarray(close, dtype=float)
    valid = close[~np.isnan(close)]
    if valid.size < 2:
        return 0.0, 0.0

    log_ret = np.diff(np.log(valid))

    sig_window = log_ret[-sigma_lookback:] if sigma_lookback > 0 else log_ret
    if sig_window.size < 10:
        return 0.0, 0.0
    sigma = float(np.std(sig_window, ddof=1))
    if not np.isfinite(sigma) or sigma <= 0:
        return 0.0, 0.0

    mu_window = log_ret[-mu_lookback:] if mu_lookback > 0 else log_ret
    mu_log = float(np.mean(mu_window))
    if not np.isfinite(mu_log):
        mu_log = 0.0

    return mu_log, sigma


def mu_arithmetic_daily(mu_log: float, sigma: float) -> float:
    """
    Konversi drift log-harga ke drift harga aritmetik (ekspektasi return
    harga per hari): mu_harga = mu_log + 0.5*sigma^2, kebalikan dari
    koreksi Ito. Dipakai hanya untuk pelaporan (mu_daily/mu_annual ke
    pengguna), bukan sebagai input drift di first_passage_cdf / p_hit_ever.
    """
    return mu_log + 0.5 * sigma * sigma


# ---------------------------------------------------------------------------
# First-Passage Time (Inverse Gaussian CDF) - GBM
# ---------------------------------------------------------------------------

def first_passage_cdf(a: float, mu: float, sigma: float, t: float) -> float:
    """
    Peluang menyentuh level dengan jarak log +a, pada atau sebelum waktu t (a > 0).

    Pakai CDF Inverse Gaussian (Wald) untuk hitting time Brownian motion
    berdrift:
        F(t) = Phi((mu*t - a)/(sigma*sqrt(t)))
             + exp(2*a*mu/sigma^2) * Phi(-(a + mu*t)/(sigma*sqrt(t)))

    Catatan: beberapa referensi menulis Phi((a-mu*t)/...) pada term pertama,
    yang keliru karena memberi F(t)=1 saat mu=0. Bentuk di atas mengikuti
    definisi standar distribusi Inverse Gaussian, dan bisa dicek: saat mu=0,
    hasilnya F(t) = 2*Phi(-a/(sigma*sqrt(t))) lewat argumen refleksi.

    Term kedua dihitung di log-space biar stabil secara numerik. Hasil
    akhir di-clip ke rentang [0, 1].
    """
    if a <= 0 or sigma <= 0 or t <= 0:
        return 0.0

    st = sigma * math.sqrt(t)
    z1 = (mu * t - a) / st
    z2 = -(a + mu * t) / st

    term1 = _normal_cdf(z1)
    log_term2 = 2.0 * a * mu / (sigma * sigma) + _log_normal_cdf(z2)
    term2 = math.exp(log_term2) if log_term2 > -745.0 else 0.0

    return min(1.0, max(0.0, term1 + term2))


def p_hit_ever(mu: float, sigma: float, a: float) -> float:
    """
    Probabilitas ultimate (tanpa batas waktu) mencapai level +a.

    mu >= 0 -> 1.0; mu < 0 -> exp(2*a*mu/sigma^2) (sebagian jalur tak pernah hit).
    """
    if a <= 0 or sigma <= 0:
        return 0.0
    if mu >= 0:
        return 1.0
    return min(1.0, math.exp(2.0 * a * mu / (sigma * sigma)))


# ---------------------------------------------------------------------------
# Model recovery empiris GLOBAL (logistic drawdown) - pengganti GBM
# ---------------------------------------------------------------------------

def _params_hash(data: dict) -> str:
    """sha256 dari blok 'horizons' (isi model) — canonical, konsisten dgn
    provenance.parameter_hash (P7.4)."""
    canon = json.dumps(data.get("horizons", {}), sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def _load_recovery_model_params() -> Optional[dict]:
    """Load parameter model logistic-drawdown hasil kalibrasi offline.

    File dibuat oleh _phase6_p61_calibrate.py dari universe_ohlcv.npz
    (963 saham IDX, split global kronologis + purge/embargo, P6.1; target =
    prior high). Return None kalau file tidak ada / tidak valid -> pemanggil
    berjalan tanpa model.

    P7.4 hard guard: produksi WAJIB punya provenance lengkap & locked=True,
    dan parameter_hash harus cocok dgn blok horizons (deteksi modifikasi
    tak sah / overwrite metodologi legacy). Bila tidak cocok -> None
    (model TIDAK dipakai — konservatif).
    """
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            config.RECOVERY_MODEL_PARAMS_FILE)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("model") != "logistic_drawdown":
            return None
        prov = data.get("provenance") or {}
        if not prov.get("locked") is True:
            print("recovery.py: REFUSED — provenance.locked != True "
                  "(P7.4 hard guard); model recovery nonaktif.", file=sys.stderr)
            return None
        if not prov.get("source_script") or not prov.get("parameter_hash"):
            print("recovery.py: REFUSED — provenance tidak lengkap (P7.4); "
                  "model recovery nonaktif.", file=sys.stderr)
            return None
        if _params_hash(data) != prov["parameter_hash"]:
            print("recovery.py: REFUSED — parameter_hash mismatch (P7.4); "
                  "model recovery nonaktif.", file=sys.stderr)
            return None
        return data
    except Exception:
        return None


def dd_fraction(close: np.ndarray,
                peak_lookback: int = config.RECOVERY_PEAK_LOOKBACK_DAYS,
                clamp: float = config.RECOVERY_MODEL_DD_CLAMP) -> tuple[Optional[float], Optional[float]]:
    """(dd_fraction, prior_peak) untuk bar terakhir.

    dd_fraction = 1 - close[-1]/prior_peak, dengan prior_peak = max(close)
    trailing peak_lookback hari (termasuk bar terakhir - konsisten dengan
    kalibrasi). Di-clamp ke [0, clamp]. Return (None, None) kalau data
    tidak cukup / harga tidak valid.
    """
    close = np.asarray(close, dtype=float)
    n = len(close)
    if n < peak_lookback:
        return None, None
    peak = float(np.nanmax(close[-peak_lookback:]))
    if not np.isfinite(peak) or peak <= 0:
        return None, None
    price = float(close[-1])
    if not np.isfinite(price) or price <= 0:
        return None, None
    dd = max(0.0, min(clamp, 1.0 - price / peak))
    return dd, peak


def recovery_model_probs(dd: float,
                         horizons: Optional[list] = None,
                         params: Optional[dict] = None) -> Optional[list[dict]]:
    """P(hit prior peak dalam h hari) dari model logistic-drawdown.

    P = 1 / (1 + exp(a_h + b_h * dd_fraction)). Return None kalau parameter
    model tidak tersedia. Nilai dibulatkan 3 desimal (gaya API konsisten).
    CI (interval 90%) — P7.12 semantics:
      CI = ESTIMATION/PARAMETER uncertainty (ketidakpastian parameter a,b
      antar-saham via cluster bootstrap), BUKAN prediction interval
      (bukan rentang hasil aktual per saham/horizon). jangan disebut
      "chance range".
      P6.2 (Agu 2026): bila params punya ci_cluster.<h> (cluster bootstrap
      saham, percentile 90%, precomputed per grid dd) -> interpolasi linear
      (PRIMARY METHOD).
      Legacy: bila a_se/b_se/cov_ab tersedia, delta method pada skala logit
      (var_logit = se_a^2 + dd^2*se_b^2 + 2*dd*cov_ab, transformasi sigmoid),
      diskala ci_bootstrap.scale_a/scale_b (F2.3). Nilai None bila tak ada.
    """
    if params is None:
        params = _load_recovery_model_params()
    if params is None:
        return None
    horizons = horizons if horizons is not None else config.RECOVERY_HORIZONS_DAYS
    out = []
    for h in horizons:
        r = params.get("horizons", {}).get(str(h))
        if not r or not r.get("fitted"):
            continue
        logit = r["a"] + r["b"] * dd
        p = 1.0 / (1.0 + math.exp(-logit))
        ci_low = ci_high = None
        ci_method = "cluster_bootstrap_90pct"  # P7.12: primary method
        # P6.2: cluster bootstrap CI (precomputed per grid dd) — diprioritaskan
        cc = params.get("ci_cluster", {}).get(str(h))
        if isinstance(cc, dict) and cc.get("fitted") and cc.get("prob_ci_grid"):
            grid = cc["prob_ci_grid"]
            ci_low = round(float(np.interp(dd, grid, cc["prob_ci_low"])), 3)
            ci_high = round(float(np.interp(dd, grid, cc["prob_ci_high"])), 3)
        # Legacy: delta method + scale (params lama pra-P6)
        elif r.get("a_se") is not None and r.get("b_se") is not None \
                and r.get("cov_ab") is not None:
            ci_method = "delta_method_90pct_legacy"
            cb = params.get("ci_bootstrap") or {}
            sa = cb.get("scale_a", 1.0) if isinstance(cb, dict) else 1.0
            sb = cb.get("scale_b", 1.0) if isinstance(cb, dict) else 1.0
            a_se = r["a_se"] * sa
            b_se = r["b_se"] * sb
            cov_ab = r["cov_ab"] * sa * sb
            var_logit = a_se * a_se + (dd * dd) * b_se * b_se + 2.0 * dd * cov_ab
            se_logit = math.sqrt(max(var_logit, 0.0))
            z = 1.645  # 90%
            ci_low = round(1.0 / (1.0 + math.exp(-(logit - z * se_logit))), 3)
            ci_high = round(1.0 / (1.0 + math.exp(-(logit + z * se_logit))), 3)
        out.append({"horizon_days": h, "p_hit": round(p, 3),
                    "ci_low": ci_low, "ci_high": ci_high,
                    "ci_method": ci_method, "ci_level": 90,
                    "ci_scope": ("parameter/estimation uncertainty antar-saham "
                                 "(cluster bootstrap) — BUKAN prediction interval")})
    return out or None


# ---------------------------------------------------------------------------
# Base rate empiris (dari history saham itu sendiri)
# ---------------------------------------------------------------------------

def empirical_base_rates(
    close: np.ndarray,
    high: np.ndarray,
    drop_pct: float,
    horizons: list[int] = config.RECOVERY_HORIZONS_DAYS,
) -> list[dict]:
    """
    Untuk tiap bar i, event terjadi kalau close[i] <= close[i-1] * (1 - X/100).
    Event dianggap recovery kalau max(high[i+1 .. i+h]) >= close[i-1] - cukup
    disentuh, konsisten dengan definisi first-passage time di atas.

    Event yang horizonnya belum lengkap (kurang data ke depan) tidak
    dihitung, supaya tidak ada look-ahead bias.
    """
    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float)
    n = len(close)
    threshold = 1.0 - drop_pct / 100.0

    events: list[int] = []
    for i in range(1, n):
        ref = close[i - 1]
        if ref > 0 and close[i] <= ref * threshold:
            events.append(i)

    out: list[dict] = []
    for h in horizons:
        n_events = 0
        n_recovered = 0
        for i in events:
            end = i + 1 + h
            if end > n:
                continue
            n_events += 1
            if np.nanmax(high[i + 1 : end]) >= close[i - 1]:
                n_recovered += 1
        out.append({
            "horizon_days": h,
            "n_events": n_events,
            "n_recovered": n_recovered,
            "rate": round(n_recovered / n_events, 3) if n_events else None,
            "target": "previous_close",   # F2.5: eksplisitkan target event
        })
    return out


# ---------------------------------------------------------------------------
# Shrinkage Beta-Binomial (F2.4) - pengganti hard switch n>=5
# ---------------------------------------------------------------------------

_SHRINKAGE_BUCKETS = [(2.0, 3.0), (3.0, 4.0), (4.0, 5.0), (5.0, 6.5),
                      (6.5, 8.0), (8.0, 10.0), (10.0, 13.0), (13.0, 20.0)]


def _load_shrinkage_params() -> Optional[dict]:
    """Prior Beta per (bucket drop, horizon) hasil _fase2_shrinkage.py.

    Return None kalau file tidak ada / tidak valid -> pemanggil memakai
    perilaku lama (hard switch n>=5). Struktur:
      {"horizons": {h: {"global_prior": {"p0","m0","a0","b0"},
                        "buckets": {"lo-hi": {"prior": {...}}}}}}
    """
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            config.RECOVERY_SHRINKAGE_PARAMS_FILE)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("method") != "beta_binomial_shrinkage":
            return None
        return data
    except Exception:
        return None


def _shrinkage_bucket_index(drop_pct: float) -> int:
    for i, (lo, hi) in enumerate(_SHRINKAGE_BUCKETS):
        if lo <= drop_pct < hi:
            return i
    return 0 if drop_pct < _SHRINKAGE_BUCKETS[0][0] else len(_SHRINKAGE_BUCKETS) - 1


def _shrunk_rate(n_recovered: int, n_events: int, drop_pct: float,
                 horizon_days: int, params: Optional[dict]) -> Optional[float]:
    """P(recovery) shrinkage utk saham ini: (k + a0) / (n + a0 + b0).

    Prior dipilih per (bucket drop, horizon); bucket tanpa prior (kekurangan
    sampel saat kalibrasi) memakai global_prior horizon tsb. Return None
    kalau params tidak tersedia (caller jatuh ke perilaku lama).
    """
    if params is None or n_events < 1:
        return None
    hs = params.get("horizons", {}).get(str(horizon_days))
    if not hs:
        return None
    prior = None
    i = _shrinkage_bucket_index(drop_pct)
    bucket = hs.get("buckets", {}).get(f"{_SHRINKAGE_BUCKETS[i][0]:.1f}-"
                                       f"{_SHRINKAGE_BUCKETS[i][1]:.1f}")
    if bucket and bucket.get("prior"):
        prior = bucket["prior"]
    else:
        prior = hs.get("global_prior")
    if not prior:
        return None
    a0 = prior.get("a0")
    b0 = prior.get("b0")
    if a0 is None or b0 is None:
        return None
    p = (n_recovered + a0) / (n_events + a0 + b0)
    return max(0.0, min(1.0, p))


# ---------------------------------------------------------------------------
# Signal & exit plan
# ---------------------------------------------------------------------------

def _build_signal(in_setup: bool, distance_pct: float, drop_pct: float,
                  p_signal: Optional[float], basis: str = "model GBM",
                  p_min: float = config.RECOVERY_SIGNAL_P_MIN) -> tuple[str, str]:
    if distance_pct >= 0:
        return "NO_SETUP", "Harga di atas atau sama dengan previous close - tidak ada setup gap-down."
    if not in_setup:
        return "NO_SETUP", (
            f"Belum turun cukup jauh (baru {distance_pct:.2f}% vs threshold {drop_pct:.1f}%)."
        )
    if p_signal is not None and p_signal >= p_min:
        return "POTENTIAL", (
            f"Setup aktif (drop {abs(distance_pct):.2f}% >= {drop_pct:.1f}%) dan "
            f"P(recovery <= {config.RECOVERY_SIGNAL_HORIZON_DAYS} hari) = {p_signal:.0%} "
            f"(basis: {basis}) >= {p_min:.0%}."
        )
    return "WATCH", (
        f"Setup aktif tapi P(recovery <= {config.RECOVERY_SIGNAL_HORIZON_DAYS} hari) "
        f"masih di bawah {p_min:.0%}."
    )


def _build_exit_plan(price: float, ref_price: float,
                     target_override: Optional[float] = None,
                     target_note: str = "") -> dict:
    sl = price - config.RECOVERY_SL_DISTANCE_MULT * (ref_price - price)
    target = target_override if target_override is not None else ref_price
    return {
        "target": round(target, 0),
        "time_stop_days": config.RECOVERY_TIME_STOP_DAYS,
        "stop_loss": round(sl, 0),
        "note": (
            f"Exit saat harga menyentuh/menutup di atas target ({target_note or 'previous close'} "
            f"{target:,.0f}), atau time-stop {config.RECOVERY_TIME_STOP_DAYS} "
            f"hari trading (~3 bulan) jika target tak tercapai. "
            f"SL proteksi: {sl:,.0f} (2x jarak drop)."
        ),
    }


def auto_drop_pct(sigma_daily: float, price: float) -> float:
    """
    Threshold drop otomatis = 2.5 x sigma_daily, di-clamp dengan floor 2%
    dan cap yang mengikuti batas Auto Rejection Bawah (ARB) BEI saat ini
    (SK Kep-00003/BEI/04-2025): ARB flat 15% untuk semua tier harga sejak
    April 2025. Karena setup recovery berkaitan dengan penurunan harga,
    acuannya adalah ARB - jadi cap dipasang ~13% (sedikit di bawah 15%)
    untuk semua tier harga.
    """
    if price < 200:
        cap = config.RECOVERY_AUTO_CAP_UNDER_200
    elif price < 5000:
        cap = config.RECOVERY_AUTO_CAP_200_TO_5000
    else:
        cap = config.RECOVERY_AUTO_CAP_AT_5000

    return round(
        max(config.RECOVERY_AUTO_MIN, min(cap, config.RECOVERY_AUTO_SIGMA_MULT * sigma_daily * 100.0)),
        1,
    )


def detect_accumulation(bars: list) -> dict:
    """
    Deteksi pola "akumulasi post-large-upmove": saham yang baru saja
    distribusi besar (lonjakan naik tajam), lalu terkumpul lagi diam-diam
    sebelum berpotensi naik.

    Catatan terminologi (audit v2 §16): event pemicu adalah "large upmove"
    (close >= prev * (1 + ACCUM_ARA_RISE_PCT/100)) dengan threshold HEURISTIC
    +10% — BUKAN definisi ARA resmi BEI (bertingkat 35/25/20 per tier harga
    dan berubah sesuai peraturan). Sistem tidak membaca aturan ARA aktual,
    jadi istilah resminya POST_LARGE_UPMOVE; nama internal "ara" dipertahankan
    demi kompatibilitas field API/validasi historis.

    Logika:
      - Event (close >= prev * (1 + ACCUM_ARA_RISE_PCT/100)) dianggap hari
        distribusi/dump, bukan hari akumulasi - jadi hari event itu sendiri
        tidak ikut dihitung sebagai bagian window.
      - Window akumulasi = semua hari trading sejak event, panjangnya dinamis
        (bukan jendela tetap). Kalau event kedua muncul dalam <= ACCUM_RVOL_PERIOD
        hari setelah event pertama, keduanya dianggap satu gelombang: window
        di-anchor ke event pertama (supaya hari di antara dua event tidak
        terbuang), tapi harga acuannya tetap event terbaru/puncak. Hari event
        kedua sendiri tetap ikut dihitung di window, baseline, dan k - yang
        dikecualikan hanya event pertama (si anchor).
      - "Heavy" dihitung per hari (point-in-time): untuk bar i di window,
        baseline-nya adalah rata-rata volume post-event sebelum hari i (anti
        self-reference, anti look-ahead, konsisten dengan konvensi RVOL di
        indicators.py; fallback ke rata-rata 20 hari pre-event, lalu ke RVOL
        biasa kalau masih kosong). Hari i dianggap heavy kalau volumenya
        >= ACCUM_HEAVY_RVOL x baseline itu. Baseline ini sifatnya lagging
        (hari bervolume besar ikut menaikkan baseline berikutnya), jadi
        ACCUM_HEAVY_RVOL adalah parameter sensitivitas utama - default 2.0x,
        bisa diturunkan ke 1.5-1.8x kalau banyak lonjakan volume terlewat.
      - Sinyal dianggap kuat kalau minimal ACCUM_MIN_HEAVY_DAYS hari heavy
        muncul di window (default 2), dan kepadatannya (density_pct) >=
        ACCUM_DENSITY_PCT (30%). Density ini gate wajib: tanpa filter ini,
        pola kehilangan edge-nya sepenuhnya (lihat hasil validasi di bawah).
      - Konfirmasi tambahan: harga harus berada di atas SMA(ACCUM_MA20_DAYS).
        Validasi atas 963 saham menunjukkan posisi harga yang sudah stabil
        di atas MA (b10 51.9%) lebih kuat daripada baru saja cross ke atas
        MA dalam <=2 hari (b10 36.4%) - jadi yang dipakai adalah posisi
        harga saat ini, bukan momen crossing-nya.
      - Syarat wajib lain: harga masih di bawah level event (belum recovery).
        Kalau harga sudah di atas level event, itu masuk fase
        recovery/distribusi, bukan akumulasi lagi, jadi sinyalnya tidak
        bermakna di situasi itu.

    Hasil validasi walk-forward terbaru (_validate_accum4.py, 915 saham IDX,
    panjang data 800 hari, baseline post-ARA + gate density, anti look-ahead):
      - density >= 30%: win-rate 10 hari (b10) = 18.4% (n=8092) vs kontrol
        (harga di bawah ARA tanpa sinyal) 5.4% (n=217521) -> edge ~3.4x,
        p < 1e-16.
      - density >= 40%: b10 = 18.6% (n=5546) vs kontrol 5.6% (n=222932).
      - Tanpa gate density: b10 = 8.7%, sama persis dengan kontrol (p~1) -
        artinya tanpa filter density, edge-nya hilang total. Ini alasan
        density dijadikan gate wajib, bukan opsional.
    Sebagai perbandingan, versi lama (baseline pre-ARA + density>=40%)
    memberi b10=16.8% vs kontrol 5.9% (n=2958). Baseline post-ARA dengan
    density>=30% memberi edge yang setara atau lebih baik (b10 18.4%),
    dengan jumlah sinyal ~2.7x lebih banyak.

    Return: dict parameter dengan valid=False kalau tidak ada sinyal akumulasi.
    """
    # Basis harga MENTAH (raw_close): % change riil pasar. Seri adjusted (close)
    # punya lompatan artifisial di batas ex-dividen/split (kasus DUTI: -1.3% riil
    # jadi +10.4% di seri adjusted -> ARA palsu). Semua gate harga di fungsi ini
    # (ARA, below level, SMA20, distance) konsisten satu basis: riil.
    close = np.array([(getattr(b, "raw_close", None) or b.close) for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)

    n = len(close)
    if n < config.ACCUM_RVOL_PERIOD + config.ACCUM_MA20_DAYS + 5:
        return {"valid": False, "reason": "data terlalu pendek"}

    rv = ind.rvol(volume, config.ACCUM_RVOL_PERIOD)  # rolling RVOL (utk display / max_rvol)

    # SMA (posisi harga vs MA) - tanpa look-ahead
    sma = np.full(n, np.nan)
    if n >= config.ACCUM_MA20_DAYS:
        cs = np.cumsum(np.concatenate(([0.0], close)))
        sma[config.ACCUM_MA20_DAYS - 1:] = (
            cs[config.ACCUM_MA20_DAYS:] - cs[:-config.ACCUM_MA20_DAYS]
        ) / config.ACCUM_MA20_DAYS

    # Cari 2 ARA terakhir sebelum bar terakhir (ara_idx = terbaru, prev_ara_idx = sebelumnya)
    t = n - 1
    ara_idx = None
    prev_ara_idx = None
    for i in range(t, 0, -1):
        if close[i - 1] > 0 and close[i] >= close[i - 1] * (1.0 + config.ACCUM_ARA_RISE_PCT / 100.0):
            if ara_idx is None:
                ara_idx = i
            else:
                prev_ara_idx = i
                break

    if ara_idx is None:
        return {
            "valid": False,
            "ready_to_fly": False,
            "reason": "Belum pernah ada large upmove (+{}%) dalam history - tidak ada acuan distribusi.".format(
                config.ACCUM_ARA_RISE_PCT),
        }

    # Baseline volume "normal" dihitung dari hari-hari setelah ARA, bukan sebelum.
    # Kalau ada ARA kedua dalam <= ACCUM_RVOL_PERIOD hari setelah ARA pertama, keduanya
    # dianggap satu gelombang akumulasi (bukan reset): window di-anchor ke ARA pertama
    # supaya hari di antara ARA #1 dan #2 tidak terbuang, dan anti-look-ahead tetap
    # terjaga karena anchor-nya tetap ARA paling awal. Harga acuan pakai ARA terbaru (puncak).
    double_ara = prev_ara_idx is not None and (ara_idx - prev_ara_idx) <= config.ACCUM_RVOL_PERIOD
    anchor_idx = prev_ara_idx if double_ara else ara_idx
    ref_ara_idx = ara_idx  # harga acuan = ARA terbaru (puncak gelombang)

    # Baseline volume dihitung per hari (point-in-time, sama seperti di
    # _validate_accum4.py): untuk hari i di window, baseline = rata-rata volume
    # post-ARA sebelum hari i (hari i sendiri tidak ikut menghitung baseline-nya,
    # dan tidak memakai data setelah i). Kalau windownya masih < 2 bar, fallback
    # ke rata-rata ACCUM_RVOL_PERIOD hari sebelum ARA; kalau masih NaN, pakai RVOL biasa.
    base_start = max(0, anchor_idx - config.ACCUM_RVOL_PERIOD)
    pre_ara_avg = float(volume[base_start:anchor_idx].mean()) if anchor_idx > base_start else float("nan")

    heavy = np.zeros(n, dtype=bool)
    post_cum = np.concatenate(([0.0], np.cumsum(volume[anchor_idx + 1 : t + 1])))
    for i in range(anchor_idx + 1, t + 1):
        cnt = i - anchor_idx - 1  # jumlah bar post-ARA sebelum hari i
        if cnt >= 2:
            base = post_cum[cnt] / cnt  # mean(volume[anchor+1 : i])
        elif np.isfinite(pre_ara_avg) and pre_ara_avg > 0:
            base = pre_ara_avg
        elif np.isfinite(rv[i]):
            heavy[i] = rv[i] >= config.ACCUM_HEAVY_RVOL
            continue
        else:
            continue
        heavy[i] = volume[i] >= config.ACCUM_HEAVY_RVOL * base

    ara_meta = {
        "prev_ara_date": str(bars[prev_ara_idx].date)[:10] if prev_ara_idx is not None else None,
        "prev_ara_ref_price": round(float(close[prev_ara_idx]), 2) if prev_ara_idx is not None else None,
        "days_since_prev_ara": (ara_idx - prev_ara_idx) if prev_ara_idx is not None else None,
        "double_ara": double_ara,
    }

    window = t - anchor_idx  # hari trading setelah ARA anchor (tanpa hari ARA itu sendiri)
    if window < 1:
        return {
            "valid": False,
            "ready_to_fly": False,
            "k_heavy": 0,  # belum ada jendela akumulasi
            "window_days": 0,
            "density_pct": None,
            "ara_date": str(bars[ara_idx].date)[:10],
            "ara_ref_price": round(float(close[ara_idx]), 2),
            "prev_ara_date": ara_meta["prev_ara_date"],
            "prev_ara_ref_price": ara_meta["prev_ara_ref_price"],
            "days_since_prev_ara": ara_meta["days_since_prev_ara"],
            "double_ara": ara_meta["double_ara"],
            "reason": "Hari ini hari event; belum ada jendela akumulasi post-event.",
        }

    k = int(heavy[anchor_idx + 1: t + 1].sum())
    density_pct = k / window * 100.0

    price = float(close[t])
    above_ma = bool(np.isfinite(sma[t]) and price >= sma[t])
    ma_price = float(sma[t]) if np.isfinite(sma[t]) else None

    below = price < float(close[ref_ara_idx])

    dist_ara = (price - float(close[ref_ara_idx])) / float(close[ref_ara_idx]) * 100.0

    density_ok = density_pct >= config.ACCUM_DENSITY_PCT  # GATE (validasi: tanpa density, edge mati)
    k_ok = k >= config.ACCUM_MIN_HEAVY_DAYS

    ready = below and k_ok and density_ok and above_ma

    def _finite(v: float) -> float | None:
        return float(v) if np.isfinite(v) else None

    post_vol = volume[anchor_idx + 1: t + 1]
    post_cls = close[anchor_idx + 1: t + 1]
    post_vol_sum = float(post_vol.sum()) if len(post_vol) > 0 else 0.0
    post_val_sum = float((post_vol * post_cls).sum()) if len(post_vol) > 0 else 0.0

    # Net Distribution window post-event: (vol hari naik - vol hari turun)/total
    # vol, rentang [-1, +1]. Positif = buyer lebih dominan (akumulasi).
    # FIX fase 1 (audit v2 §13): arah dihitung EKSPLISIT untuk SEMUA hari
    # window — hari pertama dibandingkan terhadap harga hari event (close
    # sebelumnya), bukan di-drop oleh np.diff. Sebelumnya numerator memakai
    # post_vol[1:] (buang hari pertama) tapi denominator post_vol_sum (semua
    # hari) → hari pertama masuk denominator tanpa direction (alignment bug).
    if len(post_vol) > 0 and post_vol_sum > 0:
        dirs = np.concatenate(([post_cls[0] - close[anchor_idx]],
                               np.diff(post_cls)))
        up_v = float(post_vol[dirs > 0].sum())
        dn_v = float(post_vol[dirs <= 0].sum())
        net_dist = (up_v - dn_v) / post_vol_sum
    else:
        net_dist = None
    # Net Distribution versi definisi TODO audit (HIGH#2): proporsi heavy-day
    # yang menutup DI ATAS open-nya.
    #   NetDist_heavy = (#heavy-day dengan Close > Open) / (#heavy-day)
    # Berbeda dari net_dist di atas (bobot volume, semua hari): metrik ini
    # hanya memperhitungkan HARI VOLUME TINGGI dan arah intrabar (close vs
    # open), bukan diff close antar hari. Rentang [0, 1]; > 0.5 = mayoritas
    # heavy-day diserap buyer. Kalau belum ada heavy-day, None.
    post_open = np.array(
        [float(b.open_price) if getattr(b, "open_price", 0.0) else float(b.close)
         for b in bars[anchor_idx + 1: t + 1]], dtype=float)
    heavy_w = heavy[anchor_idx + 1: t + 1]
    n_heavy = int(heavy_w.sum())
    if n_heavy > 0:
        up_heavy = int((heavy_w & (post_cls > post_open)).sum())
        net_dist_heavy = round(up_heavy / n_heavy, 4)
    else:
        net_dist_heavy = None
    # Gap harga vs SMA20 (net distance dari garis MA, dalam %)
    sma_gap_pct = (price - ma_price) / ma_price * 100.0 if ma_price else None

    # AccDensity — definisi TODO audit (HIGH#2/rombak): kepadatan akumulasi
    # yang DIBOBOTI arah heavy-day:
    #   AccDensity = (#heavy-days * NetDist) / N  = k * net_dist_heavy / window
    # Rentang [0, 1]. > 0.3 berarti heavy-day banyak DAN dominan diserap buyer.
    acc_density = None
    if n_heavy > 0 and net_dist_heavy is not None and window > 0:
        acc_density = round(k * net_dist_heavy / window, 4)

    # Penalti "kesegaran" post-ARA (MED#5 + riset decay, Agu 2026):
    #   w(d) = exp(-d/tau), cutoff keras di d >= ACCUM_DECAY_CUTOFF_DAYS.
    # Data IDX: efek negatif ARA hanya di d+1, netral sejak d>=2; literatur
    # reversal IDX half-life 1-2 hari. Dipakai utk RANKING (strength), bukan gate.
    days_since_ara = window
    if days_since_ara < config.ACCUM_DECAY_CUTOFF_DAYS:
        post_ara_decay = round(math.exp(-days_since_ara / config.ACCUM_DECAY_TAU), 4)
    else:
        post_ara_decay = 0.0

    # Gate likuiditas (rombak TODO): ADV 20 hari point-in-time (hari ARA di-
    # buang — volume ARA = antrean beli, bukan likuiditas keluar). Dasar:
    # tier margin BEI (Rp250jt + 500rb lbr) x4 + partisipasi 1-5% utk
    # posisi swing 10-50jt (Kissell & Glantz; riset Agu 2026).
    w0 = max(0, t - config.ACCUM_ADV_WINDOW + 1)
    seg_v = volume[w0:t + 1]
    seg_c = close[w0:t + 1]
    if len(seg_v) >= config.ACCUM_ADV_MIN_BARS:
        seg_ret = np.zeros(len(seg_v))
        seg_ret[1:] = seg_c[1:] / seg_c[:-1] - 1.0
        keep = seg_ret < (config.ACCUM_ARA_RISE_PCT / 100.0)
        av = seg_v[keep]
        ac = seg_c[keep]
        adv_vol = float(av.mean()) if len(av) else 0.0
        adv_val = float((av * ac).mean()) if len(av) else 0.0
    else:
        adv_vol = 0.0
        adv_val = 0.0
    liq_ok = (adv_vol >= config.ACCUM_MIN_ADV_VOL
              and adv_val >= config.ACCUM_MIN_ADV_VAL)
    liq_prima = (adv_vol >= config.ACCUM_PRIMA_ADV_VOL
                 and adv_val >= config.ACCUM_PRIMA_ADV_VAL)
    ready = ready and liq_ok

    if not ready:
        parts = []
        if not below:
            if t == ara_idx:
                parts.append("hari ini = event terbaru (belum ada bar setelah puncak)")
            else:
                parts.append("harga SUDAH di atas level event (recovery/distribusi, bukan akumulasi)")
        if not k_ok:
            parts.append(f"baru {k} dari {window} hari volume >= {config.ACCUM_HEAVY_RVOL}x "
                         f"baseline (butuh min {config.ACCUM_MIN_HEAVY_DAYS} hari)")
        if not density_ok:
            parts.append(f"volume tidak konsisten: kepadatan baru {density_pct:.1f}% "
                         f"(wajib >= {config.ACCUM_DENSITY_PCT}%)")
        if not above_ma:
            parts.append(f"harga BELUM di atas SMA{config.ACCUM_MA20_DAYS}")
        if not liq_ok:
            parts.append(f"likuiditas rendah: ADV20 {adv_vol:,.0f} lbr / "
                         f"Rp{adv_val:,.0f} (floor {config.ACCUM_MIN_ADV_VOL:,.0f} lbr "
                         f"& Rp{config.ACCUM_MIN_ADV_VAL:,.0f})")
        return {
            "valid": False,
            "ready_to_fly": False,
            "k_heavy": k,
            "window_days": window,
            "density_pct": round(density_pct, 1),
            "post_ara_volume": round(post_vol_sum, 0),
            "post_ara_value": round(post_val_sum, 0),
            "rvol": _finite(rv[t]),
            "max_rvol": _finite(np.nanmax(rv[anchor_idx + 1: t + 1])) if window else None,
            "ara_date": str(bars[ara_idx].date)[:10],
            "ara_ref_price": round(float(close[ref_ara_idx]), 2),
            "prev_ara_date": ara_meta["prev_ara_date"],
            "prev_ara_ref_price": ara_meta["prev_ara_ref_price"],
            "days_since_prev_ara": ara_meta["days_since_prev_ara"],
            "double_ara": double_ara,
            # P6.7 (C14): istilah user-facing benar — "ARA" resmi BEI berbeda;
            # event ini = large upmove (threshold heuristic). Alias dipertahankan
            # utk backward compat dgn frontend lama.
            "large_upmove_date": str(bars[ara_idx].date)[:10],
            "large_upmove_ref_price": round(float(close[ref_ara_idx]), 2),
            "prev_large_upmove_date": ara_meta["prev_ara_date"],
            "prev_large_upmove_ref_price": ara_meta["prev_ara_ref_price"],
        "sma20": round(ma_price, 2) if ma_price is not None else None,
        "state_ma20": "above" if above_ma else "below",
        "distance_pct": round(dist_ara, 2),
        "net_dist": round(net_dist, 4) if net_dist is not None else None,
        "net_dist_heavy": net_dist_heavy,
        "sma_gap_pct": round(sma_gap_pct, 2) if sma_gap_pct is not None else None,
        "acc_density": acc_density,
        "post_ara_decay": post_ara_decay,
        "adv_vol_20": round(adv_vol, 0),
        "adv_val_20": round(adv_val, 0),
        "liquidity_ok": liq_ok,
        "liquidity_prima": liq_prima,
        "gates": {"below": below, "density": density_ok, "min_heavy": k_ok,
                  "above_ma": above_ma, "liquidity": liq_ok},
        "reason": "Belum pola akumulasi post-ARA " + "; ".join(parts) + ".",
    }

    state_ma = "above"
    if above_ma:
        # deteksi fresh cross: salah satu dari 2 bar terakhir masih di bawah SMA
        state_ma = "breakout" if (
            (t - 1 >= 0 and np.isfinite(sma[t - 1]) and close[t - 1] < sma[t - 1])
            or (t - 2 >= 0 and np.isfinite(sma[t - 2]) and close[t - 2] < sma[t - 2])
        ) else "above"

    return {
        "valid": True,
        "ready_to_fly": True,
        "k_heavy": k,
        "window_days": window,
        "density_pct": round(density_pct, 1),
        "post_ara_volume": round(post_vol_sum, 0),
        "post_ara_value": round(post_val_sum, 0),
        "rvol": _finite(rv[t]),
        "max_rvol": _finite(np.nanmax(rv[anchor_idx + 1: t + 1])) if window else None,
        "ara_date": str(bars[ara_idx].date)[:10],
        "ara_ref_price": round(float(close[ref_ara_idx]), 2),
        "prev_ara_date": ara_meta["prev_ara_date"],
        "prev_ara_ref_price": ara_meta["prev_ara_ref_price"],
        "days_since_prev_ara": ara_meta["days_since_prev_ara"],
        "double_ara": double_ara,
        # P6.7 (C14): alias user-facing (istilah benar, backward compat)
        "large_upmove_date": str(bars[ara_idx].date)[:10],
        "large_upmove_ref_price": round(float(close[ref_ara_idx]), 2),
        "prev_large_upmove_date": ara_meta["prev_ara_date"],
        "prev_large_upmove_ref_price": ara_meta["prev_ara_ref_price"],
        "sma20": round(ma_price, 2) if ma_price is not None else None,
        "state_ma20": state_ma,
        "distance_pct": round(dist_ara, 2),
        "net_dist": round(net_dist, 4) if net_dist is not None else None,
        "net_dist_heavy": net_dist_heavy,
        "sma_gap_pct": round(sma_gap_pct, 2) if sma_gap_pct is not None else None,
        "acc_density": acc_density,
        "post_ara_decay": post_ara_decay,
        "strength": round(
            (density_pct / 100.0) * (net_dist_heavy if net_dist_heavy is not None else 0.5)
            * post_ara_decay, 4),
        "adv_vol_20": round(adv_vol, 0),
        "adv_val_20": round(adv_val, 0),
        "liquidity_ok": liq_ok,
        "liquidity_prima": liq_prima,
        "gates": {"below": True, "min_heavy": True, "above_ma": True,
                  "density": density_ok, "liquidity": liq_ok},
        "note": (
            f"{k} dari {window} hari sejak large upmove ({config.ACCUM_ARA_RISE_PCT:.0f}% harian "
            f"= {bars[ara_idx].date}) volume di atas {config.ACCUM_HEAVY_RVOL}x baseline "
            f"post-event (kepadatan {density_pct:.1f}% >= {config.ACCUM_DENSITY_PCT:.0f}%) sambil "
            f"harga masih DI BAWAH level event ({dist_ara:+.1f}%) dan di atas "
            f"SMA{config.ACCUM_MA20_DAYS} = pola akumulasi post-large-upmove "
            f"(validasi walk-forward 915 saham: b10 {18.4:.1f}% vs kontrol {5.4:.1f}%, edge ~3.3x)."
        ),
        "warning": "Akumulasi post-large-upmove (harga belum recovery ke level event) + konfirmasi SMA20 "
                   "probabilitas naik besar naik, tapi volatil; patuhi exit plan.",
    }


# ---------------------------------------------------------------------------
# Analisis lengkap
# ---------------------------------------------------------------------------

def _detect_corporate_action(bars: list) -> Optional[str]:
    """P7.6: deteksi corporate action (split/bonus/rights/dividen material)
    pada ~5 bar terakhir lewat lompatan faktor adj f = raw_close/adj_close
    (>2% dalam satu hari). Return catatan atau None.

    Raw & adjusted dari Yahoo: adj berubah level saat CA, raw tidak.
    Kalau CA terjadi baru-baru ini, penurunan harga raw bisa bukan
    penurunan nilai pasar — user perlu konteks.
    """
    if not bars or len(bars) < 2:
        return None
    raw = np.array([(getattr(b, "raw_close", None) or b.close) for b in bars],
                   dtype=float)
    adj = np.array([(getattr(b, "adj_close", None) or b.close) for b in bars],
                   dtype=float)
    ok = (raw > 0) & (adj > 0) & np.isfinite(raw) & np.isfinite(adj)
    if ok.sum() < 2:
        return None
    f = raw / adj
    with np.errstate(invalid="ignore", divide="ignore"):
        dl = np.diff(np.log(f))
    idx = np.flatnonzero(np.abs(dl) > np.log1p(0.02))  # >2% dalam 1 bar
    if len(idx) == 0:
        return None
    j = int(idx[-1]) + 1  # bar setelah lompatan
    if j < len(bars) - 5:  # hanya relevan kalau terjadi ~5 bar terakhir
        return None
    pct = float(np.expm1(dl[j - 1])) * 100.0
    return (f"Corporate action terdeteksi pada bar ke-{j + 1} dari akhir "
            f"(lompatan faktor penyesuaian {pct:+.1f}%): penurunan harga "
            f"mungkin bukan penurunan nilai pasar (split/bonus/rights/dividen).")


def build_recovery_analysis(
        code: str,
        nama: str,
        bars: list,
        drop_pct: Optional[float] = None,
        ref_days: Optional[int] = None,
        last_updated: str = "",
) -> dict:
    """
    Analisis recovery ke previous close untuk satu saham.

    Args:
        code: kode saham
        nama: nama emiten
        bars: list DailyBar (dari data_source.yahoo_client), urut lama->baru
        drop_pct: threshold drop X%; None = otomatis dari volatilitas saham
        last_updated: tanggal data terakhir (fallback ke bar terakhir)
        ref_days: target acuan recovery dalam hari trading (1 = previous
            close); None = previous close (close[-2], status quo)

    Returns:
        dict sesuai struktur RecoveryResponse di api.py
    """
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)

    base = {
        "kode": code,
        "nama": nama,
        "valid": False,
        "last_updated": last_updated or (bars[-1].date if bars else ""),
        "harga": float(close[-1]) if len(close) else 0.0,
        "ref_price": float(close[-2]) if len(close) > 1 else 0.0,
        "ref_days": ref_days,
        "distance_pct": None,
        "drop_pct": drop_pct,
        "drop_source": "manual",
        "in_setup": False,
        "gbm": None,          # DEPRECATED - selalu None, lihat field "model"
        "model": None,        # model recovery empiris global (logistic drawdown)
        "empirical": [],
        "signal": "NO_SETUP",
        "signal_reason": "",
        "exit_plan": None,
        "vs_lookbacks": [],
        "accumulation": None,
        "ca_note": None,   # P7.6: catatan corporate action bila terdeteksi
    }

    # P7.6: flag corporate action (ada di response walau tanpa setup)
    base["ca_note"] = _detect_corporate_action(bars)

    if len(close) < config.RECOVERY_MIN_BARS:
        base["signal_reason"] = (
            f"Data historis cuma {len(close)} bar, minimal {config.RECOVERY_MIN_BARS} "
            "untuk estimasi GBM yang stabil."
        )
        return base

    if ref_days is not None:
        if ref_days < 1:
            base["signal_reason"] = "ref_days harus >= 1."
            return base
        if len(close) <= ref_days:
            base["signal_reason"] = (
                f"Data historis cuma {len(close)} bar, tidak cukup untuk acuan "
                f"{ref_days} hari."
            )
            return base

    # Auto-drop: threshold = 2.5 x sigma_daily, clamp 2%..cap 13% (flat - ARB flat 15%)
    params = None
    if drop_pct is None:
        params = estimate_gbm_params(close)
        sigma = params[1]
        price_now = float(close[-1])
        drop_pct = auto_drop_pct(sigma, price_now)
        base["drop_source"] = "auto"
    base["drop_pct"] = drop_pct

    price = float(close[-1])
    if ref_days is not None:
        ref_price = float(close[-1 - ref_days])
    else:
        ref_price = float(close[-2])
    base["ref_price"] = ref_price
    if ref_price <= 0:
        base["signal_reason"] = "Harga acuan tidak valid."
        return base

    distance_pct = (price - ref_price) / ref_price * 100.0
    base["distance_pct"] = round(distance_pct, 2)
    base["last_updated"] = last_updated or bars[-1].date

    in_setup = distance_pct <= -drop_pct
    base["in_setup"] = in_setup

    base["empirical"] = empirical_base_rates(close, high, drop_pct)

    if price < ref_price:
        # --- Model recovery empiris global: P(hit prior high dalam h hari) ---
        dd_f, peak = dd_fraction(close)
        model_params = _load_recovery_model_params()
        probs = recovery_model_probs(dd_f, params=model_params) if dd_f is not None else None
        base["model"] = {
            "kind": "logistic_drawdown",
            "target": "prior_peak",
            "target_desc": "prior high = max(close) trailing "
                           f"{config.RECOVERY_PEAK_LOOKBACK_DAYS} hari trading",
            "dd_fraction": round(dd_f, 4) if dd_f is not None else None,
            "prior_peak": round(peak, 2) if peak is not None else None,
            "probabilities": probs,
            "params_version": model_params.get("generated") if model_params else None,
        }

        p_signal = None
        basis = "model GBM"
        emp_signal = next(
            (e for e in base["empirical"] if e["horizon_days"] == config.RECOVERY_SIGNAL_HORIZON_DAYS),
            None,
        )
        # F2.4: shrinkage Beta-Binomial (prior per bucket drop antar-saham)
        # menggantikan hard switch n>=5. Saham dengan >=1 event historis:
        # p = (k + a0)/(n + a0 + b0) — kontinu dlm n, tertarik ke pooled
        # antar-saham utk n kecil. Tanpa event (n=0) -> fallback model
        # empiris global (target prior peak). GBM dihapus dari jalur sinyal
        # karena menyesatkan (over-optimis pada drift tinggi).
        shr_params = _load_shrinkage_params()
        if emp_signal and emp_signal["n_events"] >= 1:
            p_shrunk = _shrunk_rate(emp_signal["n_recovered"],
                                    emp_signal["n_events"], drop_pct,
                                    config.RECOVERY_SIGNAL_HORIZON_DAYS,
                                    shr_params)
            if p_shrunk is not None:
                p_signal = p_shrunk
                basis = f"empiris shrinkage ({emp_signal['n_events']} event + prior beta-binomial)"
        if p_signal is None:
            p_model = next(
                (p["p_hit"] for p in (probs or [])
                 if p["horizon_days"] == config.RECOVERY_SIGNAL_HORIZON_DAYS),
                None,
            )
            if p_model is not None:
                p_signal = p_model
                basis = "model empiris global (logistic drawdown)"
        # F2.5: target sinyal eksplisit — shrinkage/empiris -> previous close,
        # model global -> prior high (dua target berbeda, jangan disamakan).
        base["signal_target"] = ("previous_close"
                                 if not basis.startswith("model")
                                 else "prior_high")
        signal, reason = _build_signal(in_setup, distance_pct, drop_pct, p_signal, basis,
                                       p_min=(config.RECOVERY_MODEL_P_MIN if basis.startswith("model")
                                              else config.RECOVERY_SIGNAL_P_MIN))
        base["signal"] = signal
        base["signal_reason"] = reason
        base["signal_basis"] = basis
    else:
        signal, reason = _build_signal(in_setup, distance_pct, drop_pct, None)
        base["signal"] = signal
        base["signal_reason"] = reason
        base["signal_basis"] = "harga di atas acuan"

    if in_setup:
        if base["signal_basis"].startswith("model"):
            # basis model -> target exit = prior high (par), bukan previous close
            peak = (dd_fraction(close)[1]) if peak is None else peak
            base["exit_plan"] = _build_exit_plan(
                price, ref_price, target_override=peak, target_note="prior high")
        else:
            base["exit_plan"] = _build_exit_plan(price, ref_price)

    # Posisi harga sekarang vs close N hari trading lalu (1D/1W/1M/3M)
    lookbacks = []
    for n in config.RECOVERY_VS_LOOKBACKS_DAYS:
        if len(close) <= n:
            continue
        ref = float(close[-1 - n])
        if ref <= 0:
            continue
        dist = (price - ref) / ref * 100.0

        rets = []
        for i in range(n, len(close)):
            rets.append(close[i] / close[i - n] - 1.0)
        
        threshold_pct = None
        if len(rets) > 1:
            sigma_n = float(np.std(rets, ddof=1))
            price_now = float(close[-1])
            if price_now < 200:
                cap = config.RECOVERY_AUTO_CAP_UNDER_200
            elif price_now < 5000:
                cap = config.RECOVERY_AUTO_CAP_200_TO_5000
            else:
                cap = config.RECOVERY_AUTO_CAP_AT_5000
            
            threshold_pct = round(
                max(config.RECOVERY_AUTO_MIN, min(cap, config.RECOVERY_AUTO_SIGMA_MULT * sigma_n * 100.0)),
                1,
            )

        status = "above" if dist >= 0 else "below"

        lookbacks.append({
            "days": n,
            "label": config.RECOVERY_VS_LABELS.get(n, f"{n}D"),
            "ref_price": round(ref, 2),
            "distance_pct": round(dist, 2),
            "status": status,
            "threshold_pct": threshold_pct,
        })
    base["vs_lookbacks"] = lookbacks

    base["accumulation"] = detect_accumulation(bars)

    base["valid"] = True
    return base