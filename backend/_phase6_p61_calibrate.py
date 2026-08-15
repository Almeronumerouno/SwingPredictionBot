"""
_phase6_p61_calibrate.py — P6.1 Integrity fix (C1) + P6.2 cluster CI (C2) + C3 report.

Perbaikan terhadap _calibrate_recovery_model.py (lihat audit eksternal C1/C2/C3):

  C1  Split GLOBAL KRONOLOGIS (bukan split posisi bar per observasi).
      - cutoff   = tanggal ke-70% dari rentang tanggal global di dataset
      - TRAIN    = observasi dengan date_e < cutoff - embargo
                   (label span selesai SEBELUM test dimulai + buffer)
      - PURGED   = observasi dengan date_s < cutoff <= date_e
                   (label menembus cutoff — overlap temporal, DIBUANG)
      - TEST     = observasi dengan date_s >= cutoff (window penuh)
      - embargo  = 5 hari kalender (~3 hari trading), buffer anti-leak
  C2  CI = CLUSTER BOOTSTRAP SAHAM (percentile 90%, B resamples), menggantikan
      delta-method + scale ad-hoc (ci_bootstrap.scale_a/scale_b dihapus).
      Tabel CI probabilitas disimpan per grid dd -> interpolasi di recovery.py.
  C3  Laporan EPISODE per horizon (klaster observasi drawdown berurutan per
      saham) di train/test — kuantifikasi overlapping events (base rates).

Model & target TIDAK berubah: P_recover = 1/(1+exp(a_h + b_h*dd)), dd = 1 -
close/prior_peak (prior_peak = max(close) trailing 252 hari trading), clamp
[0, 0.85], target = hit prior high dalam h hari (first-passage, window penuh).

HOLD-OUT P4.8 TIDAK DISENTUH: script ini hanya refit dari universe_ohlcv.npz
(live store) dan menulis file params BARU. Setelah validasi, file ditunjuk
oleh config; params lama dibackup (jejak audit).

Usage:
    python _phase6_p61_calibrate.py                 # B=500, embargo=5, cutoff=0.70
    python _phase6_p61_calibrate.py --n-boot 200 --no-save
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

# Base-rate table empiris: reuse fungsi dari calibrator lama (semantik identik,
# murni deskriptif — n/rate per bucket dd x horizon, TANPA split temporal).
from _calibrate_recovery_model import build_base_rate_table

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
PARAMS_OUT = os.path.join(DATA_DIR, "recovery_model_params_p6.json")

HORIZONS = (1, 3, 5, 10, 21, 42, 63)
DD_BUCKETS = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.15),
              (0.15, 0.25), (0.25, 0.40), (0.40, 0.60), (0.60, 0.85)]
DD_CLAMP_MAX = 0.85
PROB_CI_GRID = np.round(np.arange(0.05, 0.85 + 1e-9, 0.05), 2)  # 0.05..0.80


def _trailing_peak(close: np.ndarray, window: int) -> np.ndarray:
    """peak[i] = max(close[i-window+1 .. i]); NaN utk i < window-1."""
    n = len(close)
    out = np.full(n, np.nan)
    if n < window:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    sw = sliding_window_view(close, window)
    out[window - 1:] = sw.max(axis=1)
    return out


def _collect_obs(rows, lens, dates, window: int) -> dict[int, dict]:
    """Per-horizon: (dd, y, pos, code_idx, date_s, date_e) — point-in-time.

    Sama semantik dgn _calibrate_recovery_model._collect_rows (kolom 3 =
    close_raw, kolom 1 = high), plus date_s/date_e WAJIB terisi utk purge.
    """
    n_codes = len(lens)
    out = {h: {"dd": [], "y": [], "pos": [], "code": [],
               "date_s": [], "date_e": []} for h in HORIZONS}
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
        idx = np.where(valid)[0]
        if len(idx) == 0:
            continue
        for h in HORIZONS:
            end = idx + 1 + h
            ok_h = end <= m - 1
            i_h = idx[ok_h]
            if len(i_h) == 0:
                continue
            fmax_h = np.zeros(len(i_h))
            for j, i0 in enumerate(i_h):
                fmax_h[j] = high[i0 + 1:i0 + h + 1].max()
            y = (fmax_h >= peak[i_h]).astype(float)
            out[h]["dd"].append(dd[i_h])
            out[h]["y"].append(y)
            out[h]["pos"].append(i_h)
            out[h]["code"].append(np.full(len(i_h), c, dtype=np.int32))
            out[h]["date_s"].append(dt[i_h])
            out[h]["date_e"].append(dt[i_h + h])
    for h in HORIZONS:
        for k in ("dd", "y", "pos"):
            out[h][k] = np.concatenate(out[h][k]) if out[h][k] else np.array([])
        out[h]["code"] = (np.concatenate(out[h]["code"]) if out[h]["code"]
                          else np.array([], dtype=np.int32))
        out[h]["date_s"] = np.concatenate(out[h]["date_s"]) if out[h]["date_s"] \
            else np.array([], dtype="datetime64[D]")
        out[h]["date_e"] = np.concatenate(out[h]["date_e"]) if out[h]["date_e"] \
            else np.array([], dtype="datetime64[D]")
    return out


def _global_cutoff_date(all_dates: list) -> tuple[np.datetime64, np.datetime64]:
    """cutoff = tanggal ke-frac dari rentang global tanggal unik."""
    uniq = np.unique(np.concatenate(all_dates))
    lo, hi = uniq[0], uniq[-1]
    frac = 0.70
    idx = int(round(frac * (len(uniq) - 1)))
    return uniq[idx], (lo, hi)


def _split_purged(d: dict, cutoff: np.datetime64, embargo_days: int) -> dict:
    """TRAIN / PURGED / TEST berbasis date_s & date_e + embargo kalender."""
    emb = np.timedelta64(embargo_days, "D")
    date_s, date_e = d["date_s"], d["date_e"]
    tr = date_e < (cutoff - emb)
    te = date_s >= cutoff
    pu = ~(tr | te)  # label menembus cutoff / jatuh di buffer — DIBUANG
    out = {k: v[tr] for k, v in d.items()}
    out["test"] = {k: v[te] for k, v in d.items()}
    out["purged"] = {k: v[pu] for k, v in d.items()}
    return out


def _count_episodes(pos: np.ndarray, code: np.ndarray) -> int:
    """Klaster observasi berurutan (pos+1 berurutan, saham sama) = 1 episode."""
    if len(pos) == 0:
        return 0
    nxt = np.roll(pos, -1)
    nxt[-1] = -1
    same_stock = np.roll(code, -1)
    same_stock[-1] = -1
    cont = (pos + 1 == nxt) & (code == same_stock)
    return int((~cont).sum())


def _fit_1d(x: np.ndarray, y: np.ndarray):
    if len(x) < 50 or len(np.unique(y)) < 2:
        return None
    clf = LogisticRegression(C=np.inf, max_iter=5000)
    clf.fit(x.reshape(-1, 1), y)
    return clf


def _logit_probs(a: float, b: float, x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(a + b * x)))


def _cluster_bootstrap_ci(d: dict, n_boot: int, seed: int) -> dict:
    """Resample SAHAM (dengan replacement) dari train; refit logistic per
    horizon; percentile CI 90% utk (a, b) dan P(dd) pada grid."""
    rng = np.random.default_rng(seed)
    res: dict[str, dict] = {}
    for h in HORIZONS:
        hd = d[h]
        codes = hd["code"]
        unique_codes = np.unique(codes)
        per_stock = [np.where(codes == c)[0] for c in unique_codes]
        if len(hd["y"]) < 50 or len(np.unique(hd["y"])) < 2:
            res[str(h)] = {"fitted": False}
            continue
        ab = np.zeros((n_boot, 2))
        ok = 0
        for b in range(n_boot):
            pick = rng.integers(0, len(unique_codes), size=len(unique_codes))
            idx = np.concatenate([per_stock[i] for i in pick])
            clf = _fit_1d(hd["dd"][idx], hd["y"][idx])
            if clf is None:
                continue
            ab[ok] = (clf.intercept_[0], clf.coef_[0][0])
            ok += 1
        if ok < 100:
            res[str(h)] = {"fitted": False, "n_boot_done": int(ok)}
            continue
        ab = ab[:ok]
        lo, hi = 5.0, 95.0
        a_ci = tuple(np.percentile(ab[:, 0], [lo, hi]))
        b_ci = tuple(np.percentile(ab[:, 1], [lo, hi]))
        p_grid = np.column_stack([_logit_probs(a_, b_, PROB_CI_GRID)
                                  for a_, b_ in ab])  # (n_grid, n_boot)
        p_ci = np.percentile(p_grid, [lo, hi], axis=1)  # (2, n_grid)
        res[str(h)] = {
            "fitted": True,
            "n_boot": int(ok),
            "method": "cluster bootstrap saham (percentile 90%)",
            "a_ci": [round(float(a_ci[0]), 5), round(float(a_ci[1]), 5)],
            "b_ci": [round(float(b_ci[0]), 5), round(float(b_ci[1]), 5)],
            "prob_ci_grid": PROB_CI_GRID.tolist(),
            "prob_ci_low": [round(float(v), 4) for v in p_ci[0]],
            "prob_ci_high": [round(float(v), 4) for v in p_ci[1]],
        }
    return res


def _fit_horizon(hd: dict, h: int) -> dict:
    """Fit logistic di TRAIN bersih; evaluasi di TEST bersih."""
    dd_t, y_t = hd["dd"], hd["y"]
    dd_v, y_v = hd["test"]["dd"], hd["test"]["y"]
    clf = _fit_1d(dd_t, y_t)
    if clf is None:
        return {"horizon_days": h, "fitted": False,
                "n_train": int(len(dd_t)), "n_test": int(len(dd_v))}
    a, b = float(clf.intercept_[0]), float(clf.coef_[0][0])
    p_t, p_v = _logit_probs(a, b, dd_t), _logit_probs(a, b, dd_v)
    auc_train = roc_auc_score(y_t, p_t) if len(np.unique(y_t)) > 1 else None
    auc_test = roc_auc_score(y_v, p_v) if len(np.unique(y_v)) > 1 else None
    brier_test = float(brier_score_loss(y_v, p_v))
    cal = []
    for lo, hi in DD_BUCKETS:
        m = (dd_v >= lo) & (dd_v < hi)
        if m.sum() < 30:
            continue
        cal.append({
            "bucket": f"{lo:.2f}-{hi:.2f}",
            "n": int(m.sum()),
            "pred": round(float(p_v[m].mean()), 4),
            "actual": round(float(y_v[m].mean()), 4),
        })
    return {
        "horizon_days": h, "fitted": True,
        "a": round(a, 5), "b": round(b, 5),
        "ci_method": "cluster bootstrap saham (90%, lihat ci_cluster)",
        "n_train": int(len(dd_t)), "n_test": int(len(dd_v)),
        "n_purged": int(len(hd["purged"]["y"])),
        "n_pos_train": int(y_t.sum()), "n_pos_test": int(y_v.sum()),
        "n_episodes_train": _count_episodes(hd["pos"], hd["code"]),
        "n_episodes_test": _count_episodes(hd["test"]["pos"], hd["test"]["code"]),
        "obs_per_episode_train": round(len(dd_t) / max(1, _count_episodes(hd["pos"], hd["code"])), 1),
        "rec_rate": round(float(y_t.mean()), 4),
        "mean_dd": round(float(dd_t.mean()), 4),
        "auc_train": round(auc_train, 4) if auc_train is not None else None,
        "auc_test": round(auc_test, 4) if auc_test is not None else None,
        "brier_test": round(brier_test, 5),
        "calibration": cal,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--out", default=PARAMS_OUT)
    ap.add_argument("--peak-lookback", type=int, default=252)
    ap.add_argument("--embargo-days", type=int, default=5)
    ap.add_argument("--cutoff-frac", type=float, default=0.70)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    d = np.load(args.npz, allow_pickle=True)
    rows, lens = d["rows"], d["lens"]
    dates = d["dates"]
    print(f"Dataset: {len(lens)} kode, peak-lookback={args.peak_lookback}, "
          f"embargo={args.embargo_days}d, cutoff-frac={args.cutoff_frac}, "
          f"n_boot={args.n_boot}", flush=True)

    t0 = time.time()
    all_dates = [np.asarray(dl, dtype="datetime64[D]")
                 for dl in dates if dl is not None and len(dl)]
    cutoff, (glo, ghi) = _global_cutoff_date(all_dates)
    print(f"Rentang global: {glo} -> {ghi}; cutoff 70% = {cutoff}", flush=True)

    collected = _collect_obs(rows, lens, dates, args.peak_lookback)
    print(f"Kumpulkan observasi: {time.time()-t0:.0f}s", flush=True)

    t0 = time.time()
    split = {h: _split_purged(collected[h], cutoff, args.embargo_days)
             for h in HORIZONS}
    print(f"Split+purge: {time.time()-t0:.0f}s", flush=True)

    print("\n" + "=" * 110)
    print(f"{'h':>4} {'n_train':>10} {'n_purged':>9} {'n_test':>9} {'ep_tr':>7} "
          f"{'ep_te':>7} {'rec%':>7} {'a':>9} {'b':>9} {'AUC_tr':>8} {'AUC_te':>8} {'Brier_te':>9}")
    print("-" * 110)
    fitted = []
    for h in HORIZONS:
        r = _fit_horizon(split[h], h)
        fitted.append(r)
        if r["fitted"]:
            print(f"{h:>4} {r['n_train']:>10,} {r['n_purged']:>9,} {r['n_test']:>9,} "
                  f"{r['n_episodes_train']:>7,} {r['n_episodes_test']:>7,} "
                  f"{r['rec_rate']*100:>6.1f}% {r['a']:>9.4f} {r['b']:>9.4f} "
                  f"{str(r['auc_train']):>8} {str(r['auc_test']):>8} {r['brier_test']:>9.4f}")
        else:
            print(f"{h:>4} n_tr={r['n_train']:,} n_te={r['n_test']:,} (tidak cukup data)")
    print("=" * 110)

    print("\nCluster bootstrap CI (90%) — a_ci / b_ci:")
    t0 = time.time()
    cib = _cluster_bootstrap_ci(split, args.n_boot, args.seed)
    print(f"Bootstrap selesai: {time.time()-t0:.0f}s", flush=True)
    for h in HORIZONS:
        r = cib[str(h)]
        if r.get("fitted"):
            print(f"  h={h:>2} a_ci=({r['a_ci'][0]:.4f}, {r['a_ci'][1]:.4f}) "
                  f"b_ci=({r['b_ci'][0]:.4f}, {r['b_ci'][1]:.4f}) "
                  f"[{r['n_boot']} resamples]")
        else:
            print(f"  h={h:>2} bootstrap tidak fit ({r.get('n_boot_done', 0)} ok)")

    print("\nKalibrasi OOS (TEST bersih) h=21:")
    for r in fitted:
        if r["fitted"] and r["horizon_days"] == 21:
            for c in r["calibration"]:
                print(f"  dd {c['bucket']:12s} n={c['n']:>7,} "
                      f"pred={c['pred']:.3f} actual={c['actual']:.3f} "
                      f"dev={c['actual']-c['pred']:+.3f}")

    if args.no_save:
        return

    params = {
        "model": "logistic_drawdown",
        "target": "prior_peak",
        "target_definition": "max(close) trailing peak_lookback hari trading",
        "peak_lookback_days": args.peak_lookback,
        "dd_fraction": "1 - close/peak, clamp [0, 0.85]",
        "basis_harga": "raw close/high (konsisten jalur produksi)",
        "horizons": {str(r["horizon_days"]): r for r in fitted},
        "ci_cluster": cib,
        "base_rate_table": build_base_rate_table(rows, lens, args.peak_lookback),
        "train_frac": args.cutoff_frac,
        "embargo_days": args.embargo_days,
        "split": ("global chronological (cutoff 70 persen tanggal) + purge label-overlap "
                  "+ embargo {} hari kalender".format(args.embargo_days)),
        "split_info": {
            "method": "date-based, bukan posisi bar",
            "cutoff_date": str(cutoff),
            "global_range": [str(glo), str(ghi)],
            "embargo_days": args.embargo_days,
            "purge_rule": "buang obs train yg date_s < cutoff <= date_e",
        },
        "ci_bootstrap": None,  # legacy scale dihapus — pakai ci_cluster
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": os.path.basename(args.npz),
        "n_codes": int(len(lens)),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {args.out}")


if __name__ == "__main__":
    sys.exit(main())