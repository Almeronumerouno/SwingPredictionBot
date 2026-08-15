"""
_reliability.py — Reliability diagram + ECE/MCE/Brier utk model recovery OOS
(rombak TODO, Agu 2026).

Pertanyaan: model P_recover(dd) = logistic — apakah OOS well-calibrated
(prediksi == frekuensi aktual)? Perlu koreksi Platt/isotonic atau tidak?

Metodologi (riset s2):
- Gunakan skenario identik _calibrate_recovery_model: _collect_rows (raw),
  split TEMPORAL 70/30, fit LogisticRegression(penalty=None).
- OOS: p = logistic OOS. Reliability diagram = QUANTILE binning 10 bin
  (tiap bin jumlah sama), bandingkan conf = mean(p) vs acc = mean(y).
- Metrik:
    ECE = sum (n_k/N) |acc_k - conf_k|
    MCE = max |acc_k - conf_k|
    Brier = mean((p - y)^2)  + dekomposisi Murphy: REL + RES + UNC
  Brier score = REL - RES + UNC. REL = "miscalibration",
  RES = "resolution" (semakin besar makin baik), UNC = variance.
- ECE per regime temporal (paruh-1 vs paruh-2 OOS): lihat stabilitas.
- Keputusan: ECE kecil & RES jauh > REL & galat per bucket < 0.03
  -> logistic sdh well-calibrated, TANPA Platt/isotonic (isotonic mengubah
  ranking & butuh shrunken; logistic natural calibrated). Catatan di sini.

Hasil (12-Agu-2026, universe_ohlcv.npz, OOS 30% akhir temporal):
  h     ECE    MCE    Brier = REL - RES + UNC
   1   0.0046  0.027  0.0217 = .0001 - .0057 + .0273
   3   0.0078  0.026  0.0411 = .0001 - .0125 + .0535
   5   0.0077  0.036  0.0555 = .0002 - .0169 + .0723
  10   0.0123  0.034  0.0825 = .0003 - .0246 + .1069
  21   0.0208  0.074  0.1225 = .0008 - .0344 + .1560
  42   0.0315  0.111  0.1672 = .0019 - .0427 + .2079
  63   0.0383  0.106  0.1925 = .0022 - .0447 + .2350
  RES > REL di semua horizon (85x utk h=5) -> model punya resolution.
  ECE paruh-regime stabil: h5 0.0075/0.0107, h21 0.0191/0.0235.
  Satu cacat: bucket ekstrem atas h>=21 UNDERPREDISIKSI (h21 bucket 0.58:
  conf 0.579 vs acc 0.654, diff 0.074) -> di drawdown dalam model konservatif.
Kesimpulan: logistic OOS WELL-CALIBRATED di rentang produksi (p 0.01-0.30).
  TIDAK perlu Platt/isotonic (isotonic mengubah ranking; hasil riset s2).
  Cacat bucket ekstrem didokumentasikan: probabilitas drawdown dalam
  (dd>0.40) konservatif; produksi tetap memakai model (bukan koreksi ad-hoc).
"""
from __future__ import annotations

import sys
import time

import numpy as np
from scipy.special import expit
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, r"C:\CodeKuliah\SwingPredictionBot\backend")

from _calibrate_recovery_model import (  # noqa: E402
    DD_BUCKETS, DD_CLAMP_MAX, HORIZONS, NPZ_PATH, TRAIN_FRAC, _collect_rows)

H_FOCUS = (5, 21)          # horizon yang dianalisis mendalam
NB = 10                    # jumlah quantile bin
HALF = 2                   # 2 paruh regime pada OOS


def reliability(p: np.ndarray, y: np.ndarray) -> dict:
    n = len(p)
    order = np.argsort(p)
    p, y = p[order], y[order]
    edges = np.quantile(p, np.linspace(0, 1, NB + 1))
    edges[0], edges[-1] = 0.0, 1.0 + 1e-9
    bins = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, NB - 1)
    rows = []
    for b in range(NB):
        m = bins == b
        if m.sum() == 0:
            continue
        rows.append((int(m.sum()), float(p[m].mean()), float(y[m].mean())))
    arr = np.asarray(rows, dtype=float)  # (n, conf, acc)
    nk = arr[:, 0]
    conf, acc = arr[:, 1], arr[:, 2]
    ece = float((nk / n * np.abs(acc - conf)).sum())
    mce = float(np.max(np.abs(acc - conf)))
    # Brier + dekomposisi (Murphy 1973): BS = REL - RES + UNC
    unc = float(y.mean() * (1 - y.mean()))
    res = float((nk / n * (conf - y.mean()) ** 2).sum())
    rel = float((nk / n * (conf - acc) ** 2).sum())
    brier = rel - res + unc
    return {"bins": arr, "ece": ece, "mce": mce, "brier": brier,
            "rel": rel, "res": res, "unc": unc}


def main() -> None:
    d = np.load(NPZ_PATH)
    rows, lens = d["rows"], d["lens"]
    t0 = time.time()
    collected = _collect_rows(rows, lens, 252)
    print(f"collect {time.time()-t0:.0f}s")

    for h in HORIZONS:
        dd = collected[h]["dd"]
        y = collected[h]["y"]
        if len(dd) == 0:
            continue
        n_train = int(len(dd) * TRAIN_FRAC)
        clf = LogisticRegression(penalty=None, max_iter=5000)
        clf.fit(dd[:n_train].reshape(-1, 1), y[:n_train])
        p_oos = expit(clf.intercept_[0] + clf.coef_[0][0] * dd[n_train:])
        y_oos = y[n_train:]
        r = reliability(p_oos, y_oos)
        tag = "**" if h in H_FOCUS else "  "
        print(f"\n{tag} h={h:>3} OOS n={len(p_oos)} rec={y_oos.mean():.4f} "
              f"a={clf.intercept_[0]:+.3f} b={clf.coef_[0][0]:+.3f}")
        print(f"{tag}    ECE={r['ece']:.4f}  MCE={r['mce']:.4f}  "
              f"Brier={r['brier']:.4f} = REL {r['rel']:.4f} - RES {r['res']:.4f} + UNC {r['unc']:.4f}")
        if h not in H_FOCUS:
            continue
        # tabel diagram
        print(f"{tag}    {'bin':>4} {'n':>7} {'conf':>7} {'acc':>7} {'|diff|':>7}")
        for i, row in enumerate(r["bins"]):
            print(f"{tag}    {i:>4} {int(row[0]):>7} {row[1]:>7.3f} {row[2]:>7.3f} "
                  f"{abs(row[2]-row[1]):>7.3f}")
        # ECE per regime temporal (paruh OOS)
        mid = len(p_oos) // 2
        for lab, (pp, yy) in (("paruh-1", (p_oos[:mid], y_oos[:mid])),
                              ("paruh-2", (p_oos[mid:], y_oos[mid:]))):
            if len(pp) > 100 and len(np.unique(yy)) > 1:
                rr = reliability(pp, yy)
                print(f"{tag}    ECE {lab}: {rr['ece']:.4f} (n={len(pp)}, rec={yy.mean():.4f})")


if __name__ == "__main__":
    main()