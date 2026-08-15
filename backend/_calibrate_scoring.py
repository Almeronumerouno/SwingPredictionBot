"""_calibrate_scoring.py — Kalibrasi bobot komponen swing score pakai data (HIGH#1 audit).

Fitur  = komponen [trend, momentum, volume, price_action] per bar (point-in-time).
Label  = forward return HORIZON hari > 0 (close[i+H] > close[i]); label boleh
         pakai masa depan, fitur tidak.
Split  = TEMPORAL per saham: 65% bar pertama train, sisanya test (anti snoop).
Model  = LogisticRegression (sklearn) vs bobot config saat ini (0.15/0.15/0.25/0.45).

Output: AUC-ROC & PR-AUC + AUC@bucket utk (a) bobot config, (b) bobot hasil fit.

    python _calibrate_scoring.py --n 200 --horizon 5
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

import config as CFG
import indicators as ind
from backtest import compute_signals, BacktestConfig
from data_source import local_dataset

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
NPZ_PATH = os.path.join(BACKEND_DIR, "data", "universe_ohlcv.npz")
CONFIG_WEIGHTS = np.array([0.15, 0.15, 0.25, 0.45], dtype=float)
FEATURE_NAMES = ["trend", "momentum", "volume", "price_action"]


def indicator_data(bars: list) -> dict:
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    low = np.array([b.low for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)
    atr_val = ind.atr(high, low, close)
    adx_val = ind.adx(high, low, close)
    ema_val = ind.ema_trend(close)
    return {
        "close": close, "high": high, "low": low,
        "rsi": ind.rsi(close),
        "atr": atr_val,
        "adx": adx_val["adx"],
        "plus_di": adx_val["plus_di"],
        "minus_di": adx_val["minus_di"],
        "ema_fast": ema_val["ema_fast"],
        "ema_slow": ema_val["ema_slow"],
        "mfi": ind.mfi(high, low, close, volume),
        "rvol": ind.rvol(volume, period=CFG.RVOL_WINDOW),
        "donchian_upper": ind.donchian_channel(high, low)["upper"],
        "donchian_lower": ind.donchian_channel(high, low)["lower"],
    }


def auc_roc(y: np.ndarray, score: np.ndarray) -> float:
    """AUC-ROC rank-based (Harris, mergesort stabil utk tie)."""
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(y), dtype=float)
    ranks[order] = np.arange(1, len(y) + 1)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def pr_auc(y: np.ndarray, score: np.ndarray) -> float:
    """PR-AUC (average precision) = area di bawah precision-recall curve."""
    order = np.argsort(-score, kind="mergesort")
    ys = y[order]
    n_pos = int(ys.sum())
    if n_pos == 0:
        return float("nan")
    tp = np.cumsum(ys)
    prec = tp / np.arange(1, len(ys) + 1)
    rec = tp / n_pos
    # trapezoid atas recall bins (kecil kemungkinan gap, tp naik bertahap)
    return float(np.trapezoid(prec, rec)) if hasattr(np, "trapezoid") else float(np.trapz(prec, rec))


def collect_samples(n_stocks: int, horizon: int, seed: int = 7, min_bars: int = 300,
                    max_bars: int = 360):
    """Kumpulkan sampel (X, y, split_idx) dari n_stocks saham secara temporal."""
    d = np.load(NPZ_PATH, allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    lens = d["lens"].astype(int)
    ok = np.asarray(d["ok"]).astype(bool)

    rng = np.random.default_rng(seed)
    pool = [i for i, c in enumerate(codes) if ok[i] and lens[i] >= min_bars]
    if len(pool) > n_stocks:
        pool = list(rng.choice(pool, size=n_stocks, replace=False))
    pool.sort()

    X_tr, X_te, y_tr, y_te = [], [], [], []
    n_bars_used = 0
    for i in pool:
        # Pre-slice SATU KALI: akses d["rows"][i] per iterasi di npz DictProxy
        # lambat ~0.25s (re-parse), jadi slice dulu baru pakai.
        rows = d["rows"][i]
        m = int(lens[i])
        if max_bars and m > max_bars:
            rows = rows[m - max_bars:]
            m = max_bars
        nf = int(rows.shape[1])
        bars = [local_dataset.make_local_bar(j, rows, nf) for j in range(m)]
        data = indicator_data(bars)
        close = data["close"]
        sig = compute_signals(data, BacktestConfig())
        comps = np.stack([
            sig["trend"], sig["momentum"], sig["volume"], sig["price_action"],
        ], axis=1)  # (m, 4), NaN kalau komponen belum valid

        valid = np.isfinite(comps).all(axis=1) & (np.arange(m) + horizon < m)
        idx = np.where(valid)[0]
        if len(idx) < 60:
            continue
        X = comps[idx]
        y = (close[idx + horizon] > close[idx]).astype(int)
        cut = int(len(idx) * 0.65)
        X_tr.append(X[:cut]); y_tr.append(y[:cut])
        X_te.append(X[cut:]); y_te.append(y[cut:])
        n_bars_used += len(idx)

    X_tr = np.vstack(X_tr) if X_tr else np.zeros((0, 4))
    X_te = np.vstack(X_te) if X_te else np.zeros((0, 4))
    y_tr = np.concatenate(y_tr) if y_tr else np.zeros(0, dtype=int)
    y_te = np.concatenate(y_te) if y_te else np.zeros(0, dtype=int)
    return X_tr, X_te, y_tr, y_te, len(pool), n_bars_used


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=200, help="jumlah saham (subset acak, seed tetap)")
    ap.add_argument("--horizon", type=int, default=5, help="forward horizon (hari) utk label")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args()

    from sklearn.linear_model import LogisticRegression

    X_tr, X_te, y_tr, y_te, n_stocks, n_bars = collect_samples(args.n, args.horizon)
    print(f"saham: {n_stocks}, bar valid: {n_bars} (train {len(X_tr)}, test {len(X_te)})")

    def auc_pair(X, y):
        if len(y) == 0:
            return float("nan"), float("nan")
        sc_cfg = X @ CONFIG_WEIGHTS
        return auc_roc(y, sc_cfg), pr_auc(y, sc_cfg)

    cfg_tr = auc_pair(X_tr, y_tr)
    cfg_te = auc_pair(X_te, y_te)

    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(X_tr, y_tr)
    p_tr = clf.predict_proba(X_tr)[:, 1]
    p_te = clf.predict_proba(X_te)[:, 1]
    fit_tr = (auc_roc(y_tr, p_tr), pr_auc(y_tr, p_tr))
    fit_te = (auc_roc(y_te, p_te), pr_auc(y_te, p_te))

    coef = clf.coef_[0]
    inter = clf.intercept_[0]

    out = {
        "n_stocks": n_stocks, "n_bars": n_bars, "horizon": args.horizon,
        "base_rate_train": round(float(y_tr.mean()), 4),
        "base_rate_test": round(float(y_te.mean()), 4),
        "config_weights": CONFIG_WEIGHTS.tolist(),
        "config_auc_train": [round(v, 4) for v in cfg_tr],
        "config_auc_test": [round(v, 4) for v in cfg_te],
        "fit_coef": coef.tolist(),
        "fit_intercept": round(inter, 4),
        "fit_auc_train": [round(v, 4) for v in fit_tr],
        "fit_auc_test": [round(v, 4) for v in fit_te],
    }

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print()
        print("=" * 62)
        print("  KALIBRASI BOBOT SCORING (HIGH#1)  horizon=%d" % args.horizon)
        print("=" * 62)
        print(f"  base rate train {out['base_rate_train']:.3f} | test {out['base_rate_test']:.3f}")
        print()
        print("  %-22s %10s %10s" % ("", "AUC-ROC", "PR-AUC"))
        print("  %-22s %10.4f %10.4f" % ("config (heuristik) TRAIN", *cfg_tr))
        print("  %-22s %10.4f %10.4f" % ("config (heuristik) TEST ", *cfg_te))
        print("  %-22s %10.4f %10.4f" % ("logistic fit TRAIN     ", *fit_tr))
        print("  %-22s %10.4f %10.4f" % ("logistic fit TEST      ", *fit_te))
        print()
        print("  koefisien fit:", ", ".join(f"{n}={v:+.3f}" for n, v in zip(FEATURE_NAMES, coef)))
        print(f"  intercept: {inter:+.4f}")
        print()
        if cfg_te[0] >= fit_te[0] - 0.005:
            print("  => Model fit TIDAK mengalahkan bobot heuristik (delta kecil).")
            print("     Pertahankan bobot config; kompleksitas tambahan tidak worth it.")
        else:
            print(f"  => Model fit mengalahkan config: AUC test delta = {fit_te[0] - cfg_te[0]:+.4f}.")
            print("     Pertimbangkan update bobot di regime.py setelah validasi 2x ulang.")


if __name__ == "__main__":
    main()