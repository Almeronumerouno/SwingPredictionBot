"""
_phase4_data.py — Collector bersama data observasi Phase 4 (build cache).

Menghasilkan cache observasi (p, y, code, episode, date) per target x horizon
dari universe_ohlcv.npz, persis mengikuti jalur produksi yang di-freeze di
data/phase4_protocol.json. Dipakai oleh P4.2–P4.6 (P4.1 punya collector sendiri).

  target `previous_close` : empirical + shrinkage beta-binomial (PIT)
  target `prior_peak`     : logistic drawdown global (reuse _collect_rows)

Cache: data/phase4_obs.npz — key "<target>_<h>_<field>" per horizon.
  fields: p (float32), y (float32, NaN=censored-tidak-dipakai), code (int32),
          ep (int32 run id), date (datetime64[D])

Usage: python _phase4_data.py --build
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from scipy.special import expit

from _calibrate_recovery_model import _collect_rows, HORIZONS, NPZ_PATH
from regime import regime_series

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CACHE_PATH = os.path.join(DATA_DIR, "phase4_obs.npz")

DROP_PCT = 5.0
PEAK_WINDOW = 252


def _adx(high, low, close, period: int = 14) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        pc = close[i - 1]
        tr[i] = max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc))
    plus_dm = np.empty(n)
    minus_dm = np.empty(n)
    for i in range(1, n):
        up = high[i] - high[i - 1]
        dn = low[i - 1] - low[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
    atr = _wilder(tr, period)
    sp = _wilder(plus_dm, period)
    sm = _wilder(minus_dm, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * sp / atr
        minus_di = 100.0 * sm / atr
        dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    dx = np.where(np.isinf(dx) | np.isnan(dx), 0.0, dx)
    adx = _wilder(dx, period)
    return adx


def _wilder(x: np.ndarray, period: int) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    if n < period:
        return out
    out[period - 1] = np.nanmean(x[:period])
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + x[i]) / period
    return out


def _load_params(path: str) -> dict:
    with open(os.path.join(DATA_DIR, path), encoding="utf-8") as fh:
        return json.load(fh)


def _previous_close_arrays(rows, lens, dates_list) -> dict[int, dict]:
    from recovery import _shrunk_rate
    shr = _load_params("recovery_shrinkage_params.json")
    n_codes = len(lens)
    out = {h: {"p": [], "y": [], "code": [], "ep": [], "date": [], "regime": []} for h in HORIZONS}
    for c in range(n_codes):
        m = int(lens[c])
        if m < 30:
            continue
        close = rows[c, :m, 3].astype(np.float64)
        high = rows[c, :m, 1].astype(np.float64)
        low = rows[c, :m, 2].astype(np.float64)
        dt = (np.asarray(dates_list[c], dtype="datetime64[D]")
              if dates_list[c] is not None and len(dates_list[c]) == m else None)
        reg = regime_series(close, _adx(high, low, close))
        reg_code = np.where(reg == "bull", 1, np.where(reg == "bear", 2, 0)).astype(np.int32)
        in_setup = np.zeros(m, dtype=bool)
        for i in range(1, m):
            if close[i - 1] > 0 and close[i] <= close[i - 1] * (1.0 - DROP_PCT / 100.0):
                in_setup[i] = True
        ev_idx = np.where(in_setup)[0]
        if len(ev_idx) == 0:
            continue
        run_id = np.zeros(m, dtype=np.int32)
        rid = 0
        for i in range(1, m):
            if in_setup[i] and not in_setup[i - 1]:
                rid += 1
            if in_setup[i]:
                run_id[i] = rid
        for h in HORIZONS:
            hs = shr.get("horizons", {}).get(str(h))
            if not hs:
                continue
            cnt = np.zeros(m, dtype=np.int32)
            hit = np.zeros(m, dtype=np.int32)
            last_j = -1
            for i in ev_idx:
                lim = i - h - 1
                while last_j + 1 < len(ev_idx) and ev_idx[last_j + 1] <= lim:
                    j = ev_idx[last_j + 1]
                    cnt[i:] += 1
                    if np.nanmax(high[j + 1: j + 1 + h]) >= close[j - 1]:
                        hit[i:] += 1
                    last_j += 1
                if cnt[i] == 0:
                    continue
                p = _shrunk_rate(int(hit[i]), int(cnt[i]), DROP_PCT, h, shr)
                if p is None:
                    continue
                y_i = float(np.nanmax(high[i + 1: i + 1 + h]) >= close[i - 1]) \
                    if i + 1 + h <= m else float("nan")
                out[h]["p"].append(max(0.0, min(1.0, p)))
                out[h]["y"].append(y_i)
                out[h]["code"].append(c)
                out[h]["ep"].append(int(run_id[i]))
                out[h]["date"].append(dt[i] if dt is not None else np.datetime64("NaT"))
                out[h]["regime"].append(int(reg_code[i]))
    for h in HORIZONS:
        for k in ("p", "y", "code", "ep"):
            out[h][k] = np.asarray(out[h][k], dtype=np.float32 if k in ("p", "y")
                                   else np.int32)
        out[h]["date"] = np.asarray(out[h]["date"], dtype="datetime64[D]")
        out[h]["regime"] = np.asarray(out[h]["regime"], dtype=np.int32)
    return out


def _prior_peak_arrays(rows, lens, dates_list) -> dict[int, dict]:
    params = _load_params("recovery_model_params.json")
    collected = _collect_rows(rows, lens, PEAK_WINDOW, dates_list)
    out = {h: {"p": [], "y": [], "code": [], "ep": [], "date": [], "regime": []}
           for h in HORIZONS}
    # peta regime per kode (0 sideways, 1 bull, 2 bear)
    reg_map = {}
    for c in range(len(lens)):
        m = int(lens[c])
        if m < 30:
            continue
        close = rows[c, :m, 3].astype(np.float64)
        high = rows[c, :m, 1].astype(np.float64)
        low = rows[c, :m, 2].astype(np.float64)
        reg = regime_series(close, _adx(high, low, close))
        reg_map[c] = np.where(reg == "bull", 1, np.where(reg == "bear", 2, 0)).astype(np.int32)
    for h in HORIZONS:
        blk = collected[h]
        if len(blk["y"]) == 0:
            continue
        r = params["horizons"].get(str(h))
        if not r or not r.get("fitted"):
            continue
        p = expit(r["a"] + r["b"] * blk["dd"])
        # run id: kontigu pos per kode
        ep_ids = []
        cur = 0
        last_code, last_pos = -1, -2
        for cd, pos in zip(blk["code"].tolist(), blk["pos"].tolist()):
            if cd != last_code or pos != last_pos + 1:
                cur += 1
            ep_ids.append(cur)
            last_code, last_pos = cd, pos
        out[h]["p"] = np.asarray(p, dtype=np.float32)
        out[h]["y"] = np.asarray(blk["y"], dtype=np.float32)
        out[h]["code"] = np.asarray(blk["code"], dtype=np.int32)
        out[h]["ep"] = np.asarray(ep_ids, dtype=np.int32)
        out[h]["date"] = np.asarray(blk["date_s"], dtype="datetime64[D]")
        out[h]["regime"] = np.asarray([int(reg_map[int(cd)][int(pos)])
                                       for cd, pos in zip(blk["code"], blk["pos"])],
                                      dtype=np.int32)
    return out


def build(force: bool = False) -> dict:
    if os.path.exists(CACHE_PATH) and not force:
        return load()
    d = np.load(NPZ_PATH, allow_pickle=True)
    rows, lens, dates_list = d["rows"], d["lens"], d["dates"]
    data = {}
    for tgt, fn in (("previous_close", _previous_close_arrays),
                    ("prior_peak", _prior_peak_arrays)):
        arrs = fn(rows, lens, dates_list)
        for h, blk in arrs.items():
            if len(blk["p"]) == 0:
                continue
            for field in ("p", "y", "code", "ep", "regime"):
                data[f"{tgt}_{h}_{field}"] = blk[field]
            data[f"{tgt}_{h}_date"] = blk["date"]
    np.savez_compressed(CACHE_PATH, **data)
    print(f"[ok] cache {CACHE_PATH}", file=sys.stderr)
    return data


def load() -> dict:
    d = np.load(CACHE_PATH, allow_pickle=True)
    out = {}
    for key in d.files:
        out[key] = d[key]
    return out


def get(target: str, h: int, data: dict) -> dict:
    return {
        "p": data[f"{target}_{h}_p"],
        "y": data[f"{target}_{h}_y"],
        "code": data[f"{target}_{h}_code"],
        "ep": data[f"{target}_{h}_ep"],
        "date": data[f"{target}_{h}_date"],
        "regime": data[f"{target}_{h}_regime"],
    }


if __name__ == "__main__":
    t0 = time.time()
    build(force="--force" in sys.argv)
    print(f"build {time.time()-t0:.0f}s", file=sys.stderr)