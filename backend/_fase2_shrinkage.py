"""
_fase2_shrinkage.py — F2.4: GANTI HARD SWITCH n>=5 DGN SHRINKAGE (empirical Bayes).

Masalah hard switch produksi (recovery.py, blok sinyal):
  - n_events >= 5  -> p_signal = rate mentah per-saham (k/n). Noisy utk n
    kecil (mis. n=5: 2/5 vs 4/5 = beda 40pp), diskontinuitas tajam di n=5
    (n=4 -> model global, n=5 -> rate mentah), dan rate mentah utk saham
    dgn sedikit event sering ekstrem (0 atau 1) meski populasi ~60%.
  - n_events < 5   -> fallback model logistic global (target prior high),
    padahal sinyal utama targetnya previous close -> target beda.

Solusi F2.4 (empirical Bayes / Beta-Binomial):
  - Prior beta utk tiap (bucket drop, horizon): a0 = p0*m0, b0 = (1-p0)*m0,
    dgn p0 = pooled rate (Σk/Σn) antar-saham, m0 = kekuatan prior
    (pseudo-count) diestimasi dari overdispersion antar-saham.
  - p_shrunk = (k + a0) / (n + a0 + b0) = w*rate + (1-w)*p0, w = n/(n+m0).
    => n kecil: tertarik kuat ke p0 (pooled antar saham sejenis);
    => n besar: mendekati rate saham sendiri (m0 pseudo-count setara).
  - Diskontinuitas hilang: p bergerak kontinu thd n.
  - n == 0 (tidak ada event): tetap fallback model global (status quo).

Evaluasi OOS (kronologis, cutoff + embargo, konsisten F2.1/F2.2):
  - Train events: date_e = dates[i+h] <= cutoff (purge, label tak menembus).
  - Test events : date_s = dates[i] > cutoff + embargo.
  - Metrik per horizon: Brier tertimbang, MAD, kalibrasi bucket, serta
    perbandingan keputusan sinyal vs baseline hard switch.
  - Prior diestimasi HANYA dari train (anti look-ahead).

OUTPUT: data/recovery_shrinkage_params.json — prior per bucket+horizon +
        evaluasi OOS shrinkage vs baseline. Produksi TIDAK ditimpa.
Usage:
    python _fase2_shrinkage.py [--cutoff YYYY-MM-DD] [--embargo-days 90]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

from _fase2_temporal_split import (DATA_DIR, NPZ_PATH, _global_cutoff,
                                   _load_npz)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(DATA_DIR, "recovery_shrinkage_params.json")
DEFAULT_EMBARGO_DAYS = 90
TRAIN_FRAC = 0.70

HORIZONS = (1, 3, 5, 10, 21, 42, 63)
# Bucket threshold drop produksi (auto_drop_pct: 2.5*sigma, clamp [2,13]).
# Bounds bucket: [2,3), [3,4), [4,5), [5,6.5), [6.5,8), [8,10), [10,13), [13,20]
BUCKETS = [(2.0, 3.0), (3.0, 4.0), (4.0, 5.0), (5.0, 6.5),
           (6.5, 8.0), (8.0, 10.0), (10.0, 13.0), (13.0, 20.0)]
MIN_STOCKS_PER_BUCKET = 20      # di bawah ini -> gabung prior tetangga/global
M0_MIN, M0_MAX = 1.0, 500.0     # clamp pseudo-count prior
SIGMA_LOOKBACK = 252            # = config.RECOVERY_SIGMA_LOOKBACK_DAYS
SIGMA_MULT = 2.5                # = config.RECOVERY_AUTO_SIGMA_MULT
AUTO_MIN, AUTO_CAP = 2.0, 13.0  # = config.RECOVERY_AUTO_MIN / CAP


def _sigma_daily(close: np.ndarray) -> float:
    """std log-return 252 hari terakhir, ddof=1 (identik estimate_gbm_params)."""
    valid = close[~np.isnan(close)]
    if valid.size < 2:
        return 0.0
    lr = np.diff(np.log(valid))
    w = lr[-SIGMA_LOOKBACK:] if len(lr) > SIGMA_LOOKBACK else lr
    if w.size < 10:
        return 0.0
    s = float(np.std(w, ddof=1))
    return s if np.isfinite(s) and s > 0 else 0.0


def _auto_drop(sigma: float, price: float) -> float:
    """Duplikat recovery.auto_drop_pct (sinonim: clamp 2.5*sigma ke [2,13])."""
    return float(max(AUTO_MIN, min(AUTO_CAP, SIGMA_MULT * sigma * 100.0)))


def _event_counts(close: np.ndarray, high: np.ndarray,
                  drop_pct: float, h: int) -> tuple[int, int]:
    """(k, n) events ala empirical_base_rates produksi (target previous close).

    Event i: close[i] <= close[i-1]*(1 - drop/100); recovery h: max(high[i+1
    .. i+h]) >= close[i-1]; event valid bila window label lengkap.
    """
    n = len(close)
    if n < 2:
        return 0, 0
    th = 1.0 - drop_pct / 100.0
    ev_mask = close[1:] <= close[:-1] * th       # event di bar i+1
    # max(high[i+1 .. i+h]) per bar i via sliding window
    hh = high[1:]
    if h < len(hh):
        from numpy.lib.stride_tricks import sliding_window_view
        fmax = sliding_window_view(hh, h).max(axis=1)   # fmax[i-1] utk event i
    else:
        fmax = np.array([])
    max_h = len(fmax) + 1                              # bar event terakhir yg valid
    ev = np.where(ev_mask[:max_h - 1])[0] + 1          # bar event (1-based slice)
    if len(ev) == 0:
        return 0, 0
    rec = fmax[ev - 1] >= close[ev - 1]
    return int(rec.sum()), int(len(ev))


def _fit_beta_prior(k_list, n_list) -> dict | None:
    """Fit Beta(a0, b0) method-of-moments dari distribusi antar-saham.

    p0 = pooled rate; m0 = pseudo-count dari overdispersion:
      Var_shrunk(r) = p(1-p)(1+(n-1)*rho)/n, rho = 1/(m0+1)
      m0 = nbar/(overdisp-1) - 1,  clamp [M0_MIN, M0_MAX].
    """
    k_arr = np.asarray(k_list, dtype=float)
    n_arr = np.asarray(n_list, dtype=float)
    tot_k, tot_n = k_arr.sum(), n_arr.sum()
    if tot_n <= 0:
        return None
    p0 = float(tot_k / tot_n)
    if not (0.0 < p0 < 1.0):
        return None
    r = k_arr / n_arr
    nbar = float(n_arr.mean())
    s2_obs = float(((n_arr * (r - p0) ** 2).sum()) / tot_n)
    s2_binom = p0 * (1.0 - p0) / nbar if nbar > 0 else 0.0
    if s2_binom <= 0:
        m0 = M0_MAX
    else:
        overdisp = max(s2_obs / s2_binom, 1.0)
        if overdisp <= 1.0:
            m0 = M0_MAX
        else:
            m0 = nbar / (overdisp - 1.0) - 1.0
    m0 = float(min(max(m0, M0_MIN), M0_MAX))
    a0, b0 = p0 * m0, (1.0 - p0) * m0
    return {"p0": round(p0, 4), "m0": round(m0, 2),
            "a0": round(a0, 3), "b0": round(b0, 3)}


def _bucket_index(drop: float) -> int:
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= drop < hi:
            return i
    return 0 if drop < BUCKETS[0][0] else len(BUCKETS) - 1


def _events_train_test(rows, lens, dates, cutoff: np.datetime64,
                       embargo_days: int, h: int, min_bars: int = 40):
    """Per saham: (k_tr, n_tr, k_te, n_te, drop).

    Train: date_e = dates[i+h] <= cutoff (purge). Test: date_s = dates[i]
    > cutoff + embargo. drop = auto_drop dari sigma/price TRAIN terakhir
    (point-in-time, tanpa info test). return list dict per saham.
    """
    emb = cutoff + np.timedelta64(embargo_days, "D")
    out = []
    for c in range(len(lens)):
        m = int(lens[c])
        if m < h + 2:
            continue
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        dt = np.asarray(dates[c], dtype="datetime64[D]") if len(dates[c]) == m else None
        if dt is None:
            continue
        # bar train terakhir (point-in-time utk sigma & harga)
        tr_end = int(np.searchsorted(dt, cutoff, side="right"))  # bar dgn date<=cutoff
        if tr_end < min_bars:
            continue
        sigma = _sigma_daily(close[:tr_end])
        price_tr = float(close[tr_end - 1])
        drop = _auto_drop(sigma, price_tr) if price_tr > 0 else AUTO_MIN

        # train events: i+h <= tr_end-1 (label selesai <= cutoff)
        n_tr = k_tr = 0
        i = 0
        th = 1.0 - drop / 100.0
        while i < tr_end - 1:
            if close[i + 1] <= close[i] * th and i + 1 + h < tr_end:
                n_tr += 1
                if np.nanmax(high[i + 2:i + 2 + h]) >= close[i]:
                    k_tr += 1
            i += 1

        # test events: date_s > emb (bar setelah embargo), label lengkap
        te0 = int(np.searchsorted(dt, emb, side="right"))
        n_te = k_te = 0
        i = te0
        while i < m - 1:
            if close[i + 1] <= close[i] * th and i + 1 + h < m:
                n_te += 1
                if np.nanmax(high[i + 2:i + 2 + h]) >= close[i]:
                    k_te += 1
            i += 1

        if n_tr or n_te:
            out.append({"code": c, "drop": drop, "k_tr": k_tr, "n_tr": n_tr,
                        "k_te": k_te, "n_te": n_te})
    return out


def _eval_oos(samples: list[dict], prior: dict, h: int) -> dict:
    """Brier/MAD/kalibrasi utk 3 estimator di test events.

    - baseline_hard : rate mentah (n_tr>=5) / pooled bucket (n_tr<5)
    - shrinkage     : (k+a0)/(n+a0+b0)
    - pooled_only   : p0 bucket (referensi)
    Semua tertimbang n_te. Hanya saham dgn n_te>=1.
    """
    rows_acc = {k: {"w": 0.0, "wse": 0.0, "wad": 0.0,
                    "n_saham": 0} for k in ("baseline", "shrink", "pooled")}
    cal = {}
    for s in samples:
        if s["n_te"] < 1:
            continue
        n_tr, k_tr = s["n_tr"], s["k_tr"]
        p0 = prior.get("p0", 0.5)
        m0 = prior.get("m0", 10.0)
        rate_te = s["k_te"] / s["n_te"]
        # baseline: hard switch n>=5 (perilaku produksi lama)
        if n_tr >= 5:
            p_b = k_tr / n_tr
        else:
            p_b = p0
        p_s = (k_tr + p0 * m0) / (n_tr + m0)
        p_p = p0
        w = float(s["n_te"])
        for key, p in (("baseline", p_b), ("shrink", p_s), ("pooled", p_p)):
            a = rows_acc[key]
            a["w"] += w
            a["wse"] += w * (p - rate_te) ** 2
            a["wad"] += w * abs(p - rate_te)
            a["n_saham"] += 1
        # kalibrasi shrinkage per bucket prediksi
        b = f"{int(np.clip(p_s * 5, 0, 4))}"
        if b not in cal:
            cal[b] = {"n": 0, "w": 0.0, "sum_p": 0.0, "sum_act_w": 0.0}
        cal[b]["n"] += 1
        cal[b]["w"] += w
        cal[b]["sum_p"] += p_s * w
        cal[b]["sum_act_w"] += rate_te * w

    def _fin(a):
        if a["w"] <= 0:
            return None
        return {"brier": round(a["wse"] / a["w"], 4),
                "mad": round(a["wad"] / a["w"], 4),
                "n_saham": a["n_saham"]}

    cal_out = []
    for b in sorted(cal, key=int):
        c = cal[b]
        if c["w"] <= 0:
            continue
        cal_out.append({
            "pred_bucket": f"{int(b) * 20}-{int(b) * 20 + 20}%",
            "n_saham": c["n"],
            "mean_pred": round(c["sum_p"] / c["w"], 4),
            "mean_actual": round(c["sum_act_w"] / c["w"], 4),
        })
    return {"baseline": _fin(rows_acc["baseline"]),
            "shrinkage": _fin(rows_acc["shrink"]),
            "pooled_only": _fin(rows_acc["pooled"]),
            "calibration_shrinkage": cal_out}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--cutoff", default=None,
                    help="default: quantile TRAIN_FRAC seluruh tanggal")
    ap.add_argument("--embargo-days", type=int, default=DEFAULT_EMBARGO_DAYS)
    args = ap.parse_args()

    codes, rows, lens, dates = _load_npz(args.npz)
    cutoff = (np.datetime64(args.cutoff, "D") if args.cutoff
              else _global_cutoff(dates, TRAIN_FRAC))
    print(f"Dataset: {len(lens)} kode | cutoff={cutoff} "
          f"| embargo={args.embargo_days} hari", flush=True)

    report = {"method": "beta_binomial_shrinkage",
              "cutoff": str(cutoff),
              "embargo_days": args.embargo_days,
              "buckets": [{"lo": lo, "hi": hi} for lo, hi in BUCKETS],
              "horizons": {}, "generated":
              datetime.now(timezone.utc).isoformat(timespec="seconds")}

    t0 = time.time()
    for h in HORIZONS:
        samples = _events_train_test(rows, lens, dates, cutoff,
                                     args.embargo_days, h)
        # prior per bucket dari TRAIN
        bucket_data: dict[int, tuple[list, list]] = {i: ([], []) for i in
                                                     range(len(BUCKETS))}
        for s in samples:
            if s["n_tr"] >= 1:
                i = _bucket_index(s["drop"])
                bucket_data[i][0].append(s["k_tr"])
                bucket_data[i][1].append(s["n_tr"])
        priors = {}
        n_bucket_stocks = {}
        for i, (lo, hi) in enumerate(BUCKETS):
            kk, nn = bucket_data[i]
            n_bucket_stocks[i] = len(kk)
            prior = _fit_beta_prior(kk, nn) if len(kk) >= MIN_STOCKS_PER_BUCKET else None
            priors[i] = prior
        # fallback: bucket kekurangan sampel -> prior tetangga terdekat yg ada
        for i in range(len(BUCKETS)):
            if priors[i] is not None:
                continue
            for d in range(1, len(BUCKETS)):
                for cand in (i - d, i + d):
                    if 0 <= cand < len(BUCKETS) and priors[cand] is not None:
                        priors[i] = dict(priors[cand], fallback_from=cand)
                        break
                if priors[i] is not None:
                    break
        # prior rata-rata bucket utk referensi pooled global
        all_k, all_n = [], []
        for i in range(len(BUCKETS)):
            all_k += bucket_data[i][0]
            all_n += bucket_data[i][1]
        global_prior = _fit_beta_prior(all_k, all_n)

        # evaluasi OOS
        evals = {}
        for i, (lo, hi) in enumerate(BUCKETS):
            sel = [s for s in samples if _bucket_index(s["drop"]) == i]
            pr = priors[i] or (global_prior or {"p0": 0.5, "m0": 10.0})
            ev = _eval_oos(sel, pr, h)
            evals[f"{lo:.1f}-{hi:.1f}"] = {
                "n_stocks_train": n_bucket_stocks[i],
                "n_stocks_test": sum(1 for s in sel if s["n_te"] >= 1),
                "prior": pr,
                "eval": ev,
            }
        # agregat semua bucket
        agg_prior = global_prior or {"p0": 0.5, "m0": 10.0}
        agg = _eval_oos(samples, agg_prior, h)
        report["horizons"][str(h)] = {"n_stocks_train":
                                      sum(1 for s in samples if s["n_tr"] >= 1),
                                      "n_stocks_test":
                                      sum(1 for s in samples if s["n_te"] >= 1),
                                      "total_test_events":
                                      int(sum(s["n_te"] for s in samples)),
                                      "global_prior": agg_prior,
                                      "buckets": evals,
                                      "eval_all": agg}
        e = agg
        print(f"h={h:>2} | test saham={e['shrinkage']['n_saham']:>4} | "
              f"Brier baseline={e['baseline']['brier']:.4f} "
              f"shrink={e['shrinkage']['brier']:.4f} | "
              f"MAD baseline={e['baseline']['mad']:.4f} "
              f"shrink={e['shrinkage']['mad']:.4f} | "
              f"m0_global={agg_prior.get('m0')} "
              f"p0={agg_prior.get('p0')}", flush=True)

    print(f"\nWaktu total: {time.time()-t0:.0f}s", flush=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Tersimpan: {args.out}")


if __name__ == "__main__":
    sys.exit(main())