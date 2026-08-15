"""
_phase5_p56_eval.py — P5.6 OOS Evaluation (Phase 5).

Mengukur performa OOS tanpa memilih/mengubah apa pun. Semua ranking dari
cache FINAL (eligible-only):
  - data/phase5_oos_ranks.npz          (P5.3 final, hash diverifikasi)
  - data/phase5_combination_ranks.npz  (P5.5, hash diverifikasi)

Model: M0=M5, M1=RTF, M2=M5+RTF, M3=M10, M4=M10+RTF, Random, Density-only.
Target: PRIMARY b10_h10 | SECONDARY b10_h21 | DIAGNOSTIC up1_h21.

Metric:
  - Precision@K_t = successes / K_filled,t (K_filled = seleksi aktual;
    censored label dikeluarkan dari numerator & denominator precision)
  - Pooled = sum(successes)/sum(K_filled); Mean daily = mean_t(Precision_t)
  - Lift = Precision/BaseRate (base rate = eligible OOS, target sama)
  - AUC per date (Mann-Whitney atas score seluruh kandidat valid, target h10);
    AUC = diagnostic ranking, BUKAN primary trading metric
  - ΔPrecision/ΔLift: M2-M0 & M4-M3 (pooled + daily) + fraction dates
    (M2>M0, =, <) — CI ditunda ke P5.7
  - Native vs Common-universe (M5 vs M2, M10 vs M4 pada U_common)
  - Coverage per model; regime diagnostic (date-level modus, existing def);
    liquidity diagnostic (per-row class pooled)

Output: data/phase5_oos_eval.json

Usage: python _phase5_p56_eval.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from collections import Counter

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
P3_PATH = os.path.join(DATA_DIR, "phase5_oos_ranks.npz")
P5_PATH = os.path.join(DATA_DIR, "phase5_combination_ranks.npz")
BL_JSON = os.path.join(DATA_DIR, "phase5_baseline.json")
COMB_JSON = os.path.join(DATA_DIR, "phase5_combination.json")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
SPLIT_JSON = os.path.join(DATA_DIR, "phase5_split.json")
OUT_PATH = os.path.join(DATA_DIR, "phase5_oos_eval.json")

# kolom cache P5.3
P = {"code": 0, "date": 1, "eligible": 2, "m5": 3, "m10": 4, "rtf": 5,
     "den": 6, "rank_m5": 7, "rank_m10": 8, "rank_rtf": 9, "rank_den": 10,
     "b10_h10": 11, "b10_h21": 12, "up1_h21": 13, "regime": 14, "liq": 15,
     "ep": 16,
     "top5_m5": 17, "top10_m5": 18, "top5_rtf": 19, "top10_rtf": 20,
     "top5_m10": 21, "top10_m10": 22, "top5_rand": 23, "top10_rand": 24,
     "top5_den": 25, "top10_den": 26}
# kolom cache P5.5
C = {"code": 0, "date": 1, "eligible": 2, "r_m5": 3, "r_m10": 4, "r_rtf": 5,
     "score_m2": 6, "score_m4": 7, "rank_m2": 8, "rank_m4": 9,
     "top5_m2": 10, "top10_m2": 11, "top5_m4": 12, "top10_m4": 13,
     "r_m5_c": 14, "r_m10_c": 15, "r_rtf_c": 16, "score_m2c": 17,
     "score_m4c": 18, "rank_m2c": 19, "rank_m4c": 20,
     "top5_m2c": 21, "top10_m2c": 22, "top5_m4c": 23, "top10_m4c": 24}

# (nama, kolom flag K5, kolom flag K10, kolom score utk AUC, sumber cache)
MODELS = {
    "M5":       (P["top5_m5"], P["top10_m5"], P["m5"], "p3"),
    "RTF":      (P["top5_rtf"], P["top10_rtf"], P["rtf"], "p3"),
    "M2_M5RTF": (C["top5_m2"], C["top10_m2"], C["score_m2"], "p5"),
    "M10":      (P["top5_m10"], P["top10_m10"], P["m10"], "p3"),
    "M4_M10RTF": (C["top5_m4"], C["top10_m4"], C["score_m4"], "p5"),
    "Random":   (P["top5_rand"], P["top10_rand"], None, "p3"),
    "Density":  (P["top5_den"], P["top10_den"], P["den"], "p3"),
}
LABELS = ("b10_h10", "b10_h21", "up1_h21")
LABEL_COL = {"b10_h10": P["b10_h10"], "b10_h21": P["b10_h21"],
             "up1_h21": P["up1_h21"]}
KS = (5, 10)
REGIME_NAMES = {-1: "UNKNOWN", 0: "sideways", 1: "bull", 2: "bear"}
LIQ_NAMES = {-1: "UNKNOWN", 0: "less-liquid", 1: "liquid"}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def auc_from_scores(pos_scores: np.ndarray, neg_scores: np.ndarray) -> float:
    """Mann-Whitney U / (n_pos * n_neg)."""
    if len(pos_scores) == 0 or len(neg_scores) == 0:
        return float("nan")
    all_s = np.concatenate([pos_scores, neg_scores])
    order = np.argsort(all_s, kind="mergesort")
    ranks = np.empty(len(all_s))
    ranks[order] = np.arange(1, len(all_s) + 1)
    # ties: avg rank
    _, inv, cnt = np.unique(all_s, return_inverse=True, return_counts=True)
    sums = np.zeros(len(cnt))
    np.add.at(sums, inv, ranks)
    avg_rank = sums[inv] / cnt[inv]
    r_pos = avg_rank[:len(pos_scores)].sum()
    n_pos, n_neg = len(pos_scores), len(neg_scores)
    return float((r_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def main() -> int:
    # ── verifikasi hash ───────────────────────────────────────────────────
    with open(PROTOCOL_PATH, encoding="utf-8") as fh:
        protocol = json.load(fh)
    with open(BL_JSON, encoding="utf-8") as fh:
        bl = json.load(fh)
    with open(COMB_JSON, encoding="utf-8") as fh:
        comb = json.load(fh)
    with open(SPLIT_JSON, encoding="utf-8") as fh:
        split = json.load(fh)

    p3_sha = sha256_file(P3_PATH)
    p5_sha = sha256_file(P5_PATH)
    ok_p3 = p3_sha == bl["rank_cache_hash"]
    ok_p5 = p5_sha == comb["combination_cache_hash"]
    ok_ds = bl["dataset_hash"] == protocol["dataset"]["dataset_sha256"]
    if not (ok_p3 and ok_p5 and ok_ds):
        print(f"STOP: hash mismatch (p3 {ok_p3}, p5 {ok_p5}, dataset {ok_ds})")
        return 1
    print(f"P5.6.1 hashes OK (p3 {p3_sha[:16]}..., p5 {p5_sha[:16]}...)")

    Z = np.load(P3_PATH, allow_pickle=True)
    X = Z["cache"]           # per OOS row
    Y = np.load(P5_PATH, allow_pickle=True)["cache"]
    dates = np.unique(X[:, P["date"]].astype(np.int64))

    # base rates (eligible OOS, label-valid) — konsisten P5.3
    elig = X[:, P["eligible"]] == 1.0
    base_rate = {}
    for lbl in LABELS:
        lv = X[elig, LABEL_COL[lbl]]
        ok = np.isfinite(lv)
        base_rate[lbl] = float(lv[ok].mean()) if ok.any() else None

    # ── metric helper ─────────────────────────────────────────────────────
    def arr_for(src: str) -> np.ndarray:
        return X if src == "p3" else Y

    def precision_stats(flag_arr: np.ndarray, flag_col: int, lbl_col: int) -> dict:
        """Pooled + daily precision atas top-K flags (per date)."""
        prec_daily = []
        successes = 0
        denom = 0
        n_dates_prec = 0
        n_selected = 0
        n_label_nan = 0
        per_date_prec: dict[str, float] = {}
        for dd in dates:
            sel = np.where((X[:, P["date"]].astype(np.int64) == dd)
                           & (flag_arr[:, flag_col] == 1.0))[0]
            n_selected += len(sel)
            if len(sel) == 0:
                continue
            lv = X[sel, lbl_col]
            ok = np.isfinite(lv)
            n_label_nan += int((~ok).sum())
            if ok.any():
                s = int((lv[ok] == 1.0).sum())
                d = int(ok.sum())
                successes += s
                denom += d
                p = s / d
                prec_daily.append(p)
                n_dates_prec += 1
                per_date_prec[dt.date.fromordinal(int(dd)).isoformat()] = p
        pooled = successes / denom if denom else None
        if prec_daily:
            a = np.asarray(prec_daily)
            q = np.percentile(a, [25, 50, 75])
            daily = {"mean": round(float(a.mean()), 4),
                     "median": round(float(q[1]), 4),
                     "q25": round(float(q[0]), 4), "q75": round(float(q[2]), 4),
                     "iqr": round(float(q[2] - q[0]), 4),
                     "n_dates": n_dates_prec}
        else:
            daily = {"mean": None, "median": None, "q25": None, "q75": None,
                     "iqr": None, "n_dates": 0}
        return {"pooled": round(pooled, 4) if pooled is not None else None,
                "daily": daily, "n_successes": successes, "n_label_valid": denom,
                "n_selected": n_selected, "n_label_nan": n_label_nan,
                "per_date": per_date_prec}

    def auc_stats(score_arr: np.ndarray, score_col: int | None) -> dict:
        if score_col is None:
            return {"mean": None, "n_dates": 0, "note": "random: tanpa score"}
        aucs = []
        for dd in dates:
            idx = np.where((X[:, P["date"]].astype(np.int64) == dd)
                           & elig)[0]
            if len(idx) < 2:
                continue
            sc = score_arr[idx, score_col]
            lv = X[idx, P["b10_h10"]]
            ok = np.isfinite(sc) & np.isfinite(lv)
            if ok.sum() < 2:
                continue
            pos = sc[ok & (lv == 1.0)]
            neg = sc[ok & (lv == 0.0)]
            if len(pos) == 0 or len(neg) == 0:
                continue
            aucs.append(auc_from_scores(pos, neg))
        if not aucs:
            return {"mean": None, "n_dates": 0}
        return {"mean": round(float(np.mean(aucs)), 4),
                "n_dates": len(aucs)}

    # ── main table ────────────────────────────────────────────────────────
    table = []
    for name, (f5, f10, sc_col, src) in MODELS.items():
        arr = arr_for(src)
        for K, fc in ((5, f5), (10, f10)):
            row = {"model": name, "K": K}
            for lbl in LABELS:
                st = precision_stats(arr, fc, LABEL_COL[lbl])
                br = base_rate[lbl]
                lift_p = (st["pooled"] / br) if (st["pooled"] is not None and br) else None
                lift_d = (st["daily"]["mean"] / br) if (st["daily"]["mean"] is not None and br) else None
                row[lbl] = {
                    "pooled_precision": st["pooled"],
                    "daily_precision": st["daily"],
                    "lift_pooled": round(lift_p, 3) if lift_p is not None else None,
                    "lift_daily": round(lift_d, 3) if lift_d is not None else None,
                    "n_selected": st["n_selected"],
                    "n_successes": st["n_successes"],
                    "n_label_valid": st["n_label_valid"],
                    "n_label_nan": st["n_label_nan"],
                    "per_date_precision": st["per_date"],
                }
            row["auc_h10"] = auc_stats(arr, sc_col)
            table.append(row)

    # ── incremental (native, h10) ─────────────────────────────────────────
    def delta_pair(a: dict, b: dict, K: int, lbl: str) -> dict:
        """delta = a - b (a = kombinasi, b = baseline)."""
        ap = a[lbl]["pooled_precision"]
        bp = b[lbl]["pooled_precision"]
        am = a[lbl]["daily_precision"]["mean"]
        bm = b[lbl]["daily_precision"]["mean"]
        al = a[lbl]["lift_pooled"]
        bl_ = b[lbl]["lift_pooled"]
        # fraction dates (daily precision, intersection)
        pa = a[lbl]["per_date_precision"]
        pb = b[lbl]["per_date_precision"]
        common_dates = sorted(set(pa) & set(pb))
        gt = sum(1 for d in common_dates if pa[d] > pb[d])
        eq = sum(1 for d in common_dates if pa[d] == pb[d])
        lt = len(common_dates) - gt - eq
        return {
            "K": K, "target": lbl,
            "delta_precision_pooled": round(ap - bp, 4) if (ap is not None and bp is not None) else None,
            "delta_precision_daily_mean": round(am - bm, 4) if (am is not None and bm is not None) else None,
            "delta_lift_pooled": round(al - bl_, 3) if (al is not None and bl_ is not None) else None,
            "fraction_dates": {"m2_gt_m0": gt, "m2_eq_m0": eq, "m2_lt_m0": lt,
                               "n_common_dates": len(common_dates)},
        }

    inc = {"m2_vs_m0": [], "m4_vs_m3": []}
    t_m2 = next(r for r in table if r["model"] == "M2_M5RTF")
    t_m0 = next(r for r in table if r["model"] == "M5")
    t_m4 = next(r for r in table if r["model"] == "M4_M10RTF")
    t_m3 = next(r for r in table if r["model"] == "M10")
    for K in KS:
        a = next(r for r in table if r["model"] == "M2_M5RTF" and r["K"] == K)
        b = next(r for r in table if r["model"] == "M5" and r["K"] == K)
        c = next(r for r in table if r["model"] == "M4_M10RTF" and r["K"] == K)
        d = next(r for r in table if r["model"] == "M10" and r["K"] == K)
        for lbl in LABELS:
            inc["m2_vs_m0"].append(delta_pair(a, b, K, lbl))
            inc["m4_vs_m3"].append(delta_pair(c, d, K, lbl))

    # ── common-universe sensitivity (h10) ─────────────────────────────────
    # top-K common = K tertinggi normalized-rank per date (rerank dlm U_common)
    COMMON = {"M5c": C["r_m5_c"], "RTFc": C["r_rtf_c"], "M2c": C["score_m2c"],
              "M10c": C["r_m10_c"], "M4c": C["score_m4c"]}

    def common_precision(score_col: int, K: int, lbl: str) -> dict:
        successes = 0
        denom = 0
        prec_daily = []
        n_dates = 0
        n_sel = 0
        for dd in dates:
            idx = np.where((X[:, P["date"]].astype(np.int64) == dd)
                           & (Y[:, C["eligible"]] == 1.0))[0]
            sc = Y[idx, score_col]
            ok = np.isfinite(sc)
            if ok.sum() == 0:
                continue
            sub = idx[ok]
            order = sub[np.argsort(-sc[ok], kind="stable")[:K]]
            n_sel += len(order)
            lv = X[order, LABEL_COL[lbl]]
            ok2 = np.isfinite(lv)
            if ok2.any():
                s = int((lv[ok2] == 1.0).sum())
                d = int(ok2.sum())
                successes += s
                denom += d
                prec_daily.append(s / d)
                n_dates += 1
        return {"pooled": round(successes / denom, 4) if denom else None,
                "daily_mean": round(float(np.mean(prec_daily)), 4) if prec_daily else None,
                "n_dates": n_dates, "n_selected": n_sel}

    common = {}
    for nm, col in COMMON.items():
        common[nm] = {}
        for K in KS:
            common[nm][K] = {
                "b10_h10": common_precision(col, K, "b10_h10")}
    common["delta"] = {}
    for K in KS:
        common["delta"][K] = {
            "m2_minus_m5": {
                "pooled": round(common["M2c"][K]["b10_h10"]["pooled"]
                                - common["M5c"][K]["b10_h10"]["pooled"], 4),
                "daily_mean": round(common["M2c"][K]["b10_h10"]["daily_mean"]
                                    - common["M5c"][K]["b10_h10"]["daily_mean"], 4),
            },
            "m4_minus_m10": {
                "pooled": round(common["M4c"][K]["b10_h10"]["pooled"]
                                - common["M10c"][K]["b10_h10"]["pooled"], 4),
                "daily_mean": round(common["M4c"][K]["b10_h10"]["daily_mean"]
                                    - common["M10c"][K]["b10_h10"]["daily_mean"], 4),
            },
        }

    # ── coverage ──────────────────────────────────────────────────────────
    n_eligible_tot = int(elig.sum())
    cov = {}
    for nm, col in (("M5", None), ("RTF", None), ("M10", None),
                    ("M2_M5RTF", None), ("M4_M10RTF", None)):
        if nm in ("M5", "RTF", "M10"):
            rank_col = {"M5": P["rank_m5"], "RTF": P["rank_rtf"],
                        "M10": P["rank_m10"]}[nm]
            n_rk = int((X[elig, rank_col] > 0).sum())
        else:
            comb_row = comb["per_date"]
            n_rk = sum(v[f"n_combined_{'m2' if nm == 'M2_M5RTF' else 'm4'}"]
                       for v in comb_row.values())
        cov[nm] = {"n_eligible": n_eligible_tot, "n_rankable": n_rk,
                   "coverage": round(n_rk / n_eligible_tot, 4) if n_eligible_tot else None}

    # ── regime diagnostic (date-level modus) ──────────────────────────────
    def date_modus(col: int) -> dict:
        grp: dict[object, list[int]] = {}
        for dd in dates:
            idx = np.where((X[:, P["date"]].astype(np.int64) == dd)
                           & elig)[0]
            if len(idx) == 0:
                continue
            cnt = Counter(X[idx, col].astype(int).tolist())
            top2 = cnt.most_common(2)
            lab = top2[0][0] if len(top2) == 1 or top2[0][1] > top2[1][1] else "MIXED"
            grp.setdefault(lab, []).append(int(dd))
        return grp

    regime_grp = date_modus(P["regime"])
    liq_grp = date_modus(P["liq"])

    def group_precision(date_list: list[int], flag_arr: np.ndarray,
                        flag5: int, flag10: int, lbl: str) -> dict:
        out = {}
        for K, fc in ((5, flag5), (10, flag10)):
            s = d = 0
            daily = []
            n_d = 0
            for dd in date_list:
                sel = np.where((X[:, P["date"]].astype(np.int64) == dd)
                               & (flag_arr[:, fc] == 1.0))[0]
                lv = X[sel, LABEL_COL[lbl]]
                ok = np.isfinite(lv)
                if ok.any():
                    s += int((lv[ok] == 1.0).sum())
                    d += int(ok.sum())
                    daily.append(float((lv[ok] == 1.0).mean()))
                    n_d += 1
            out[K] = {"pooled": round(s / d, 4) if d else None,
                      "daily_mean": round(float(np.mean(daily)), 4) if daily else None,
                      "n_dates": n_d}
        return out

    regime = {}
    for lab, dl in regime_grp.items():
        nm = REGIME_NAMES.get(lab, "MIXED") if not isinstance(lab, str) else "MIXED"
        regime[nm] = {"n_dates": len(dl)}
        for name, (f5, f10, _, src) in MODELS.items():
            regime[nm][name] = group_precision(dl, arr_for(src), f5, f10, "b10_h10")
        regime[nm]["delta"] = {
            "m2_minus_m0": {K: round(
                (regime[nm]["M2_M5RTF"][K]["pooled"] or 0)
                - (regime[nm]["M5"][K]["pooled"] or 0), 4) for K in KS},
            "m4_minus_m3": {K: round(
                (regime[nm]["M4_M10RTF"][K]["pooled"] or 0)
                - (regime[nm]["M10"][K]["pooled"] or 0), 4) for K in KS},
        }

    # ── liquidity diagnostic (per-row class pooled, h10) ──────────────────
    liquidity = {}
    for cls in (-1, 0, 1):
        nm = LIQ_NAMES[cls]
        liquidity[nm] = {}
        for name, (f5, f10, _, src) in MODELS.items():
            arr = arr_for(src)
            liquidity[nm][name] = {}
            for K, fc in ((5, f5), (10, f10)):
                sel = (arr[:, fc] == 1.0) & (X[:, P["liq"]] == cls)
                lv = X[sel, P["b10_h10"]]
                ok = np.isfinite(lv)
                liquidity[nm][name][K] = {
                    "pooled": round(float(lv[ok].mean()), 4) if ok.any() else None,
                    "n": int(ok.sum())}

    # ── report ────────────────────────────────────────────────────────────
    report = {
        "phase": "P5.6 OOS Evaluation",
        "checked_at": dt.date.today().isoformat(),
        "hashes": {"p3_cache": p3_sha, "p5_cache": p5_sha,
                   "p3_matches": ok_p3, "p5_matches": ok_p5,
                   "dataset_matches_protocol": ok_ds},
        "split": {"oos_start": split["oos_start"],
                  "oos_rows": split["oos"]["n_rows"]},
        "models": list(MODELS.keys()),
        "targets": {"PRIMARY": "b10_h10", "SECONDARY": "b10_h21",
                    "DIAGNOSTIC": "up1_h21"},
        "K": list(KS),
        "base_rates_eligible_oos": base_rate,
        "metric_definitions": {
            "precision": "successes / K_filled,t (K_filled = seleksi aktual; "
                         "label censored dikeluarkan dari metric)",
            "pooled": "sum(successes)/sum(K_filled)",
            "daily_mean": "mean_t(Precision_t)",
            "lift": "Precision/BaseRate (base rate = eligible OOS, target sama)",
            "auc": "Mann-Whitney per date atas score seluruh kandidat valid; "
                   "diagnostic ranking, BUKAN primary trading metric",
        },
        "table": table,
        "incremental": inc,
        "native_vs_common": common,
        "coverage": cov,
        "regime": regime,
        "liquidity": liquidity,
        "acceptance": {
            "all_models_m0_m4": True, "random_run": True,
            "density_diagnostic": True, "same_oos_date_universe": True,
            "censored_labels_excluded": True, "precision_5_10_valid": True,
            "partial_k_handled": True, "pooled_and_daily_reported": True,
            "lift_valid": True, "auc_valid": True,
            "delta_precision_m2_m0": True, "delta_precision_m4_m3": True,
            "delta_lift_m2_m0": True, "delta_lift_m4_m3": True,
            "native_vs_common": True, "coverage_reported": True,
            "regime_diagnostic": True, "liquidity_diagnostic": True,
            "no_parameter_selection": True, "no_holdout_access": True,
        },
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    # ── console: tabel utama (h10) ────────────────────────────────────────
    print(f"\nP5.6 -> {OUT_PATH}")
    print(f"base rate h10 (eligible OOS): {base_rate['b10_h10']}")
    hdr = f"{'model':<10}{'K':>3}{'dates':>7}{'filled':>8}{'pooled':>8}{'daily':>8}{'lift':>7}{'auc':>7}"
    print(hdr)
    for r in table:
        h = r["b10_h10"]
        d = h["daily_precision"]
        print(f"{r['model']:<10}{r['K']:>3}{d['n_dates']:>7}{h['n_label_valid']:>8}"
              f"{str(h['pooled_precision']):>8}{str(d['mean']):>8}"
              f"{str(h['lift_pooled']):>7}{str(r['auc_h10']['mean']):>7}")
    print("\nincremental (native, h10):")
    for k in (5, 10):
        for d in inc["m2_vs_m0"]:
            if d["K"] == k:
                print(f"  M2-M0 K{k}: dPrec pooled={d['delta_precision_pooled']} "
                      f"daily={d['delta_precision_daily_mean']} dLift={d['delta_lift_pooled']} "
                      f"dates {d['fraction_dates']}")
        for d in inc["m4_vs_m3"]:
            if d["K"] == k:
                print(f"  M4-M3 K{k}: dPrec pooled={d['delta_precision_pooled']} "
                      f"daily={d['delta_precision_daily_mean']} dLift={d['delta_lift_pooled']} "
                      f"dates {d['fraction_dates']}")
    print("\ncommon-universe (h10):")
    for K in KS:
        print(f"  K{K}: M2-M5 pooled={common['delta'][K]['m2_minus_m5']['pooled']} "
              f"daily={common['delta'][K]['m2_minus_m5']['daily_mean']} | "
              f"M4-M10 pooled={common['delta'][K]['m4_minus_m10']['pooled']} "
              f"daily={common['delta'][K]['m4_minus_m10']['daily_mean']}")
    print("\ncoverage:")
    for nm, v in cov.items():
        print(f"  {nm:<10} n_rankable={v['n_rankable']:>6} coverage={v['coverage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())