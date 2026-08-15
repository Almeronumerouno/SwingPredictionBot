"""
_fase2_episodes.py — F2.2: DEDUP / CLUSTER EPISODE RECOVERY.

Masalah:
  Observasi recovery tidak independen: selama satu "episode" drawdown
  (rangkaian bar berturut-turut dgn dd > 0), setiap bar menghasilkan satu
  observasi padahal semuanya dari KEJADIAN yang sama & sangat overlap
  (label horizon saling tumpang-tindih). Ini menggelembungkan ukuran sampel
  dan membuat CI/validasi tampak lebih kuat dari sebenarnya.

Solusi F2.2:
  1. Identifikasi EPISODE per saham: run kontigu bar dgn dd > 0
     (drawdown dari trailing peak; episode berakhir saat close >= peak lagi).
  2. GUNAKAN SATU OBSERVASI REPRESENTATIF per episode = bar dengan dd
     TERDALAM (trough) — titik paling relevan utk pertanyaan "berapa
     P(recover) dari drawdown terdalam?".
  3. Ulangi evaluasi temporal F2.1 (cutoff global + purge + embargo) pada
     sampel hasil dedup → bandingkan AUC/Brier/kalibrasi bucket vs sampel
     penuh. Kalau overprediksi produksi PERSIST di sampel independen →
     masalah kalibrasi nyata; kalau hilang → artefak overlap.

Asumsi per episode: label dihitung sama dgn _collect_rows (target = prior
high dalam h bar setelah trough).

OUTPUT: data/recovery_episodes_eval.json (evaluasi) — produksi TIDAK ditimpa.
Usage:
    python _fase2_episodes.py [--cutoff YYYY-MM-DD] [--embargo-days 90]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

from _calibrate_recovery_model import (DD_BUCKETS, DD_CLAMP_MAX, HORIZONS,
                                       TRAIN_FRAC, _trailing_peak)
from _fase2_temporal_split import (DATA_DIR, NPZ_PATH, PARAMS_JSON,
                                   _fit_and_eval, _global_cutoff, _load_npz,
                                   _prod_on_test, _purge_embargo_masks)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(DATA_DIR, "recovery_episodes_eval.json")
DEFAULT_EMBARGO_DAYS = 90


def _collect_episode_rows(rows, lens, window, codes, dates_list=None,
                          rep="trough"):
    """1 observasi per episode (default: bar trough = argmax dd; rep="first"
    = bar pertama episode sbg uji sensitivitas komposisi sampel).

    Returns: dict per horizon {h: {"dd","y","code","date_s","date_e"}},
    kompatibel dgn struktur _collect_rows utk _purge_embargo_masks.
    Juga stats episode (n episode, durasi, ukuran obs per episode).
    """
    n_codes = len(lens)
    out: dict[int, dict] = {h: {"dd": [], "y": [], "code": [],
                                "date_s": [], "date_e": []} for h in HORIZONS}
    stats = {"episodes": 0, "obs_in_episodes": 0,
             "durasi_min": None, "durasi_max": 0, "durasi_slices": [],
             "trough_bars_used": 0}
    # durasi episode per kode utk bucket
    dur_hist = {}

    for c in range(n_codes):
        m = int(lens[c])
        if m < window + max(HORIZONS) + 5:
            continue
        dt = None
        if dates_list is not None and c < len(dates_list):
            dl = dates_list[c]
            if dl is not None and len(dl) == m:
                dt = np.asarray(dl, dtype="datetime64[D]")
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        peak = _trailing_peak(close, window)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.clip(1.0 - close / peak, 0.0, DD_CLAMP_MAX)
        in_dd = np.isfinite(dd) & (dd > 0.0)

        # cari run kontigu dd>0
        i = 0
        while i < m:
            if not in_dd[i]:
                i += 1
                continue
            j = i
            while j + 1 < m and in_dd[j + 1]:
                j += 1
            # run [i..j]
            seg = dd[i:j + 1]
            if rep == "trough":
                rep_bar = int(i + np.argmax(seg))   # bar dd terdalam
            elif rep == "first":
                rep_bar = i                          # bar pertama episode
            else:
                raise ValueError(f"rep tidak dikenal: {rep!r}")
            stats["episodes"] += 1
            stats["obs_in_episodes"] += (j - i + 1)
            d = j - i + 1
            stats["durasi_max"] = max(stats["durasi_max"], d)
            if stats["durasi_min"] is None or d < stats["durasi_min"]:
                stats["durasi_min"] = d
            dur_hist.setdefault(d, 0)
            dur_hist[d] += 1
            for h in HORIZONS:
                end = rep_bar + 1 + h
                if end > m - 1:
                    continue
                fmax_h = high[rep_bar + 1:rep_bar + h + 1].max()
                y = float(fmax_h >= peak[rep_bar])
                out[h]["dd"].append(dd[rep_bar])
                out[h]["y"].append(y)
                out[h]["code"].append(np.int32(c))
                if dt is not None:
                    out[h]["date_s"].append(dt[rep_bar])
                    out[h]["date_e"].append(dt[rep_bar + h])
            stats["trough_bars_used"] += 1
            i = j + 1

    for h in HORIZONS:
        if out[h]["dd"]:
            out[h]["dd"] = np.asarray(out[h]["dd"], dtype=float)
            out[h]["y"] = np.asarray(out[h]["y"], dtype=float)
            out[h]["code"] = np.asarray(out[h]["code"], dtype=np.int32)
        else:
            out[h]["dd"] = np.array([])
            out[h]["y"] = np.array([])
            out[h]["code"] = np.array([], dtype=np.int32)
        if out[h]["date_s"]:
            out[h]["date_s"] = np.asarray(out[h]["date_s"], dtype="datetime64[D]")
            out[h]["date_e"] = np.asarray(out[h]["date_e"], dtype="datetime64[D]")
        else:
            out[h]["date_s"] = np.array([], dtype="datetime64[D]")
            out[h]["date_e"] = np.array([], dtype="datetime64[D]")
    stats["durasi_hist"] = dict(sorted(dur_hist.items()))
    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--cutoff", default=None)
    ap.add_argument("--peak-lookback", type=int, default=252)
    ap.add_argument("--embargo-days", type=int, default=DEFAULT_EMBARGO_DAYS)
    ap.add_argument("--rep", choices=("trough", "first"), default="trough",
                    help="bar representatif per episode: trough (dd terdalam) "
                         "atau first (bar pertama episode)")
    ap.add_argument("--out-json", default=OUT_JSON)
    args = ap.parse_args()

    codes, rows, lens, dates = _load_npz(args.npz)
    print(f"Dataset: {len(codes)} kode, peak-lookback={args.peak_lookback}, "
          f"rep={args.rep}", flush=True)

    t0 = time.time()
    collected, stats = _collect_episode_rows(rows, lens, args.peak_lookback,
                                             codes, dates_list=dates,
                                             rep=args.rep)
    print(f"collect episodes: {time.time()-t0:.0f}s", flush=True)
    print(f"Episode total: {stats['episodes']:,} | obs dalam episode: "
          f"{stats['obs_in_episodes']:,} | durasi min={stats['durasi_min']} "
          f"max={stats['durasi_max']} bar", flush=True)
    print(f"Durasi histogram (bar): {dict(list(stats['durasi_hist'].items())[:12])} "
          f"...", flush=True)

    cutoff = (np.datetime64(args.cutoff, "D") if args.cutoff
              else _global_cutoff(dates, TRAIN_FRAC))
    print(f"Cutoff global: {cutoff} | embargo: {args.embargo_days} hari",
          flush=True)

    with open(PARAMS_JSON, encoding="utf-8") as f:
        params = json.load(f)

    n_full = {}
    for h in HORIZONS:
        # bandingkan ukuran: sampel penuh (F2.1) vs dedup (F2.2)
        full = None
        if h in (1, 21, 63):
            from _calibrate_recovery_model import _collect_rows
            full_all = _collect_rows(rows, lens, args.peak_lookback)
            n_full[h] = int(len(full_all[h]["dd"]))

    print("\n" + "=" * 118)
    print(f"{'h':>4} | {'n_dedup':>9} {'n_full':>9} | {'rec_te':>7} | "
          f"{'AUC_penuh':>9} {'AUC_dedup':>9} | {'Br_dedup':>9} | "
          f"{'ovr_prod_dedup':>12} | n_purged")
    print("-" * 118)
    report = {"cutoff": str(cutoff), "embargo_days": args.embargo_days,
              "episode_stats": stats, "refit_dedup": {}, "full_ref": {},
              "production_on_dedup_test": {}, "n_purged": {}, "n_gap": {}}

    # bandingkan hingga 4 desimal dgn sampel penuh dari json F2.1
    try:
        with open(os.path.join(DATA_DIR, "recovery_temporal_eval.json"),
                  encoding="utf-8") as f:
            f21 = json.load(f)
        full_ref = {h: f21["refit"].get(str(h), {}) for h in map(str, HORIZONS)}
        has_f21 = True
    except (FileNotFoundError, KeyError):
        full_ref = {}
        has_f21 = False
        print("(recovery_temporal_eval.json tidak ada — banding full skipped)")

    for h in HORIZONS:
        dd = collected[h]["dd"]
        y = collected[h]["y"]
        code = collected[h]["code"]
        d_s = collected[h]["date_s"]
        d_e = collected[h]["date_e"]
        if len(dd) == 0:
            continue
        tr, te, purged, gap = _purge_embargo_masks(
            dd, code, d_s, d_e, cutoff, args.embargo_days, h)
        r = _fit_and_eval(dd[tr], y[tr], dd[te], y[te], h)
        p = _prod_on_test(params, dd[te], y[te], h)
        report["refit_dedup"][str(h)] = r
        report["production_on_dedup_test"][str(h)] = p
        report["n_purged"][str(h)] = int(purged.sum())
        report["n_gap"][str(h)] = int(gap.sum())
        n_te = r.get("n_test", 0)
        auc_d = r.get("auc_test")
        auc_f = full_ref.get(str(h), {}).get("auc_test") if has_f21 else None
        if r.get("fitted"):
            print(f"{h:>4} | {r['n_train']+n_te:>9,} {n_full.get(h, 0):>9,} | "
                  f"{r['rec_test']*100:>6.1f}% | {str(auc_f):>9} "
                  f"{str(auc_d):>9} | {r['brier_test']:>9.4f} | "
                  f"{p.get('overpred', 0):>+11.1%} | {int(purged.sum()):,}")
        else:
            print(f"{h:>4} | (tidak cukup) | n_purged={int(purged.sum()):,}")

    print("=" * 118)
    print("AUC_penuh = refit F2.1 sampel penuh (overlapping); AUC_dedup = 1 obs/episode")
    print("ovr_prod_dedup = overprediction produksi di test dedup (positif = over)")

    print("\nKalibrasi bucket PRODUKSI di test DEDUP (h=21):")
    c21 = report["production_on_dedup_test"].get("21", {})
    for c in c21.get("calibration", []):
        print(f"  dd {c['bucket']:12s} n={c['n']:>6,} pred={c['pred']:.3f} "
              f"actual={c['actual']:.3f} dev={c['dev']:+.3f}")
    if has_f21:
        print("\nKalibrasi bucket PRODUKSI di test PENUH (h=21, dari F2.1):")
        c21f = f21["production"].get("21", {})
        for c in c21f.get("calibration", []):
            print(f"  dd {c['bucket']:12s} n={c['n']:>6,} pred={c['pred']:.3f} "
                  f"actual={c['actual']:.3f} dev={c['dev']:+.3f}")

    report.update({
        "model": "logistic_drawdown",
        "split": "chronological_global + purge + embargo (sama dgn F2.1)",
        "dedup": "1 observasi per episode dd>0",
        "rep": args.rep,
        "train_frac": TRAIN_FRAC,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {args.out_json} (produksi TIDAK ditimpa)")


if __name__ == "__main__":
    sys.exit(main())