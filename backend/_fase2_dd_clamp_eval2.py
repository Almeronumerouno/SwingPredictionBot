"""F2.6 (fix): sensitivitas clamp — fit manual di dd MENTAH per skenario clamp."""
import json
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

from _calibrate_recovery_model import HORIZONS
from _fase2_temporal_split import (DATA_DIR, NPZ_PATH, _global_cutoff,
                                   _load_npz)

WINDOW = 252
TRAIN_FRAC = 0.70
EMBARGO = 90
H = 21


def trailing_peak(close, window):
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(close)
    out = np.full(n, np.nan)
    if n < window:
        return out
    out[window - 1:] = sliding_window_view(close, window).max(axis=1)
    return out


codes, rows, lens, dates = _load_npz(NPZ_PATH)
cutoff = _global_cutoff(dates, TRAIN_FRAC)
emb = cutoff + np.timedelta64(EMBARGO, "D")

# kumpulkan dd MENTAH (tanpa clamp) + y utk h=21
dd_raw_all, y_all, tr_all, te_all = [], [], [], []
for c in range(len(lens)):
    m = int(lens[c])
    if m < WINDOW + max(HORIZONS) + 5:
        continue
    dt = np.asarray(dates[c], dtype="datetime64[D]") if len(dates[c]) == m else None
    if dt is None:
        continue
    close = rows[c, :m, 3]
    high = rows[c, :m, 1]
    peak = trailing_peak(close, WINDOW)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = 1.0 - close / peak
    valid = np.isfinite(dd) & (dd > 0)
    idx = np.where(valid)[0]
    if len(idx) == 0:
        continue
    end = idx + 1 + H
    ok = end <= m - 1
    i_h = idx[ok]
    if len(i_h) == 0:
        continue
    fmax = np.array([high[i0 + 1:i0 + H + 1].max() for i0 in i_h])
    y = (fmax >= peak[i_h]).astype(float)
    dts = dt[i_h]
    dte = dt[i_h + H]
    tr = (dts <= cutoff) & (dte <= cutoff)
    te = dts > emb
    if tr.any():
        dd_raw_all.append(dd[i_h][tr])
        y_all.append(y[tr])
        tr_all.append(np.ones(int(tr.sum()), dtype=bool))
    if te.any():
        dd_raw_all.append(dd[i_h][te])
        y_all.append(y[te])
        tr_all.append(np.zeros(int(te.sum()), dtype=bool))

dd_raw_all = np.concatenate(dd_raw_all)
y_all = np.concatenate(y_all)
tr_all = np.concatenate(tr_all)
print(f"obs train={int(tr_all.sum()):,} test={int((~tr_all).sum()):,}")
print(f"dd mentah max={dd_raw_all.max():.3f} | n > 0.85: "
      f"{int((dd_raw_all > 0.85).sum())} ({100.0*(dd_raw_all > 0.85).mean():.3f}%)")

results = {}
for clamp_max in (0.85, 0.95, 1.00):
    dd = np.clip(dd_raw_all, 0.0, clamp_max)
    clf = LogisticRegression(penalty=None, max_iter=5000)
    clf.fit(dd[tr_all].reshape(-1, 1), y_all[tr_all])
    p_te = clf.predict_proba(dd[~tr_all].reshape(-1, 1))[:, 1]
    auc = roc_auc_score(y_all[~tr_all], p_te)
    brier = float(brier_score_loss(y_all[~tr_all], p_te))
    a, b = float(clf.intercept_[0]), float(clf.coef_[0][0])
    results[str(clamp_max)] = {"a": round(a, 5), "b": round(b, 5),
                               "auc_te": round(auc, 4),
                               "brier_te": round(brier, 5)}
    print(f"clamp {clamp_max:.2f}: a={a:.5f} b={b:.5f} AUC_te={auc:.4f} "
          f"Brier_te={brier:.5f}")

with open(f"{DATA_DIR}/recovery_dd_clamp_eval.json", "w", encoding="utf-8") as f:
    json.dump({"h": H, "clamp_results": results,
               "n_clamped_0_85": int((dd_raw_all > 0.85).sum())}, f, indent=2)
print("Tersimpan: data/recovery_dd_clamp_eval.json")
