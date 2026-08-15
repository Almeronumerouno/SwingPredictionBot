"""
_phase3_rtf_common.py — Module bersama Phase 3: RTF (Ready To Fly) validation.

Meniru logika PRODUKSI recovery.detect_accumulation PERSIS, tapi dievaluasi
untuk SETIAP baris t sebagai titik sinyal potensial (feature <= t, label > t)
— eval-only; TIDAK mengubah recovery.py / config.py / produksi mana pun.

Data: data/universe_ohlcv.npz (963 kode, dates nyata per bar, raw close).
Label: definisi _validate_accum4.py (multihorizon):
    rec_N  = max(high[t+1..t+N]) >= ref                     (balik ke ARA)
    b5_N   = max(high[t+1..t+N]) >= ref * 1.05              (breakout +5%)
    b10_N  = max(high[t+1..t+N]) >= ref * 1.10              (boom +10%)
    up1_N  = max(close[t+1..t+N]) >= close[t] * 1.05        (pump +5%)
    ret_N  = close[t+N-1]/close[t] - 1                      (return point)
  ref = harga event (ARA/puncak gelombang terbaru sebelum t).
  NaN bila forward window tidak lengkap (anti-lookahead, censored).

Parameter produksi dibaca dari config.py; grid eksperimen (tuning) didefinisikan
di sini. Komponen per-multiplier heavy dihitung sekaligus untuk MULT_GRID
(mirip _validate_accum4.py: _heavy_flags_multi).

Split (acceptance user):
  - cutoff global = quantile 0.70 dari SELURUH tanggal baris (absolut, disimpan)
  - PURGE: sinyal train yang forward window horizon MAKSIMUM (63) menembus
    cutoff dikeluarkan dari train
  - EMBARGO: test = sinyal dengan date_s > cutoff + 90 hari kalender;
    sinyal di rentang (cutoff, cutoff+90] dibuang (n_gap)
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

import config as CFG
import indicators as ind

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
DEFAULT_NPZ = os.path.join(DATA_DIR, "universe_ohlcv.npz")
ROWS_NPZ_PATH = os.path.join(DATA_DIR, "phase3_rtf_rows.npz")
ROWS_META_PATH = os.path.join(DATA_DIR, "phase3_rtf_rows_meta.json")

# ─────────────────────────────────────────────────────────────
# Konstanta eksperimen (grid tuning — TRAIN ONLY, tidak menyentuh produksi)
# ─────────────────────────────────────────────────────────────
HORIZONS = (5, 10, 21, 63)          # horizon outcome (hari trading ke depan)
PURGE_HORIZON = 63                  # horizon label maksimum utk purge
EMBARGO_DAYS = 90                   # hari kalender
CUTOFF_QUANTILE = 0.70

MULT_GRID = (1.5, 1.75, 2.0, 2.5, 3.0)     # ACCUM_HEAVY_RVOL kandidat
DENSITY_GRID = (20.0, 25.0, 30.0, 35.0, 40.0, 50.0)  # ACCUM_DENSITY_PCT (persen)
MIN_HEAVY_GRID = (1, 2, 3)                    # ACCUM_MIN_HEAVY_DAYS
TAU_GRID = (1.0, 1.5, 2.0, 3.0)               # ACCUM_DECAY_TAU
CUTOFF_GRID = (None, 5, 7, 10)                # ACCUM_DECAY_CUTOFF_DAYS (None = tanpa cutoff)

N_MIN_SIGNALS = 300         # min sinyal arm di TRAIN agar kandidat layak
NEAR_TIE_TOL_LIFT = 0.05    # beda lift <= tol -> prefer default (stabil/sederhana)
NEAR_TIE_TOL_AUC = 0.01     # beda AUC <= tol -> prefer default

MIN_BAR_IDX = 24            # guard v3/v4: rvol & sma valid


# ─────────────────────────────────────────────────────────────
# Load universe
# ─────────────────────────────────────────────────────────────
def load_universe(npz_path: str | None = None) -> dict:
    npz_path = npz_path or DEFAULT_NPZ
    d = np.load(npz_path, allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    lens = d["lens"].astype(int)
    return {
        "codes": codes,
        "rows": d["rows"],       # list per kode: (900, 6) [open, high, low, close, adj, vol]
        "lens": lens,
        "dates": d["dates"],     # list per kode: ISO strings, len == lens
    }


# ─────────────────────────────────────────────────────────────
# Forward arrays (copy _validate_accum4._forward_arrays)
# ─────────────────────────────────────────────────────────────
def _forward_arrays(high: np.ndarray, close: np.ndarray,
                    horizons: tuple[int, ...]) -> tuple[dict, dict, dict]:
    n = len(high)
    fmax: dict[int, np.ndarray] = {}
    fmaxc: dict[int, np.ndarray] = {}
    fret: dict[int, np.ndarray] = {}
    for N in horizons:
        if N + 1 <= n:
            sw = sliding_window_view(high, N + 1)
            fmax[N] = sw[:, 1:].max(axis=1)
            swc = sliding_window_view(close, N + 1)
            fmaxc[N] = swc[:, 1:].max(axis=1)
            fret[N] = close[N - 1: n - 1] / close[0: n - N] - 1.0
        else:
            fmax[N] = np.full(0, np.nan)
            fmaxc[N] = np.full(0, np.nan)
            fret[N] = np.full(0, np.nan)
    return fmax, fmaxc, fret


# ─────────────────────────────────────────────────────────────
# Per-kode: fitur per-baris (mirror produksi detect_accumulation)
# ─────────────────────────────────────────────────────────────
# Kolom baris hasil (float32) — indeks dipetakan lewat consts:
#   0  bar_idx (t asli)
#   1  anchor_idx
#   2  ref_idx
#   3  window (t - anchor)
#   4  pos_vs_ara (close[t]/close[ref])
#   5  above_ma (0/1)
#   6  liq_ok (0/1)
#   7..11   k_m      utk MULT_GRID
#   12..16  density_m (fraksi, 0..1)  utk MULT_GRID
#   17..21  ndh_m    utk MULT_GRID  (NaN bila k_m==0)
#   22..37  label: rec_N, b5_N, b10_N, up1_N x HORIZONS (NaN censored)
#   38..41  ret_N x HORIZONS (NaN censored)
#   42  ret_lag5 (feature momentum, feature <= t)
#   43  ret_lag10
NCOL = 44
I_BAR, I_ANCHOR, I_REF, I_WINDOW = 0, 1, 2, 3
I_POS, I_ABOVE_MA, I_LIQ = 4, 5, 6
I_K0, I_DEN0, I_NDH0 = 7, 12, 17
I_LABEL0 = 22          # rec/b5/b10/up1 x HORIZONS
I_RET0 = 38
I_RETLAG5, I_RETLAG10 = 42, 43

OUT_NAMES: list[str] = []
for _m in ("rec", "b5", "b10", "up1"):
    for _N in HORIZONS:
        OUT_NAMES.append(f"{_m}_{_N}")


def compute_code(rows: np.ndarray, dates: list, lens_i: int,
                 mults: tuple[float, ...] = MULT_GRID) -> np.ndarray | None:
    """Hitung baris fitur+label utk SATU kode. rows = (900,6) array npz."""
    n = int(lens_i)
    if n < MIN_BAR_IDX + 2:
        return None
    close = rows[:n, 3].astype(np.float64)   # raw close (basis produksi)
    high = rows[:n, 1].astype(np.float64)
    open_ = rows[:n, 0].astype(np.float64)
    volume = rows[:n, 5].astype(np.float64)

    rv = ind.rvol(volume, CFG.ACCUM_RVOL_PERIOD)

    # SMA20 tanpa look-ahead
    sma = np.full(n, np.nan)
    if n >= CFG.ACCUM_MA20_DAYS:
        cs = np.cumsum(np.concatenate(([0.0], close)))
        sma[CFG.ACCUM_MA20_DAYS - 1:] = (
            cs[CFG.ACCUM_MA20_DAYS:] - cs[:-CFG.ACCUM_MA20_DAYS]
        ) / CFG.ACCUM_MA20_DAYS

    # Event large upmove
    ara = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if close[i - 1] > 0 and close[i] >= close[i - 1] * (1.0 + CFG.ACCUM_ARA_RISE_PCT / 100.0):
            ara[i] = True

    fmax, fmaxc, fret = _forward_arrays(high, close, HORIZONS)

    cols: list[np.ndarray] = []
    last_ara: int | None = None
    prev_ara: int | None = None
    cur_anchor: int | None = None
    flags: list[np.ndarray] | None = None
    prefix_k: list[np.ndarray] | None = None   # cumsum heavy per mult
    prefix_ku: list[np.ndarray] | None = None  # cumsum (heavy & close>open) per mult

    nmult = len(mults)
    for t in range(1, n):
        if ara[t]:
            prev_ara, last_ara = last_ara, t
        if last_ara is None or t < MIN_BAR_IDX:
            continue

        # anchor & ref (mirror produksi)
        if prev_ara is not None and (last_ara - prev_ara) <= CFG.ACCUM_RVOL_PERIOD:
            anchor = prev_ara
            ref_idx = last_ara
        else:
            anchor = last_ara
            ref_idx = last_ara
        if anchor >= t:
            continue

        if anchor != cur_anchor:
            cur_anchor = anchor
            flags = _heavy_flags_multi(volume, rv, anchor, mults)
            prefix_k = [np.concatenate(([0], np.cumsum(f))) for f in flags]
            upf = [(f & (close > open_)).astype(float) for f in flags]
            prefix_ku = [np.concatenate(([0], np.cumsum(u))) for u in upf]

        ref = close[ref_idx]
        if not (ref > 0 and np.isfinite(ref)):
            continue
        window = t - anchor
        pos = close[t] / ref
        below = pos < 1.0
        above_ma = bool(np.isfinite(sma[t]) and close[t] >= sma[t])

        # ── per-mult heavy stats ──
        k_vals = np.zeros(nmult, dtype=np.float32)
        den_vals = np.full(nmult, np.nan, dtype=np.float32)
        ndh_vals = np.full(nmult, np.nan, dtype=np.float32)
        for m in range(nmult):
            k_vals[m] = int(prefix_k[m][t + 1] - prefix_k[m][anchor + 1])
            if window > 0:
                den_vals[m] = k_vals[m] / window
            if k_vals[m] > 0:
                ku = int(prefix_ku[m][t + 1] - prefix_ku[m][anchor + 1])
                ndh_vals[m] = ku / k_vals[m]

        # ── liquidity gate (ADV20 point-in-time, hari ARA dibuang) ──
        w0 = max(0, t - CFG.ACCUM_ADV_WINDOW + 1)
        seg_v = volume[w0:t + 1]
        seg_c = close[w0:t + 1]
        liq_ok = 0.0
        if len(seg_v) >= CFG.ACCUM_ADV_MIN_BARS:
            seg_ret = np.zeros(len(seg_v))
            seg_ret[1:] = seg_c[1:] / seg_c[:-1] - 1.0
            keep = seg_ret < (CFG.ACCUM_ARA_RISE_PCT / 100.0)
            av = seg_v[keep]
            ac = seg_c[keep]
            if len(av):
                adv_vol = float(av.mean())
                adv_val = float((av * ac).mean())
                liq_ok = 1.0 if (adv_vol >= CFG.ACCUM_MIN_ADV_VOL
                                 and adv_val >= CFG.ACCUM_MIN_ADV_VAL) else 0.0

        # ── label forward (NaN bila tidak lengkap) ──
        lab = np.full(len(OUT_NAMES), np.nan, dtype=np.float32)
        rets = np.full(len(HORIZONS), np.nan, dtype=np.float32)
        for hi, N in enumerate(HORIZONS):
            if t + N <= n - 1:
                fi = fmax[N][t]
                fi_c = fmaxc[N][t]
                lab[hi * 4 + 0] = 1.0 if fi >= ref else 0.0        # rec_N
                lab[hi * 4 + 1] = 1.0 if fi >= ref * 1.05 else 0.0  # b5_N
                lab[hi * 4 + 2] = 1.0 if fi >= ref * 1.10 else 0.0  # b10_N
                lab[hi * 4 + 3] = 1.0 if fi_c >= close[t] * 1.05 else 0.0  # up1_N
                rets[hi] = fret[N][t]

        rlag5 = close[t] / close[t - 5] - 1.0 if t >= 5 and close[t - 5] > 0 else np.nan
        rlag10 = close[t] / close[t - 10] - 1.0 if t >= 10 and close[t - 10] > 0 else np.nan

        row = np.concatenate([
            np.array([t, anchor, ref_idx, window, pos, float(above_ma), liq_ok],
                     dtype=np.float32),
            k_vals, den_vals, ndh_vals,
            lab, rets,
            np.array([rlag5, rlag10], dtype=np.float32),
        ])
        cols.append(row)

    if not cols:
        return None
    return np.stack(cols)


def _heavy_flags_multi(volume: np.ndarray, rv: np.ndarray, anchor: int,
                       mults: tuple[float, ...]) -> list[np.ndarray]:
    """Flag heavy per mult, satu anchor — mirror produksi (recovery.py)."""
    n = len(volume)
    out = [np.zeros(n, dtype=bool) for _ in mults]
    base_start = max(0, anchor - CFG.ACCUM_RVOL_PERIOD)
    pre_ara_avg = float(volume[base_start:anchor].mean()) if anchor > base_start else float("nan")
    if not (np.isfinite(pre_ara_avg) and pre_ara_avg > 0):
        pre_ara_avg = float("nan")

    cs = np.cumsum(np.concatenate(([0.0], volume)))
    for j in range(anchor + 1, n):
        cnt = j - anchor - 1
        if cnt >= 2:
            avg = (cs[j] - cs[anchor + 1]) / cnt
        else:
            avg = pre_ara_avg
        if np.isfinite(avg) and avg > 0:
            for k, m in enumerate(mults):
                out[k][j] = volume[j] >= m * avg
        else:
            valid_rv = bool(np.isfinite(rv[j]))
            for k, m in enumerate(mults):
                out[k][j] = valid_rv and rv[j] >= m
    return out


# ─────────────────────────────────────────────────────────────
# Aggregasi seluruh universe + cache row-level
# ─────────────────────────────────────────────────────────────
def build_rows(workers: int = 8) -> tuple[np.ndarray, list[str], np.ndarray, np.ndarray]:
    """Hitung baris utk seluruh kode; simpan cache phase3_rtf_rows.npz."""
    uni = load_universe()
    codes = uni["codes"]
    parts: list[np.ndarray] = []
    code_idx: list[int] = []
    code_ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut_map = {
            ex.submit(compute_code, uni["rows"][i], list(uni["dates"][i]), int(uni["lens"][i])): i
            for i in range(len(codes))
        }
        for fut in as_completed(fut_map):
            i = fut_map[fut]
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"[ERROR] {codes[i]}: {e}", file=sys.stderr)
                continue
            if r is None:
                continue
            code_ok += 1
            parts.append(r)
            code_idx.append(np.full(len(r), i, dtype=np.int32))

    rows = np.concatenate(parts) if parts else np.empty((0, NCOL), dtype=np.float32)
    ci = np.concatenate(code_idx) if code_idx else np.empty(0, dtype=np.int32)
    os.makedirs(DATA_DIR, exist_ok=True)
    np.savez_compressed(ROWS_NPZ_PATH, rows=rows.astype(np.float32),
                        code_idx=ci, codes=np.array(codes, dtype="S12"))
    meta = {
        "file": os.path.basename(ROWS_NPZ_PATH),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_codes": len(codes), "codes_ok": code_ok,
        "total_rows": int(len(rows)),
        "ncol": NCOL,
        "columns": {
            "0..6": "bar_idx, anchor_idx, ref_idx, window, pos_vs_ara, above_ma, liq_ok",
            "7..21": "k_m, density_m, ndh_m x MULT_GRID",
            "22..37": "rec/b5/b10/up1 x HORIZONS (NaN censored)",
            "38..41": "ret_N x HORIZONS (NaN censored)",
            "42..43": "ret_lag5, ret_lag10 (feature momentum)",
        },
        "horizons": list(HORIZONS),
        "mult_grid": list(MULT_GRID),
        "min_bar_idx": MIN_BAR_IDX,
        "censor_policy": "outcome NaN bila forward window [t+1..t+N] tidak penuh",
        "source": "universe_ohlcv.npz (local, tanpa Yahoo)",
    }
    with open(ROWS_META_PATH, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
    print(f"[ok] rows: {len(rows):,} baris, {code_ok}/{len(codes)} kode -> {ROWS_NPZ_PATH}",
          file=sys.stderr)
    return rows, codes, ci, np.array(codes, dtype="S12")


def load_rows(rows_path: str | None = None) -> tuple[np.ndarray, list[str], np.ndarray]:
    rows_path = rows_path or ROWS_NPZ_PATH
    if not os.path.exists(rows_path):
        raise FileNotFoundError(
            f"Cache rows tidak ada: {rows_path} — jalankan _phase3_rtf_common.build_rows "
            f"atau _phase3_rtf_wf.py --build")
    d = np.load(rows_path, allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    return d["rows"], codes, d["code_idx"]


# ─────────────────────────────────────────────────────────────
# Tanggal baris (datetime64) — untuk split
# ─────────────────────────────────────────────────────────────
def row_dates(codes: list[str], rows: np.ndarray, code_idx: np.ndarray) -> np.ndarray:
    """datetime64[D] per baris, dibaca dari universe_ohlcv.npz dates."""
    uni = load_universe()
    dates_obj = uni["dates"]
    out = np.empty(len(rows), dtype="datetime64[D]")
    seen: dict[int, np.ndarray] = {}
    for i in range(len(codes)):
        ds = np.array(dates_obj[i], dtype="datetime64[D]") if len(dates_obj[i]) else None
        seen[i] = ds
    for j in range(len(rows)):
        ci = int(code_idx[j])
        t = int(rows[j, I_BAR])
        out[j] = seen[ci][t]
    return out


# ─────────────────────────────────────────────────────────────
# Split global (acceptance: cutoff absolut + purge horizon max + embargo)
# ─────────────────────────────────────────────────────────────
def make_split(codes: list[str], rows: np.ndarray, code_idx: np.ndarray,
               dates_dt: np.ndarray, cutoff_q: float = CUTOFF_QUANTILE,
               embargo_days: int = EMBARGO_DAYS,
               purge_horizon: int = PURGE_HORIZON) -> dict:
    """Return masks train/test + metadata (cutoff absolut, purge, embargo)."""
    # cutoff absolut: quantile dari SELURUH tanggal baris
    sorted_dates = np.sort(dates_dt)
    cutoff_dt = sorted_dates[min(len(sorted_dates) - 1, int(len(sorted_dates) * cutoff_q))]
    cutoff_date = str(cutoff_dt)

    # bar terakhir per kode yang masih <= cutoff (utk purge)
    uni = load_universe()
    last_train_t = np.full(len(codes), -1, dtype=np.int32)
    for i in range(len(codes)):
        ds = np.array(uni["dates"][i], dtype="datetime64[D]")
        if len(ds) == 0:
            continue
        idx = np.searchsorted(ds, cutoff_dt, side="right") - 1
        last_train_t[i] = idx

    emb_dt = cutoff_dt + np.timedelta64(embargo_days, "D")

    n = len(rows)
    train = np.zeros(n, dtype=bool)
    test = np.zeros(n, dtype=bool)
    for j in range(n):
        ci = int(code_idx[j])
        t = int(rows[j, I_BAR])
        d = dates_dt[j]
        if d <= cutoff_dt:
            # purge: label horizon maksimum harus selesai sebelum cutoff
            if t + purge_horizon <= last_train_t[ci]:
                train[j] = True
        elif d > emb_dt:
            test[j] = True
        # else: n_gap (embargo) — dibuang

    return {
        "train": train,
        "test": test,
        "n_gap": int(n - int(train.sum()) - int(test.sum())),
        "n_train_rows": int(train.sum()),
        "n_test_rows": int(test.sum()),
        "cutoff_date": cutoff_date,
        "embargo_date": str(emb_dt),
        "purge_horizon": purge_horizon,
        "embargo_days": embargo_days,
        "cutoff_quantile": cutoff_q,
    }


# ─────────────────────────────────────────────────────────────
# Arm / kontrol / metrik
# ─────────────────────────────────────────────────────────────
def arm_mask(rows: np.ndarray, thr_density: float, mult: float, min_heavy: int) -> np.ndarray:
    """READY produksi: below & k>=min_heavy & density>=thr & above_ma & liq_ok.

    density & k & ndh diambil dari kolom multiplier `mult`.
    """
    m = int(MULT_GRID.index(mult))
    k = rows[:, I_K0 + m]
    den = rows[:, I_DEN0 + m]
    return ((rows[:, I_POS] < 1.0) & (k >= min_heavy) & (den * 100.0 >= thr_density)
            & (rows[:, I_ABOVE_MA] == 1.0) & (rows[:, I_LIQ] == 1.0))


def ctrl_mask(rows: np.ndarray) -> np.ndarray:
    """Kontrol: semua baris post-event yang masih di bawah level event."""
    return rows[:, I_POS] < 1.0


def strength_score(rows: np.ndarray, mult: float, tau: float,
                   cutoff: int | None) -> np.ndarray:
    """Formula produksi: (density/100) * (ndh or 0.5) * decay(d, tau, cutoff)."""
    m = int(MULT_GRID.index(mult))
    den = rows[:, I_DEN0 + m]
    ndh = rows[:, I_NDH0 + m]
    d = rows[:, I_WINDOW]
    decay = np.where(d < cutoff, np.exp(-d / tau), 0.0) if cutoff is not None \
        else np.exp(-d / tau)
    ndh_safe = np.where(np.isfinite(ndh), ndh, 0.5)
    return den * ndh_safe * decay


def label_col(label: str, horizon: int) -> int:
    idx = OUT_NAMES.index(f"{label}_{horizon}")
    return I_LABEL0 + idx


def _prop_test(a: np.ndarray, c: np.ndarray) -> dict | None:
    from scipy.stats import chi2_contingency, norm
    a = np.asarray(a, dtype=float)
    c = np.asarray(c, dtype=float)
    a = a[np.isfinite(a)]
    c = c[np.isfinite(c)]
    x1, n1 = int(a.sum()), int(len(a))
    x2, n2 = int(c.sum()), int(len(c))
    if n1 == 0 or n2 == 0:
        return None
    p1, p2 = x1 / n1, x2 / n2
    phat = (x1 + x2) / (n1 + n2)
    se = np.sqrt(phat * (1.0 - phat) * (1.0 / n1 + 1.0 / n2))
    z = (p1 - p2) / se if se > 0 else float("nan")
    p_z = float(2.0 * (1.0 - norm.cdf(abs(z)))) if np.isfinite(z) else None
    table = [[x1, n1 - x1], [x2, n2 - x2]]
    try:
        chi2_val, p_chi, _, _ = chi2_contingency(table, correction=True)
    except ValueError:  # noqa: BLE001
        chi2_val, p_chi = float("nan"), 1.0
    return {
        "n_arm": n1, "n_ctrl": n2,
        "rate_arm": round(float(p1), 4), "rate_ctrl": round(float(p2), 4),
        "delta": round(float(p1 - p2), 4),
        "z": round(float(z), 3) if np.isfinite(z) else None,
        "p_z": round(p_z, 4) if p_z is not None else None,
    }


def metrics_arm(rows: np.ndarray, arm: np.ndarray, ctrl: np.ndarray,
                horizons: tuple[int, ...] = HORIZONS) -> dict:
    """Metrik arm vs kontrol per horizon + ret median arm."""
    out = {"n_arm": int(arm.sum()), "n_ctrl": int(ctrl.sum()), "horizons": []}
    for hi, N in enumerate(horizons):
        rec = rows[arm, I_LABEL0 + hi * 4 + 0]
        b5 = rows[arm, I_LABEL0 + hi * 4 + 1]
        b10 = rows[arm, I_LABEL0 + hi * 4 + 2]
        up = rows[arm, I_LABEL0 + hi * 4 + 3]
        c10 = rows[ctrl, I_LABEL0 + hi * 4 + 2]
        b10_arm = float(np.nanmean(b10)) if np.isfinite(b10).any() else None
        b10_ctrl = float(np.nanmean(c10)) if np.isfinite(c10).any() else None
        lift = (b10_arm / b10_ctrl) if (b10_arm is not None and b10_ctrl not in (None, 0.0)) else None
        ret_med = None
        rv = rows[arm, I_RET0 + hi]
        if np.isfinite(rv).any():
            ret_med = float(np.median(rv[np.isfinite(rv)]))
        out["horizons"].append({
            "horizon": N,
            "arm": {
                "n": int(np.isfinite(b10).sum()),
                "rec": round(float(np.nanmean(rec)), 4) if np.isfinite(rec).any() else None,
                "b5": round(float(np.nanmean(b5)), 4) if np.isfinite(b5).any() else None,
                "b10": round(b10_arm, 4) if b10_arm is not None else None,
                "up1": round(float(np.nanmean(up)), 4) if np.isfinite(up).any() else None,
                "ret_median": round(ret_med, 4) if ret_med is not None else None,
            },
            "ctrl": {
                "b10": round(b10_ctrl, 4) if b10_ctrl is not None else None,
            },
            "lift_b10": round(lift, 3) if lift is not None else None,
            "test_b10": _prop_test(rows[arm, I_LABEL0 + hi * 4 + 2],
                                   rows[ctrl, I_LABEL0 + hi * 4 + 2]),
        })
    return out


def train_metrics(rows: np.ndarray, arm: np.ndarray, ctrl: np.ndarray) -> dict:
    """Acceptance user: train_metrics = {b10, lift_b10, n_signals} (horizon 10)."""
    hi10 = HORIZONS.index(10)
    b10 = rows[arm, I_LABEL0 + hi10 * 4 + 2]
    c10 = rows[ctrl, I_LABEL0 + hi10 * 4 + 2]
    b10_arm = float(np.nanmean(b10)) if np.isfinite(b10).any() else None
    b10_ctrl = float(np.nanmean(c10)) if np.isfinite(c10).any() else None
    lift = (b10_arm / b10_ctrl) if (b10_arm is not None and b10_ctrl not in (None, 0.0)) else None
    return {
        "b10": round(b10_arm, 4) if b10_arm is not None else None,
        "lift_b10": round(lift, 3) if lift is not None else None,
        "n_signals": int(np.isfinite(b10).sum()),
    }


# ─────────────────────────────────────────────────────────────
# Ranking: AUC & precision@K (Phase E)
# ─────────────────────────────────────────────────────────────
def auc_score(rows: np.ndarray, mask: np.ndarray, score: np.ndarray,
              label: str, horizon: int) -> float | None:
    from sklearn.metrics import roc_auc_score
    col = label_col(label, horizon)
    sel = mask & np.isfinite(score) & np.isfinite(rows[:, col])
    if int(sel.sum()) < 4:
        return None
    y = rows[sel, col]
    if len(set(y.tolist())) < 2:
        return None
    try:
        return round(float(roc_auc_score(y, score[sel])), 4)
    except ValueError:
        return None


def precision_at_k(rows: np.ndarray, mask: np.ndarray, score: np.ndarray,
                   label: str, horizon: int, K: int) -> dict | None:
    col = label_col(label, horizon)
    sel = mask & np.isfinite(score) & np.isfinite(rows[:, col])
    n = int(sel.sum())
    if n == 0:
        return None
    k = min(K, n)
    order = np.argsort(-score[sel])[:k]
    y = rows[sel, col][order]
    base = float(np.nanmean(rows[sel, col]))
    prec = float(np.mean(y))
    return {
        "K": K, "n_avail": n,
        "precision": round(prec, 4),
        "base_rate": round(base, 4),
        "lift": round(prec / base, 3) if base > 0 else None,
    }


# ─────────────────────────────────────────────────────────────
# Bootstrap CI (stock-cluster, tanpa refit — rule-based)
# ─────────────────────────────────────────────────────────────
def bootstrap_ci(metric_fn, n_stocks: int, B: int = 1000, seed: int = 42,
                 workers: int = 8) -> dict:
    rng = np.random.default_rng(seed)

    def _one(_: int) -> float | None:
        stocks = rng.integers(0, n_stocks, size=n_stocks)
        try:
            return metric_fn(stocks)
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        vals = list(ex.map(_one, range(B)))
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"error": "bootstrap kosong"}
    arr = np.asarray(vals)
    return {
        "B": len(vals),
        "point": round(float(np.mean(arr)), 4),
        "ci95": [round(float(np.percentile(arr, 2.5)), 4),
                 round(float(np.percentile(arr, 97.5)), 4)],
        "p_gt_0": round(float(np.mean(arr > 0)), 4),
    }


# ─────────────────────────────────────────────────────────────
# Utilitas JSON
# ─────────────────────────────────────────────────────────────
def write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, default=str)
    print(f"[ok] {path}", file=sys.stderr)


def default_config() -> dict:
    return {
        "ACCUM_ARA_RISE_PCT": CFG.ACCUM_ARA_RISE_PCT,
        "ACCUM_RVOL_PERIOD": CFG.ACCUM_RVOL_PERIOD,
        "ACCUM_DENSITY_PCT": CFG.ACCUM_DENSITY_PCT,
        "ACCUM_MIN_HEAVY_DAYS": CFG.ACCUM_MIN_HEAVY_DAYS,
        "ACCUM_HEAVY_RVOL": CFG.ACCUM_HEAVY_RVOL,
        "ACCUM_MA20_DAYS": CFG.ACCUM_MA20_DAYS,
        "ACCUM_DECAY_TAU": CFG.ACCUM_DECAY_TAU,
        "ACCUM_DECAY_CUTOFF_DAYS": CFG.ACCUM_DECAY_CUTOFF_DAYS,
        "ACCUM_MIN_ADV_VOL": CFG.ACCUM_MIN_ADV_VOL,
        "ACCUM_MIN_ADV_VAL": CFG.ACCUM_MIN_ADV_VAL,
    }


def selected_config(density: float, mult: float, min_heavy: int,
                    tau: float, cutoff: int | None) -> dict:
    c = default_config()
    c["ACCUM_DENSITY_PCT"] = density
    c["ACCUM_HEAVY_RVOL"] = mult
    c["ACCUM_MIN_HEAVY_DAYS"] = min_heavy
    c["ACCUM_DECAY_TAU"] = tau
    c["ACCUM_DECAY_CUTOFF_DAYS"] = cutoff
    return c


if __name__ == "__main__":
    build_rows(workers=int(sys.argv[1]) if len(sys.argv) > 1 else 8)
