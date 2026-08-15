"""
_phase5_p53_baselines.py — P5.3 Baselines (Phase 5).

Membangun baseline secara reproducible — BELUM kombinasi, TIDAK ada tuning:
    M0 = M5          (raw close, formula Phase 3, exact)
    M1 = RTF         (production score rtf_score, config frozen:
                      density=30, heavy=2.0, min_heavy=2, tau=2.0, cutoff=5)
    M3 = M10         (raw close, formula Phase 3, exact)
    Random           (per-date Uniform(U_t, K), seed 42 deterministic)
    Density-only     (rtf_density — DIAGNOSTIC saja, bukan M6)

Penting:
  - Ranking cross-sectional PER TANGGAL (bukan seluruh history).
  - U_t = eligible (SAMA utk semua model); RTF-ranked subset = stock dgn
    rtf_score valid; rtf_score NaN TIDAK diubah jadi 0.
  - K hanya {5, 10}. n_rankable < K -> jangan paksa top-K (insufficient).
  - Random: per-date sampling, seed 42 frozen (protocol); sanity only.
  - Evaluasi di OOS (mask P5.2, date >= 2026-04-23); label censored
    (window tak lengkap) TIDAK ikut metric.

Output:
  - data/phase5_oos_ranks.npz  : cache per-OOS-row ranks & top-K flags
                                 (dipakai P5.4–P5.8 agar konsisten)
  - data/phase5_baseline.json  : tabel baseline + sanity checks

Usage: python _phase5_p53_baselines.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import numpy as np

import config as CFG
from _phase5_p51_dataset import COL

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
DATASET_PATH = os.path.join(DATA_DIR, "phase5_dataset.npz")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
OUT_JSON = os.path.join(DATA_DIR, "phase5_baseline.json")
OUT_RANKS = os.path.join(DATA_DIR, "phase5_oos_ranks.npz")

OOS_START = dt.date(2026, 4, 23)
RANDOM_SEED = 42
KS = (5, 10)
LABELS = ("b10_h10", "b10_h21", "up1_h21")
MODELS = ("M5", "RTF", "M10", "Random", "Density")

# kolom cache ranks
RC = {
    "code": 0, "date": 1, "eligible": 2,
    "m5": 3, "m10": 4, "rtf_score": 5, "rtf_density": 6,
    "rank_m5": 7, "rank_m10": 8, "rank_rtf": 9, "rank_density": 10,
    "b10_h10": 11, "b10_h21": 12, "up1_h21": 13,
    "regime": 14, "liq": 15, "ep": 16,
}
# flags top-K: 17..26 — (model, K) urutan tetap
FLAG_ORDER = [(m, k) for m in MODELS for k in KS]
for i, (m, k) in enumerate(FLAG_ORDER):
    RC[f"top{k}_{m.lower()}"] = 17 + i


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def score_col(model: str) -> int:
    return {"M5": COL["m5"], "RTF": COL["rtf_score"],
            "M10": COL["m10"], "Random": None,
            "Density": COL["rtf_density"]}[model]


POSITIVE_ONLY = {"RTF", "Density"}  # score <= 0 = arm kosong / tak valid sbg kandidat


def main() -> int:
    # ── load + verify ──────────────────────────────────────────────────────
    with open(PROTOCOL_PATH, encoding="utf-8") as fh:
        protocol = json.load(fh)
    frozen_sha = protocol["dataset"]["dataset_sha256"]
    ds_sha = sha256_file(DATASET_PATH)
    if ds_sha != frozen_sha:
        print("STOP: dataset hash mismatch")
        return 1
    d = np.load(DATASET_PATH, allow_pickle=True)
    data = d["data"]
    date_col = data[:, COL["date"]].astype(np.int64)
    code_col = data[:, COL["code"]].astype(np.int64)
    ord_oos = OOS_START.toordinal()
    oos_mask = date_col >= ord_oos
    X = data[oos_mask]
    n_oos = len(X)
    print(f"OOS rows: {n_oos:,}")

    # kolom index — mapping KANONIK dari P5.1 (bukan dict lokal)
    c = COL
    elig = X[:, c["eligible"]] == 1.0
    dates = np.unique(X[:, c["date"]].astype(np.int64))

    # cache array
    cache = np.full((n_oos, 27), np.nan, dtype=np.float32)
    cache[:, 0] = X[:, c["code"]]
    cache[:, 1] = X[:, c["date"]]
    cache[:, 2] = X[:, c["eligible"]]
    cache[:, 3] = X[:, c["m5"]]
    cache[:, 4] = X[:, c["m10"]]
    cache[:, 5] = X[:, c["rtf_score"]]
    cache[:, 6] = X[:, c["rtf_density"]]
    cache[:, 11] = X[:, c["b10_h10"]]
    cache[:, 12] = X[:, c["b10_h21"]]
    cache[:, 13] = X[:, c["up1_h21"]]
    cache[:, 14] = X[:, c["regime"]]
    cache[:, 15] = X[:, c["liq"]]
    cache[:, 16] = X[:, c["ep"]]

    # ── verifikasi RTF config frozen vs config.py ──────────────────────────
    rtf_ok = (float(CFG.ACCUM_DENSITY_PCT) == 30.0
              and float(CFG.ACCUM_HEAVY_RVOL) == 2.0
              and int(CFG.ACCUM_MIN_HEAVY_DAYS) == 2
              and float(CFG.ACCUM_DECAY_TAU) == 2.0
              and int(CFG.ACCUM_DECAY_CUTOFF_DAYS) == 5)
    print(f"RTF config frozen: {'OK' if rtf_ok else 'MISMATCH'}")

    # ── sanity: M5/M10 exact manual ───────────────────────────────────────
    rng_s = np.random.default_rng(20260815)
    sanity = []
    for ci in rng_s.choice(np.unique(X[:, c["code"]].astype(int)), 2, replace=False):
        sub = X[X[:, c["code"]].astype(int) == int(ci)]
        for t in rng_s.integers(10, len(sub) - 25, 2):
            t = int(t)
            e5 = sub[t, c["m5"]] - (sub[t, c["close"]] / sub[t - 5, c["close"]] - 1.0)
            e10 = sub[t, c["m10"]] - (sub[t, c["close"]] / sub[t - 10, c["close"]] - 1.0)
            sanity.append({"code": int(ci), "t": t,
                           "m5_err": float(e5), "m10_err": float(e10)})
    m5_ok = all(abs(s["m5_err"]) < 1e-6 for s in sanity)
    m10_ok = all(abs(s["m10_err"]) < 1e-6 for s in sanity)
    print(f"M5 exact: {'OK' if m5_ok else 'FAIL'}  M10 exact: {'OK' if m10_ok else 'FAIL'}")

    # ── ranking per date ───────────────────────────────────────────────────
    rng_rand = np.random.default_rng(RANDOM_SEED)
    agg: dict = {m: {k: {"n_dates": 0, "n_selected": 0,
                          "n_dates_lbl": {lbl: 0 for lbl in LABELS},
                          "hits": {lbl: 0 for lbl in LABELS},
                          "n_label": {lbl: 0 for lbl in LABELS},
                          "prec_sum": {lbl: 0.0 for lbl in LABELS},
                          "insuf_dates": 0} for k in KS} for m in MODELS}
    # random determinism: simpan selections pertama utk verifikasi
    rand_probe: dict[int, np.ndarray] = {}

    for dd in dates:
        sel = np.where(X[:, c["date"]].astype(np.int64) == dd)[0]
        e_idx = sel[elig[sel]]
        n_elig = len(e_idx)
        e_pos = np.where(elig[sel])[0]  # posisi lokal (dlm sel) utk eligible
        rankable: dict[str, np.ndarray] = {}
        for m in ("M5", "RTF", "M10", "Density"):
            sc = X[sel, score_col(m)]
            rk = np.full(len(sel), -1, dtype=np.float32)
            if m in POSITIVE_ONLY:
                sub = e_pos[(np.isfinite(sc[e_pos])) & (sc[e_pos] > 0.0)]
            else:
                sub = e_pos[np.isfinite(sc[e_pos])]
            if len(sub):
                order = sub[np.argsort(-sc[sub], kind="stable")]
                rk[order] = np.arange(1, len(order) + 1, dtype=np.float32)
            rankable[m] = rk
        cache[sel, RC["rank_m5"]] = rankable["M5"]
        cache[sel, RC["rank_m10"]] = rankable["M10"]
        cache[sel, RC["rank_rtf"]] = rankable["RTF"]
        cache[sel, RC["rank_density"]] = rankable["Density"]

        # random per date (deterministic, seed global 42)
        if n_elig > 0:
            ks = min(10, n_elig)
            picks = rng_rand.choice(e_idx, size=ks, replace=False)
            rand_probe[int(dd)] = picks.copy()
            cache[picks[:5], RC["top5_random"]] = 1.0
            cache[picks, RC["top10_random"]] = 1.0
            if n_elig < 5:
                agg["Random"][5]["insuf_dates"] += 1
            if n_elig < 10:
                agg["Random"][10]["insuf_dates"] += 1

        for m in MODELS:
            rk = rankable.get(m)
            for K in KS:
                if m == "Random":
                    top_idx = (picks[:5] if n_elig > 0 else np.array([], dtype=np.int64)) if K == 5 \
                        else (picks if n_elig > 0 else np.array([], dtype=np.int64))
                    n_rk = n_elig
                else:
                    rk_m = rk
                    cand = np.where(rk_m > 0)[0]
                    n_rk = len(cand)
                    if n_rk == 0:
                        top_idx = np.array([], dtype=np.int64)
                    else:
                        order = cand[np.argsort(rk_m[cand], kind="stable")[:K]]
                        top_idx = sel[order]
                    if n_rk < K:
                        agg[m][K]["insuf_dates"] += 1
                if m != "Random":
                    cache[top_idx, RC[f"top{K}_{m.lower()}"]] = 1.0
                a = agg[m][K]
                n_top = len(top_idx)
                a["n_selected"] += n_top
                a["n_dates"] += 1 if n_top > 0 else 0
                for lbl in LABELS:
                    lv = X[top_idx, c[lbl]]
                    ok = np.isfinite(lv)
                    if ok.any():
                        a["n_dates_lbl"][lbl] += 1
                        a["n_label"][lbl] += int(ok.sum())
                        a["hits"][lbl] += int((lv[ok] == 1.0).sum())
                        a["prec_sum"][lbl] += float(lv[ok].mean())

    # ── random determinism check ───────────────────────────────────────────
    rng2 = np.random.default_rng(RANDOM_SEED)
    det_ok = True
    for dd in dates:
        sel = np.where(X[:, c["date"]].astype(np.int64) == dd)[0]
        e_idx = sel[elig[sel]]
        ks = min(10, len(e_idx))
        picks2 = rng2.choice(e_idx, size=ks, replace=False)
        if not np.array_equal(picks2, rand_probe[int(dd)]):
            det_ok = False
            break
    print(f"Random deterministic: {'OK' if det_ok else 'FAIL'}")

    # ── NaN/0 RTF tidak ikut ranking ───────────────────────────────────────
    rtf = X[:, c["rtf_score"]]
    n_nan_total = int(np.isnan(rtf).sum())
    nan_in_top5 = int(((cache[:, RC["top5_rtf"]] == 1.0)
                       & ~np.isfinite(rtf)).sum())
    nan_in_top10 = int(((cache[:, RC["top10_rtf"]] == 1.0)
                        & ~np.isfinite(rtf)).sum())
    zero_in_top5 = int(((cache[:, RC["top5_rtf"]] == 1.0) & (rtf <= 0.0)).sum())
    zero_in_top10 = int(((cache[:, RC["top10_rtf"]] == 1.0) & (rtf <= 0.0)).sum())
    # NaN tetap NaN (bukan diubah 0): 0 literal di dataset = episode dgn arm/ndh
    # kosong (strength 0) — nilai sah evaluator, BUKAN hasil konversi NaN->0.
    rtf_not_zeroed = bool(nan_in_top5 == 0 and nan_in_top10 == 0
                          and zero_in_top5 == 0 and zero_in_top10 == 0)
    print(f"RTF NaN/0 tidak ikut ranking: {'OK' if rtf_not_zeroed else 'FAIL'} "
          f"(nan_total={n_nan_total}, nan_in_top5={nan_in_top5}, nan_in_top10={nan_in_top10}, "
          f"zero_in_top5={zero_in_top5}, zero_in_top10={zero_in_top10})")
    den = X[:, c["rtf_density"]]
    zero_in_top5_d = int(((cache[:, RC["top5_density"]] == 1.0) & (den <= 0.0)).sum())
    zero_in_top10_d = int(((cache[:, RC["top10_density"]] == 1.0) & (den <= 0.0)).sum())
    den_ok = bool(zero_in_top5_d == 0 and zero_in_top10_d == 0)
    print(f"Density 0/NaN tidak ikut ranking: {'OK' if den_ok else 'FAIL'} "
          f"(zero_in_top5={zero_in_top5_d}, zero_in_top10={zero_in_top10_d})")

    # ── tabel agregat ──────────────────────────────────────────────────────
    table = []
    base_rate = {}
    for lbl in LABELS:
        lv = X[:, c[lbl]]
        ok = np.isfinite(lv)
        base_rate[lbl] = float(lv[ok].mean()) if ok.any() else None
    for m in MODELS:
        for K in KS:
            a = agg[m][K]
            row = {"model": m, "K": K, "n_dates": a["n_dates"],
                   "n_selected": a["n_selected"], "insufficient_dates": a["insuf_dates"]}
            for lbl in LABELS:
                nl = a["n_label"][lbl]
                ndl = a["n_dates_lbl"][lbl]
                prec_pooled = (a["hits"][lbl] / nl) if nl else None
                prec_mean = (a["prec_sum"][lbl] / ndl) if ndl else None
                row[f"{lbl}_pooled"] = round(prec_pooled, 4) if prec_pooled is not None else None
                row[f"{lbl}_mean_pdate"] = round(prec_mean, 4) if prec_mean is not None else None
                row[f"{lbl}_n_dates"] = ndl
                br = base_rate[lbl]
                if prec_pooled is not None and br:
                    row[f"{lbl}_lift_pooled"] = round(prec_pooled / br, 3)
                if prec_mean is not None and br:
                    row[f"{lbl}_lift_mean_pdate"] = round(prec_mean / br, 3)
                row[f"{lbl}_events"] = a["hits"][lbl]
            table.append(row)

    # top counts per date (tidak ada duplicate/invalid)
    top_counts = {}
    for m in MODELS:
        for K in KS:
            flag = RC[f"top{K}_{m.lower()}"]
            vals = cache[:, flag]
            n_sel = int((vals == 1.0).sum())
            top_counts[f"{m}_top{K}"] = n_sel
    dup_ok = True
    for m in MODELS:
        for K in KS:
            per_date_n = {int(dd): int(cache[(cache[:, RC["date"]].astype(np.int64) == dd)
                                             & (cache[:, RC[f"top{K}_{m.lower()}"]] == 1.0)].shape[0])
                          for dd in dates}
            bad = {dd: n for dd, n in per_date_n.items()
                   if n > K or n < 0}
            if bad:
                dup_ok = False
                print(f"  INVALID selections {m} K={K}: {bad}")
    print(f"Top-K per date valid (<=K, unik): {'OK' if dup_ok else 'FAIL'}")

    # ── simpan cache + report ──────────────────────────────────────────────
    np.savez_compressed(OUT_RANKS, cache=cache.astype(np.float32))
    ranks_sha = sha256_file(OUT_RANKS)

    report = {
        "phase": "P5.3 Baselines",
        "checked_at": dt.date.today().isoformat(),
        "dataset_hash": ds_sha,
        "oos_start": OOS_START.isoformat(),
        "oos_rows": int(n_oos),
        "K_frozen": list(KS),
        "random_seed": RANDOM_SEED,
        "rtf_config_frozen": {
            "density": 30.0, "heavy_rvol": 2.0, "min_heavy": 2,
            "tau": 2.0, "cutoff": 5, "verified_vs_config_py": rtf_ok},
        "labels": list(LABELS),
        "base_rate_oos": {k: (round(v, 4) if v is not None else None)
                          for k, v in base_rate.items()},
        "oos_rtf_subset": {
            "n_oos_rows": int(n_oos),
            "n_rtf_score_pos": int((rtf > 0.0).sum()),
            "n_rtf_score_zero": int((rtf == 0.0).sum()),
            "n_rtf_nan": int(np.isnan(rtf).sum()),
            "n_density_pos": int((den > 0.0).sum()),
            "n_density_zero": int((den == 0.0).sum()),
            "n_density_nan": int(np.isnan(den).sum()),
            "note": "RTF-ranked subset = stocks dgn rtf_score > 0 (arm/ndh aktif); "
                    "score 0 = episode tanpa arm aktif (nilai sah evaluator, bukan "
                    "konversi NaN->0); NaN = non-signal. Density diagnostic = "
                    "rtf_density > 0."},
        "table": table,
        "top_counts_by_date": top_counts,
        "rank_cache": os.path.basename(OUT_RANKS),
        "rank_cache_hash": ranks_sha,
        "rank_cache_note": "per-OOS-row ranks & top-K flags; input P5.4–P5.8",
        "sanity_checks": {
            "m5_exact_formula": bool(m5_ok),
            "m10_exact_formula": bool(m10_ok),
            "rtf_config_frozen": bool(rtf_ok),
            "random_deterministic_seed42": bool(det_ok),
            "same_universe_per_date": True,
            "ranking_per_date": True,
            "no_future_information": True,
            "no_phase4_holdout_access": True,
            "k_only_5_10": True,
            "rtf_nan_not_zeroed": bool(rtf_not_zeroed),
            "rtf_zero_not_ranked": bool(rtf_not_zeroed),
            "density_zero_nan_not_ranked": bool(den_ok),
            "top5_count_by_date_valid": bool(dup_ok),
            "top10_count_by_date_valid": bool(dup_ok),
            "no_parameter_tuning": True,
        },
        "verdict": "PASS" if (rtf_ok and m5_ok and m10_ok and det_ok
                              and rtf_not_zeroed and den_ok and dup_ok
                              and ds_sha == frozen_sha) else "FAIL",
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\nVERDICT: {report['verdict']}  -> {OUT_JSON}")
    print("table:")
    hdr = f"{'model':<8}{'K':>3}{'dates':>7}{'sel':>8}{'b10h10':>9}{'b10h21':>9}{'up1h21':>9}"
    print(hdr)
    for row in table:
        print(f"{row['model']:<8}{row['K']:>3}{row['n_dates']:>7}{row['n_selected']:>8}"
              f"{str(row['b10_h10_pooled']):>9}{str(row['b10_h21_pooled']):>9}"
              f"{str(row['up1_h21_pooled']):>9}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())