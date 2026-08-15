"""
_phase5_p54_dependency.py — P5.4 Dependency Audit (Phase 5).

DIAGNOSTIC MURNI — tidak mengubah model/config/K/weight, tidak memilih
combination. Menjawab: apakah RTF membawa informasi berbeda dari M5/M10?

Input: cache P5.3 data/phase5_oos_ranks.npz (hash diverifikasi vs
       phase5_baseline.json) — TIDAK rebuild ranking dari dataset.

Metodologi:
  - Spearman RTF vs M5 / RTF vs M10 PER TANGGAL, hanya pada intersection
    U_t^{RTF cap M} = rows dgn rank_rtf > 0 & rank_m > 0 (RTF rankable =
    rtf_score > 0 sesuai P5.3; NaN/score-0 TIDAK ikut; tidak di-zero).
    Ranks unik per date -> Spearman = Pearson pada ranks (monotonic, sesuai
    rank-normalization di combination).
  - Overlap@K = |TopK_RTF ∩ TopK_M| / K (K tetap 5/10; K yg sama -> mudah
    diinterpretasi). Jaccard@K = |A∩B|/|A∪B| sebagai diagnostic tambahan.
  - PRIMARY = date-level; pooled (satu rho atas semua rows) hanya SECONDARY.
  - Regime & liquidity breakdown: date-level group = modus regime/liq pada
    eligible rows tanggal tsb (existing definitions; UNKNOWN tetap UNKNOWN,
    tie -> MIXED, tidak dipaksa). Dependency dihitung ulang per grup.
  - n_pairs per date dilaporkan (corr hanya utk n_pairs >= 2;
    n_dates_insufficient dicatat).

Output: data/phase5_dependency.json

Usage: python _phase5_p54_dependency.py
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
RANKS_PATH = os.path.join(DATA_DIR, "phase5_oos_ranks.npz")
BASELINE_JSON = os.path.join(DATA_DIR, "phase5_baseline.json")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
OUT_PATH = os.path.join(DATA_DIR, "phase5_dependency.json")

# kolom cache (sama dgn P5.3)
C = {"code": 0, "date": 1, "eligible": 2, "m5": 3, "m10": 4,
     "rtf_score": 5, "rtf_density": 6,
     "rank_m5": 7, "rank_m10": 8, "rank_rtf": 9, "rank_density": 10,
     "b10_h10": 11, "b10_h21": 12, "up1_h21": 13,
     "regime": 14, "liq": 15, "ep": 16,
     "top5_m5": 17, "top10_m5": 18, "top5_rtf": 19, "top10_rtf": 20,
     "top5_m10": 21, "top10_m10": 22, "top5_rand": 23, "top10_rand": 24,
     "top5_den": 25, "top10_den": 26}
TOPK = {"top5": 17, "top10": 18}  # offset utk m5; rtf=+2, m10=+4

REGIME_NAMES = {-1: "UNKNOWN", 0: "sideways", 1: "bull", 2: "bear"}
LIQ_NAMES = {-1: "UNKNOWN", 0: "less-liquid", 1: "liquid"}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.corrcoef(x, y)[0, 1])


def summarize(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "mean": None, "median": None, "q25": None,
                "q75": None, "min": None, "max": None}
    a = np.asarray(vals, dtype=np.float64)
    q = np.percentile(a, [25, 50, 75])
    return {"n": int(len(a)), "mean": round(float(a.mean()), 4),
            "median": round(float(q[1]), 4), "q25": round(float(q[0]), 4),
            "q75": round(float(q[2]), 4),
            "min": round(float(a.min()), 4), "max": round(float(a.max()), 4)}


def dist_bins(vals: list[float]) -> dict:
    bins = {"lt_0": 0, "0_to_0p25": 0, "0p25_to_0p50": 0,
            "0p50_to_0p75": 0, "ge_0p75": 0}
    for v in vals:
        if v < 0:
            bins["lt_0"] += 1
        elif v < 0.25:
            bins["0_to_0p25"] += 1
        elif v < 0.50:
            bins["0p25_to_0p50"] += 1
        elif v < 0.75:
            bins["0p50_to_0p75"] += 1
        else:
            bins["ge_0p75"] += 1
    n = len(vals) or 1
    return {k: {"n": v, "frac": round(v / n, 3)} for k, v in bins.items()}


def main() -> int:
    # ── P5.4.1 hash checks ────────────────────────────────────────────────
    with open(PROTOCOL_PATH, encoding="utf-8") as fh:
        protocol = json.load(fh)
    with open(BASELINE_JSON, encoding="utf-8") as fh:
        bl = json.load(fh)
    ranks_sha_now = sha256_file(RANKS_PATH)
    ranks_sha_frozen = bl["rank_cache_hash"]
    hash_ok = ranks_sha_now == ranks_sha_frozen
    ds_ok = bl["dataset_hash"] == protocol["dataset"]["dataset_sha256"]
    if not hash_ok or not ds_ok:
        print(f"STOP: hash mismatch (cache {ranks_sha_now[:16]} vs "
              f"{ranks_sha_frozen[:16]}; dataset {ds_ok})")
        return 1
    print(f"P5.4.1 cache hash OK ({ranks_sha_now[:16]}...) — no rebuild")

    z = np.load(RANKS_PATH, allow_pickle=True)
    X = z["cache"]
    dates = np.unique(X[:, C["date"]].astype(np.int64))

    # ── helper: dependency atas subset rows ───────────────────────────────
    def dependency(rows: np.ndarray, m_col_rank: int, m_col_top5: int,
                   m_col_top10: int, label: str) -> dict:
        rho_vals: list[float] = []
        n_pairs_list: list[int] = []
        ov5: list[float] = []
        ov10: list[float] = []
        jac5: list[float] = []
        jac10: list[float] = []
        n_rho_insuf = 0
        n_topk_insuf = 0
        n_zero_pairs = 0
        for dd in dates:
            sub = rows[rows[:, C["date"]].astype(np.int64) == dd]
            elig = sub[:, C["eligible"]] == 1.0
            sub = sub[elig]
            if len(sub) == 0:
                continue
            rr = sub[:, C["rank_rtf"]]
            rm = sub[:, m_col_rank]
            both = (rr > 0) & (rm > 0)
            np_ = int(both.sum())
            if np_ > 0:
                n_pairs_list.append(np_)
            else:
                n_zero_pairs += 1
            if np_ >= 2:
                rho_vals.append(spearman(rr[both], rm[both]))
            else:
                n_rho_insuf += 1
            for col, ov, jac, K in ((m_col_top5, ov5, jac5, 5),
                                    (m_col_top10, ov10, jac10, 10)):
                a = set(np.where(sub[:, C["top5_rtf"]] == 1.0)[0]) if K == 5 \
                    else set(np.where(sub[:, C["top10_rtf"]] == 1.0)[0])
                b = set(np.where(sub[:, col] == 1.0)[0])
                if len(a) < K:
                    n_topk_insuf += 1  # top-K RTF tak lengkap (tiap K dihitung sekali)
                inter = len(a & b)
                ov.append(inter / K)
                union = len(a | b)
                jac.append(inter / union if union else 0.0)
        return {
            "label": label,
            "spearman": {**summarize(rho_vals),
                         "bins": dist_bins(rho_vals)},
            "overlap_at_5": summarize(ov5),
            "overlap_at_10": summarize(ov10),
            "jaccard_at_5": summarize(jac5),
            "jaccard_at_10": summarize(jac10),
            "n_pairs_per_date": summarize(n_pairs_list),
            "n_dates_zero_pairs": n_zero_pairs,
            "n_dates_insufficient_rho": n_rho_insuf,
            "n_dates_topk_incomplete": n_topk_insuf,
        }

    # ── P5.4.2/3/5/6 main: RTF vs M5, RTF vs M10 (date-level) ─────────────
    rtf_m5 = dependency(X, C["rank_m5"], C["top5_m5"], C["top10_m5"], "RTF vs M5")
    rtf_m10 = dependency(X, C["rank_m10"], C["top5_m10"], C["top10_m10"], "RTF vs M10")

    # ── P5.4.7 pooled (SECONDARY only) ────────────────────────────────────
    def pooled(m_col_rank: int) -> float | None:
        elig = X[:, C["eligible"]] == 1.0
        rr = X[elig, C["rank_rtf"]]
        rm = X[elig, m_col_rank]
        both = (rr > 0) & (rm > 0)
        n = int(both.sum())
        if n < 2:
            return None
        return round(spearman(rr[both], rm[both]), 4)

    pooled_m5 = pooled(C["rank_m5"])
    pooled_m10 = pooled(C["rank_m10"])

    # ── cell-level rho (date x segment) utk breakdown — TANPA modus ───────
    def cell_rho(col: int) -> dict:
        """rho per cell (date, segment): pairs dlm subset segment tsb.
        Menjawab langsung 'di segment mana independence muncul' — tidak
        mengubah definisi top-K global."""
        cells: dict[int, dict[str, list]] = {}
        for dd in dates:
            idx = np.where((X[:, C["date"]].astype(np.int64) == dd)
                           & (X[:, C["eligible"]] == 1.0))[0]
            if len(idx) == 0:
                continue
            for seg in np.unique(X[idx, col].astype(int)):
                sub = idx[X[idx, col].astype(int) == int(seg)]
                out = cells.setdefault(int(seg), {"m5": [], "m10": []})
                for key, mc in (("m5", C["rank_m5"]), ("m10", C["rank_m10"])):
                    rr = X[sub, C["rank_rtf"]]
                    rm = X[sub, mc]
                    both = (rr > 0) & (rm > 0)
                    n = int(both.sum())
                    if n >= 2:
                        out[key].append(spearman(rr[both], rm[both]))
        return cells

    regime_cells = cell_rho(C["regime"])
    liq_cells = cell_rho(C["liq"])

    def cell_block(cells: dict, names: dict) -> dict:
        out = {}
        for seg, v in sorted(cells.items()):
            nm = names.get(int(seg), f"seg{seg}")
            out[nm] = {"rtf_m5": summarize(v["m5"]), "rtf_m10": summarize(v["m10"])}
        return out

    # ── P5.4.8 regime breakdown (date-level modus, existing def) ──────────
    def date_group(col: int) -> dict[int, np.ndarray]:
        """Peta date -> array index rows; group label = modus kolom pada
        eligible rows; tie -> MIXED."""
        groups: dict[int, list[int]] = {}
        for dd in dates:
            idx = np.where((X[:, C["date"]].astype(np.int64) == dd)
                           & (X[:, C["eligible"]] == 1.0))[0]
            if len(idx) == 0:
                continue
            cnt = Counter(X[idx, col].astype(int).tolist())
            top2 = cnt.most_common(2)
            lab = top2[0][0] if len(top2) == 1 or top2[0][1] > top2[1][1] else "MIXED"
            groups.setdefault(lab, []).extend(idx.tolist())
        return {k: np.asarray(v, dtype=np.int64) for k, v in groups.items()}

    regime_grp = date_group(C["regime"])
    liq_grp = date_group(C["liq"])

    def breakdown(grp: dict, names: dict) -> dict:
        out = {}
        for lab, idx in sorted(grp.items(), key=lambda kv: (isinstance(kv[0], str), kv[0])):
            nm = names.get(lab, "MIXED") if not isinstance(lab, str) else "MIXED"
            rows = X[idx]
            out[nm] = {
                "n_rows": int(len(rows)),
                "n_dates": int(len(np.unique(rows[:, C["date"]].astype(np.int64)))),
                "rtf_m5": dependency(rows, C["rank_m5"], C["top5_m5"], C["top10_m5"],
                                     "RTF vs M5")["spearman"],
                "rtf_m10": dependency(rows, C["rank_m10"], C["top5_m10"], C["top10_m10"],
                                      "RTF vs M10")["spearman"],
                "overlap_at_5": {
                    "rtf_m5": dependency(rows, C["rank_m5"], C["top5_m5"], C["top10_m5"],
                                         "RTF vs M5")["overlap_at_5"],
                    "rtf_m10": dependency(rows, C["rank_m10"], C["top5_m10"], C["top10_m10"],
                                          "RTF vs M10")["overlap_at_5"]},
                "overlap_at_10": {
                    "rtf_m5": dependency(rows, C["rank_m5"], C["top5_m5"], C["top10_m5"],
                                         "RTF vs M5")["overlap_at_10"],
                    "rtf_m10": dependency(rows, C["rank_m10"], C["top5_m10"], C["top10_m10"],
                                          "RTF vs M10")["overlap_at_10"]},
            }
        return out

    # efisiensi: hitung sekali per (rows, model) lalu pakai
    def dep_compact(rows: np.ndarray, m_col_rank: int, m_top5: int,
                    m_top10: int) -> dict:
        d = dependency(rows, m_col_rank, m_top5, m_top10, "")
        return {"spearman": d["spearman"], "overlap_at_5": d["overlap_at_5"],
                "overlap_at_10": d["overlap_at_10"]}

    regime_out = {}
    for lab, idx in sorted(regime_grp.items(),
                           key=lambda kv: (isinstance(kv[0], str), str(kv[0]))):
        nm = REGIME_NAMES.get(lab, "MIXED") if not isinstance(lab, str) else "MIXED"
        rows = X[idx]
        regime_out[nm] = {
            "n_rows": int(len(rows)),
            "n_dates": int(len(np.unique(rows[:, C["date"]].astype(np.int64)))),
            "rtf_m5": dep_compact(rows, C["rank_m5"], C["top5_m5"], C["top10_m5"]),
            "rtf_m10": dep_compact(rows, C["rank_m10"], C["top5_m10"], C["top10_m10"]),
        }

    liq_out = {}
    for lab, idx in sorted(liq_grp.items(),
                           key=lambda kv: (isinstance(kv[0], str), str(kv[0]))):
        nm = LIQ_NAMES.get(lab, "MIXED") if not isinstance(lab, str) else "MIXED"
        rows = X[idx]
        liq_out[nm] = {
            "n_rows": int(len(rows)),
            "n_dates": int(len(np.unique(rows[:, C["date"]].astype(np.int64)))),
            "rtf_m5": dep_compact(rows, C["rank_m5"], C["top5_m5"], C["top10_m5"]),
            "rtf_m10": dep_compact(rows, C["rank_m10"], C["top5_m10"], C["top10_m10"]),
        }

    # ── P5.4.11 target dependency: deferred (AUC di P5.6) ─────────────────
    # ── holdout untouched ─────────────────────────────────────────────────
    out = {
        "phase": "P5.4 Dependency Audit",
        "status": "PASS",
        "checked_at": dt.date.today().isoformat(),
        "cache_hash": ranks_sha_now,
        "cache_hash_matches_p53": hash_ok,
        "dataset_hash_matches_protocol": ds_ok,
        "n_dates": int(len(dates)),
        "method": {
            "primary": "date-level (cross-sectional per tanggal); Spearman "
                       "pada ranks (unique per date); intersection "
                       "U_t^{RTF cap M} = rank_rtf>0 & rank_m>0",
            "rtf_rankable": "rtf_score > 0 (P5.3); NaN & score-0 TIDAK masuk, "
                            "tidak di-zero",
            "overlap": "|TopK_RTF ∩ TopK_M| / K, K fixed; Jaccard = "
                       "diagnostic tambahan",
            "regime_liq_group": "date-level modus pada eligible rows (existing "
                                "definitions); tie -> MIXED; UNKNOWN tetap "
                                "UNKNOWN (tidak dipaksa)",
            "pooled": "SECONDARY diagnostic only — tidak menggantikan "
                      "date-level",
        },
        "rtf_m5": rtf_m5,
        "rtf_m10": rtf_m10,
        "pooled_secondary": {
            "spearman_rtf_m5": pooled_m5,
            "spearman_rtf_m10": pooled_m10,
            "note": "satu rho atas semua OOS rows (bukan primary)",
        },
        "regime": regime_out,
        "liquidity": liq_out,
        "regime_cell_rho": cell_block(regime_cells, REGIME_NAMES),
        "liquidity_cell_rho": cell_block(liq_cells, LIQ_NAMES),
        "breakdown_method": {
            "regime_liq_group": "date-level modus pada eligible rows (existing "
                                "definitions); tie -> MIXED; UNKNOWN tetap "
                                "UNKNOWN; utk overlap@K & interpretasi",
            "cell_rho": "Spearman pairwise per (date, segment) cell — primary "
                        "utk segment dependency; tidak mengubah top-K global",
            "caution": "rho ±1 pada cell kecil (n_pairs=2) adalah artefak "
                       "ukuran sample — baca median/IQR & n_pairs, bukan "
                       "min/max; bull/less-liquid dgn n_dates kecil = "
                       "INSUFFICIENT utk kesimpulan",
        },
        "target_dependency": {
            "deferred_to_p56": "AUC (Phase 3/5 metric) dihitung di P5.6; "
                               "P5.4 bukan performance test",
        },
        "interpretation_cases": {
            "A_high_dependency": "rho tinggi + overlap tinggi -> RTF mirip "
                                 "recent-return signal; combination mungkin "
                                 "redundant",
            "B_low_dep_both_predictive": "rho/overlap rendah + RTF > random + "
                                         "M5/M10 > random -> complementary; "
                                         "P5.5 justified",
            "C_low_dep_rtf_weak": "independence bukan berarti usefulness",
            "D_conditional": "dependency berbeda per regime/liquidity -> "
                             "hypothesis utk future; BELUM boleh regime-"
                             "specific weighting",
        },
        "no_model_selection": True,
        "no_config_modification": True,
        "phase4_holdout_untouched": True,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    # ── console ───────────────────────────────────────────────────────────
    print(f"\nP5.4 status: {out['status']}  -> {OUT_PATH}")
    for key, d in (("rtf_m5", rtf_m5), ("rtf_m10", rtf_m10)):
        s = d["spearman"]
        print(f"\n{key}: spearman median={s['median']} q25={s['q25']} q75={s['q75']} "
              f"mean={s['mean']} min={s['min']} max={s['max']} n_dates={s['n']}")
        print(f"   bins: {dist_bins_compact(s['bins'])}")
        o5, o10 = d["overlap_at_5"], d["overlap_at_10"]
        print(f"   overlap@5: median={o5['median']} q25={o5['q25']} q75={o5['q75']}")
        print(f"   overlap@10: median={o10['median']} q25={o10['q25']} q75={o10['q75']}")
        print(f"   n_pairs/date: median={d['n_pairs_per_date']['median']} "
              f"min={d['n_pairs_per_date']['min']} max={d['n_pairs_per_date']['max']} "
              f"zero_pairs={d['n_dates_zero_pairs']} "
              f"insuf_rho={d['n_dates_insufficient_rho']} "
              f"topk_incomplete={d['n_dates_topk_incomplete']}")
    print(f"\npooled (secondary): RTF-M5 {pooled_m5} | RTF-M10 {pooled_m10}")
    print("regime breakdown (median rho):")
    for nm, v in regime_out.items():
        print(f"  {nm:<10} rtf_m5={v['rtf_m5']['spearman']['median']} "
              f"rtf_m10={v['rtf_m10']['spearman']['median']} "
              f"ov5_m5={v['rtf_m5']['overlap_at_5']['median']} "
              f"ov5_m10={v['rtf_m10']['overlap_at_5']['median']} "
              f"(dates={v['n_dates']}, rows={v['n_rows']})")
    print("regime cell-rho (pairwise per date x regime):")
    for nm, v in cell_block(regime_cells, REGIME_NAMES).items():
        print(f"  {nm:<10} m5 median={v['rtf_m5']['median']} (n={v['rtf_m5']['n']}) "
              f"| m10 median={v['rtf_m10']['median']} (n={v['rtf_m10']['n']})")
    print("liquidity breakdown (median rho):")
    for nm, v in liq_out.items():
        print(f"  {nm:<12} rtf_m5={v['rtf_m5']['spearman']['median']} "
              f"rtf_m10={v['rtf_m10']['spearman']['median']} "
              f"ov5_m5={v['rtf_m5']['overlap_at_5']['median']} "
              f"ov5_m10={v['rtf_m10']['overlap_at_5']['median']} "
              f"(dates={v['n_dates']}, rows={v['n_rows']})")
    print("liquidity cell-rho (pairwise per date x liq):")
    for nm, v in cell_block(liq_cells, LIQ_NAMES).items():
        print(f"  {nm:<12} m5 median={v['rtf_m5']['median']} (n={v['rtf_m5']['n']}) "
              f"| m10 median={v['rtf_m10']['median']} (n={v['rtf_m10']['n']})")
    return 0 if out["status"] == "PASS" else 1


def dist_bins_compact(bins: dict) -> str:
    return " ".join(f"{k.split('_')[0]}{k.split('_')[-1] if '_' in k else ''}:"
                    f"{v['n']}" for k, v in bins.items())


if __name__ == "__main__":
    raise SystemExit(main())