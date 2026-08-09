"""
_validate_accum4.py — [v4.2] Validasi pola "akumulasi post-ARA" — replikasi
walk-forward dari logika PRODUKSI TERBARU (recovery.detect_accumulation,
November 2026): baseline volume = mean polos SELURUH hari post-ARA sebelum
hari berjalan (anti-self-referencing), fallback pre-ARA 20d / RVOL20;
anchor double-ARA; heavy_cnt >= MIN + pos_vs_ara < 1.0 + close >= SMA20 =
sinyal READY produksi. Gate density diuji sebagai knob threshold
(0.30 / 0.40) dalam SATU pass.

Perbedaan v4.1 -> v4.2 (request user 2026-08-09 — SATU pass 963 saham):
  1. MULTI-HORIZON: outcome dihitung utk N = 5 / 10 / 21 / 63 hari trading
     ke depan SEKALIGUS per baris (bukan cuma 5d):
         rec_N  = max(high[t+1..t+N]) >= ref                    (balik ke ARA)
         b5_N   = max(high[t+1..t+N]) >= ref * 1.05             (breakout +5%)
         b10_N  = max(high[t+1..t+N]) >= ref * 1.10             (boom +10%)
         up1_N  = max(close[t+1..t+N]) >= close[t] * 1.05       (pump +5%)
         ret_N  = close[t+N-1]/close[t] - 1                     (return point)
       Implementasi vektor per kode via sliding-window-view (murah).
       Outcome = NaN (censored) bila forward window N belum lengkap
       (anti-lookahead: baris tetap tersimpan utk horizon yang lebih pendek).
  2. DUA THRESHOLD DENSITY (0.30 & 0.40) dihitung sekaligus:
         arm-lengkap   = pos<ARA && heavy_cnt>=2 && density>=thr && above_MA20
         kontrol       = density < thr   (kontrol-below utk perbandingan adil)
     Klasifikasi dilakukan SAAT ANALISIS dari row-level — threshold baru
     TIDAK perlu fetch ulang.
  3. ROW-LEVEL disimpan ke data/accum_rows.npz (compressed) +
     data/accum_rows_meta.json — riset lanjutan TANPA fetch 963 saham.
     Kolom: code_idx, bar_idx, pos_vs_ara, heavy_cnt, window, density,
     above_ma, cross2, heavy_cnt_25, density_25, seluruh outcome 16
     kolom (rec/b5/b10/up1 x 5/10/21/63), ret_5 & ret_21.
  4. Analisis tetap per horizon per threshold: n, rec_N, b5_N, b10_N,
     up1_N utk arm & kontrol-below + delta b10 + chi2-Yates & uji-z dua
     proporsi; median & mean return utk N = 5 & 21.
  5. Mode BARU --analyze PATH: reproduksi laporan dari rows.npz TANPA
     jaringan; threshold lain lewat --thr — eksperimen lanjutan murah.

TIDAK mengubah recovery.py / config.py / _validate_accum3.py.

Usage:
    python _validate_accum4.py                                 # scan universe (963)
    python _validate_accum4.py --codes SOLA AKPI               # batasi kode
    python _validate_accum4.py --length 800 --workers 8        # satu pass penuh
    python _validate_accum4.py --thr 0.30 0.40 0.50            # set thr analisis
    python _validate_accum4.py --analyze data/accum_rows.npz   # offline re-run
    python _validate_accum4.py --analyze ... --thr 0.50 0.60   # thr baru, no fetch
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.stats import chi2_contingency, norm

import config as CFG
import indicators as ind
from data_source.gainers import get_or_fetch_securities_list
from data_source.yahoo_client import fetch_trading_info

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")

# ---- Parameter tetap (keputusan produksi, mirror recovery.py) ----
HEAVY_MULT_BASE = 2.0        # multiplikator heavy setting produksi
HEAVY_MULT_EXTRA = 2.5       # knob alternatif — ikut dihitung sekali
MIN_HEAVY_BASE = 2           # minimal hari heavy utk "READY"
HORIZONS = (5, 10, 21, 63)   # horizon outcome (hari trading ke depan)
THR_DEFAULT = (0.30, 0.40)   # gate density yang diuji

# ---- nama & indeks kolom outcome: rec_N, b5_N, b10_N, up1_N x HORIZONS ----
OUT_NAMES: list[str] = []
OUT_IDX: dict[str, int] = {}
for _m in ("rec", "b5", "b10", "up1"):
    for _N in HORIZONS:
        OUT_IDX[f"{_m}_{_N}"] = len(OUT_NAMES)
        OUT_NAMES.append(f"{_m}_{_N}")
OUT_NCOLS = len(OUT_NAMES)  # 16

# kolom fitur (baris row-level)
FEAT_NAMES = ["pos_vs_ara", "heavy_cnt", "window", "density",
              "above_ma", "cross2", "heavy_cnt_25", "density_25"]
FEAT_NCOLS = len(FEAT_NAMES)

# path default output
MULTI_JSON_PATH = os.path.join(DATA_DIR, "validate_multihorizon.json")
ROWS_NPZ_PATH = os.path.join(DATA_DIR, "accum_rows.npz")
ROWS_META_PATH = os.path.join(DATA_DIR, "accum_rows_meta.json")


# ---------------------------------------------------------------------------
# Inti per-kode: SATU fetch -> semua fitur + semua outcome horizon
# ---------------------------------------------------------------------------

def _forward_arrays(high: np.ndarray, close: np.ndarray,
                    horizons: tuple[int, ...]) -> tuple[dict, dict, dict]:
    """
    Utk tiap N, array berindeks baris i:
      fmax[N][i]  = max(high[i+1 .. i+N])      (valid utk i+N <= n-1; len n-N)
      fmaxc[N][i] = max(close[i+1 .. i+N])     (sama)
      fret[N][i]  = close[i+N-1] / close[i] - 1
    Sliding view (n-N, N+1): baris i = [i..i+N] -> ambil [1:] = [i+1..i+N].
    Array DIMENSI len 0 bila data < N+1 (jarang terjadi utk length 800).
    """
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
            # fret[N][i] = close[i+N-1]/close[i] - 1, i valid utk 0..n-N-1
            fret[N] = close[N - 1: n - 1] / close[0: n - N] - 1.0
        else:
            fmax[N] = np.full(0, np.nan)
            fmaxc[N] = np.full(0, np.nan)
            fret[N] = np.full(0, np.nan)
    return fmax, fmaxc, fret


def _heavy_flags_multi(volume: np.ndarray, rv: np.ndarray, anchor: int,
                       mults: list[float]) -> list[np.ndarray]:
    """
    Flag "heavy" utk SEMUA mult sekaligus, satu anchor — mirror produksi
    recovery.detect_accumulation per hari j:
      baseline_j = mean(volume[anchor+1 : j])  (eksklusif j; anti-self-ref)
                   kalau len >= 2 & finite & > 0,
      else fallback mean(volume[max(0,anchor-20) : anchor]),
      else RVOL rolling 20 (rv[j] >= mult).
    Hari ARA anchor tidak ikut baseline & window.
    """
    n = len(volume)
    out = [np.zeros(n, dtype=bool) for _ in mults]
    base_start = max(0, anchor - 20)
    pre_ara_avg = float(volume[base_start:anchor].mean()) if anchor > base_start else float("nan")
    if not (np.isfinite(pre_ara_avg) and pre_ara_avg > 0):
        pre_ara_avg = float("nan")

    cs = np.cumsum(np.concatenate(([0.0], volume)))
    for j in range(anchor + 1, n):
        cnt = j - anchor - 1  # len(volume[anchor+1 : j])
        if cnt >= 2:
            avg = (cs[j] - cs[anchor + 1]) / cnt
        else:
            avg = pre_ara_avg
        if np.isfinite(avg) and avg > 0:
            for k, mult in enumerate(mults):
                out[k][j] = volume[j] >= mult * avg
        else:
            valid_rv = bool(np.isfinite(rv[j]))
            for k, mult in enumerate(mults):
                out[k][j] = valid_rv and rv[j] >= mult
    return out


def _events_for_code(code: str, length: int, ara_pct: float, ma_days: int) -> dict:
    bars = fetch_trading_info(code, length=length)
    if not bars:
        return {"code": code, "error": "data kosong (Yahoo kosong/delisted)"}
    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    volume = np.array([b.volume for b in bars], dtype=float)
    n = len(close)
    if n > 0 and n < CFG.RECOVERY_MIN_BARS:
        return {"code": code, "error": f"data cuma {n} bar"}

    rv = ind.rvol(volume, 20)

    # rolling SMA tanpa look-ahead: sma[i] = mean(close[i-ma_days+1..i])
    sma = np.full(n, np.nan)
    if n >= ma_days:
        cs = np.cumsum(np.concatenate(([0.0], close)))
        sma[ma_days - 1:] = (cs[ma_days:] - cs[:-ma_days]) / ma_days

    # ARA: close[i] >= close[i-1] * (1 + ara_pct/100)
    ara = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if close[i - 1] > 0 and close[i] >= close[i - 1] * (1.0 + ara_pct / 100.0):
            ara[i] = True

    # outcome forward multi-horizon (vektor per N)
    fmax, fmaxc, fret = _forward_arrays(high, close, HORIZONS)

    feats: list[np.ndarray] = []   # (FEAT_NCOLS,) float32
    outs: list[np.ndarray] = []    # (OUT_NCOLS,) float32, NaN bila horizon <N
    rets: list[np.ndarray] = []    # (2,) float32: ret_5, ret_21
    bars_idx: list[int] = []

    last_ara: int | None = None
    prev_ara: int | None = None
    cur_anchor: int | None = None
    flags: list[np.ndarray] | None = None
    prefix: list[np.ndarray] | None = None

    for idx in range(1, n):
        if ara[idx]:
            prev_ara, last_ara = last_ara, idx
        if last_ara is None:
            continue
        # butuh sma valid, rv valid (guard v3/v4: i >= 24)
        if idx < 24:
            continue

        # anchor & referensi harga (mirror produksi, point-in-time):
        # double-wave: ARA kedua <= 20 hari setelah ARA pertama -> anchor =
        # ARA pertama, referensi harga = ARA terbaru (puncak gelombang).
        if prev_ara is not None and (last_ara - prev_ara) <= CFG.ACCUM_RVOL_PERIOD:
            anchor = prev_ara
            ref_idx = last_ara  # konsisten v4: ref = puncak gelombang
        else:
            anchor = last_ara
            ref_idx = last_ara
        if anchor >= idx:
            continue  # hari ini = ARA terbaru -> belum ada window akumulasi

        if anchor != cur_anchor:
            cur_anchor = anchor
            flags = _heavy_flags_multi(volume, rv, anchor,
                                       [HEAVY_MULT_BASE, HEAVY_MULT_EXTRA])
            prefix = [np.concatenate(([0], np.cumsum(f))) for f in flags]

        ref = close[ref_idx]
        if not (ref > 0 and np.isfinite(ref)):
            continue
        window = idx - anchor
        pos = close[idx] / ref
        below = pos < 1.0
        above_ma = bool(np.isfinite(sma[idx]) and close[idx] >= sma[idx])
        cross2 = above_ma and (
            (np.isfinite(sma[idx - 1]) and close[idx - 1] < sma[idx - 1])
            or (idx - 2 >= 0 and np.isfinite(sma[idx - 2]) and close[idx - 2] < sma[idx - 2])
        )

        heavy_cnt = int(prefix[0][idx + 1] - prefix[0][anchor + 1])
        density = heavy_cnt / window
        heavy_cnt_25 = int(prefix[1][idx + 1] - prefix[1][anchor + 1])
        density_25 = heavy_cnt_25 / window

        # outcome per horizon — akses langsung dari array forward
        out = np.full(OUT_NCOLS, np.nan, dtype=np.float32)
        for N in HORIZONS:
            if idx + N <= n - 1:  # forward window [idx+1 .. idx+N] lengkap
                fi = fmax[N][idx]
                fi_c = fmaxc[N][idx]
                out[OUT_IDX[f"rec_{N}"]] = 1.0 if fi >= ref else 0.0
                out[OUT_IDX[f"b5_{N}"]] = 1.0 if fi >= ref * 1.05 else 0.0
                out[OUT_IDX[f"b10_{N}"]] = 1.0 if fi >= ref * 1.10 else 0.0
                out[OUT_IDX[f"up1_{N}"]] = 1.0 if fi_c >= close[idx] * 1.05 else 0.0

        ret = np.full(2, np.nan, dtype=np.float32)
        if idx + 5 <= n - 1:
            ret[0] = float(fret[5][idx])
        if idx + 21 <= n - 1:
            ret[1] = float(fret[21][idx])

        feats.append(np.array([pos, heavy_cnt, window, density,
                               float(above_ma), float(cross2),
                               heavy_cnt_25, density_25], dtype=np.float32))
        outs.append(out)
        rets.append(ret)
        bars_idx.append(idx)

    if not feats:
        return {"code": code, "rows": 0}
    return {
        "code": code,
        "rows": len(feats),
        "feats": np.stack(feats),
        "outs": np.stack(outs),
        "rets": np.stack(rets),
        "bars": np.asarray(bars_idx, dtype=np.uint16),
    }


# ---------------------------------------------------------------------------
# Statistik & tabel
# ---------------------------------------------------------------------------

def _prop_test(a: np.ndarray, c: np.ndarray) -> dict | None:
    """Uji dua proporsi (kolom outcome): chi2 2x2 (Yates) + uji-z dua proporsi."""
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
        chi2_val, p_chi, _ = float("nan"), 1.0, None
    return {
        "n_arm": n1, "n_ctrl": n2,
        "rate_arm": round(p1, 4), "rate_ctrl": round(p2, 4),
        "delta": round(p1 - p2, 4),
        "chi2": round(float(chi2_val), 3) if chi2_val is not None else None,
        "p_chi2": round(float(p_chi), 4),
        "z": round(float(z), 3) if np.isfinite(z) else None,
        "p_z": round(p_z, 4) if p_z is not None else None,
    }


def _analyze_rows(feats: np.ndarray, outs: np.ndarray, rets: np.ndarray,
                  thr: float) -> dict:
    """
    Analisis satu threshold, per horizon N (5/10/21/63):
      arm  = pos_below && heavy_cnt>=MIN && density>=thr && above_MA
      ctrl = density < thr  (kontrol-below: juga pos<ARA — perbandingan adil)
    Plus median/mean return ret_5 / ret_21 & uji b10 per horizon.
    """
    pos = feats[:, 0].astype(np.float64)
    heavy = feats[:, 1]
    density = feats[:, 3]
    above_ma = feats[:, 4] == 1.0

    below = pos < 1.0
    arm_mask = below & (heavy >= MIN_HEAVY_BASE) & (density >= thr) & above_ma
    ctrl_mask = (density < thr) & below  # kontrol-below
    ctrl_all_mask = density < thr

    per_horizon: list[dict] = []
    for N in HORIZONS:
        idx_rec, idx_b5, idx_b10, idx_up = (OUT_IDX[f"rec_{N}"], OUT_IDX[f"b5_{N}"],
                                            OUT_IDX[f"b10_{N}"], OUT_IDX[f"up1_{N}"])

        def _stat(mask: np.ndarray) -> dict:
            rec = outs[mask, idx_rec]
            b5 = outs[mask, idx_b5]
            b10 = outs[mask, idx_b10]
            up = outs[mask, idx_up]
            return {
                "n": int(mask.sum()),
                "rec": float(np.nanmean(rec)) if np.isfinite(rec).any() else None,
                "b5": float(np.nanmean(b5)) if np.isfinite(b5).any() else None,
                "b10": float(np.nanmean(b10)) if np.isfinite(b10).any() else None,
                "up1": float(np.nanmean(up)) if np.isfinite(up).any() else None,
            }

        s_arm = _stat(arm_mask)
        s_ctrl = _stat(ctrl_mask)

        # median/mean return — rets[:,0]=ret_5, rets[:,1]=ret_21
        ret_block: dict[str, dict] = {}
        for tag, col in (("5", 0), ("21", 1)):
            v = rets[:, col].astype(np.float64)
            va = v[arm_mask][np.isfinite(v[arm_mask])]
            vc = v[ctrl_mask][np.isfinite(v[ctrl_mask])]
            ret_block[f"ret_{tag}"] = {
                "median_arm": round(float(np.median(va)), 4) if va.size else None,
                "mean_arm": round(float(np.mean(va)), 4) if va.size else None,
                "median_ctrl": round(float(np.median(vc)), 4) if vc.size else None,
                "mean_ctrl": round(float(np.mean(vc)), 4) if vc.size else None,
            }

        per_horizon.append({
            "horizon": N,
            "arm": s_arm,
            "ctrl": s_ctrl,
            "test_b10": _prop_test(outs[arm_mask, idx_b10], outs[ctrl_mask, idx_b10]),
            **ret_block,
        })

    return {
        "threshold": thr,
        "n_arm_total": int(arm_mask.sum()),
        "n_ctrl_total": int(ctrl_mask.sum()),
        "n_ctrl_all": int(ctrl_all_mask.sum()),
        "horizons": per_horizon,
    }


# ---------------------------------------------------------------------------
# Aggregator multikode + simpan row-level
# ---------------------------------------------------------------------------

def _analyze_loaded(z: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Muat kembali arrays dari npz (dipanggil run & analyze mode)."""
    return z["feats"], z["outs"], z["rets"]


def _save_rows(npz_path: str, codes: list[str], feats: np.ndarray, outs: np.ndarray,
               rets: np.ndarray, bars: np.ndarray, code_idx: np.ndarray,
               extra: dict) -> None:
    os.makedirs(os.path.dirname(npz_path) if os.path.dirname(npz_path) else ".", exist_ok=True)
    np.savez_compressed(
        npz_path,
        feats=feats.astype(np.float32),
        outs=outs.astype(np.float32),
        rets=rets.astype(np.float32),
        bars=bars,
        code_idx=code_idx,
        codes=np.array(codes, dtype="S12"),
    )
    meta = {
        "file": os.path.basename(npz_path),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "param": {
            "ara_pct": extra.get("ara_pct"), "ma_days": extra.get("ma_days"),
            "length": extra.get("length"),
            "heavy_mult_base": HEAVY_MULT_BASE, "heavy_mult_extra": HEAVY_MULT_EXTRA,
            "min_heavy_base": MIN_HEAVY_BASE,
        },
        "horizons": list(HORIZONS),
        "thresholds": list(THR_DEFAULT),
        "warnings": extra.get("warnings", {}),
        "n_codes": extra.get("n_codes"), "codes_ok": extra.get("codes_ok"),
        "total_rows": int(len(feats)),
        "columns": {
            "code_idx": "indeks kode dalam 'codes' (urutan ekstra['code_order'])",
            "bar_idx": "indeks bar dalam windows length=.. (0-based, dari terlama)",
            "feats": FEAT_NAMES,
            "outs": OUT_NAMES,
            "rets": ["ret_5", "ret_21"],
        },
        "censor_policy": "outcome NaN bila forward window [t+1..t+N] tidak penuh (anti-lookahead)",
        "code_order": extra.get("code_order", []),
    }
    with open(ROWS_META_PATH, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
    print(f"  [ok] row-level disimpan: {npz_path}  ({meta['total_rows']} baris)", file=sys.stderr)
    print(f"  [ok] meta: {ROWS_META_PATH}", file=sys.stderr)


def _run(codes: list[str], length: int, workers: int, ara_pct: float,
         ma_days: int, thrs: tuple[float, ...]) -> dict:
    n_codes = len(codes)
    print(f"Scan {n_codes} saham (ARA +{ara_pct:.0f}%, SMA{ma_days}, length {length}, "
          f"{workers} worker) — multihorizon {HORIZONS}; UDAH SAAT: {datetime.now():%H:%M:%S}…",
          file=sys.stderr)

    fetch_errors: list[str] = []
    short_data: list[str] = []
    empty_data: list[str] = []
    ok_codes = 0
    total_rows = 0

    feats_parts: list[np.ndarray] = []
    outs_parts: list[np.ndarray] = []
    rets_parts: list[np.ndarray] = []
    bars_parts: list[np.ndarray] = []
    code_idx_parts: list[np.ndarray] = []

    done = 0
    code_map = {c: i for i, c in enumerate(codes)}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_events_for_code, c, length, ara_pct, ma_days): c for c in codes}
        for fut in as_completed(futures):
            code = futures[fut]
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f"  [{done}/{len(futures)}]", file=sys.stderr)
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001 — rate-limit/network dll
                fetch_errors.append(code)
                print(f"[ERROR] {code}: {e}", file=sys.stderr)
                continue
            if "error" in res:
                if res["error"].startswith("data kosong"):
                    empty_data.append(code)
                else:
                    short_data.append(code)
                print(f"[WARN] {code}: {res['error']}", file=sys.stderr)
                continue
            ok_codes += 1
            k = res.get("rows", 0)
            if k == 0:
                continue
            total_rows += k
            feats_parts.append(res["feats"])
            outs_parts.append(res["outs"])
            rets_parts.append(res["rets"])
            bars_parts.append(res["bars"])
            code_idx_parts.append(np.full(k, code_map[code], dtype=np.uint16))

    feats = np.concatenate(feats_parts) if feats_parts else np.empty((0, FEAT_NCOLS), dtype=np.float32)
    outs = np.concatenate(outs_parts) if outs_parts else np.empty((0, OUT_NCOLS), dtype=np.float32)
    rets = np.concatenate(rets_parts) if rets_parts else np.empty((0, 2), dtype=np.float32)
    bars = np.concatenate(bars_parts) if bars_parts else np.empty(0, dtype=np.uint16)
    code_idx = np.concatenate(code_idx_parts) if code_idx_parts else np.empty(0, dtype=np.uint16)

    warnings = {"fetch_errors": len(fetch_errors), "short_data": len(short_data),
                "empty_data": len(empty_data)}
    extra = {
        "length": length, "ara_pct": ara_pct, "ma_days": ma_days,
        "warnings": warnings, "codes": n_codes, "codes_ok": ok_codes,
        "code_order": codes,
    }
    _save_rows(ROWS_NPZ_PATH, codes, feats, outs, rets, bars, code_idx, extra)

    # analisis per threshold
    result = {
        "codes": n_codes, "codes_ok": ok_codes, "length": length,
        "ara_pct": ara_pct, "ma_days": ma_days,
        "warnings": warnings,
        "failed_codes": sorted(fetch_errors + short_data + empty_data),
        "total_rows": total_rows,
        "rows_file": ROWS_NPZ_PATH,
        "rows_meta": ROWS_META_PATH,
        "thresholds": [],
    }
    for thr in thrs:
        result["thresholds"].append(_analyze_rows(feats, outs, rets, thr))

    return result


# ---------------------------------------------------------------------------
# Laporan (Bahasa Indonesia)
# ---------------------------------------------------------------------------

def _pct(x: float | None, nd: int = 1) -> str:
    return f"{x * 100:.{nd}f}%" if x is not None else "—"


def _fmt(tb: dict | None, key: str) -> str:
    if tb is None or tb.get(key) is None:
        return "—"
    v = tb[key]
    if v == 0.0:
        return "<1e-16"
    return f"{v:.1e}"


def _print_report(result: dict) -> None:
    print()
    print("=" * 116)
    print("  VALIDASI v4.2 - akumulasi post-ARA MULTI-HORIZON "
          f"(B={HEAVY_MULT_BASE:.1f}x, K>={MIN_HEAVY_BASE}, density>=thr, SMA20)")
    ara_s = f"{result['ara_pct']:.0f}%" if result.get("ara_pct") is not None else "-"
    len_s = str(result["length"]) if result.get("length") is not None else "-"
    print(f"  ARA +{ara_s} | panjang {len_s} | "
          f"{result['codes']} kode ({result['codes_ok']} OK) | " 
          f"baris: {result['total_rows']:,}")
    print("=" * 116)
    for t in result["thresholds"]:
        thr = t["threshold"]
        print()
        print(f"  + THRESHOLD DENSITY >= {thr:.2f} - (arm = below+heavy>=K+density>=thr+SMA20 | "
              f"kontrol = density<{thr:.2f} & below)")
        print(f"  |  arm total n={t['n_arm_total']:,} | kontrol-below n={t['n_ctrl_total']:,} | "
              f"kontrol-semua n={t['n_ctrl_all']:,}")
        print(f"  +- {'N':>3} {'arm n':>7} {'rec%':>7} {'b5%':>7} {'b10%':>7} {'up1%':>7} "
              f"| {'ctrl n':>8} {'rec%':>7} {'b5%':>7} {'b10%':>7} {'up1%':>7} "
              f"| {'d b10':>7} {'p_chi2':>8} {'p_z':>8} | ret_median arm/ktrl")
        print(f"  |   {'-' * 108}")
        for h in t["horizons"]:
            N = h["horizon"]
            a, c = h["arm"], h["ctrl"]
            tb = h["test_b10"]
            db = f"{tb['delta'] * 100:+.1f}pp" if tb else "—"
            p1 = _fmt(tb, "p_chi2")
            p2 = _fmt(tb, "p_z")
            r5 = h.get("ret_5", {}).get("median_arm")
            r21 = h.get("ret_21", {}).get("median_arm")
            r5c = h.get("ret_5", {}).get("median_ctrl")
            r21c = h.get("ret_21", {}).get("median_ctrl")
            rets_str = f"5d:{_pct(r5, 2)}|{_pct(r5c, 2)} 21d:{_pct(r21, 2)}/{_pct(r21c, 2)}"
            print(f"  | {N:>3} {a['n']:>7,} {_pct(a['rec']):>7} {_pct(a['b5']):>7} {_pct(a['b10']):>7} {_pct(a['up1']):>7}"
                  f" | {c['n']:>8,} {_pct(c['rec']):>7} {_pct(c['b5']):>7} {_pct(c['b10']):>7} {_pct(c['up1']):>7}"
                  f" | {db:>7} {p1:>8} {p2:>8} | {rets_str}")
    # ringkasan insan
    print()
    print("=" * 116)

    for t in result["thresholds"]:
        thr = t["threshold"]
        for h in t["horizons"]:
            if h["horizon"] != 21:
                continue
            a, c = h["arm"], h["ctrl"]
            tb = h["test_b10"]
            if a["n"] and c["n"] and tb:
                print(f"  [thr {thr:.2f} / N=21] READY n={a['n']:,} -> boom+10% 21d = {_pct(a['b10'])} "
                      f"vs kontrol-below {_pct(c['b10'])} ({c['n']:,}); d={tb['delta'] * 100:+.1f}pp; "
                      f"p_chi2={tb['p_chi2']}")
    w = result["warnings"]
    print(f"  [info] fetch error {w['fetch_errors']}, data pendek {w['short_data']}, "
          f"kosong {w['empty_data']}; simpan: {result['rows_file']}")
    if result["failed_codes"]:
        print(f"  [warn] kode gagal: {', '.join(result['failed_codes'][:25])}"
              f"{' …' if len(result['failed_codes']) > 25 else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validasi akumulasi post-ARA multihorizon + grid density (v4.2)")
    parser.add_argument("codes", nargs="*", help="kode saham (default: semua universe)")
    parser.add_argument("--codes", dest="codes_opt", nargs="*", help="kode saham lewat opsi")
    parser.add_argument("--ara-pct", type=float, default=10.0)
    parser.add_argument("--ma", type=int, default=20)
    parser.add_argument("--length", type=int, default=800)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--thr", nargs="+", type=float, default=list(THR_DEFAULT),
                        help=f"gate density yg diuji (default: 0.30 0.40)")
    parser.add_argument("--rows", default=ROWS_NPZ_PATH, metavar="PATH",
                        help=f"simpan row-level ke PATH (default: {ROWS_NPZ_PATH})")
    parser.add_argument("--json", action="store_true", help="simpan JSON analisis ke data/validate_multihorizon.json")
    parser.add_argument("--analyze", nargs="?", const=ROWS_NPZ_PATH, metavar="PATH",
                        help="muat rows.npz & reproduksi laporan offline")
    args = parser.parse_args()

    # ---- mode ANALYZE: muat rows.npz, ulangi analisis (offline) ----
    if args.analyze is not None:
        path = args.analyze if args.analyze else ROWS_NPZ_PATH
        with np.load(path, allow_pickle=False) as z:
            feats = z["feats"]
            outs = z["outs"]
            rets = z["rets"]
            codes = [c.decode() for c in z["codes"]]
        print(f"  [ok] muat {path}: {len(feats):,} baris, {len(codes)} kode", file=sys.stderr)
        result = {
            "codes": len(codes), "codes_ok": len(codes), "length": None,
            "ara_pct": None, "ma_days": None,
            "warnings": {"fetch_errors": 0, "short_data": 0, "empty_data": 0},
            "failed_codes": [], "total_rows": len(feats),
            "rows_file": path, "rows_meta": ROWS_META_PATH,
            "thresholds": [_analyze_rows(feats, outs, rets, thr) for thr in args.thr],
        }
        _print_report(result)
        if args.json:
            _write_json(result)
        return

    codes = args.codes or args.codes_opt
    if not codes:
        securities = get_or_fetch_securities_list()
        if not securities:
            print("Daftar sekuritas kosong.", file=sys.stderr)
            return
        codes = [s.code for s in securities]

    result = _run(codes, args.length, args.workers, args.ara_pct, args.ma,
                  tuple(args.thr))
    _print_report(result)

    if args.json:
        _write_json(result)


def _write_json(result: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MULTI_JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(f"  [ok] JSON analisis: {MULTI_JSON_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()