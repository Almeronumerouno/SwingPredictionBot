"""
recovery.py — Mean Reversion / Recovery ke Previous Price.

Menghitung probabilitas harga kembali ke previous close (close bar
sebelumnya) dalam horizon 1D-3M untuk saham yang sedang di bawah level
tersebut ("gap-down" / drop X%).

Dua pendekatan digabung:
  1. GBM analitik First-Passage Time (CDF Inverse Gaussian / Wald):
     a = ln(S_target / S_0), drift mu & volatilitas sigma diestimasi dari
     log-return historis. F(T) = P(hit target pada atau sebelum T hari).
     Implementasi numpy murni — normal CDF via math.erf (stdlib), TANPA
     scipy / sklearn / lifelines.
  2. Base rate empiris historis: berapa % event "close turun X% di bawah
     previous close" yang sebelumnya pernah recovery (high menyentuh ref)
     dalam horizon yang sama — cross-check data-driven yang jujur.

Ini BUKAN rekomendasi beli. Ini estimasi probabilitas (ekspektasi), bukan
jaminan. Exit plan (target/time-stop/SL) bersifat informasional.

Dependensi: numpy + math saja.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

import config


# ---------------------------------------------------------------------------
# Distribusi normal (via erf, stdlib — tanpa scipy)
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
    Estimasi drift harian mu & vol harian sigma dari log-return.

    mu   = mean(log-return mu_lookback terakhir) + 0.5*sigma^2  (drift GBM aritmetik)
    sigma = std(log-return sigma_lookback terakhir, ddof=1)

    Returns (mu_daily, sigma_daily); (0.0, 0.0) jika data tidak cukup.
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
    mu = float(np.mean(mu_window)) + 0.5 * sigma * sigma
    if not np.isfinite(mu):
        mu = 0.0

    return mu, sigma


# ---------------------------------------------------------------------------
# First-Passage Time (Inverse Gaussian CDF) — GBM
# ---------------------------------------------------------------------------

def first_passage_cdf(a: float, mu: float, sigma: float, t: float) -> float:
    """
    P(hit level log-distance +a pada atau sebelum waktu t), a > 0.

    CDF Inverse Gaussian (Wald) untuk hitting time BM berdrift:
        F(t) = Phi((mu*t - a)/(sigma*sqrt(t)))
             + exp(2*a*mu/sigma^2) * Phi(-(a + mu*t)/(sigma*sqrt(t)))

    CATATAN: versi pertama di beberapa sumber menulis Phi((a-mu*t)/...) pada
    term pertama — itu salah (memberi F(t)=1 saat mu=0). Bentuk di atas
    adalah bentuk standar (Wikipedia: Inverse Gaussian distribution) dan
    tervalidasi: mu=0 -> F(t) = 2*Phi(-a/(sigma*sqrt(t))) via refleksi.

    Term kedua dihitung di log-space (stabil numerik). Output di-clip ke [0,1].
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
    Untuk tiap bar i: event = close[i] <= close[i-1] * (1 - X/100).
    Recovery = max(high[i+1 .. i+h]) >= close[i-1] (touch, konsisten dgn FPT).

    Event tanpa horizon penuh di-censor (tidak dihitung) — anti look-ahead.
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
        return "NO_SETUP", "Harga di atas atau sama dengan previous close — tidak ada setup gap-down."
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
    Threshold otomatis: 2.5 x sigma_daily, di-clamp floor 2% dan cap sesuai
    tier harga saham (batas fluktuasi harian IDX / auto reject).

    - harga < Rp 200       -> cap 30%   (IDX limit ±35%)
    - Rp 200 - < Rp 5000   -> cap 18%   (IDX limit ±20%)
    - harga >= Rp 5000     -> cap 13%   (IDX limit ±15%)
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


# ---------------------------------------------------------------------------
# Analisis lengkap
# ---------------------------------------------------------------------------

def build_recovery_analysis(
    code: str,
    nama: str,
    bars: list,
    drop_pct: float = config.RECOVERY_DROP_DEFAULT,
    last_updated: Optional[str] = None,
) -> dict:
    """
    Analisis recovery ke previous close untuk satu saham.

    Args:
        code: kode saham
        nama: nama emiten
        bars: list DailyBar (dari data_source.yahoo_client), urut lama->baru
        drop_pct: threshold drop X%; None = otomatis dari volatilitas saham
        last_updated: tanggal data terakhir (fallback ke bar terakhir)

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
        "distance_pct": None,
        "drop_pct": drop_pct,
        "drop_source": "manual",
        "in_setup": False,
        "gbm": None,
        "empirical": [],
        "signal": "NO_SETUP",
        "signal_reason": "",
        "exit_plan": None,
    }

    if len(close) < config.RECOVERY_MIN_BARS:
        base["signal_reason"] = (
            f"Data historis cuma {len(close)} bar, minimal {config.RECOVERY_MIN_BARS} "
            "untuk estimasi GBM yang stabil."
        )
        return base

    # Auto-drop: threshold = 2.5 x sigma_daily, clamp 2%..cap(tier harga IDX)
    params = None
    if drop_pct is None:
        params = estimate_gbm_params(close)
        sigma = params[1]
        price_now = float(close[-1])
        drop_pct = auto_drop_pct(sigma, price_now)
        base["drop_source"] = "auto"
    base["drop_pct"] = drop_pct

    price = float(close[-1])
    ref_price = float(close[-2])
    if ref_price <= 0:
        base["signal_reason"] = "Previous close tidak valid."
        return base

    distance_pct = (price - ref_price) / ref_price * 100.0
    base["distance_pct"] = round(distance_pct, 2)
    base["last_updated"] = last_updated or bars[-1].date

    in_setup = distance_pct <= -drop_pct
    base["in_setup"] = in_setup

    base["empirical"] = empirical_base_rates(close, high, drop_pct)

    if price < ref_price:
        a = math.log(ref_price / price)
        mu, sigma = params if params else estimate_gbm_params(close)
        probs = [
            {"horizon_days": h, "p_hit": round(first_passage_cdf(a, mu, sigma, h), 3)}
            for h in config.RECOVERY_HORIZONS_DAYS
        ]
        ever = p_hit_ever(mu, sigma, a)
        base["gbm"] = {
            "mu_daily": round(mu, 6),
            "sigma_daily": round(sigma, 6),
            "mu_annual": round(mu * 252, 4),
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
        # Walk-forward (5 saham IDX, 35 event) menunjukkan GBM under-predict;
        # base rate empiris saham tsb lebih representatif saat sampel cukup.
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

    base["valid"] = True
    return base
