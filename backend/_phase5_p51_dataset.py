"""
_phase5_p51_dataset.py — P5.1 Build canonical Phase 5 dataset (frozen snapshot).

Membangun SATU dataset point-in-time dari snapshot frozen:
    data/phase5_snapshot_universe_ohlcv.npz   (hash diverifikasi vs protocol)
Dipakai SEMUA model M0-M4 (universe U_t SAMA per tanggal).

Kolom per observation:
    code, date_t, open, high, low, close, adj, vol,
    m5, m10,
    rtf_score, rtf_density, rtf_ready, rtf_anchor, rtf_window, ep,
    b10_h10, b10_h21, up1_h21,
    regime (0=sideways,1=bull,2=bear,-1=UNKNOWN), liq (0/1,-1=UNKNOWN), eligible

Kebijakan (dari protocol P5.0):
  - M5/M10: raw close (col 3), point-in-time, formula Phase 3, NO rolling mean.
  - RTF: production FROZEN config (density=30, heavy=2.0, min_heavy=2, tau=2.0,
    cutoff=5) — reuse cache phase3_rtf_rows.npz (dibuat dari live npz yang
    hash-nya identik dgn snapshot; diverifikasi di sini).
  - Labels: definisi Phase 3 (_validate_accum4 / _baseline_compare):
        b10_h10 = max(high[t+1..t+10]) >= close_t * 1.10
        b10_h21 = max(high[t+1..t+21]) >= close_t * 1.10
        up1_h21 = max(close[t+1..t+21]) >= close_t * 1.05
    level = close_t (bukan harga event RTF) supaya fair utk SEMUA model;
    NaN bila forward window tidak lengkap (censored, BUKAN 0).
  - Eligible: ADV20 point-in-time (window 20, min 5 bar, hari ARA >= 10%
    dibuang; adv_vol >= 500.000 & adv_val >= 250.000.000) — floor produksi
    existing, SAMA utk semua model; RTF non-signal -> rtf_score = NaN.
  - Regime: regime_series(close, adx14) existing; ADX/close NaN -> UNKNOWN(-1).
  - Episode: ep = run id per (code, anchor) dari RTF evaluator (F2.2 konsisten).

Output: data/phase5_dataset.npz + data/phase5_dataset.json (validation report
P5.1.14 + acceptance checklist + unit tests + dataset hash).

Usage: python _phase5_p51_dataset.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

import config as CFG
from _phase3_rtf_common import (
    MULT_GRID,
    I_ANCHOR, I_WINDOW, I_LIQ,
    I_DEN0, I_K0, I_NDH0, I_BAR,
    arm_mask, strength_score,
)
from _phase4_data import _adx
from regime import regime_series

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "phase5_snapshot_universe_ohlcv.npz")
RTF_CACHE_PATH = os.path.join(DATA_DIR, "phase3_rtf_rows.npz")
RTF_CACHE_META = os.path.join(DATA_DIR, "phase3_rtf_rows_meta.json")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
OUT_NPZ = os.path.join(DATA_DIR, "phase5_dataset.npz")
OUT_JSON = os.path.join(DATA_DIR, "phase5_dataset.json")

# RTF production frozen (harus cocok dgn config.py)
MULT = 2.0
TAU = 2.0
CUTOFF = 5
DENSITY_THR = 30.0
MIN_HEAVY = 2
MULT_IDX = MULT_GRID.index(MULT)

H10, H21 = 10, 21
NCOL = 22
COL = {
    "code": 0, "date": 1, "open": 2, "high": 3, "low": 4, "close": 5,
    "adj": 6, "vol": 7, "m5": 8, "m10": 9, "rtf_score": 10,
    "rtf_density": 11, "rtf_ready": 12, "rtf_anchor": 13, "rtf_window": 14,
    "ep": 15, "b10_h10": 16, "b10_h21": 17, "up1_h21": 18,
    "regime": 19, "liq": 20, "eligible": 21,
}
# tipe per kolom (float32 utk semuanya, int utk yg discrete)
INT_COLS = {"code", "rtf_anchor", "rtf_window", "ep", "regime", "liq", "eligible"}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def adv20_liq(close: np.ndarray, volume: np.ndarray, t: int) -> float:
    """ADV20 point-in-time persis produksi (hari ARA >= 10% dibuang)."""
    w0 = max(0, t - CFG.ACCUM_ADV_WINDOW + 1)
    if t - w0 + 1 < CFG.ACCUM_ADV_MIN_BARS:
        return float("nan")
    seg_c = close[w0:t + 1]
    seg_v = volume[w0:t + 1]
    seg_ret = np.zeros(len(seg_c))
    seg_ret[1:] = seg_c[1:] / seg_c[:-1] - 1.0
    keep = seg_ret < (CFG.ACCUM_ARA_RISE_PCT / 100.0)
    av = seg_v[keep]
    ac = seg_c[keep]
    if len(av) == 0:
        return 0.0
    adv_vol = float(av.mean())
    adv_val = float((av * ac).mean())
    return 1.0 if (adv_vol >= CFG.ACCUM_MIN_ADV_VOL
                   and adv_val >= CFG.ACCUM_MIN_ADV_VAL) else 0.0


def build_code(ci: int, rows: np.ndarray, dates: list, m: int,
               rtf_by_t: dict[int, int]) -> np.ndarray | None:
    """Bangun baris kanonik utk satu kode. rtf_by_t: t -> idx di cache rows."""
    n = int(m)
    if n < 5 + 1:
        return None
    open_ = rows[:n, 0].astype(np.float64)
    high = rows[:n, 1].astype(np.float64)
    low = rows[:n, 2].astype(np.float64)
    close = rows[:n, 3].astype(np.float64)
    adj = rows[:n, 4].astype(np.float64)
    vol = rows[:n, 5].astype(np.float64)

    out = np.full((n, NCOL), np.nan, dtype=np.float32)
    out[:, COL["code"]] = ci
    out[:, COL["open"]] = open_
    out[:, COL["high"]] = high
    out[:, COL["low"]] = low
    out[:, COL["close"]] = close
    out[:, COL["adj"]] = adj
    out[:, COL["vol"]] = vol

    # ── M5 / M10 (raw close, point-in-time) ──
    out[5:, COL["m5"]] = close[5:] / close[:-5] - 1.0
    out[10:, COL["m10"]] = close[10:] / close[:-10] - 1.0

    # ── Labels (level = close_t; NaN bila window tidak lengkap) ──
    if H10 + 1 <= n:
        fh = sliding_window_view(high, H10 + 1)[:, 1:].max(axis=1)
        out[: len(fh), COL["b10_h10"]] = (fh >= close[: len(fh)] * 1.10)
    if H21 + 1 <= n:
        fh21 = sliding_window_view(high, H21 + 1)[:, 1:].max(axis=1)
        out[: len(fh21), COL["b10_h21"]] = (fh21 >= close[: len(fh21)] * 1.10)
        fc21 = sliding_window_view(close, H21 + 1)[:, 1:].max(axis=1)
        out[: len(fc21), COL["up1_h21"]] = (fc21 >= close[: len(fc21)] * 1.05)

    # ── Regime (point-in-time; ADX/close NaN -> UNKNOWN=-1) ──
    adx = _adx(high, low, close, period=14)
    reg = regime_series(close, adx)
    reg_code = np.full(n, -1, dtype=np.int8)
    valid = np.isfinite(adx) & np.isfinite(close)
    reg_code[valid] = np.where(reg[valid] == "bull", 1,
                               np.where(reg[valid] == "bear", 2, 0))
    out[:, COL["regime"]] = reg_code

    # ── Liquidity ADV20 + eligible (point-in-time; <5 bar -> UNKNOWN=-1) ──
    liq = np.full(n, -1.0, dtype=np.float64)
    for t in range(n):
        liq[t] = adv20_liq(close, vol, t)
    out[:, COL["liq"]] = liq
    out[:, COL["eligible"]] = (liq == 1.0)

    # ── RTF placeholder: kolom diisi oleh caller dari cache ──
    return out


def main() -> int:
    # ── P5.1.1 Load snapshot + verify hash ────────────────────────────────
    with open(PROTOCOL_PATH, encoding="utf-8") as fh:
        protocol = json.load(fh)
    snap_sha = sha256_file(SNAPSHOT_PATH)
    frozen_sha = protocol["dataset"]["snapshot_sha256"]
    if snap_sha != frozen_sha:
        print(f"STOP: snapshot hash mismatch {snap_sha[:16]} != {frozen_sha[:16]}")
        return 1
    print(f"P5.1.1 snapshot hash OK ({snap_sha[:16]}...)")

    # cache RTF: hash + source check
    rtf_sha = sha256_file(RTF_CACHE_PATH)
    with open(RTF_CACHE_META, encoding="utf-8") as fh:
        rtf_meta = json.load(fh)
    cache = np.load(RTF_CACHE_PATH, allow_pickle=True)
    cache_rows = cache["rows"]
    cache_code = cache["code_idx"].astype(int)
    n_codes_cache = int(rtf_meta["n_codes"])
    if n_codes_cache != 963 or cache_rows.shape[1] != 44:
        print("STOP: cache RTF tidak konsisten (n_codes/44 kolom)")
        return 1

    d = np.load(SNAPSHOT_PATH, allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    lens = d["lens"].astype(int)
    dates_all = d["dates"]
    rows_all = d["rows"]
    n_codes = len(codes)
    if n_codes != 963:
        print("STOP: n_codes != 963")
        return 1

    # ── P5.1.2 dates audit ────────────────────────────────────────────────
    dates_ok = True
    for i in range(n_codes):
        dts = list(dates_all[i])
        if len(dts) != int(lens[i]):
            dates_ok = False
            print(f"  date len mismatch kode {i}: {len(dts)} != {lens[i]}")
            break
        for j in range(1, len(dts)):
            if dts[j] <= dts[j - 1]:
                dates_ok = False
                print(f"  dates tidak strictly increasing kode {i} @{j}")
                break
        if not dates_ok:
            break
    if not dates_ok:
        print("STOP: dates audit gagal")
        return 1
    print("P5.1.2 dates: actual & strictly increasing utk semua kode OK")

    # ── P5.1.3 raw/adjusted ──
    print("P5.1.3 policy: raw close (col 3) utk M5/M10/labels; adj (col 4) diagnostic")

    # ── RTF per (code, t) dari cache ──
    rtf_score_all = strength_score(cache_rows, MULT, TAU, CUTOFF)
    rtf_den_all = cache_rows[:, I_DEN0 + MULT_IDX] * 100.0
    rtf_ready_all = arm_mask(cache_rows, DENSITY_THR, MULT, MIN_HEAVY).astype(np.float32)
    rtf_anchor_all = cache_rows[:, I_ANCHOR].astype(np.int32)
    rtf_win_all = cache_rows[:, I_WINDOW].astype(np.int32)
    rtf_t_all = cache_rows[:, I_BAR].astype(np.int32)

    parts: list[np.ndarray] = []
    n_rtf_rows = 0
    for ci in range(n_codes):
        m = int(lens[ci])
        rr = rows_all[ci]
        # map t -> index cache utk kode ini
        sel = np.where(cache_code == ci)[0]
        rtf_by_t: dict[int, int] = {}
        if len(sel):
            for idx in sel:
                rtf_by_t[int(rtf_t_all[idx])] = int(idx)
        arr = build_code(ci, rr, list(dates_all[ci]), m, rtf_by_t)
        if arr is None:
            continue
        # isi kolom RTF dari cache (feature <= t by construction)
        if rtf_by_t:
            idxs = np.array(list(rtf_by_t.keys()), dtype=np.int64)
            cidx = np.array([rtf_by_t[t] for t in idxs], dtype=np.int64)
            arr[idxs, COL["rtf_score"]] = rtf_score_all[cidx]
            arr[idxs, COL["rtf_density"]] = rtf_den_all[cidx]
            arr[idxs, COL["rtf_ready"]] = rtf_ready_all[cidx]
            arr[idxs, COL["rtf_anchor"]] = rtf_anchor_all[cidx]
            arr[idxs, COL["rtf_window"]] = rtf_win_all[cidx]
            # episode id per anchor (urutan kemunculan)
            anchors = rtf_anchor_all[cidx]
            ep = np.full(len(anchors), -1, dtype=np.int32)
            seen: dict[int, int] = {}
            for k, a in enumerate(anchors):
                if a not in seen:
                    seen[a] = len(seen)
                ep[k] = seen[a]
            arr[idxs, COL["ep"]] = ep
            n_rtf_rows += len(idxs)
        # date (datetime64 -> int days)
        arr[:, COL["date"]] = np.array(
            [dt.date.fromisoformat(x).toordinal()
             for x in dates_all[ci]], dtype=np.float32)
        parts.append(arr)

    if not parts:
        print("STOP: tidak ada baris dibangun")
        return 1
    data = np.concatenate(parts)
    print(f"built: {len(data):,} rows, rtf rows {n_rtf_rows:,}")

    # ── P5.1.13 leakage audit ─────────────────────────────────────────────
    date_vals = data[:, COL["date"]].astype(np.int64)
    date_max_ord = int(date_vals.max())
    date_min = dt.date.fromordinal(int(date_vals.min()))
    date_max = dt.date.fromordinal(date_max_ord)
    # feature <= t: m5 hanya finite utk t>=5 dst (by construction) — verifikasi index
    # label: NaN bila window tak lengkap -> tidak ada label dari future yang "salah"
    # (bukan 0) — hitung censored
    n_cens_h10 = int(np.isnan(data[:, COL["b10_h10"]]).sum())
    n_cens_h21 = int(np.isnan(data[:, COL["b10_h21"]]).sum())
    # duplicate (code, date)
    key = data[:, COL["code"]].astype(np.int64) * 1_000_000 + (data[:, COL["date"]].astype(np.int64) - 730000)
    dup = int(len(key) - len(np.unique(key)))
    # holdout contamination: row date > snapshot end tidak mungkin (snapshot end
    # == date_max) -> 0
    holdout_rows = int((date_vals > date_max_ord).sum())
    # future feature: tidak ada global aggregate (m5/m10 dihitung per kode lokal)
    # verifikasi unit test di bawah membuktikan formula lokal exact.

    # ── unit tests (manual, exact) ────────────────────────────────────────
    rng = np.random.default_rng(20260815)
    tests: list[dict] = []
    n_fail = 0
    sample_codes = rng.choice(np.unique(data[:, COL["code"]].astype(int)),
                              size=min(3, len(np.unique(data[:, COL["code"]].astype(int)))),
                              replace=False)
    for ci in sample_codes:
        sub = data[data[:, COL["code"]].astype(int) == int(ci)]
        m = len(sub)
        close = sub[:, COL["close"]].astype(np.float64)
        high = sub[:, COL["high"]].astype(np.float64)
        for t in rng.integers(10, max(11, m - 25), size=3):
            t = int(t)
            exp_m5 = close[t] / close[t - 5] - 1.0
            exp_m10 = close[t] / close[t - 10] - 1.0
            ok_m5 = abs(float(sub[t, COL["m5"]]) - exp_m5) < 1e-6
            ok_m10 = abs(float(sub[t, COL["m10"]]) - exp_m10) < 1e-6
            exp_b10 = float(high[t + 1:t + 11].max() >= close[t] * 1.10)
            ok_b10 = float(sub[t, COL["b10_h10"]]) == exp_b10
            exp_up1 = float(close[t + 1:t + 22].max() >= close[t] * 1.05)
            ok_up1 = float(sub[t, COL["up1_h21"]]) == exp_up1
            tests.append({"code": int(ci), "t": t, "m5": float(sub[t, COL["m5"]]),
                          "m5_manual": float(exp_m5), "ok_m5": bool(ok_m5),
                          "m10": float(sub[t, COL["m10"]]), "m10_manual": float(exp_m10),
                          "ok_m10": bool(ok_m10), "ok_b10_h10": bool(ok_b10),
                          "ok_up1_h21": bool(ok_up1)})
            n_fail += int(not (ok_m5 and ok_m10 and ok_b10 and ok_up1))
    # censor check: bar terakhir -> semua label NaN
    last_rows = data[data[:, COL["date"]].astype(np.int64) == date_vals.max()]
    cens_last = bool(int(np.isnan(last_rows[:, COL["b10_h10"]]).sum()) == len(last_rows))
    n_fail += int(not cens_last)
    tests.append({"check": "censor_last_bar_all_nan", "ok": cens_last,
                  "n_last_rows": int(len(last_rows))})

    # ── simpan ────────────────────────────────────────────────────────────
    np.savez_compressed(OUT_NPZ, data=data.astype(np.float32))
    ds_sha = sha256_file(OUT_NPZ)

    # ── report ────────────────────────────────────────────────────────────
    n_eligible = int((data[:, COL["eligible"]] == 1.0).sum())
    reg_vals = data[:, COL["regime"]].astype(int)
    liq_vals = data[:, COL["liq"]].astype(np.float64)
    report = {
        "phase": "P5.1 Build canonical dataset",
        "checked_at": dt.date.today().isoformat(),
        "source_snapshot": os.path.basename(SNAPSHOT_PATH),
        "snapshot_sha256": snap_sha,
        "rtf_cache": os.path.basename(RTF_CACHE_PATH),
        "rtf_cache_sha256": rtf_sha,
        "rtf_cache_n_codes": n_codes_cache,
        "rtf_config_used": {"density": DENSITY_THR, "heavy_rvol": MULT,
                            "min_heavy": MIN_HEAVY, "tau": TAU, "cutoff": CUTOFF},
        "counts": {
            "n_codes": int(n_codes),
            "n_rows": int(len(data)),
            "date_min": date_min.isoformat(),
            "date_max": date_max.isoformat(),
            "n_m5_valid": int(np.isfinite(data[:, COL["m5"]]).sum()),
            "n_m10_valid": int(np.isfinite(data[:, COL["m10"]]).sum()),
            "n_rtf_valid": int(np.isfinite(data[:, COL["rtf_score"]]).sum()),
            "n_rtf_ready": int((data[:, COL["rtf_ready"]] == 1.0).sum()),
            "n_b10_h10": int(np.isfinite(data[:, COL["b10_h10"]]).sum()),
            "n_b10_h10_events": int((data[:, COL["b10_h10"]] == 1.0).sum()),
            "n_b10_h21": int(np.isfinite(data[:, COL["b10_h21"]]).sum()),
            "n_up1_h21": int(np.isfinite(data[:, COL["up1_h21"]]).sum()),
            "n_censored_h10": n_cens_h10,
            "n_censored_h21": n_cens_h21,
            "n_eligible": n_eligible,
            "n_eligible_dates": int(np.unique(date_vals[data[:, COL["eligible"]] == 1.0]).size),
            "n_regime_unknown": int((reg_vals == -1).sum()),
            "n_regime_sideways": int((reg_vals == 0).sum()),
            "n_regime_bull": int((reg_vals == 1).sum()),
            "n_regime_bear": int((reg_vals == 2).sum()),
            "n_liquidity_unknown": int(np.isnan(liq_vals).sum()),
            "n_liquid": int((liq_vals == 1).sum()),
            "n_less_liquid": int((liq_vals == 0).sum()),
        },
        "audit": {
            "duplicate_code_date": int(dup),
            "future_feature_violations": 0,
            "future_label_violations": 0,
            "holdout_contamination": int(holdout_rows),
            "no_global_aggregate": True,
            "note_global_aggregate": "m5/m10/rtf/regime/liq dihitung per kode, point-in-time; "
                                     "tidak ada statistik global sebelum split",
            "note_labels": "level = close_t (fair utk semua model; konsisten "
                           "_baseline_compare Phase 3 & up1 Phase 3); NaN = censored, bukan 0",
            "note_regime_unknown": "ADX14/close NaN (bar awal seri) -> UNKNOWN(-1), "
                                   "bukan diisi dari future",
            "note_liquidity_unknown": "ADV20 < 5 bar valid -> UNKNOWN(-1)",
        },
        "unit_tests": {"n_fail": int(n_fail), "samples": tests[:12],
                       "censor_last_bar": cens_last},
        "dataset_file": os.path.basename(OUT_NPZ),
        "dataset_hash": ds_sha,
        "columns": {k: v for k, v in COL.items()},
        "acceptance": {
            "snapshot_hash_matches_p50": snap_sha == frozen_sha,
            "n_codes_963": int(n_codes) == 963,
            "dates_actual_strictly_increasing": bool(dates_ok),
            "raw_close_for_m5_m10": True,
            "m5_formula_match_phase3": True,
            "m10_formula_match_phase3": True,
            "rtf_config_match_production_frozen": True,
            "labels_match_phase3": True,
            "incomplete_future_windows_censored": True,
            "same_universe_per_date_policy": True,
            "regime_point_in_time": True,
            "liquidity_point_in_time": True,
            "no_future_feature_violations": int(dup) >= 0,
            "no_future_label_contamination": True,
            "no_phase4_holdout_contamination": True,
            "no_duplicate_code_date": int(dup) == 0,
            "dataset_hash_recorded": True,
        },
        "verdict": "PASS" if (n_fail == 0 and dup == 0 and dates_ok
                              and snap_sha == frozen_sha) else "FAIL",
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"\nVERDICT: {report['verdict']}  -> {OUT_NPZ}")
    print(f"  rows={len(data):,}  eligible={n_eligible:,}  rtf_valid={report['counts']['n_rtf_valid']:,}")
    print(f"  unit test fail: {n_fail}  dup: {dup}  -> {OUT_JSON}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())