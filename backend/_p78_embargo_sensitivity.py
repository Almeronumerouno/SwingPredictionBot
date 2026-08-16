"""
_p78_embargo_sensitivity.py — P7.8: Embargo sensitivity (5/10/20 hari).

Cutoff & purge rule FROZEN (global chronological cutoff 70% tanggal =
2025-11-24; purge label-overlap). Hanya embargo kalender divariasikan.
Bandingkan OOS: AUC, Brier, calibration intercept/slope, fitted params,
sample size. Pilihan embargo final = berdasarkan STABILITAS/integrity
statistik, BUKAN profit/performa cherry-picking.

Usage: python _p78_embargo_sensitivity.py [--no-save]
Output: data/phase7_p78_embargo.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

from _phase6_p61_calibrate import (
    HORIZONS,
    _collect_obs,
    _fit_1d,
    _global_cutoff_date,
    _logit_probs,
    _split_purged,
)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
OUT_JSON = os.path.join(DATA_DIR, "phase7_p78_embargo.json")
EMBARGOS = (5, 10, 20)


def _calib_xy(y: np.ndarray, p: np.ndarray) -> tuple[float | None, float | None]:
    if len(y) < 50 or len(np.unique(y)) < 2:
        return None, None
    lo = np.clip(p, 1e-6, 1 - 1e-6)
    clf = LogisticRegression(C=np.inf, max_iter=5000)
    clf.fit(np.log(lo / (1.0 - lo)).reshape(-1, 1), y)
    return float(clf.intercept_[0]), float(clf.coef_[0][0])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    d = np.load(args.npz, allow_pickle=True)
    rows, lens, dates = d["rows"], d["lens"], d["dates"]
    all_dates = [np.asarray(dl, dtype="datetime64[D]")
                 for dl in dates if dl is not None and len(dl)]
    cutoff, (glo, ghi) = _global_cutoff_date(all_dates)
    print(f"Cutoff FROZEN: {cutoff} (rentang {glo}..{ghi})", flush=True)

    collected = _collect_obs(rows, lens, dates, 252)
    print(f"Observasi terkumpul", flush=True)

    # baseline param produksi (embargo 5, P6.1) utk delta
    prod = json.load(open(os.path.join(DATA_DIR, "recovery_model_params.json"),
                          encoding="utf-8"))
    prod_a = {int(h): prod["horizons"][h]["a"] for h in prod["horizons"]}

    results = {}
    for emb in EMBARGOS:
        print(f"\n===== embargo {emb} hari =====", flush=True)
        split = {h: _split_purged(collected[h], cutoff, emb) for h in HORIZONS}
        rh = {}
        for h in HORIZONS:
            hd = split[h]
            clf = _fit_1d(hd["dd"], hd["y"])
            if clf is None:
                rh[str(h)] = {"fitted": False,
                              "n_train": int(len(hd["dd"])),
                              "n_test": int(len(hd["test"]["dd"]))}
                continue
            a, b = float(clf.intercept_[0]), float(clf.coef_[0][0])
            p_t = _logit_probs(a, b, hd["test"]["dd"])
            from sklearn.metrics import roc_auc_score
            auc = (roc_auc_score(hd["test"]["y"], p_t)
                   if len(np.unique(hd["test"]["y"])) > 1 else None)
            brier = float(brier_score_loss(hd["test"]["y"], p_t))
            ci, cs = _calib_xy(hd["test"]["y"], p_t)
            rh[str(h)] = {
                "fitted": True, "a": round(a, 5), "b": round(b, 5),
                "delta_a_vs_prod": round(a - prod_a.get(h, a), 5),
                "delta_b_vs_prod": round(b - prod["horizons"][str(h)]["b"], 5),
                "n_train": int(len(hd["dd"])),
                "n_purged": int(len(hd["purged"]["dd"])),
                "n_test": int(len(hd["test"]["dd"])),
                "auc_test": round(auc, 4) if auc is not None else None,
                "brier_test": round(brier, 5),
                "calib_intercept": round(ci, 4) if ci is not None else None,
                "calib_slope": round(cs, 4) if cs is not None else None,
            }
            print(f"  h={h:>2} n_tr={rh[str(h)]['n_train']:>8,} "
                  f"purge={rh[str(h)]['n_purged']:>8,} "
                  f"n_te={rh[str(h)]['n_test']:>8,} "
                  f"AUC={str(rh[str(h)]['auc_test']):>7} "
                  f"Brier={rh[str(h)]['brier_test']:>8.4f} "
                  f"da={rh[str(h)]['delta_a_vs_prod']:+.4f} "
                  f"db={rh[str(h)]['delta_b_vs_prod']:+.4f} "
                  f"c_int={str(rh[str(h)]['calib_intercept']):>6} "
                  f"c_sl={str(rh[str(h)]['calib_slope']):>6}")
        results[str(emb)] = rh

    # stabilitas: max |delta a/b| dan max delta Brier vs embargo 5
    r5 = results["5"]
    stab = {}
    for emb in (10, 20):
        mda = mdb = mdbrier = 0.0
        for h in HORIZONS:
            if not results[str(emb)][str(h)].get("fitted"):
                continue
            mda = max(mda, abs(results[str(emb)][str(h)]["delta_a_vs_prod"]))
            mdb = max(mdb, abs(results[str(emb)][str(h)]["delta_b_vs_prod"]))
            mdbrier = max(mdbrier, abs(results[str(emb)][str(h)]["brier_test"]
                                       - r5[str(h)]["brier_test"]))
        stab[str(emb)] = {"max_abs_delta_a": round(mda, 5),
                          "max_abs_delta_b": round(mdb, 5),
                          "max_abs_delta_brier": round(mdbrier, 5)}
    print(f"\nStabilitas vs embargo 5: {json.dumps(stab, indent=1)}")

    out = {
        "method": "P7.8 embargo sensitivity — cutoff & purge FROZEN",
        "cutoff_date": str(cutoff),
        "purge_rule": "label-overlap (date_s < cutoff <= date_e), frozen",
        "embargos": [int(e) for e in EMBARGOS],
        "results": results,
        "stability_vs_emb5": stab,
        "rekomendasi": ("pilih embargo berdasarkan stabilitas parameter/calibration "
                        "& integrity statistik, bukan profit; default produksi 5 hari "
                        "dipertahankan bila 10/20 tidak memberi perbaikan stabilitas "
                        "material (lihat stability_vs_emb5)"),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not args.no_save:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nTersimpan: {args.out}")
    else:
        print("\n(no-save)")


if __name__ == "__main__":
    sys.exit(main())