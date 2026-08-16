"""
_p75_episode_sensitivity.py — P7.5: Recovery Episode / Dependence Sensitivity.

Bandingkan estimator produksi (daily-event logistic, P6.1) vs estimator
EPISODE-REPRESENTATIVE (1 observasi per episode drawdown, bar trough =
argmax dd — definisi episode F2.2, rep "trough") dengan SEMUA semantik
identik: target (hit prior_peak dalam h hari), peak-lookback 252, clamp
dd [0, 0.85], split temporal global (cutoff 70% tanggal, = 2025-11-24),
purge label-overlap, embargo 5 hari kalender, stock-cluster bootstrap.

Metrik dibandingkan per horizon (test bersih OOS):
  - probability level (mean p)
  - Brier, Brier Skill Score (vs base rate test)
  - calibration intercept & slope (regresi logit: y ~ logit(p))
  - reliability (deviasi maks |actual - pred| per bucket dd)
  - CI 90% stock-cluster bootstrap utk perbedaan Brier (episode - daily)
  - sensitivity terhadap jumlah episode per stock (korelasi & median split)

Keputusan P7.5: estimator produksi TIDAK diganti hanya karena point
estimate berbeda; promotion butuh incremental OOS evidence. Hasil
negatif/null = alasan valid utk TIDAK mengubah produksi.

Usage:
    python _p75_episode_sensitivity.py [--n-boot 100] [--seed 42] [--no-save]
Output: data/phase7_p75_episode.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

# Reuse logika P6.1 yang sudah divalidasi (split/purge/fit identik produksi).
from _phase6_p61_calibrate import (
    HORIZONS,
    DD_BUCKETS,
    DD_CLAMP_MAX,
    _collect_obs,
    _fit_1d,
    _global_cutoff_date,
    _logit_probs,
    _split_purged,
    _trailing_peak,
)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
OUT_JSON = os.path.join(DATA_DIR, "phase7_p75_episode.json")
PROD_PARAMS = os.path.join(DATA_DIR, "recovery_model_params.json")


def _collect_episode_reps(rows, lens, dates, window: int) -> dict[int, dict]:
    """1 observasi per episode drawdown: bar TROUGH (argmax dd) per episode.

    Episode = run kontigu bar dgn dd > 0 (drawdown dari trailing peak,
    sama dgn F2.2). Target semantics identik dgn _collect_obs: y = hit
    prior_peak dalam h hari setelah bar rep (window penuh, high saja).
    date_s = bar rep, date_e = bar rep + h (utk purge label-overlap).
    """
    n_codes = len(lens)
    out = {h: {"dd": [], "y": [], "pos": [], "code": [],
               "date_s": [], "date_e": [], "ep_dur": []} for h in HORIZONS}
    for c in range(n_codes):
        m = int(lens[c])
        if m < window + max(HORIZONS) + 5:
            continue
        dl = dates[c] if (dates is not None and c < len(dates)) else None
        if dl is None or len(dl) != m:
            continue
        dt = np.asarray(dl, dtype="datetime64[D]")
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        peak = _trailing_peak(close, window)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.clip(1.0 - close / peak, 0.0, DD_CLAMP_MAX)
        valid = np.isfinite(dd) & (dd > 0.0)
        if not valid.any():
            continue
        # run kontigu dd>0 = episode
        pos = np.flatnonzero(valid)
        run_breaks = np.flatnonzero(np.diff(pos) != 1)
        runs = np.split(pos, run_breaks + 1)
        for run in runs:
            t = run[int(np.argmax(dd[run]))]  # trough
            for h in HORIZONS:
                if t + 1 + h > m - 1:
                    continue
                fmax = high[t + 1:t + h + 1].max()
                y = float(fmax >= peak[t])
                out[h]["dd"].append(float(dd[t]))
                out[h]["y"].append(y)
                out[h]["pos"].append(int(t))
                out[h]["code"].append(int(c))
                out[h]["date_s"].append(dt[t])
                out[h]["date_e"].append(dt[t + h])
                out[h]["ep_dur"].append(int(len(run)))
    for h in HORIZONS:
        for k in ("dd", "y", "pos", "code", "ep_dur"):
            out[h][k] = np.asarray(out[h][k])
        out[h]["date_s"] = np.asarray(out[h]["date_s"], dtype="datetime64[D]")
        out[h]["date_e"] = np.asarray(out[h]["date_e"], dtype="datetime64[D]")
    return out


def _calib_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    """Brier, BSS, calibration intercept/slope, reliability, mean p."""
    n = len(y)
    base = float(y.mean()) if n else 0.0
    brier = float(brier_score_loss(y, p)) if n else float("nan")
    bss = 1.0 - brier / (base * (1.0 - base)) if 0.0 < base < 1.0 else float("nan")
    calib_intercept = calib_slope = None
    if n >= 50 and len(np.unique(y)) > 1:
        lo = np.clip(p, 1e-6, 1 - 1e-6)
        clf = LogisticRegression(C=np.inf, max_iter=5000)
        clf.fit(np.log(lo / (1.0 - lo)).reshape(-1, 1), y)
        calib_intercept = float(clf.intercept_[0])
        calib_slope = float(clf.coef_[0][0])
    rel_buckets = []
    return {
        "n": int(n), "base_rate": round(base, 4),
        "brier": round(brier, 5), "bss": round(bss, 4),
        "mean_p": round(float(p.mean()), 4) if n else None,
        "calib_intercept": round(calib_intercept, 4) if calib_intercept is not None else None,
        "calib_slope": round(calib_slope, 4) if calib_slope is not None else None,
        "reliability": rel_buckets,
    }


def _reliability_by_dd(dd, y, p) -> list[dict]:
    out = []
    for lo, hi in DD_BUCKETS:
        m = (dd >= lo) & (dd < hi)
        if m.sum() < 30:
            continue
        out.append({
            "bucket": f"{lo:.2f}-{hi:.2f}",
            "n": int(m.sum()),
            "pred": round(float(p[m].mean()), 4),
            "actual": round(float(y[m].mean()), 4),
            "dev": round(float(y[m].mean() - p[m].mean()), 4),
        })
    return out


def _fit_and_eval(tr, te) -> dict | None:
    """Fit logistic di train; metrik lengkap di test."""
    clf = _fit_1d(tr["dd"], tr["y"])
    if clf is None:
        return None
    a, b = float(clf.intercept_[0]), float(clf.coef_[0][0])
    p = _logit_probs(a, b, te["dd"])
    m = _calib_metrics(te["y"], p)
    m.update({"a": round(a, 5), "b": round(b, 5)})
    m["reliability"] = _reliability_by_dd(te["dd"], te["y"], p)
    return m


def _bootstrap_diff(tr_d, tr_e, te_d, te_e, n_boot: int, seed: int) -> dict:
    """Stock-cluster bootstrap: resample SAHAM dgn replacement dari train,
    refit kedua estimator, eval di TEST PENUH; CI 90% utk diff Brier
    (episode - daily) dan diff mean_p."""
    rng = np.random.default_rng(seed)

    def run(h):
        hd = tr_d[h]
        codes = hd["code"]
        uniq = np.unique(codes)
        per_stock_d = [np.where(codes == c)[0] for c in uniq]
        ep_codes = tr_e[h]["code"]
        per_stock_e = {int(c): np.where(ep_codes == c)[0]
                       for c in np.unique(ep_codes)}
        te_dd, te_y = te_d[h]["dd"], te_d[h]["y"]
        te_e_dd, te_e_y = te_e[h]["dd"], te_e[h]["y"]
        d_brier, e_brier, d_mp, e_mp = [], [], [], []
        ok = 0
        for _ in range(n_boot):
            pick = rng.integers(0, len(uniq), size=len(uniq))
            idx_d = np.concatenate([per_stock_d[i] for i in pick])
            idx_e = np.concatenate([per_stock_e[int(c)] for c in uniq[pick]
                                    if int(c) in per_stock_e])
            if len(idx_e) < 50:
                continue
            clf_d = _fit_1d(hd["dd"][idx_d], hd["y"][idx_d])
            clf_e = _fit_1d(tr_e[h]["dd"][idx_e], tr_e[h]["y"][idx_e])
            if clf_d is None or clf_e is None:
                continue
            p_d = _logit_probs(float(clf_d.intercept_[0]), float(clf_d.coef_[0][0]), te_dd)
            p_e = _logit_probs(float(clf_e.intercept_[0]), float(clf_e.coef_[0][0]), te_e_dd)
            d_brier.append(brier_score_loss(te_y, p_d))
            e_brier.append(brier_score_loss(te_e_y, p_e))
            d_mp.append(float(p_d.mean()))
            e_mp.append(float(p_e.mean()))
            ok += 1
        if ok < 30:
            return str(h), {"fitted": False, "n_boot_done": ok}
        d_brier, e_brier = np.asarray(d_brier), np.asarray(e_brier)
        diff = e_brier - d_brier
        lo, hi = np.percentile(diff, [5, 95])
        return str(h), {
            "fitted": True, "n_boot": ok,
            "brier_daily_mean": round(float(d_brier.mean()), 5),
            "brier_episode_mean": round(float(e_brier.mean()), 5),
            "diff_ep_minus_daily_mean": round(float(diff.mean()), 5),
            "ci90_low": round(float(lo), 5),
            "ci90_high": round(float(hi), 5),
            "pct_episode_better": round(float((diff < 0).mean()), 3),
            "mean_p_daily": round(float(np.mean(d_mp)), 4),
            "mean_p_episode": round(float(np.mean(e_mp)), 4),
        }

    results = Parallel(n_jobs=min(8, os.cpu_count() or 1))(
        delayed(run)(h) for h in HORIZONS)
    return {k: v for k, v in results}


def _episode_count_sensitivity(te_e: dict, r_d: dict, r_e: dict, h: int) -> dict:
    """Test stocks split by jumlah episode (median) -> Brier per grup + korelasi
    |y-p| vs jumlah episode per stock. Kedua estimator dievaluasi pada SET yang
    SAMA (episode test obs) agar perbandingan per grup fair."""
    dd, y = te_e[h]["test"]["dd"], te_e[h]["test"]["y"]
    code = te_e[h]["test"]["code"]
    uniq = np.unique(code)
    n_ep = {c: int((code == c).sum()) for c in uniq}
    med = float(np.median([n_ep[c] for c in uniq])) if len(uniq) else 0.0
    # proba kedua estimator pada episode test obs
    p_d = _logit_probs(r_d["a"], r_d["b"], dd)
    p_e = _logit_probs(r_e["a"], r_e["b"], dd)
    ec = np.asarray([n_ep[int(c)] for c in code])
    corr_d = float(np.corrcoef(np.abs(y - p_d), ec)[0, 1]) if len(uniq) > 2 else None
    corr_e = float(np.corrcoef(np.abs(y - p_e), ec)[0, 1]) if len(uniq) > 2 else None
    lo_m, hi_m = ec <= med, ec > med
    out = {
        "n_stocks": int(len(uniq)),
        "median_episodes_per_stock": float(med),
        "daily": {
            "corr_abs_err_vs_ep_count": round(corr_d, 4) if corr_d is not None else None,
            "brier_stocks_few_ep": round(float(brier_score_loss(y[lo_m], p_d[lo_m])), 5) if lo_m.sum() >= 30 else None,
            "brier_stocks_many_ep": round(float(brier_score_loss(y[hi_m], p_d[hi_m])), 5) if hi_m.sum() >= 30 else None,
            "n_few_ep": int(lo_m.sum()), "n_many_ep": int(hi_m.sum()),
        },
        "episode": {
            "corr_abs_err_vs_ep_count": round(corr_e, 4) if corr_e is not None else None,
            "brier_stocks_few_ep": round(float(brier_score_loss(y[lo_m], p_e[lo_m])), 5) if lo_m.sum() >= 30 else None,
            "brier_stocks_many_ep": round(float(brier_score_loss(y[hi_m], p_e[hi_m])), 5) if hi_m.sum() >= 30 else None,
            "n_few_ep": int(lo_m.sum()), "n_many_ep": int(hi_m.sum()),
        },
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--peak-lookback", type=int, default=252)
    ap.add_argument("--embargo-days", type=int, default=5)
    ap.add_argument("--cutoff-frac", type=float, default=0.70)
    ap.add_argument("--n-boot", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    d = np.load(args.npz, allow_pickle=True)
    rows, lens, dates = d["rows"], d["lens"], d["dates"]
    print(f"Dataset: {len(lens)} kode", flush=True)

    t0 = time.time()
    all_dates = [np.asarray(dl, dtype="datetime64[D]")
                 for dl in dates if dl is not None and len(dl)]
    cutoff, (glo, ghi) = _global_cutoff_date(all_dates)
    print(f"Rentang global: {glo} -> {ghi}; cutoff 70% = {cutoff}", flush=True)

    # Verifikasi konsistensi dgn produksi (P6): cutoff harus SAMA.
    prod = json.load(open(PROD_PARAMS, encoding="utf-8"))
    prod_cut = prod.get("split_info", {}).get("cutoff_date")
    if prod_cut and str(cutoff) != prod_cut:
        print(f"WARNING: cutoff beda dgn produksi ({prod_cut}) — pakai cutoff "
              f"produksi utk konsistensi.", flush=True)
        cutoff = np.datetime64(prod_cut, "D")

    daily = _collect_obs(rows, lens, dates, args.peak_lookback)
    print(f"Daily obs: {time.time()-t0:.0f}s", flush=True)

    t0 = time.time()
    ep = _collect_episode_reps(rows, lens, dates, args.peak_lookback)
    print(f"Episode reps: {time.time()-t0:.0f}s", flush=True)
    for h in HORIZONS:
        n_ep_tot = len(ep[h]["dd"])
        if n_ep_tot:
            print(f"  h={h:>2} episodes total {n_ep_tot:>7,} | durasi median "
                  f"{int(np.median(ep[h]['ep_dur'])):>4}d | obs daily per episode "
                  f"{len(daily[h]['dd']) / n_ep_tot:6.1f}", flush=True)

    sp_d = {h: _split_purged(daily[h], cutoff, args.embargo_days)
            for h in HORIZONS}
    sp_e = {h: _split_purged(ep[h], cutoff, args.embargo_days)
            for h in HORIZONS}

    print("\n" + "=" * 118)
    print(f"{'h':>4} | {'n_tr':>9} {'n_te':>9} | {'Brier_d':>8} {'Brier_e':>8} "
          f"{'BSS_d':>6} {'BSS_e':>6} | {'c_int_d':>7} {'c_int_e':>7} "
          f"{'c_sl_d':>6} {'c_sl_e':>6} | {'mP_d':>5} {'mP_e':>5}")
    print("-" * 118)

    res = {}
    for h in HORIZONS:
        r_d = _fit_and_eval(sp_d[h], sp_d[h]["test"])
        r_e = _fit_and_eval(sp_e[h], sp_e[h]["test"])
        res[str(h)] = {
            "daily": r_d, "episode": r_e,
            "n_train_daily": int(len(sp_d[h]["dd"])),
            "n_train_episode": int(len(sp_e[h]["dd"])),
            "n_test_daily": int(len(sp_d[h]["test"]["dd"])),
            "n_test_episode": int(len(sp_e[h]["test"]["dd"])),
            "n_purged_daily": int(len(sp_d[h]["purged"]["dd"])),
            "n_purged_episode": int(len(sp_e[h]["purged"]["dd"])),
        }
        if r_d and r_e:
            print(f"{h:>4} | {len(sp_d[h]['dd']):>9,} {len(sp_d[h]['test']['dd']):>9,} | "
                  f"{r_d['brier']:>8.4f} {r_e['brier']:>8.4f} "
                  f"{r_d['bss']:>6.3f} {r_e['bss']:>6.3f} | "
                  f"{str(r_d['calib_intercept']):>7} {str(r_e['calib_intercept']):>7} "
                  f"{str(r_d['calib_slope']):>6} {str(r_e['calib_slope']):>6} | "
                  f"{r_d['mean_p']:>5.3f} {r_e['mean_p']:>5.3f}", flush=True)
        else:
            print(f"{h:>4} | tidak cukup data utk salah satu estimator", flush=True)

    print("=" * 118)

    print("\nStock-cluster bootstrap diff Brier (episode - daily), CI 90%:")
    t0 = time.time()
    boot = _bootstrap_diff(sp_d, sp_e, {h: v["test"] for h, v in sp_d.items()},
                           {h: v["test"] for h, v in sp_e.items()},
                           args.n_boot, args.seed)
    print(f"Bootstrap selesai: {time.time()-t0:.0f}s", flush=True)
    for h in HORIZONS:
        b = boot[str(h)]
        if b.get("fitted"):
            print(f"  h={h:>2} diff={b['diff_ep_minus_daily_mean']:+.5f} "
                  f"CI90=({b['ci90_low']:+.5f}, {b['ci90_high']:+.5f}) "
                  f"episode lebih baik {b['pct_episode_better']*100:.0f}% resamples",
                  flush=True)
        else:
            print(f"  h={h:>2} tidak fit ({b.get('n_boot_done', 0)} ok)", flush=True)
    for h in HORIZONS:
        res[str(h)]["bootstrap_diff"] = boot[str(h)]

    print("\nSensitivity jumlah episode per stock (test):")
    for h in HORIZONS:
        rd = res[str(h)]["daily"]
        re_ = res[str(h)]["episode"]
        if rd is None or re_ is None:
            continue
        sens = _episode_count_sensitivity(sp_e, rd, re_, h)
        res[str(h)]["episode_count_sensitivity"] = sens
        sd, se = sens["daily"], sens["episode"]
        print(f"  h={h:>2} n_stocks={sens['n_stocks']} "
              f"median_ep={sens['median_episodes_per_stock']:.0f} | "
              f"corr |y-p|~ep: d={sd['corr_abs_err_vs_ep_count']} "
              f"e={se['corr_abs_err_vs_ep_count']} | "
              f"Brier few_ep: d={sd['brier_stocks_few_ep']} "
              f"e={se['brier_stocks_few_ep']} | "
              f"Brier many_ep: d={sd['brier_stocks_many_ep']} "
              f"e={se['brier_stocks_many_ep']}", flush=True)

    out = {
        "method": "P7.5 episode/dependence sensitivity",
        "episode_definition": "F2.2: run kontigu dd>0 (drawdown dari trailing peak 252), "
                              "rep = bar trough (argmax dd)",
        "target": "prior_peak (max high dalam h hari setelah bar rep) — identik P6",
        "split": ("global chronological cutoff 70% tanggal = " + str(cutoff) +
                  " + purge label-overlap + embargo 5 hari"),
        "horizons": res,
        "n_boot": args.n_boot,
        "seed": args.seed,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not args.no_save:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nTersimpan: {args.out}")
    else:
        print("\n(no-save: tidak menulis file)")


if __name__ == "__main__":
    sys.exit(main())