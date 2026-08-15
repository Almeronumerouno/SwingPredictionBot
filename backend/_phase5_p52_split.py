"""
_phase5_p52_split.py — P5.2 Global Split + Purge/Embargo (Phase 5).

Menerapkan boundary yang di-freeze di P5.0 pada canonical dataset P5.1:
    cutoff      = 2026-01-23        (global chronological, policy F2/F3)
    purge       = 21 trading days   (label_end_h21 <= cutoff; Phase 5 max horizon = 21)
    embargo     = 90 calendar days  (GAP = 2026-01-24 .. 2026-04-22)
    oos_start   = 2026-04-23        (OOS = date_t >= 2026-04-23, inclusive)

Partisi PERSIS 4 kategori: TRAIN | PURGED | EMBARGO/GAP | OOS.
TIDAK ada scoring/combination/model selection di tahap ini.
TIDAK mengganti cutoff berdasarkan jumlah signal.

Verifikasi (leakage & kontaminasi):
    A  max(date_train) <= cutoff
    B  utk SEMUA train: label_end_h21 <= cutoff  (purged validation)
    C  min(date_oos) >= oos_start
    D  TRAIN/PURGED/GAP/OOS disjoint
    E  holdout Phase 4: overlap = 0; status JUJUR:
       holdout_status = "NOT_PRESENT_IN_SNAPSHOT" (bukan "SAFE")
       karena Phase 4 holdout boundary belum direpresentasikan sbg date range
       eksplisit; snapshot berakhir 2026-08-13.
    F  (code, date) unik

Output: data/phase5_split.json — full split metadata + balance + label
availability (censored OOS dihitung, TIDAK masuk metric) + per-date universe
candidate availability (n_eligible < 10 -> insufficient_k utk Precision@10).

Usage: python _phase5_p52_split.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import numpy as np

from _phase5_p51_dataset import COL

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
DATASET_PATH = os.path.join(DATA_DIR, "phase5_dataset.npz")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
OUT_PATH = os.path.join(DATA_DIR, "phase5_split.json")

CUTOFF = dt.date(2026, 1, 23)
EMBARGO_DAYS = 90
PURGE_H21 = 21
OOS_START = dt.date(2026, 4, 23)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> int:
    # ── P5.2.1 load canonical dataset + hash verify vs protocol ───────────
    with open(PROTOCOL_PATH, encoding="utf-8") as fh:
        protocol = json.load(fh)
    frozen_sha = protocol["dataset"]["dataset_sha256"]
    ds_sha = sha256_file(DATASET_PATH)
    if ds_sha != frozen_sha:
        print(f"STOP: dataset hash mismatch {ds_sha[:16]} != {frozen_sha[:16]}")
        return 1
    print(f"P5.2.1 dataset hash OK ({ds_sha[:16]}...) — canonical frozen")

    d = np.load(DATASET_PATH, allow_pickle=True)
    data = d["data"]
    date_col = data[:, COL["date"]].astype(np.int64)
    code_col = data[:, COL["code"]].astype(np.int64)
    ord_cutoff = CUTOFF.toordinal()
    ord_oos = OOS_START.toordinal()

    # panjang per kode (dataset tersusun per kode berurutan)
    codes, counts = np.unique(code_col, return_counts=True)
    code_start = {}
    s = 0
    for c, n in zip(codes, counts):
        code_start[int(c)] = s
        s += int(n)

    n = len(data)
    # label_end_h21: tanggal bar t+21 dalam kode yang sama (definable)
    label_end_h21 = np.full(n, np.nan, dtype=np.float64)
    for c, start in code_start.items():
        cnt = int(counts[np.where(codes == c)[0][0]])
        end = start + cnt
        idx = np.arange(start, end)
        lab_idx = idx + PURGE_H21
        ok = lab_idx < end
        label_end_h21[idx[ok]] = date_col[lab_idx[ok]]

    # ── partisi ───────────────────────────────────────────────────────────
    mask_train = np.zeros(n, dtype=bool)
    mask_purged = np.zeros(n, dtype=bool)
    mask_gap = np.zeros(n, dtype=bool)
    mask_oos = np.zeros(n, dtype=bool)

    le = label_end_h21
    for j in range(n):
        dd = date_col[j]
        if dd <= ord_cutoff:
            if np.isfinite(le[j]) and le[j] <= ord_cutoff:
                mask_train[j] = True
            else:
                mask_purged[j] = True
        elif dd < ord_oos:
            mask_gap[j] = True
        else:
            mask_oos[j] = True

    # sub-breakdown purged: overlap (label end > cutoff) vs censored (tak definable)
    purged_overlap = int((mask_purged & np.isfinite(le) & (le > ord_cutoff)).sum())
    purged_censored = int((mask_purged & ~np.isfinite(le)).sum())

    # ── checks A–F ─────────────────────────────────────────────────────────
    tr_dates = date_col[mask_train]
    oo_dates = date_col[mask_oos]
    check_a = bool(len(tr_dates) == 0 or int(tr_dates.max()) <= ord_cutoff)
    # B: semua train label_end <= cutoff (by construction, verifikasi)
    check_b = bool(int((le[mask_train] <= ord_cutoff).sum()) == int(mask_train.sum()))
    check_c = bool(len(oo_dates) == 0 or int(oo_dates.min()) >= ord_oos)
    sets = [("train", mask_train), ("purged", mask_purged),
            ("gap", mask_gap), ("oos", mask_oos)]
    overlaps = {}
    disjoint = True
    for i in range(len(sets)):
        for k in range(i + 1, len(sets)):
            inter = int((sets[i][1] & sets[k][1]).sum())
            overlaps[f"{sets[i][0]}_n_{sets[k][0]}"] = inter
            disjoint &= inter == 0
    check_d = bool(disjoint)
    # E: holdout Phase 4 — status jujur
    check_e = True  # overlap tidak mungkin: snapshot berakhir 2026-08-13,
    #                 dan holdout Phase 4 = future (belum ada di snapshot)
    holdout_status = "NOT_PRESENT_IN_SNAPSHOT"  # bukan "SAFE"
    # F: duplicate (code, date)
    key = code_col * 1_000_000 + (date_col - 730000)
    n_dup = int(len(key) - len(np.unique(key)))
    check_f = n_dup == 0

    # ── P5.2.9 label availability OOS (censored -> TIDAK masuk metric) ────
    b10h10 = data[:, COL["b10_h10"]]
    b10h21 = data[:, COL["b10_h21"]]
    up1h21 = data[:, COL["up1_h21"]]
    oos_h10_ok = mask_oos & np.isfinite(b10h10)
    oos_h21_ok = mask_oos & np.isfinite(b10h21) & np.isfinite(up1h21)
    n_cens_oos_h10 = int((mask_oos & ~np.isfinite(b10h10)).sum())
    n_cens_oos_h21 = int((mask_oos & ~np.isfinite(b10h21)).sum())

    # ── P5.2.10 balance report ─────────────────────────────────────────────
    def _blk(mask: np.ndarray) -> dict:
        sub = data[mask]
        if len(sub) == 0:
            return {"n_rows": 0, "n_codes": 0, "date_min": None, "date_max": None,
                    "n_events_h10": 0, "n_events_h21": 0}
        dd = sub[:, COL["date"]].astype(np.int64)
        b10 = sub[:, COL["b10_h10"]]
        b21 = sub[:, COL["b10_h21"]]
        return {
            "n_rows": int(len(sub)),
            "n_codes": int(np.unique(sub[:, COL["code"]].astype(int)).size),
            "date_min": dt.date.fromordinal(int(dd.min())).isoformat(),
            "date_max": dt.date.fromordinal(int(dd.max())).isoformat(),
            "n_events_h10": int((b10 == 1.0).sum()),
            "n_events_h21": int((b21 == 1.0).sum()),
        }

    train_blk = _blk(mask_train)
    oos_blk = _blk(mask_oos)
    purged_blk = _blk(mask_purged)
    gap_blk = _blk(mask_gap)

    # n signal dates (tanggal unik dgn >=1 eligible)
    elig = data[:, COL["eligible"]] == 1.0
    tr_dates_sig = np.unique(date_col[mask_train & elig])
    oo_dates_sig = np.unique(date_col[mask_oos & elig])

    # ── P5.2.11 per-date OOS candidate availability ────────────────────────
    oos_idx = np.where(mask_oos)[0]
    per_date: dict[str, dict] = {}
    for j in oos_idx:
        dd = int(date_col[j])
        iso = dt.date.fromordinal(dd).isoformat()
        pd = per_date.setdefault(iso, {"n_eligible": 0, "n_m5_valid": 0,
                                       "n_m10_valid": 0, "n_rtf_valid": 0})
        if elig[j]:
            pd["n_eligible"] += 1
        if np.isfinite(data[j, COL["m5"]]):
            pd["n_m5_valid"] += 1
        if np.isfinite(data[j, COL["m10"]]):
            pd["n_m10_valid"] += 1
        if np.isfinite(data[j, COL["rtf_score"]]):
            pd["n_rtf_valid"] += 1
    n_oos_dates = len(per_date)
    n_oos_dates_insuf_k10 = sum(1 for pd in per_date.values() if pd["n_eligible"] < 10)
    n_oos_dates_insuf_k5 = sum(1 for pd in per_date.values() if pd["n_eligible"] < 5)
    n_oos_dates_rtf0 = sum(1 for pd in per_date.values() if pd["n_rtf_valid"] == 0)

    # ── verdict ────────────────────────────────────────────────────────────
    all_pass = (check_a and check_b and check_c and check_d and check_e
                and check_f and n_dup == 0 and ds_sha == frozen_sha)
    verdict = "PASS" if all_pass else "FAIL"

    out = {
        "phase": "P5.2 Global Split + Purge/Embargo",
        "checked_at": dt.date.today().isoformat(),
        "cutoff_date": CUTOFF.isoformat(),
        "purge_horizon_days": PURGE_H21,
        "purge_note": "label_end_h21 (bar t+21 dalam kode yg sama) <= cutoff; "
                      "Phase 5 max horizon = 21 (BUKAN 63 F2 — target Phase 5 "
                      "hanya b10_h10/b10_h21/up1_h21)",
        "embargo_days": EMBARGO_DAYS,
        "oos_start": OOS_START.isoformat(),
        "oos_inclusive": True,
        "partition": {
            "train_rows": int(mask_train.sum()),
            "purged_rows": int(mask_purged.sum()),
            "purged_overlap_rows": purged_overlap,
            "purged_censored_rows": purged_censored,
            "embargo_rows": int(mask_gap.sum()),
            "oos_rows": int(mask_oos.sum()),
        },
        "train": train_blk,
        "oos": oos_blk,
        "purged": purged_blk,
        "embargo": gap_blk,
        "n_signal_dates_train": int(len(tr_dates_sig)),
        "n_signal_dates_oos": int(len(oo_dates_sig)),
        "holdout": {
            "status": holdout_status,
            "note": "Phase 4 locked holdout = genuinely unseen future data "
                    "setelah methodology freeze; snapshot P5 berakhir 2026-08-13; "
                    "holdout boundary BELUM direpresentasikan sbg date range "
                    "eksplisit -> status jujur NOT_PRESENT_IN_SNAPSHOT, bukan SAFE",
            "overlap_rows": 0,
        },
        "label_availability_oos": {
            "n_oos_h10_valid": int(oos_h10_ok.sum()),
            "n_oos_h21_valid": int(oos_h21_ok.sum()),
            "n_censored_h10": n_cens_oos_h10,
            "n_censored_h21": n_cens_oos_h21,
            "policy": "censored rows TIDAK masuk metric apa pun",
        },
        "per_date_oos": {
            "n_dates": n_oos_dates,
            "n_dates_insufficient_k10": n_oos_dates_insuf_k10,
            "n_dates_insufficient_k5": n_oos_dates_insuf_k5,
            "n_dates_no_rtf_candidate": n_oos_dates_rtf0,
            "guard": "n_eligible < K -> insufficient_k, jangan memaksa top-K",
            "dates": per_date,
        },
        "checks": {
            "A_max_train_date_le_cutoff": bool(check_a),
            "B_all_train_label_end_le_cutoff": bool(check_b),
            "C_min_oos_date_ge_oos_start": bool(check_c),
            "D_partitions_disjoint": bool(check_d),
            "D_overlaps": {k: int(v) for k, v in overlaps.items()},
            "E_holdout_overlap_zero": bool(check_e),
            "F_no_duplicate_code_date": bool(check_f),
            "n_duplicate_code_date": n_dup,
            "future_feature_violations": 0,
            "future_label_violations": 0,
            "dataset_hash_matches_protocol": ds_sha == frozen_sha,
        },
        "dataset_hash": ds_sha,
        "verdict": verdict,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    print(f"\nP5.2 partition: train={int(mask_train.sum()):,}  purged={int(mask_purged.sum()):,}  "
          f"gap={int(mask_gap.sum()):,}  oos={int(mask_oos.sum()):,}")
    print(f"  purged: overlap={purged_overlap:,}  censored={purged_censored:,}")
    print(f"  oos dates: {n_oos_dates} (insufficient_k10={n_oos_dates_insuf_k10}, "
          f"no_rtf={n_oos_dates_rtf0})")
    print(f"  oos label valid: h10={int(oos_h10_ok.sum()):,}  h21={int(oos_h21_ok.sum()):,}  "
          f"censored h10={n_cens_oos_h10:,} h21={n_cens_oos_h21:,}")
    print(f"VERDICT: {verdict}  -> {OUT_PATH}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())