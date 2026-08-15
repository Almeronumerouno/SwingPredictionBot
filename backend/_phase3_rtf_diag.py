"""
_phase3_rtf_diag.py — Diagnostic: stabilitas orientasi strength (read-only).

Menjawab pertanyaan user (verdict Phase 3, poin #4):
  "apakah inverse relationship strength -> up1 stabil di TRAIN dan OOS,
   antar stock, dan antar regime?"

Analisis (TIDAK ada pemilihan parameter — murni diagnostik):
  1. AUC strength -> up1_21 & b10_21 (juga up1_10/b10_10) di TRAIN vs OOS,
     untuk score FULL (density*ndh*decay) dan density-only.
  2. Per-kode: distribusi AUC per kode (>=20 sinyal valid) — fraksi kode
     dengan orientasi inverse (AUC<0.5) vs positif (AUC>0.5).
  3. Per-kuartal (proxy regime temporal): AUC per kuartal kalender.

Config evaluasi: winner tuning (density 50, mult 2.0, mh 2, tau 2, cutoff None).

Output: data/phase3_rtf_diag.json
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import numpy as np

import _phase3_rtf_common as C

MIN_PER_KODE = 20
MIN_PER_QUARTER = 50


def _auc(rows, mask, score, label, h):
    return C.auc_score(rows, mask, score, label, h)


def main() -> None:
    rows, codes, code_idx = C.load_rows()
    dates_dt = C.row_dates(codes, rows, code_idx)
    split = C.make_split(codes, rows, code_idx, dates_dt)
    train, test = split["train"], split["test"]

    mult = 2.0
    cfg = C.selected_config(50.0, mult, 2, 2.0, None)
    arm = C.arm_mask(rows, cfg["ACCUM_DENSITY_PCT"], cfg["ACCUM_HEAVY_RVOL"],
                     cfg["ACCUM_MIN_HEAVY_DAYS"])
    m = int(C.MULT_GRID.index(mult))
    score_full = C.strength_score(rows, mult, 2.0, None)
    score_den = rows[:, C.I_DEN0 + m].astype(np.float64)

    targets = [("up1", 21), ("up1", 10), ("b10", 21), ("b10", 10)]

    # ── 1) TRAIN vs OOS ──
    train_oos = {}
    for score_name, sc in (("full", score_full), ("density_only", score_den)):
        block = {}
        for label, h in targets:
            block[f"{label}_{h}"] = {
                "train": _auc(rows, arm & train, sc, label, h),
                "oos": _auc(rows, arm & test, sc, label, h),
            }
        train_oos[score_name] = block

    # ── 2) per-kode (up1_21, full & density) ──
    n_stocks = int(code_idx.max()) + 1
    per_code = {"full": [], "density_only": []}
    for i in range(n_stocks):
        cm = (code_idx == i) & arm
        for score_name, sc in (("full", score_full), ("density_only", score_den)):
            sel = cm & np.isfinite(sc) & np.isfinite(rows[:, C.label_col("up1", 21)])
            if int(sel.sum()) < MIN_PER_KODE:
                continue
            y = rows[sel, C.label_col("up1", 21)]
            if len(set(y.tolist())) < 2:
                continue
            from sklearn.metrics import roc_auc_score
            per_code[score_name].append(float(roc_auc_score(y, sc[sel])))
    per_code_summary = {}
    for score_name, vals in per_code.items():
        arr = np.asarray(vals)
        per_code_summary[score_name] = {
            "n_codes": int(len(arr)),
            "median_auc": round(float(np.median(arr)), 4) if len(arr) else None,
            "frac_inverse_lt_0.5": round(float(np.mean(arr < 0.5)), 4) if len(arr) else None,
            "frac_pos_gt_0.5": round(float(np.mean(arr > 0.5)), 4) if len(arr) else None,
            "q25_q75": [round(float(np.percentile(arr, 25)), 4),
                        round(float(np.percentile(arr, 75)), 4)] if len(arr) else None,
        }

    # ── 3) per-kuartal (up1_21, full & density) — proxy regime temporal ──
    years = dates_dt.astype("datetime64[Y]").astype(int) + 1970
    months = dates_dt.astype("datetime64[M]").astype(int) % 12 + 1
    qtr = np.array([f"{y}-Q{(mo - 1) // 3 + 1}" for y, mo in zip(years, months)])
    per_quarter = {}
    for q in np.unique(qtr):
        qm = (qtr == q) & arm
        block = {}
        for score_name, sc in (("full", score_full), ("density_only", score_den)):
            sel = qm & np.isfinite(sc) & np.isfinite(rows[:, C.label_col("up1", 21)])
            if int(sel.sum()) < MIN_PER_QUARTER:
                block[score_name] = None
                continue
            y = rows[sel, C.label_col("up1", 21)]
            if len(set(y.tolist())) < 2:
                block[score_name] = None
                continue
            from sklearn.metrics import roc_auc_score
            block[score_name] = {"n": int(sel.sum()),
                                 "auc": round(float(roc_auc_score(y, sc[sel])), 4)}
        per_quarter[str(q)] = block

    doc = {
        "phase": "Phase 3 — diagnostic orientasi strength (read-only, config winner)",
        "question": ("apakah inverse relationship strength->up1 stabil di TRAIN vs OOS, "
                     "antar stock, dan antar regime?"),
        "note": "Diagnostik MURNI; tidak ada parameter yang dipilih dari hasil ini.",
        "winner_config": cfg,
        "n_arm_total": int(arm.sum()),
        "n_arm_train": int((arm & train).sum()),
        "n_arm_oos": int((arm & test).sum()),
        "train_vs_oos": train_oos,
        "per_code": per_code_summary,
        "per_quarter": per_quarter,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    C.write_json(C.DATA_DIR + r"\phase3_rtf_diag.json", doc)

    print("=== TRAIN vs OOS (AUC) ===", file=sys.stderr)
    for score_name, blk in train_oos.items():
        for k, v in blk.items():
            print(f"  {score_name:12s} {k:8s} train={v['train']} oos={v['oos']}",
                  file=sys.stderr)
    print("=== per-kode (up1_21) ===", file=sys.stderr)
    for score_name, s in per_code_summary.items():
        print(f"  {score_name:12s} {s}", file=sys.stderr)
    print("=== per-kuartal (up1_21, full) ===", file=sys.stderr)
    for q in sorted(per_quarter):
        blk = per_quarter[q]
        if blk and blk.get("full"):
            print(f"  {q}: n={blk['full']['n']} AUC_full={blk['full']['auc']} "
                  f"AUC_den={blk['density_only']['auc'] if blk['density_only'] else None}",
                  file=sys.stderr)


if __name__ == "__main__":
    main()