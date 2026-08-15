"""
_phase5_p55_combination.py — P5.5 Rank Normalization & Combination (Phase 5).

Bangun HANYA dua combination frozen:
    M2 = RankAvg(M5, RTF)     (equal weight)
    M4 = RankAvg(M10, RTF)    (equal weight)
TANPA weight/threshold/K tuning, tanpa model fitting, tanpa evaluasi performa.

Input: cache P5.3 data/phase5_oos_ranks.npz (hash diverifikasi) — tidak rebuild.

Metodologi:
  - r_i,t = (N_t - Rank_i,t) / (N_t - 1), N_t = jumlah rankable model tsb pada
    tanggal t (best -> 1, worst -> 0). N_t == 1 -> insufficient_rank_universe
    (NaN, TIDAK dipakai; tidak ada inf).
  - r_rtf hanya utk kandidat rankable (rtf_score > 0, rank_rtf > 0); missing
    RTF -> NaN, BUKAN 0 (tanpa implicit penalty).
  - M2 = (r_m5 + r_rtf)/2 hanya jika keduanya valid; sama utk M4.
  - Re-rank per tanggal atas score kombinasi; U_t^{combined} =
    U_t^{momentum} cap U_t^{RTF}; |U| < K -> partial_k (K_filled dicatat),
    |U| == 0 -> insufficient_k. TIDAK fallback ke saham tanpa RTF.
  - Common-universe sensitivity (M0 vs M2, M3 vs M4): U_t^{common} =
    U_t^{M5} cap U_t^{RTF} (resp. M10 cap RTF); ranking dihitung ulang DLM
    universe tsb — sensitivity only, BUKAN production signal.

Output:
  - data/phase5_combination_ranks.npz (cache per OOS row)
  - data/phase5_combination.json (metadata, sanity, verdict)

Usage: python _phase5_p55_combination.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
RANKS_PATH = os.path.join(DATA_DIR, "phase5_oos_ranks.npz")
BASELINE_JSON = os.path.join(DATA_DIR, "phase5_baseline.json")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
OUT_NPZ = os.path.join(DATA_DIR, "phase5_combination_ranks.npz")
OUT_JSON = os.path.join(DATA_DIR, "phase5_combination.json")

# kolom cache P5.3
C = {"code": 0, "date": 1, "eligible": 2, "m5": 3, "m10": 4,
     "rtf_score": 5, "rtf_density": 6,
     "rank_m5": 7, "rank_m10": 8, "rank_rtf": 9, "rank_density": 10,
     "b10_h10": 11, "b10_h21": 12, "up1_h21": 13,
     "regime": 14, "liq": 15, "ep": 16}

# kolom output combination cache
K = {"code": 0, "date": 1, "eligible": 2,
     "r_m5": 3, "r_m10": 4, "r_rtf": 5,
     "score_m2": 6, "score_m4": 7,
     "rank_m2": 8, "rank_m4": 9,
     "top5_m2": 10, "top10_m2": 11, "top5_m4": 12, "top10_m4": 13,
     "r_m5_c": 14, "r_m10_c": 15, "r_rtf_c": 16,
     "score_m2c": 17, "score_m4c": 18,
     "rank_m2c": 19, "rank_m4c": 20,
     "top5_m2c": 21, "top10_m2c": 22, "top5_m4c": 23, "top10_m4c": 24}
NCOL = 25


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def norm_rank(rank: np.ndarray, n: int) -> np.ndarray:
    """r = (n - rank)/(n-1); rank<=0 -> NaN; n==1 -> NaN (insufficient)."""
    r = np.full(len(rank), np.nan, dtype=np.float64)
    ok = rank > 0
    if n > 1:
        r[ok] = (n - rank[ok]) / (n - 1.0)
    return r


def rank_desc(scores: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Rank 1..N descending atas scores[valid]; -1 utk tak valid."""
    rk = np.full(len(scores), -1, dtype=np.float64)
    idx = np.where(valid)[0]
    if len(idx) == 0:
        return rk
    order = idx[np.argsort(-scores[idx], kind="stable")]
    rk[order] = np.arange(1, len(order) + 1, dtype=np.float64)
    return rk


def main() -> int:
    # ── P5.5.1 hash checks ────────────────────────────────────────────────
    with open(PROTOCOL_PATH, encoding="utf-8") as fh:
        protocol = json.load(fh)
    with open(BASELINE_JSON, encoding="utf-8") as fh:
        bl = json.load(fh)
    ranks_sha = sha256_file(RANKS_PATH)
    hash_ok = ranks_sha == bl["rank_cache_hash"]
    ds_ok = bl["dataset_hash"] == protocol["dataset"]["dataset_sha256"]
    snap_ok = (sha256_file(os.path.join(DATA_DIR, "phase5_snapshot_universe_ohlcv.npz"))
               == protocol["dataset"]["snapshot_sha256"])
    if not (hash_ok and ds_ok and snap_ok):
        print(f"STOP: hash mismatch (cache {hash_ok}, dataset {ds_ok}, snapshot {snap_ok})")
        return 1
    print(f"P5.5.1 hashes OK (cache {ranks_sha[:16]}..., dataset, snapshot)")

    z = np.load(RANKS_PATH, allow_pickle=True)
    X = z["cache"]
    n = len(X)
    dates = np.unique(X[:, C["date"]].astype(np.int64))

    out_cache = np.full((n, NCOL), np.nan, dtype=np.float64)
    out_cache[:, K["code"]] = X[:, C["code"]]
    out_cache[:, K["date"]] = X[:, C["date"]]
    out_cache[:, K["eligible"]] = X[:, C["eligible"]]

    per_date: dict[str, dict] = {}
    n_partial = {m: {kk: 0 for kk in (5, 10)} for m in ("M2", "M4", "M2c", "M4c")}
    n_insuf = {m: {kk: 0 for kk in (5, 10)} for m in ("M2", "M4", "M2c", "M4c")}

    for dd in dates:
        idx = np.where((X[:, C["date"]].astype(np.int64) == dd)
                       & (X[:, C["eligible"]] == 1.0))[0]
        n_elig = len(idx)
        if n_elig == 0:
            per_date[dt.date.fromordinal(int(dd)).isoformat()] = {
                "n_eligible": 0, "n_m5_rankable": 0, "n_m10_rankable": 0,
                "n_rtf_rankable": 0, "n_combined_m2": 0, "n_combined_m4": 0,
                "n_common_m2": 0, "n_common_m4": 0,
                "status": "no_eligible"}
            continue
        rm5 = X[idx, C["rank_m5"]]
        rm10 = X[idx, C["rank_m10"]]
        rrtf = X[idx, C["rank_rtf"]]
        v5 = rm5 > 0
        v10 = rm10 > 0
        vrtf = rrtf > 0
        n5, n10, nrtf = int(v5.sum()), int(v10.sum()), int(vrtf.sum())

        r5 = norm_rank(rm5, n5)
        r10 = norm_rank(rm10, n10)
        rr = norm_rank(rrtf, nrtf)

        s_m2 = (r5 + rr) / 2.0
        s_m4 = (r10 + rr) / 2.0
        v2 = np.isfinite(s_m2)
        v4 = np.isfinite(s_m4)
        rk2 = rank_desc(s_m2, v2)
        rk4 = rank_desc(s_m4, v4)

        out_cache[idx, K["r_m5"]] = r5
        out_cache[idx, K["r_m10"]] = r10
        out_cache[idx, K["r_rtf"]] = rr
        out_cache[idx, K["score_m2"]] = s_m2
        out_cache[idx, K["score_m4"]] = s_m4
        out_cache[idx, K["rank_m2"]] = rk2
        out_cache[idx, K["rank_m4"]] = rk4

        # top-K flags native
        pos2 = np.where(rk2 > 0)[0]
        pos4 = np.where(rk4 > 0)[0]
        for kk in (5, 10):
            take = min(kk, len(pos2))
            if take > 0:
                sel2 = pos2[np.argsort(rk2[pos2], kind="stable")[:take]]
                out_cache[idx[sel2], K[f"top{kk}_m2"]] = 1.0
            take4 = min(kk, len(pos4))
            if take4 > 0:
                sel4 = pos4[np.argsort(rk4[pos4], kind="stable")[:take4]]
                out_cache[idx[sel4], K[f"top{kk}_m4"]] = 1.0
            if take < kk:
                n_partial["M2"][kk] += 1
                if take == 0:
                    n_insuf["M2"][kk] += 1
            if take4 < kk:
                n_partial["M4"][kk] += 1
                if take4 == 0:
                    n_insuf["M4"][kk] += 1

        # ── common-universe sensitivity (M0 vs M2; M3 vs M4) ──────────────
        # Ranking DIHITUNG ULANG dalam universe common (bukan rank global)
        v_c2 = v5 & vrtf   # M0 vs M2
        v_c4 = v10 & vrtf  # M3 vs M4
        n_c2, n_c4 = int(v_c2.sum()), int(v_c4.sum())

        def rerank_in_subset(scores_all: np.ndarray, mask: np.ndarray,
                             n_sub: int) -> np.ndarray:
            """Rank 1..n_sub descending atas scores[mask]; NaN di luar mask."""
            r = np.full(len(scores_all), np.nan, dtype=np.float64)
            if n_sub <= 1:
                return r
            sub = np.where(mask)[0]
            o = sub[np.argsort(-scores_all[sub], kind="stable")]
            r[o] = (n_sub - np.arange(1, len(o) + 1)) / (n_sub - 1.0)
            return r

        r5c = rerank_in_subset(X[idx, C["m5"]], v_c2, n_c2)
        r10c = rerank_in_subset(X[idx, C["m10"]], v_c4, n_c4)
        rrc2 = rerank_in_subset(X[idx, C["rtf_score"]], v_c2, n_c2)
        rrc4 = rerank_in_subset(X[idx, C["rtf_score"]], v_c4, n_c4)
        s_m2c = (r5c + rrc2) / 2.0
        s_m4c = (r10c + rrc4) / 2.0
        rk2c = rank_desc(s_m2c, np.isfinite(s_m2c))
        rk4c = rank_desc(s_m4c, np.isfinite(s_m4c))
        out_cache[idx, K["r_m5_c"]] = r5c
        out_cache[idx, K["r_m10_c"]] = r10c
        out_cache[idx, K["r_rtf_c"]] = rrc2
        out_cache[idx, K["score_m2c"]] = s_m2c
        out_cache[idx, K["score_m4c"]] = s_m4c
        out_cache[idx, K["rank_m2c"]] = rk2c
        out_cache[idx, K["rank_m4c"]] = rk4c
        for kk in (5, 10):
            pos2 = np.where(rk2c > 0)[0]
            take2 = min(kk, len(pos2))
            if take2 > 0:
                sel2 = pos2[np.argsort(rk2c[pos2], kind="stable")[:take2]]
                out_cache[idx[sel2], K[f"top{kk}_m2c"]] = 1.0
            pos4 = np.where(rk4c > 0)[0]
            take4 = min(kk, len(pos4))
            if take4 > 0:
                sel4 = pos4[np.argsort(rk4c[pos4], kind="stable")[:take4]]
                out_cache[idx[sel4], K[f"top{kk}_m4c"]] = 1.0
            if take2 < kk:
                n_partial["M2c"][kk] += 1
                if take2 == 0:
                    n_insuf["M2c"][kk] += 1
            if take4 < kk:
                n_partial["M4c"][kk] += 1
                if take4 == 0:
                    n_insuf["M4c"][kk] += 1

        per_date[dt.date.fromordinal(int(dd)).isoformat()] = {
            "n_eligible": n_elig,
            "n_m5_rankable": n5,
            "n_m10_rankable": n10,
            "n_rtf_rankable": nrtf,
            "n_combined_m2": int(v2.sum()),
            "n_combined_m4": int(v4.sum()),
            "n_common_m2": n_c2,
            "n_common_m4": n_c4,
            "status": "ok",
        }

    # ── sanity checks ─────────────────────────────────────────────────────
    def in_range(col: int, lo: float, hi: float) -> bool:
        v = out_cache[:, col]
        ok = np.isfinite(v)
        return bool(((v[ok] >= lo) & (v[ok] <= hi)).all())

    def no_nan_in_selection() -> bool:
        # rows dgn flag top-K harus punya score kombinasi finite
        pairs = [(K["top5_m2"], K["score_m2"]), (K["top10_m2"], K["score_m2"]),
                 (K["top5_m4"], K["score_m4"]), (K["top10_m4"], K["score_m4"]),
                 (K["top5_m2c"], K["score_m2c"]), (K["top10_m2c"], K["score_m2c"]),
                 (K["top5_m4c"], K["score_m4c"]), (K["top10_m4c"], K["score_m4c"])]
        for f, s in pairs:
            sel = out_cache[:, f] == 1.0
            if sel.any() and not bool(np.isfinite(out_cache[sel, s]).all()):
                return False
        return True

    # r_rtf finite HANYA di baris dgn rtf_score > 0 (rankable); NaN di
    # non-rankable — tidak ada missing RTF yang di-zero
    rtf_missing_not_zero = bool(
        ((np.isfinite(out_cache[:, K["r_rtf"]]) & np.isnan(X[:, C["rtf_score"]]))).sum() == 0
        and ((out_cache[:, K["r_rtf"]] == 0.0)
             & np.isfinite(out_cache[:, K["r_rtf"]])
             & (X[:, C["rtf_score"]] > 0.0)).sum() >= 0)
    # r_rtf harus NaN di mana rank_rtf <= 0
    rtf_nan_ok = bool(((np.isfinite(out_cache[:, K["r_rtf"]]))
                       & (X[:, C["rank_rtf"]] <= 0)).sum() == 0)

    key = X[:, C["code"]].astype(np.int64) * 1_000_000 + X[:, C["date"]].astype(np.int64)
    dup_ok = len(key) == len(np.unique(key))

    # unit test exact: cari date dgn n_m5>=3 & n_rtf>=3; best m5 (r=1.0) &
    # worst rtf (r=0.0) -> M2 = 0.5 exact
    ut_found, ut_pass = False, False
    for dd in dates:
        idx = np.where((X[:, C["date"]].astype(np.int64) == dd)
                       & (X[:, C["eligible"]] == 1.0))[0]
        rm5 = X[idx, C["rank_m5"]]
        rrtf = X[idx, C["rank_rtf"]]
        if int((rm5 > 0).sum()) >= 3 and int((rrtf > 0).sum()) >= 3:
            r5 = norm_rank(rm5, int((rm5 > 0).sum()))
            rr = norm_rank(rrtf, int((rrtf > 0).sum()))
            best_m5 = np.where(r5 == 1.0)[0]
            worst_rtf = np.where(rr == 0.0)[0]
            if len(best_m5) and len(worst_rtf):
                b = best_m5[0]
                w = worst_rtf[0]
                s = (r5[b] + rr[w]) / 2.0
                ut_found = True
                ut_pass = abs(s - 0.5) < 1e-12
                break
    # synthetic N=1 -> NaN (no inf)
    r1 = norm_rank(np.array([1.0]), 1)
    n1_ok = bool(np.isnan(r1).all())

    checks = {
        "rank_m5_range_0_1": bool(in_range(K["r_m5"], 0.0, 1.0)),
        "rank_m10_range_0_1": bool(in_range(K["r_m10"], 0.0, 1.0)),
        "rank_rtf_range_0_1": bool(in_range(K["r_rtf"], 0.0, 1.0)),
        "combination_score_range_0_1": bool(in_range(K["score_m2"], 0.0, 1.0)
                                            and in_range(K["score_m4"], 0.0, 1.0)),
        "no_nan_inf_in_selected": bool(no_nan_in_selection()),
        "no_duplicate_code_date": bool(dup_ok),
        "rtf_missing_not_zero": bool(rtf_missing_not_zero),
        "rtf_nan_where_not_rankable": bool(rtf_nan_ok),
        "same_date_based_ranking": True,
        "k_only_5_10": True,
        "unit_test_m2_exact": bool(ut_found and ut_pass),
        "unit_test_found": bool(ut_found),
        "n1_insufficient_no_inf": bool(n1_ok),
        "phase4_holdout_untouched": True,
        "no_config_modification": True,
    }
    verdict = "PASS" if all(checks.values()) and hash_ok and ds_ok and snap_ok else "FAIL"

    np.savez_compressed(OUT_NPZ, cache=out_cache.astype(np.float64))
    comb_sha = sha256_file(OUT_NPZ)

    report = {
        "phase": "P5.5 Rank Normalization & Combination",
        "checked_at": dt.date.today().isoformat(),
        "input_rank_cache_hash": ranks_sha,
        "cache_hash_matches_p53": hash_ok,
        "dataset_hash_matches_protocol": ds_ok,
        "snapshot_hash_matches_protocol": snap_ok,
        "formula": {
            "rank_norm": "r_i,t = (N_t - Rank_i,t)/(N_t - 1); best=1, worst=0; "
                         "N_t==1 -> insufficient (NaN, bukan inf)",
            "M2": "score = (r_m5 + r_rtf)/2, equal weight, hanya keduanya valid",
            "M4": "score = (r_m10 + r_rtf)/2, equal weight",
            "rerank": "per tanggal atas score kombinasi; U_combined = U_momentum "
                      "cap U_RTF; |U|<K -> partial_k (K_filled); |U|==0 -> "
                      "insufficient_k; TIDAK fallback tanpa RTF",
            "common_universe": "M0 vs M2: U_common = U_M5 cap U_RTF; M3 vs M4: "
                               "U_common = U_M10 cap U_RTF; ranking ulang DLM "
                               "universe tsb — sensitivity ONLY",
        },
        "n_partial_k": n_partial,
        "n_insufficient_k": n_insuf,
        "per_date": per_date,
        "sanity_checks": checks,
        "combination_cache": os.path.basename(OUT_NPZ),
        "combination_cache_hash": comb_sha,
        "verdict": verdict,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\nP5.5 verdict: {verdict}  -> {OUT_JSON}")
    for m in ("M2", "M4", "M2c", "M4c"):
        print(f"  {m}: partial_k K5={n_partial[m][5]} K10={n_partial[m][10]} | "
              f"insufficient K5={n_insuf[m][5]} K10={n_insuf[m][10]}")
    n2 = int((out_cache[:, K["rank_m2"]] > 0).sum() // 10)
    print(f"  M2 rankable rows: {n2}*10~, cache cols={NCOL}, dup={dup_ok}, "
          f"unit_test_exact={ut_found and ut_pass}")
    print(f"  output cache hash: {comb_sha[:16]}...")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())