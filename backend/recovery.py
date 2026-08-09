"""
recovery.py - Mean reversion: probabilitas harga balik ke level sebelumnya.

Modul ini menghitung peluang harga saham kembali ke previous close dalam
horizon 1 hari sampai 3 bulan, untuk saham yang baru gap-down / turun
tajam X%.

Dua pendekatan dipakai berbarengan:
  1. First-passage time GBM (CDF Inverse Gaussian / Wald): a = ln(S_target/S_0),
     drift mu dan volatilitas sigma diestimasi dari log-return historis,
     lalu F(T) = peluang menyentuh target pada atau sebelum T hari. Semua
     dihitung pakai numpy + math.erf saja, tanpa scipy/sklearn/lifelines.
  2. Base rate empiris: dari histori harga saham itu sendiri, berapa persen
     kejadian "turun X% dari previous close" yang akhirnya recovery (high
     menyentuh level referensi) dalam horizon yang sama.

Ini bukan rekomendasi beli - murni estimasi probabilitas, bukan jaminan.
Exit plan (target/time-stop/stop-loss) sifatnya informasional saja.

Dependensi: numpy dan math (stdlib).
"""

from __future__ import annotations

import math
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
        })
    return out


# ---------------------------------------------------------------------------
# Signal & exit plan
# ---------------------------------------------------------------------------

def _build_signal(in_setup: bool, distance_pct: float, drop_pct: float,
                  p_signal: Optional[float], basis: str = "model GBM") -> tuple[str, str]:
    if distance_pct >= 0:
        return "NO_SETUP", "Harga di atas atau sama dengan previous close - tidak ada setup gap-down."
    if not in_setup:
        return "NO_SETUP", (
            f"Belum turun cukup jauh (baru {distance_pct:.2f}% vs threshold {drop_pct:.1f}%)."
        )
    if p_signal is not None and p_signal >= config.RECOVERY_SIGNAL_P_MIN:
        return "POTENTIAL", (
            f"Setup aktif (drop {abs(distance_pct):.2f}% >= {drop_pct:.1f}%) dan "
            f"P(recovery <= {config.RECOVERY_SIGNAL_HORIZON_DAYS} hari) = {p_signal:.0%} "
            f"(basis: {basis}) >= {config.RECOVERY_SIGNAL_P_MIN:.0%}."
        )
    return "WATCH", (
        f"Setup aktif tapi P(recovery <= {config.RECOVERY_SIGNAL_HORIZON_DAYS} hari) "
        f"masih di bawah {config.RECOVERY_SIGNAL_P_MIN:.0%}."
    )


def _build_exit_plan(price: float, ref_price: float) -> dict:
    sl = price - config.RECOVERY_SL_DISTANCE_MULT * (ref_price - price)
    return {
        "target": round(ref_price, 0),
        "time_stop_days": config.RECOVERY_TIME_STOP_DAYS,
        "stop_loss": round(sl, 0),
        "note": (
            f"Exit saat harga menyentuh/menutup di atas target (previous close "
            f"{ref_price:,.0f}), atau time-stop {config.RECOVERY_TIME_STOP_DAYS} "
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
    Deteksi pola "akumulasi post-ARA": saham yang baru saja distribusi besar
    (ARA), lalu terkumpul lagi diam-diam sebelum berpotensi naik.

    Logika:
      - ARA (close >= prev * (1 + ACCUM_ARA_RISE_PCT/100)) dianggap hari
        distribusi/dump, bukan hari akumulasi - jadi hari ARA itu sendiri
        tidak ikut dihitung sebagai bagian window.
      - Window akumulasi = semua hari trading sejak ARA, panjangnya dinamis
        (bukan jendela tetap). Kalau ARA kedua muncul dalam <= ACCUM_RVOL_PERIOD
        hari setelah ARA pertama, keduanya dianggap satu gelombang: window
        di-anchor ke ARA pertama (supaya hari di antara dua ARA tidak
        terbuang), tapi harga acuannya tetap ARA terbaru/puncak. Hari ARA
        kedua sendiri tetap ikut dihitung di window, baseline, dan k - yang
        dikecualikan hanya ARA pertama (si anchor).
      - "Heavy" dihitung per hari (point-in-time): untuk bar i di window,
        baseline-nya adalah rata-rata volume post-ARA sebelum hari i (anti
        self-reference, anti look-ahead, konsisten dengan konvensi RVOL di
        indicators.py; fallback ke rata-rata 20 hari pre-ARA, lalu ke RVOL
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
      - Syarat wajib lain: harga masih di bawah level ARA (belum recovery).
        Kalau harga sudah di atas ARA, itu masuk fase recovery/distribusi,
        bukan akumulasi lagi, jadi sinyalnya tidak bermakna di situasi itu.

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
    close = np.array([b.close for b in bars], dtype=float)
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
            "reason": "Belum pernah ada ARA (+{}%) dalam history - tidak ada acuan distribusi.".format(
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
            "reason": "Hari ini hari ARA belum ada jendela akumulasi.",
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

    if not ready:
        parts = []
        if not below:
            if t == ara_idx:
                parts.append("hari ini = ARA terbaru (belum ada bar setelah puncak)")
            else:
                parts.append("harga SUDAH di atas level ARA (recovery/distribusi, bukan akumulasi)")
        if not k_ok:
            parts.append(f"baru {k} dari {window} hari volume >= {config.ACCUM_HEAVY_RVOL}x "
                         f"baseline (butuh min {config.ACCUM_MIN_HEAVY_DAYS} hari)")
        if not density_ok:
            parts.append(f"volume tidak konsisten: kepadatan baru {density_pct:.1f}% "
                         f"(wajib >= {config.ACCUM_DENSITY_PCT}%)")
        if not above_ma:
            parts.append(f"harga BELUM di atas SMA{config.ACCUM_MA20_DAYS}")
        return {
            "valid": False,
            "ready_to_fly": False,
            "k_heavy": k,
            "window_days": window,
            "density_pct": round(density_pct, 1),
            "rvol": _finite(rv[t]),
            "max_rvol": _finite(np.nanmax(rv[anchor_idx + 1: t + 1])) if window else None,
            "ara_date": str(bars[ara_idx].date)[:10],
            "ara_ref_price": round(float(close[ref_ara_idx]), 2),
            "prev_ara_date": ara_meta["prev_ara_date"],
            "prev_ara_ref_price": ara_meta["prev_ara_ref_price"],
            "days_since_prev_ara": ara_meta["days_since_prev_ara"],
            "double_ara": double_ara,
            "sma20": round(ma_price, 2) if ma_price is not None else None,
            "state_ma20": "above" if above_ma else "below",
            "distance_pct": round(dist_ara, 2),
            "gates": {"below": below, "density": density_ok, "min_heavy": k_ok,
                      "above_ma": above_ma},
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
        "rvol": _finite(rv[t]),
        "max_rvol": _finite(np.nanmax(rv[anchor_idx + 1: t + 1])) if window else None,
        "ara_date": str(bars[ara_idx].date)[:10],
        "ara_ref_price": round(float(close[ref_ara_idx]), 2),
        "prev_ara_date": ara_meta["prev_ara_date"],
        "prev_ara_ref_price": ara_meta["prev_ara_ref_price"],
        "days_since_prev_ara": ara_meta["days_since_prev_ara"],
        "double_ara": double_ara,
        "sma20": round(ma_price, 2) if ma_price is not None else None,
        "state_ma20": state_ma,
        "distance_pct": round(dist_ara, 2),
        "gates": {"below": True, "min_heavy": True, "above_ma": True, "density": density_ok},
        "note": (
            f"{k} dari {window} hari sejak ARA ({config.ACCUM_ARA_RISE_PCT:.0f}% harian "
            f"= {bars[ara_idx].date}) volume di atas {config.ACCUM_HEAVY_RVOL}x baseline "
            f"post-ARA (kepadatan {density_pct:.1f}% >= {config.ACCUM_DENSITY_PCT:.0f}%) sambil "
            f"harga masih DI BAWAH level ARA ({dist_ara:+.1f}%) dan di atas "
            f"SMA{config.ACCUM_MA20_DAYS} = pola akumulasi post-ARA "
            f"(validasi walk-forward 915 saham: b10 {18.4:.1f}% vs kontrol {5.4:.1f}%, edge ~3.3x)."
        ),
        "warning": "Akumulasi post-ARA (harga belum recovery ke level ARA) + konfirmasi SMA20 "
                   "probabilitas naik besar naik, tapi volatil; patuhi exit plan.",
    }


# ---------------------------------------------------------------------------
# Analisis lengkap
# ---------------------------------------------------------------------------

def build_recovery_analysis(
    code: str,
    nama: str,
    bars: list,
    drop_pct: float = config.RECOVERY_DROP_DEFAULT,
    last_updated: Optional[str] = None,
    ref_days: Optional[int] = None,
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
        "gbm": None,
        "empirical": [],
        "signal": "NO_SETUP",
        "signal_reason": "",
        "exit_plan": None,
        "vs_lookbacks": [],
        "accumulation": None,
    }

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
        a = math.log(ref_price / price)
        # estimate_gbm_params mengembalikan drift proses log-harga (mu_log),
        # dan itu memang yang dibutuhkan first_passage_cdf/p_hit_ever - pakai
        # apa adanya, jangan tambah +0.5*sigma^2 (itu koreksi Ito untuk drift harga).
        mu_log, sigma = params if params else estimate_gbm_params(close)
        mu_arith = mu_arithmetic_daily(mu_log, sigma)
        probs = [
            {"horizon_days": h, "p_hit": round(first_passage_cdf(a, mu_log, sigma, h), 3)}
            for h in config.RECOVERY_HORIZONS_DAYS
        ]
        ever = p_hit_ever(mu_log, sigma, a)
        base["gbm"] = {
            "mu_daily": round(mu_arith, 6),
            "sigma_daily": round(sigma, 6),
            "mu_annual": round(mu_arith * 252, 4),
            "sigma_annual": round(sigma * math.sqrt(252), 4),
            "p_hit_ever": round(ever, 3),
            "probabilities": probs,
        }

        p_signal = None
        basis = "model GBM"
        emp_signal = next(
            (e for e in base["empirical"] if e["horizon_days"] == config.RECOVERY_SIGNAL_HORIZON_DAYS),
            None,
        )
        # Base rate empiris lebih representatif kalau sampelnya cukup; kalau
        # tidak, fallback ke model GBM (drift log-nya sudah diestimasi dengan
        # benar, jadi tidak ada bias over-optimis dari +0.5*sigma^2).
        if emp_signal and emp_signal["n_events"] >= 5 and emp_signal["rate"] is not None:
            p_signal = emp_signal["rate"]
            basis = f"empiris {emp_signal['n_events']} event historis"
        else:
            p_signal = next(
                (p["p_hit"] for p in probs if p["horizon_days"] == config.RECOVERY_SIGNAL_HORIZON_DAYS),
                None,
            )
        signal, reason = _build_signal(in_setup, distance_pct, drop_pct, p_signal, basis)
        base["signal"] = signal
        base["signal_reason"] = reason
    else:
        signal, reason = _build_signal(in_setup, distance_pct, drop_pct, None)
        base["signal"] = signal
        base["signal_reason"] = reason

    if in_setup:
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