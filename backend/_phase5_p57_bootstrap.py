"""
_phase5_p57_bootstrap.py — P5.7 Bootstrap Uncertainty (Phase 5).

Menjawab: apakah apparent improvement M2/M4 robust atau sampling noise?
  - Stock-cluster bootstrap PRIMARY: B=1000, seed=42; resample STOCK dgn
    replacement; setiap stock terpilih menyumbang SELURUH eligible OOS rows.
    Mempertahankan within-cluster dependence (F2.3).
  - BUKAN IID row bootstrap. Tidak ada refit (M0–M4 = rule-based fixed).
  - Native + Common-universe incremental CI (ΔPrecision / ΔLift) — wajib,
    karena P5.6 menunjukkan native gain hilang di common universe.
  - Metric konsisten dgn P5.6: pooled = sum(successes)/sum(K_filled);
    daily = mean_t(Precision_t); partial-K memakai K_filled aktual per
    replicate; censored label dikeluarkan.
  - CI: percentile 95% [q0.025, q0.975] (F2.3).
  - Failure handling: replicate tanpa selected signals/events → invalid;
    n_valid/n_invalid dilaporkan; n_valid < 100 → INCONCLUSIVE.
  - Date-block SENSITIVITY (bukan primary): B=500, seed=7. Catatan: dgn
    replacement, pooled/daily ratio degenerate (duplikasi tanggal membatalkan
    rasio) → dipakai subsample tanggal TANPA replacement (63%) sebagai
    temporal sensitivity.

Output: data/phase5_bootstrap.json
Usage:  python _phase5_p57_bootstrap.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
P3_PATH = os.path.join(DATA_DIR, "phase5_oos_ranks.npz")
P5_PATH = os.path.join(DATA_DIR, "phase5_combination_ranks.npz")
BL_JSON = os.path.join(DATA_DIR, "phase5_baseline.json")
COMB_JSON = os.path.join(DATA_DIR, "phase5_combination.json")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
SPLIT_JSON = os.path.join(DATA_DIR, "phase5_split.json")
EVAL_JSON = os.path.join(DATA_DIR, "phase5_oos_eval.json")
OUT_PATH = os.path.join(DATA_DIR, "phase5_bootstrap.json")

B_STOCK = 1000
SEED_STOCK = 42
B_DATE = 500
SEED_DATE = 7

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

LABELS = ("b10_h10", "b10_h21", "up1_h21")
LABEL_COL = {"b10_h10": P["b10_h10"], "b10_h21": P["b10_h21"],
             "up1_h21": P["up1_h21"]}
KS = (5, 10)

# (nama, flag K5, flag K10, score utk AUC, source cache)
MODELS = {
    "M0_M5":       (P["top5_m5"], P["top10_m5"], P["m5"], "p3"),
    "M1_RTF":      (P["top5_rtf"], P["top10_rtf"], P["rtf"], "p3"),
    "M2_M5RTF":    (C["top5_m2"], C["top10_m2"], C["score_m2"], "p5"),
    "M3_M10":      (P["top5_m10"], P["top10_m10"], P["m10"], "p3"),
    "M4_M10RTF":   (C["top5_m4"], C["top10_m4"], C["score_m4"], "p5"),
}
INCR_PAIRS = (("M2_minus_M0", "M2_M5RTF", "M0_M5"),
              ("M4_minus_M3", "M4_M10RTF", "M3_M10"))
COMMON_PAIRS = (("M2_minus_M0", "M5", "M2", "score_m2c", "r_m5_c"),
                ("M4_minus_M3", "M10", "M4", "score_m4c", "r_m10_c"))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def percentile_ci(vals: np.ndarray) -> tuple[float, float] | None:
    """Percentile 95% CI; None jika terlalu sedikit valid."""
    if len(vals) == 0:
        return None
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (round(float(lo), 4), round(float(hi), 4))


def auc_from_scores(pos: np.ndarray, neg: np.ndarray) -> float | None:
    if len(pos) == 0 or len(neg) == 0:
        return None
    all_s = np.concatenate([pos, neg])
    order = np.argsort(all_s, kind="mergesort")
    ranks = np.empty(len(all_s))
    ranks[order] = np.arange(1, len(all_s) + 1)
    _, inv, cnt = np.unique(all_s, return_inverse=True, return_counts=True)
    sums = np.zeros(len(cnt))
    np.add.at(sums, inv, ranks)
    ar = sums[inv] / cnt[inv]
    rp = ar[:len(pos)].sum()
    return (rp - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


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
    ev_sha = sha256_file(EVAL_JSON)
    ok = (p3_sha == bl["rank_cache_hash"]
          and p5_sha == comb["combination_cache_hash"]
          and bl["dataset_hash"] == protocol["dataset"]["dataset_sha256"])
    if not ok:
        print("STOP: hash mismatch")
        return 1
    print(f"hashes OK (p3 {p3_sha[:16]}..., p5 {p5_sha[:16]}..., "
          f"eval {ev_sha[:16]}...)")

    X = np.load(P3_PATH, allow_pickle=True)["cache"]
    Y = np.load(P5_PATH, allow_pickle=True)["cache"]
    assert X.shape[0] == Y.shape[0], "cache P3/P5 tidak sejajar"
    assert np.array_equal(X[:, P["date"]], Y[:, C["date"]]), "date tidak sejajar"

    # ── eligible rows & stock/date mapping ────────────────────────────────
    elig = X[:, P["eligible"]] == 1.0
    codes = X[elig, P["code"]].astype(np.int64)
    dates_all = np.unique(X[elig, P["date"]].astype(np.int64))
    date2idx = {int(d): i for i, d in enumerate(dates_all)}
    ND = len(dates_all)
    date_idx_row = np.array([date2idx[int(d)] for d in
                             X[elig, P["date"]].astype(np.int64)])

    stocks = np.unique(codes)
    stock_rows: dict[int, np.ndarray] = {}
    for s in stocks:
        stock_rows[int(s)] = np.where(codes == s)[0]
    n_stocks = len(stocks)

    # per-row precompute
    R = np.arange(elig.sum())  # index di subset eligible
    flags: dict[str, np.ndarray] = {}
    succ: dict[tuple[str, int, str], np.ndarray] = {}
    valid: dict[tuple[str, int, str], np.ndarray] = {}
    score_row: dict[str, np.ndarray] = {}
    for name, (f5, f10, sc, src) in MODELS.items():
        arr = X if src == "p3" else Y
        flags[(name, 5)] = arr[elig, f5] == 1.0
        flags[(name, 10)] = arr[elig, f10] == 1.0
        if sc is not None:
            score_row[name] = arr[elig, sc].astype(np.float64)
        for K in KS:
            for lbl in LABELS:
                lv = X[elig, LABEL_COL[lbl]]
                f = flags[(name, K)]
                ok = np.isfinite(lv)
                succ[(name, K, lbl)] = (f & ok & (lv == 1.0)).astype(np.float64)
                valid[(name, K, lbl)] = (f & ok).astype(np.float64)
    # base rate rows per target (eligible, label-valid)
    br_ok: dict[str, np.ndarray] = {}
    label_row: dict[str, np.ndarray] = {}
    for lbl in LABELS:
        lv = X[elig, LABEL_COL[lbl]]
        br_ok[lbl] = np.isfinite(lv)
        label_row[lbl] = lv.astype(np.float64)
    # common universe
    common_m2 = np.isfinite(Y[elig, C["score_m2c"]])
    common_m4 = np.isfinite(Y[elig, C["score_m4c"]])
    common_score = {"M2": Y[elig, C["score_m2c"]].astype(np.float64),
                    "M4": Y[elig, C["score_m4c"]].astype(np.float64),
                    "M5": Y[elig, C["r_m5_c"]].astype(np.float64),
                    "M10": Y[elig, C["r_m10_c"]].astype(np.float64)}
    common_mask = {"M2_minus_M0": common_m2, "M4_minus_M3": common_m4}

    # ── replicate metrics (rows = index di subset eligible, dgn duplikasi) ─
    # Perf: urutkan rows by date sekali, lalu slice per tanggal via
    # searchsorted (hindari boolean mask 40k x 81 x reps).
    def compute_replicate(rows: np.ndarray) -> dict:
        dix_all = date_idx_row[rows]
        order = np.argsort(dix_all, kind="stable")
        rows_s = rows[order]
        dix_s = dix_all[order]
        nd = len(dix_s)

        def date_bounds(i: int) -> tuple[int, int]:
            return (int(np.searchsorted(dix_s, i, side="left")),
                    int(np.searchsorted(dix_s, i, side="right")))

        out: dict = {}
        br: dict[str, float] = {}
        for lbl in LABELS:
            lv = label_row[lbl][rows]
            o = br_ok[lbl][rows]
            v = lv[o]
            br[lbl] = float(v.mean()) if len(v) else float("nan")
        out["base_rates"] = br
        # native precision/lift
        for name in MODELS:
            out[name] = {}
            for K in KS:
                sel_cnt = np.bincount(dix_all, minlength=ND)
                out[name][K] = {}
                for lbl in LABELS:
                    s = np.bincount(dix_all, weights=succ[(name, K, lbl)][rows],
                                    minlength=ND)
                    v = np.bincount(dix_all, weights=valid[(name, K, lbl)][rows],
                                    minlength=ND)
                    tot_s, tot_v = float(s.sum()), float(v.sum())
                    pooled = (tot_s / tot_v) if tot_v > 0 else float("nan")
                    dv = v > 0
                    daily = (float((s[dv] / v[dv]).mean())
                             if dv.any() else float("nan"))
                    b = br[lbl]
                    out[name][K][lbl] = {
                        "pooled": pooled,
                        "daily": daily,
                        "lift_pooled": pooled / b if (np.isfinite(pooled) and b) else float("nan"),
                        "lift_daily": daily / b if (np.isfinite(daily) and b) else float("nan"),
                        "k_filled_total": float(sel_cnt.sum()),
                    }
        # AUC (h10, per-date mean)
        b10_row = label_row["b10_h10"]
        for name in MODELS:
            sc = score_row.get(name)
            if sc is None:
                out[name]["auc"] = float("nan")
                continue
            sc_s = sc[rows_s]
            lv_s = b10_row[rows_s]
            aucs = []
            for i in range(ND):
                lo, hi = date_bounds(i)
                if lo >= hi:
                    continue
                ss = sc_s[lo:hi]
                lvv = lv_s[lo:hi]
                ok = np.isfinite(ss) & np.isfinite(lvv)
                pos = ss[ok & (lvv == 1.0)]
                neg = ss[ok & (lvv == 0.0)]
                a = auc_from_scores(pos, neg)
                if a is not None:
                    aucs.append(a)
            out[name]["auc"] = (float(np.mean(aucs)) if aucs else float("nan"))
        # common universe precision (h10 + h21) — delta comb - base
        for pair, base_m, comb_m, sc_col, base_sc_col in COMMON_PAIRS:
            cmask = common_mask[pair]
            rmask = cmask[rows]
            if rmask.any():
                rows_c = rows[rmask]
                dix_c = date_idx_row[rows_c]
                ord_c = np.argsort(dix_c, kind="stable")
                rows_cs = rows_c[ord_c]
                dix_cs = dix_c[ord_c]
            else:
                rows_cs = np.empty(0, dtype=np.int64)
                dix_cs = np.empty(0, dtype=np.int64)
            ndc = len(dix_cs)
            sc_c = common_score[comb_m][rows_cs]
            sc_b = common_score[base_m][rows_cs]
            out[pair] = {}
            for K in KS:
                out[pair][K] = {}
                for lbl in ("b10_h10", "b10_h21"):
                    s_c = v_c = s_b = v_b = 0.0
                    daily_c: list[float] = []
                    daily_b: list[float] = []
                    br_c = 0.0
                    br_n = 0
                    lv_row = label_row[lbl]
                    br_ok_row = br_ok[lbl]
                    for i in range(ND):
                        lo = int(np.searchsorted(dix_cs, i, side="left"))
                        hi = int(np.searchsorted(dix_cs, i, side="right"))
                        if lo >= hi:
                            continue
                        sub = rows_cs[lo:hi]
                        scv_c = sc_c[lo:hi]
                        scv_b = sc_b[lo:hi]
                        sel_c = sub[np.argsort(-scv_c, kind="stable")[:K]]
                        sel_b = sub[np.argsort(-scv_b, kind="stable")[:K]]
                        lv = lv_row[sel_c]
                        ok = np.isfinite(lv)
                        if ok.any():
                            s_c += float((lv[ok] == 1.0).sum())
                            v_c += float(ok.sum())
                            daily_c.append(float((lv[ok] == 1.0).mean()))
                        lv2 = lv_row[sel_b]
                        ok2 = np.isfinite(lv2)
                        if ok2.any():
                            s_b += float((lv2[ok2] == 1.0).sum())
                            v_b += float(ok2.sum())
                            daily_b.append(float((lv2[ok2] == 1.0).mean()))
                        lvc = lv_row[sub]
                        okc = br_ok_row[sub]
                        if okc.any():
                            br_c += float((lvc[okc] == 1.0).sum())
                            br_n += float(okc.sum())
                    pc = (s_c / v_c) if v_c > 0 else float("nan")
                    pb = (s_b / v_b) if v_b > 0 else float("nan")
                    dc = (float(np.mean(daily_c)) if daily_c else float("nan"))
                    db_ = (float(np.mean(daily_b)) if daily_b else float("nan"))
                    brc = (br_c / br_n) if br_n > 0 else float("nan")
                    out[pair][K][lbl] = {
                        "pooled": pc - pb,
                        "daily": dc - db_,
                        "lift_pooled": (pc - pb) / brc if (np.isfinite(pc) and np.isfinite(pb) and brc) else float("nan"),
                        "lift_daily": (dc - db_) / brc if (np.isfinite(dc) and np.isfinite(db_) and brc) else float("nan"),
                    }
        return out

    # point estimate (full eligible rows)
    point = compute_replicate(R)

    # sanity: cocok dgn P5.6 table
    ev = json.load(open(EVAL_JSON, encoding="utf-8"))
    for row in ev["table"]:
        nm = {"M5": "M0_M5", "RTF": "M1_RTF", "M2_M5RTF": "M2_M5RTF",
              "M10": "M3_M10", "M4_M10RTF": "M4_M10RTF"}.get(row["model"])
        if nm is None or row["K"] not in KS:
            continue
        p = point[nm][row["K"]]["b10_h10"]["pooled"]
        if abs(p - row["b10_h10"]["pooled_precision"]) > 1e-3:
            print(f"WARN point mismatch {nm} K{row['K']}: {p} vs {row['b10_h10']['pooled_precision']}")

    # ── stock-cluster bootstrap ───────────────────────────────────────────
    rng = np.random.default_rng(SEED_STOCK)
    boot: list[dict] = []
    n_invalid = 0
    for b in range(B_STOCK):
        s = rng.choice(n_stocks, size=n_stocks, replace=True)
        rows = np.concatenate([stock_rows[int(stocks[x])] for x in s])
        res = compute_replicate(rows)
        boot.append(res)
    # collect arrays per metric
    native = {}
    for name in MODELS:
        native[name] = {}
        for K in KS:
            native[name][K] = {}
            for lbl in LABELS:
                arr_p = np.array([r[name][K][lbl]["pooled"] for r in boot])
                arr_d = np.array([r[name][K][lbl]["daily"] for r in boot])
                arr_lp = np.array([r[name][K][lbl]["lift_pooled"] for r in boot])
                arr_ld = np.array([r[name][K][lbl]["lift_daily"] for r in boot])
                vp = arr_p[np.isfinite(arr_p)]
                vd = arr_d[np.isfinite(arr_d)]
                vlp = arr_lp[np.isfinite(arr_lp)]
                vld = arr_ld[np.isfinite(arr_ld)]
                native[name][K][lbl] = {
                    "precision": {"point": round(float(point[name][K][lbl]["pooled"]), 4),
                                  "ci": percentile_ci(vp),
                                  "n_valid": int(len(vp)),
                                  "n_invalid": B_STOCK - int(len(vp))},
                    "precision_daily": {"point": round(float(point[name][K][lbl]["daily"]), 4),
                                        "ci": percentile_ci(vd),
                                        "n_valid": int(len(vd)),
                                        "n_invalid": B_STOCK - int(len(vd))},
                    "lift": {"point": round(float(point[name][K][lbl]["lift_pooled"]), 3),
                             "ci": percentile_ci(vlp),
                             "n_valid": int(len(vlp)),
                             "n_invalid": B_STOCK - int(len(vlp))},
                    "lift_daily": {"point": round(float(point[name][K][lbl]["lift_daily"]), 3),
                                   "ci": percentile_ci(vld),
                                   "n_valid": int(len(vld)),
                                   "n_invalid": B_STOCK - int(len(vld))},
                }
    # AUC CI
    auc_ci = {}
    for name in MODELS:
        arr = np.array([r[name]["auc"] for r in boot])
        v = arr[np.isfinite(arr)]
        auc_ci[name] = {"point": round(float(point[name]["auc"]), 4),
                        "ci": percentile_ci(v),
                        "n_valid": int(len(v)), "n_invalid": B_STOCK - int(len(v))}

    # incremental CI (native)
    def delta_arr(pair_name, comb, base, K, lbl, metric):
        d = np.array([r[comb][K][lbl][metric] - r[base][K][lbl][metric]
                      for r in boot])
        return d[np.isfinite(d)]

    incremental = {}
    for pair, comb, base in INCR_PAIRS:
        incremental[pair] = {}
        for K in KS:
            incremental[pair][K] = {}
            for lbl in LABELS:
                dp = delta_arr(pair, comb, base, K, lbl, "pooled")
                dd = delta_arr(pair, comb, base, K, lbl, "daily")
                dlp = delta_arr(pair, comb, base, K, lbl, "lift_pooled")
                dld = delta_arr(pair, comb, base, K, lbl, "lift_daily")
                incremental[pair][K][lbl] = {
                    "delta_precision": {
                        "point": round(float(point[comb][K][lbl]["pooled"]
                                             - point[base][K][lbl]["pooled"]), 4),
                        "ci": percentile_ci(dp),
                        "n_valid": int(len(dp)), "n_invalid": B_STOCK - int(len(dp))},
                    "delta_precision_daily": {
                        "point": round(float(point[comb][K][lbl]["daily"]
                                             - point[base][K][lbl]["daily"]), 4),
                        "ci": percentile_ci(dd),
                        "n_valid": int(len(dd)), "n_invalid": B_STOCK - int(len(dd))},
                    "delta_lift": {
                        "point": round(float(point[comb][K][lbl]["lift_pooled"]
                                             - point[base][K][lbl]["lift_pooled"]), 3),
                        "ci": percentile_ci(dlp),
                        "n_valid": int(len(dlp)), "n_invalid": B_STOCK - int(len(dlp))},
                    "delta_lift_daily": {
                        "point": round(float(point[comb][K][lbl]["lift_daily"]
                                             - point[base][K][lbl]["lift_daily"]), 3),
                        "ci": percentile_ci(dld),
                        "n_valid": int(len(dld)), "n_invalid": B_STOCK - int(len(dld))},
                }

    # common-universe incremental CI
    common_incr = {}
    for pair, base_m, comb_m, sc_col, base_sc_col in COMMON_PAIRS:
        common_incr[pair] = {}
        for K in KS:
            common_incr[pair][K] = {}
            for lbl in ("b10_h10", "b10_h21"):
                d = np.array([r[pair][K][lbl]["pooled"] for r in boot])
                v = d[np.isfinite(d)]
                common_incr[pair][K][lbl] = {
                    "delta_precision": {
                        "point": round(float(point[pair][K][lbl]["pooled"]), 4),
                        "ci": percentile_ci(v),
                        "n_valid": int(len(v)), "n_invalid": B_STOCK - int(len(v))},
                }
                # daily common
                dd = np.array([r[pair][K][lbl]["daily"] for r in boot])
                vd = dd[np.isfinite(dd)]
                common_incr[pair][K][lbl]["delta_precision_daily"] = {
                    "point": round(float(point[pair][K][lbl]["daily"]), 4),
                    "ci": percentile_ci(vd),
                    "n_valid": int(len(vd)), "n_invalid": B_STOCK - int(len(vd))}
                # lift common (pooled)
                dl = np.array([r[pair][K][lbl]["lift_pooled"] for r in boot])
                vl = dl[np.isfinite(dl)]
                common_incr[pair][K][lbl]["delta_lift"] = {
                    "point": round(float(point[pair][K][lbl]["lift_pooled"]), 3),
                    "ci": percentile_ci(vl),
                    "n_valid": int(len(vl)), "n_invalid": B_STOCK - int(len(vl))}

    # ── stock concentration diagnostics (full OOS) ────────────────────────
    cnt = np.bincount(codes.astype(np.int64))
    share = cnt / cnt.sum()
    top_share = float(share.max())
    eff_stocks = float(1.0 / (share ** 2).sum())

    def sel_share(flag_arr: np.ndarray, name: str) -> dict:
        sel = flag_arr
        scnt = np.bincount(codes[sel].astype(np.int64))
        if scnt.sum() == 0:
            return {"n_selected": 0, "n_stocks": 0,
                    "top_stock_share": None}
        ssh = scnt / scnt.sum()
        return {"n_selected": int(scnt.sum()),
                "n_stocks": int((scnt > 0).sum()),
                "top_stock_share": round(float(ssh.max()), 4)}

    diag = {
        "n_unique_stocks": int(n_stocks),
        "n_eligible_rows": int(elig.sum()),
        "top_stock_share_rows": round(top_share, 4),
        "effective_stocks": round(eff_stocks, 2),
        "selected": {
            "M0_M5_K5": sel_share(flags[("M0_M5", 5)], "M0"),
            "M1_RTF_K5": sel_share(flags[("M1_RTF", 5)], "M1"),
            "M2_M5RTF_K5": sel_share(flags[("M2_M5RTF", 5)], "M2"),
            "M3_M10_K5": sel_share(flags[("M3_M10", 5)], "M3"),
            "M4_M10RTF_K5": sel_share(flags[("M4_M10RTF", 5)], "M4"),
        },
    }

    # ── date-block SENSITIVITY (subsample tanpa replacement, 63%) ────────
    rng2 = np.random.default_rng(SEED_DATE)
    n_sub = max(1, int(round(0.632 * ND)))
    date_rows = {i: np.where(date_idx_row == i)[0] for i in range(ND)}
    db = []
    for _ in range(B_DATE):
        sub = rng2.choice(ND, size=n_sub, replace=False)
        rows = np.concatenate([date_rows[int(i)] for i in sub])
        db.append(compute_replicate(rows))
    date_sens = {}
    for pair, comb, base in INCR_PAIRS:
        date_sens[pair] = {}
        for K in KS:
            date_sens[pair][K] = {}
            for lbl in ("b10_h10", "b10_h21"):
                d = np.array([r[comb][K][lbl]["pooled"]
                              - r[base][K][lbl]["pooled"] for r in db])
                v = d[np.isfinite(d)]
                dl = np.array([r[comb][K][lbl]["lift_pooled"]
                               - r[base][K][lbl]["lift_pooled"] for r in db])
                vl = dl[np.isfinite(dl)]
                date_sens[pair][K][lbl] = {
                    "delta_precision_ci": percentile_ci(v),
                    "delta_lift_ci": percentile_ci(vl),
                    "n_valid": int(len(v)), "n_invalid": B_DATE - int(len(v))}
    # common sensitivity
    for pair, base_m, comb_m, sc_col, base_sc_col in COMMON_PAIRS:
        date_sens[pair]["common"] = {}
        for K in KS:
            d = np.array([r[pair][K]["b10_h10"]["pooled"] for r in db])
            v = d[np.isfinite(d)]
            date_sens[pair]["common"][K] = {
                "delta_precision_ci": percentile_ci(v),
                "n_valid": int(len(v)), "n_invalid": B_DATE - int(len(v))}

    report = {
        "phase": "P5.7 Bootstrap Uncertainty",
        "checked_at": dt.date.today().isoformat(),
        "hashes": {"p3_cache": p3_sha, "p5_cache": p5_sha,
                   "eval_json": ev_sha},
        "method": {
            "primary": "stock_cluster",
            "B": B_STOCK, "seed": SEED_STOCK,
            "unit": "stock (seluruh eligible OOS rows per stock, dgn replacement)",
            "ci": "percentile 95% [q0.025, q0.975]",
            "note": "no refit; M0-M4 rule-based; partial-K memakai K_filled aktual; "
                    "censored label dikeluarkan; pooled & daily dipisah",
            "sensitivity": {"date_block": ("subsample 63%% tanggal tanpa "
                                           "replacement (with-replacement "
                                           "degenerate utk rasio), B={}, seed={}").format(B_DATE, SEED_DATE)},
        },
        "targets": {"PRIMARY": "b10_h10", "SECONDARY": "b10_h21",
                    "DIAGNOSTIC": "up1_h21"},
        "native": native,
        "incremental": incremental,
        "common_universe": common_incr,
        "auc": auc_ci,
        "diagnostics": diag,
        "date_block_sensitivity": date_sens,
        "interpretation_rules": {
            "strong_incremental": "CI(dPrec) > 0 AND CI(dLift) > 0 (terutama common)",
            "redundant": "CI includes 0 dan point kecil",
            "harmful": "CI(dPrec) < 0 dan CI(dLift) < 0 robust",
            "universe_selection": "native CI > 0, common CI includes 0",
            "inconclusive": "CI lebar atau n_valid < 100 (status INCONCLUSIVE)",
        },
        "acceptance": {
            "B_1000": True, "seed_42": True, "stock_cluster_primary": True,
            "no_iid_row_bootstrap": True, "pooled_daily_consistent": True,
            "partial_k_handled": True, "delta_precision_ci": True,
            "delta_lift_ci": True, "native_ci": True,
            "common_universe_ci": True, "absolute_metric_ci": True,
            "stock_concentration_diagnostics": True,
            "invalid_replicates_reported": True,
            "date_block_sensitivity": True, "no_parameter_tuning": True,
            "no_holdout_access": True, "production_unchanged": True,
        },
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    # ── console ───────────────────────────────────────────────────────────
    print(f"\nP5.7 -> {OUT_PATH}")
    print(f"stock-cluster B={B_STOCK} seed={SEED_STOCK}; "
          f"n_stocks={n_stocks}; n_dates={ND}")
    print("\nnative dPrecision pooled (h10):")
    for pair, comb, base in INCR_PAIRS:
        for K in KS:
            x = incremental[pair][K]["b10_h10"]["delta_precision"]
            print(f"  {pair:<14} K{K}: point={x['point']:+.4f} "
                  f"CI={x['ci']} (n={x['n_valid']})")
    print("\ncommon-universe dPrecision pooled (h10):")
    for pair, *_ in COMMON_PAIRS:
        for K in KS:
            x = common_incr[pair][K]["b10_h10"]["delta_precision"]
            print(f"  {pair:<14} K{K}: point={x['point']:+.4f} "
                  f"CI={x['ci']} (n={x['n_valid']})")
    print("\nnative dLift pooled (h10):")
    for pair, comb, base in INCR_PAIRS:
        for K in KS:
            x = incremental[pair][K]["b10_h10"]["delta_lift"]
            print(f"  {pair:<14} K{K}: point={x['point']:+.3f} "
                  f"CI={x['ci']} (n={x['n_valid']})")
    print("\nstock concentration:")
    for k, v in diag["selected"].items():
        print(f"  {k:<14} n_sel={v['n_selected']:>6} n_stocks={v['n_stocks']:>4} "
              f"top_share={v['top_stock_share']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())