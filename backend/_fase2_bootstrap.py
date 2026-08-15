"""
_fase2_bootstrap.py — F2.3: STOCK-CLUSTER BOOTSTRAP + episode-block sensitivity.

MASALAH (dituntaskan F2.1/F2.2):
  - F2.1: split temporal global + purge/embargo (leakage-aware validation).
  - F2.2: 275 rb observasi hanya 4.605 episode independen. Sampel IID palsu.
  - KESIMPULAN: uncertainty W Ajib dihitung pada struktur dependent/clustered,
    bukan IID. Inilah tugas F2.3.

DESAIN F2.3 (sesuai keputusan user):
  Level 1 (PRIMARY CI) — stock-cluster bootstrap:
      sample SAHAM dengan replacement (unit = stock)
        -> ambil SELURUH episode dari stock terpilih (episode tetap utuh)
        -> REFIT logistic: logit(P_h) = a_h + b_h*DD   (bukan bootstrap angka final)
        -> hitung AUC / Brier / beta / alpha / calibration slope+intercept
      Distribusi (a_h^b, b_h^b) = parameter estimation + sampling uncertainty.
  Level 2 (SENSITIVITY) — episode/block bootstrap WITHIN stock:
      per saham: resample episode miliknya sendiri (block internal),
      komposisi stock tetap, dependence intra-stock diguncang.
      -> sensitivity thd struktur episode, bukan CI utama.

  KLASIFIKASI: beta_h < 0 robust? => P(beta < 0) atas B replicate (fraction).

  TIDAK dilakukan:
    - sampling 4.605 episode secara IID (merusak clustering antar stock).
    - bootstrap thd hasil final saja (CI harus mencakup refit).

  CATATAN evaluasi: ini adalah inference uncertainty dari FIT model
  (parameter & performa tentatif), bukan OOS validity — F2.1/F2.2 sudah
  menyediakan lapisan temporal. Rekalibrasi (F2.5/F2.6/Phase 4) DITAHAN
  sampai CI cross-stock tersedia.

OUTPUT: data/recovery_bootstrap_{rep}.json
Usage:
    python _fase2_bootstrap.py [--rep trough|first] [--B 1000] [--B-within 500]
                               [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

from _calibrate_recovery_model import DD_CLAMP_MAX, HORIZONS, _trailing_peak
from _fase2_temporal_split import DATA_DIR, NPZ_PATH, _load_npz

warnings.filterwarnings("ignore", category=FutureWarning)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

MIN_EPISODES_FIT = 40       # minimal episode agar replicate dipakai
MIN_K = 30                  # minimal episode utk kalibrasi slope/intercept


def _collect_episodes_by_stock(rows, lens, window, dates_list=None, rep="trough"):
    """Per saham per horizon: episode -> (dd, y) wakil rep.

    Returns:
      per_h: {h: {"codes": ndarray(int), "dd": ndarray, "y": ndarray}}
        codes = indeks saham utk tiap episode (utk stock-cluster bootstrap).
    Juga stats: episode_per_stock[h] = array jumlah episode per saham yg
    memiliki episode utk horizon h.
    """
    n_codes = len(lens)
    per_h = {h: {"codes": [], "dd": [], "y": []} for h in HORIZONS}
    ep_per_stock = {h: np.zeros(n_codes, dtype=int) for h in HORIZONS}

    for c in range(n_codes):
        m = int(lens[c])
        if m < window + max(HORIZONS) + 5:
            continue
        dt = None
        if dates_list is not None and c < len(dates_list):
            dl = dates_list[c]
            if dl is not None and len(dl) == m:
                dt = np.asarray(dl, dtype="datetime64[D]")
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        peak = _trailing_peak(close, window)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.clip(1.0 - close / peak, 0.0, DD_CLAMP_MAX)
        in_dd = np.isfinite(dd) & (dd > 0.0)

        i = 0
        while i < m:
            if not in_dd[i]:
                i += 1
                continue
            j = i
            while j + 1 < m and in_dd[j + 1]:
                j += 1
            seg = dd[i:j + 1]
            rb = int(i + np.argmax(seg)) if rep == "trough" else int(i)
            for h in HORIZONS:
                if rb + 1 + h > m - 1:
                    continue
                fmax = high[rb + 1:rb + h + 1].max()
                per_h[h]["codes"].append(np.int32(c))
                per_h[h]["dd"].append(dd[rb])
                per_h[h]["y"].append(float(fmax >= peak[rb]))
            i = j + 1

    for h in HORIZONS:
        if per_h[h]["dd"]:
            per_h[h]["codes"] = np.asarray(per_h[h]["codes"], dtype=np.int32)
            per_h[h]["dd"] = np.asarray(per_h[h]["dd"], dtype=float)
            per_h[h]["y"] = np.asarray(per_h[h]["y"], dtype=float)
            codes_h = per_h[h]["codes"]
            ep_per_stock[h] = np.bincount(codes_h, minlength=n_codes)
        else:
            per_h[h]["codes"] = np.array([], dtype=np.int32)
            per_h[h]["dd"] = np.array([])
            per_h[h]["y"] = np.array([])
    return per_h, ep_per_stock


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1.0 - p))


def _fit_and_metrics(dd: np.ndarray, y: np.ndarray):
    """Refit logistic lalu hitung AUC/Brier/alpha/beta/cal slope+intercept."""
    if len(dd) < MIN_EPISODES_FIT or len(np.unique(y)) < 2:
        return None
    clf = LogisticRegression(penalty=None, max_iter=5000)
    clf.fit(dd.reshape(-1, 1), y)
    a = float(clf.intercept_[0])
    b = float(clf.coef_[0][0])
    p = 1.0 / (1.0 + np.exp(-(a + b * dd)))
    auc = roc_auc_score(y, p)
    brier = float(brier_score_loss(y, p))
    cal = {"slope": None, "intercept": None}
    if len(dd) >= MIN_K and len(np.unique(y)) >= 2:
        try:
            clf_c = LogisticRegression(penalty=None, max_iter=5000)
            clf_c.fit(_logit(p).reshape(-1, 1), y)
            cal["intercept"] = float(clf_c.intercept_[0])
            cal["slope"] = float(clf_c.coef_[0][0])
        except Exception:  # noqa: BLE001
            pass
    return {"a": a, "b": b, "auc": auc, "brier": brier,
            "cal_slope": cal["slope"], "cal_intercept": cal["intercept"]}


def _percentile(draws: np.ndarray, q=(2.5, 50.0, 97.5)):
    lo, mid, hi = np.percentile(draws, q)
    return {"lower": float(lo), "median": float(mid), "upper": float(hi),
            "mean": float(draws.mean()), "sd": float(draws.std(ddof=1))}


def _eval_oob(a: float, b: float, dd_oob: np.ndarray, y_oob: np.ndarray,
              min_k: int = MIN_K):
    """Evaluasi model (a,b) di episode dari SAHAM YANG TIDAK TERPILIH.

    In-sample cal slope/intercept = tautologi (fit di sampel yang sama);
    OOB inilah yang menjawab: konsistenkah bias kalibrasi ACROSS stocks.
    Returns dict (auc, brier, overpred, cal_slope, cal_intercept) atau None
    bila sampel OOB terlalu kecil.
    """
    if len(dd_oob) < MIN_EPISODES_FIT or len(np.unique(y_oob)) < 2:
        return None
    p = 1.0 / (1.0 + np.exp(-(a + b * dd_oob)))
    out = {
        "auc": roc_auc_score(y_oob, p),
        "brier": float(brier_score_loss(y_oob, p)),
        "overpred": float(p.mean() - y_oob.mean()),
    }
    if len(dd_oob) >= min_k:
        try:
            clf_c = LogisticRegression(penalty=None, max_iter=5000)
            clf_c.fit(_logit(p).reshape(-1, 1), y_oob)
            out["cal_slope"] = float(clf_c.coef_[0][0])
            out["cal_intercept"] = float(clf_c.intercept_[0])
        except Exception:  # noqa: BLE001
            out["cal_slope"] = None
            out["cal_intercept"] = None
    else:
        out["cal_slope"] = None
        out["cal_intercept"] = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--peak-lookback", type=int, default=252)
    ap.add_argument("--rep", choices=("trough", "first"), default="trough")
    ap.add_argument("--B", type=int, default=1000, help="replicate stock-cluster")
    ap.add_argument("--B-within", type=int, default=500,
                    help="replicate episode-block within stock (sensitivity)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    codes, rows, lens, dates = _load_npz(args.npz)
    t0 = time.time()
    per_h, ep_per_stock = _collect_episodes_by_stock(
        rows, lens, args.peak_lookback, dates_list=dates, rep=args.rep)
    print(f"collect episodes by stock: {time.time()-t0:.0f}s | rep={args.rep}",
          flush=True)

    rng = np.random.default_rng(args.seed)
    n_codes = len(codes)
    horizons_show = (1, 21, 63)

    report = {"rep": args.rep, "B": args.B, "B_within": args.B_within,
              "seed": args.seed, "generated":
              datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "stock_cluster": {}, "stock_cluster_oob": {},
              "within_stock": {}, "point": {},
              "stock_stats": {}, "draws_stock": {}, "draws_oob": {},
              "draws_within": {}}
    INTEREST = ("auc", "brier", "a", "b", "cal_slope", "cal_intercept")

    print("\n" + "=" * 120)
    print("LEVEL 1 — STOCK-CLUSTER BOOTSTRAP (primary CI)")
    print("=" * 120)
    for h in HORIZONS:
        codes_h = per_h[h]["codes"]
        dd_all = per_h[h]["dd"]
        y_all = per_h[h]["y"]
        n_ep = len(dd_all)
        n_stk = int(np.unique(codes_h).size)
        if n_ep < MIN_EPISODES_FIT:
            continue
        # sampel saham dgn penggantian -> ambil seluruh episode-nya
        stk_pool = np.unique(codes_h)      # hanya saham yg punya episode h
        draws = {k: [] for k in INTEREST}
        draws_oob = {k: [] for k in ("auc", "brier", "overpred",
                                     "cal_slope", "cal_intercept")}
        n_fail = 0
        n_oob_fail = 0
        for _ in range(args.B):
            picked = rng.choice(stk_pool, size=len(stk_pool), replace=True)
            mask = np.isin(codes_h, picked)
            m = _fit_and_metrics(dd_all[mask], y_all[mask])
            if m is None:
                n_fail += 1
                continue
            for k in INTEREST:
                v = m[k]
                if v is not None:
                    draws[k].append(v)
            # OOB: evaluasi di episode dari saham yg TIDAK terpilih
            oob_mask = ~np.isin(codes_h, np.unique(picked))
            eo = _eval_oob(m["a"], m["b"], dd_all[oob_mask], y_all[oob_mask])
            if eo is None:
                n_oob_fail += 1
            else:
                for k in draws_oob:
                    draws_oob[k].append(eo[k])
        # point estimate: fit di SEMUA episode (data penuh)
        point = _fit_and_metrics(dd_all, y_all)
        if point is None:
            continue
        ds = {k: _percentile(np.asarray(draws[k])) if draws[k] else None
              for k in INTEREST}
        report["point"][str(h)] = point
        report["stock_cluster"][str(h)] = ds
        report["stock_stats"][str(h)] = {
            "n_stocks": int(n_stk),
            "n_episodes": int(n_ep),
            "median_episodes_per_stock": float(np.median(ep_per_stock[h][:n_stk])),
            "min_episodes_per_stock": int(ep_per_stock[h][:n_stk].min()),
            "max_episodes_per_stock": int(ep_per_stock[h][:n_stk].max()),
            "n_rep_used": int(len(draws["auc"])),
            "n_rep_fail": n_fail,
            "n_oob_used": int(len(draws_oob["auc"])),
            "n_oob_fail": n_oob_fail,
        }
        ds_oob = {k: (_percentile(np.asarray(draws_oob[k]))
                      if draws_oob[k] else None) for k in draws_oob}
        report["stock_cluster_oob"][str(h)] = ds_oob
        if h in horizons_show:
            p_beta_neg = float(np.mean(np.asarray(draws["b"]) < 0))
            report["stock_cluster"][str(h)]["p_beta_negative"] = p_beta_neg
            a_o = ds_oob["auc"]
            br_o = ds_oob["brier"]
            ov_o = ds_oob["overpred"]
            cs_o = ds_oob["cal_slope"]
            ci_o = ds_oob["cal_intercept"]
            line = (f"h={h:>2} n_ep={n_ep:>6,} n_stk={n_stk:>4} | "
                    f"AUC point={point['auc']:.4f} "
                    f"CI[{ds['auc']['lower']:.4f},{ds['auc']['upper']:.4f}] | "
                    f"Brier={point['brier']:.4f} "
                    f"CI[{ds['brier']['lower']:.4f},{ds['brier']['upper']:.4f}] | "
                    f"beta={point['b']:.3f} "
                    f"CI[{ds['b']['lower']:.3f},{ds['b']['upper']:.3f}] "
                    f"P(b<0)={p_beta_neg:.0%}")
            print(line, flush=True)
            line2 = (f"     OOB (saham tak terpilih): AUC "
                     f"CI[{a_o['lower']:.4f},{a_o['upper']:.4f}] | "
                     f"Brier CI[{br_o['lower']:.4f},{br_o['upper']:.4f}] | "
                     f"under/overpred CI[{ov_o['lower']:+.3f},{ov_o['upper']:+.3f}] | "
                     f"cal_slope CI[{cs_o['lower']:.3f},{cs_o['upper']:.3f}] | "
                     f"cal_int CI[{ci_o['lower']:.3f},{ci_o['upper']:.3f}]")
            print(line2, flush=True)
        if h in horizons_show:
            report["draws_stock"][str(h)] = {k: list(draws[k]) for k in INTEREST}
            report["draws_oob"][str(h)] = {k: list(draws_oob[k])
                                           for k in draws_oob}

    print("\n" + "=" * 120)
    print("LEVEL 2 — EPISODE-BLOCK BOOTSTRAP WITHIN STOCK (sensitivity)")
    print("=" * 120)
    for h in HORIZONS:
        codes_h = per_h[h]["codes"]
        dd_all = per_h[h]["dd"]
        y_all = per_h[h]["y"]
        n_ep = len(dd_all)
        if n_ep < MIN_EPISODES_FIT:
            continue
        drains = {k: [] for k in INTEREST}
        for _ in range(args.B_within):
            # per saham: resample episode miliknya sendiri dgn replacement
            dd_b = []
            y_b = []
            for c in np.unique(codes_h):
                m = codes_h == c
                n_e = int(m.sum())
                idx = rng.integers(0, n_e, size=n_e)
                dd_b.append(dd_all[m][idx])
                y_b.append(y_all[m][idx])
            dd_b = np.concatenate(dd_b)
            y_b = np.concatenate(y_b)
            m2 = _fit_and_metrics(dd_b, y_b)
            if m2 is None:
                continue
            for k in INTEREST:
                if m2[k] is not None:
                    drains[k].append(m2[k])
        ds = {k: _percentile(np.asarray(drains[k])) if drains[k] else None
              for k in INTEREST}
        report["within_stock"][str(h)] = ds
        if h in horizons_show:
            print(f"h={h:>2} n_ep={n_ep:>6,} | "
                  f"AUC CI[{ds['auc']['lower']:.4f},{ds['auc']['upper']:.4f}] | "
                  f"Brier CI[{ds['brier']['lower']:.4f},{ds['brier']['upper']:.4f}] | "
                  f"beta CI[{ds['b']['lower']:.3f},{ds['b']['upper']:.3f}] | "
                  f"cal_slope CI[{ds['cal_slope']['lower']:.3f},{ds['cal_slope']['upper']:.3f}]",
                  flush=True)
        if h in horizons_show:
            report["draws_within"][str(h)] = {k: list(drains[k]) for k in INTEREST}

    out = os.path.join(DATA_DIR, f"recovery_bootstrap_{args.rep}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {out}")


if __name__ == "__main__":
    sys.exit(main())