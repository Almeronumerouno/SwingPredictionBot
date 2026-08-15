"""
_phase4_p41_audit.py — P4.1: Audit frozen production probabilities (PIT).

Mengevaluasi probability yang BENAR-BENAR keluar dari jalur produksi
(protocol frozen: data/phase4_protocol.json) — per target x horizon:

  target `previous_close` : empirical + shrinkage beta-binomial (F2.4)
      p_t,h = (k_{t,h} + a0)/(n_{t,h} + a0 + b0), dihitung PIT:
      n_{t,h} = event saham dgn date_e <= t (window lengkap SEBELUM event t)
  target `prior_peak`     : logistic drawdown global (recovery_model_params.json)
      p = 1/(1+exp(a_h + b_h*dd)); observasi = hari dd>0 (reuse _collect_rows)

Split (protocol): dev = date_s <= 2026-01-23 & date_s + h <= cutoff (purged);
validation = date_s > 2026-04-23 (embargo 90d); sisanya gap.

Output per (target, h, split): n_stocks / n_episodes / n_events / n_non_events /
mean_p / observed_rate / O-E / O/E. Output: data/phase4_p41_audit.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np
from scipy.special import expit

import _phase3_rtf_common as C
from _calibrate_recovery_model import _collect_rows, HORIZONS, NPZ_PATH

DROP_PCT = 5.0
CUTOFF_DT = np.datetime64("2026-01-23")
EMBARGO_DT = np.datetime64("2026-04-23")


def _load_params(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _previous_close_rows(rows: np.ndarray, lens: np.ndarray,
                         dates_list: np.ndarray) -> dict[int, dict]:
    """Per h: p (PIT shrinkage), y, code, date_s, episode_id (run in-setup)."""
    n_codes = len(lens)
    out: dict[int, dict] = {h: {"p": [], "y": [], "code": [], "date_s": [],
                                "ep": []} for h in HORIZONS}
    shr = _load_params(r"data/recovery_shrinkage_params.json")
    from recovery import _shrunk_rate
    for c in range(n_codes):
        m = int(lens[c])
        if m < 30:
            continue
        close = rows[c, :m, 3].astype(np.float64)
        high = rows[c, :m, 1].astype(np.float64)
        dt = (np.asarray(dates_list[c], dtype="datetime64[D]")
              if dates_list[c] is not None and len(dates_list[c]) == m else None)
        in_setup = np.zeros(m, dtype=bool)
        for i in range(1, m):
            if close[i - 1] > 0 and close[i] <= close[i - 1] * (1.0 - DROP_PCT / 100.0):
                in_setup[i] = True
        ev_idx = np.where(in_setup)[0]
        if len(ev_idx) == 0:
            continue
        # run id
        run_id = np.zeros(m, dtype=np.int32)
        rid = 0
        for i in range(1, m):
            if in_setup[i] and not in_setup[i - 1]:
                rid += 1
            if in_setup[i]:
                run_id[i] = rid
        # kumulatif PIT per horizon: prefix sum atas event yg window selesai <= i
        for h in HORIZONS:
            hs = shr.get("horizons", {}).get(str(h))
            if not hs:
                continue
            # PIT counters
            cnt = np.zeros(m, dtype=np.int32)   # n yg window selesai <= i
            hit = np.zeros(m, dtype=np.int32)
            last_j = -1
            for i in ev_idx:
                # event j selesai bila j + h + 1 <= i  -> j <= i - h - 1
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
                    if i + 1 + h <= m else None
                if y_i is None:
                    continue
                out[h]["p"].append(max(0.0, min(1.0, p)))
                out[h]["y"].append(y_i)
                out[h]["code"].append(c)
                out[h]["ep"].append((c, int(run_id[i])))
                out[h]["date_s"].append(dt[i] if dt is not None else None)
    for h in HORIZONS:
        for k in ("p", "y", "code", "ep"):
            out[h][k] = np.asarray(out[h][k], dtype=float if k in ("p", "y") else np.int32
                                   if k == "code" else object)
        out[h]["date_s"] = np.asarray(out[h]["date_s"], dtype="datetime64[D]")
    return out


def _split_masks(date_s: np.ndarray, h: int):
    dev = (date_s <= CUTOFF_DT) & (date_s + np.timedelta64(h, "D") <= CUTOFF_DT)
    val = date_s > EMBARGO_DT
    return dev, val


def _summary(p: np.ndarray, y: np.ndarray, code: np.ndarray,
             ep: np.ndarray, split_name: str) -> dict:
    n = int(len(p))
    if n == 0:
        return {"split": split_name, "n_events": 0}
    y = y.astype(float)
    obs = np.isfinite(y)
    n_obs = int(obs.sum())
    n_pos = int(y[obs].sum())
    mean_p = float(p[obs].mean())
    rate = float(y[obs].mean())
    return {
        "split": split_name,
        "n_events": n,
        "n_obs": n_obs,
        "n_non_events": n_obs - n_pos,
        "n_stocks": int(len(set(code.tolist()))),
        "n_episodes": int(len(set(map(tuple, ep.tolist())))),
        "mean_p": round(mean_p, 4),
        "observed_rate": round(rate, 4),
        "O_minus_E": round(rate - mean_p, 4),
        "O_over_E": round(rate / mean_p, 3) if mean_p > 0 else None,
    }


def main() -> None:
    d = np.load(NPZ_PATH, allow_pickle=True)
    rows, lens = d["rows"], d["lens"]
    dates_list = d["dates"]

    result = {"phase": "P4.1 — Audit frozen production probabilities (PIT)",
              "protocol": "data/phase4_protocol.json",
              "drop_pct": DROP_PCT,
              "cutoff_date": str(CUTOFF_DT),
              "validation_start": str(EMBARGO_DT),
              "targets": {}}

    # ── prior_peak (logistic global) ──
    params = _load_params(r"data/recovery_model_params.json")
    collected = _collect_rows(rows, lens, 252, dates_list)
    pp = {"horizons": {}}
    for h in HORIZONS:
        blk = collected[h]
        if len(blk["y"]) == 0:
            continue
        r = params["horizons"].get(str(h))
        if not r or not r.get("fitted"):
            continue
        p = expit(r["a"] + r["b"] * blk["dd"])
        y = blk["y"]
        code = blk["code"]
        date_s = blk["date_s"]
        # episode run: kontigu pos per kode
        ep = np.array([(int(cd), int(pos)) for cd, pos in zip(code, blk["pos"])], dtype=object)
        # run id: pos diff != 1 -> run baru
        run_ids = []
        cur = 0
        last_code, last_pos = -1, -2
        for cd, pos in zip(code.tolist(), blk["pos"].tolist()):
            if cd != last_code or pos != last_pos + 1:
                cur += 1
            run_ids.append((cd, cur))
            last_code, last_pos = cd, pos
        ep = np.asarray(run_ids, dtype=object)
        out_h = {"n_stocks_all": int(len(set(code.tolist()))),
                 "mean_dd": round(float(np.mean(blk["dd"])), 4)}
        for hh in HORIZONS:
            pass
        dev, val = _split_masks(date_s, h)
        out_h["dev"] = _summary(p[dev], y[dev], code[dev], ep[dev], "dev")
        out_h["validation"] = _summary(p[val], y[val], code[val], ep[val], "validation")
        out_h["n_gap"] = int((~dev & ~val).sum())
        out_h["params_note"] = ("params model di-fit pada 70% awal data (split kalibrator "
                                "temporal, BUKAN cutoff P4) — dev sebagian in-sample utk param")
        pp["horizons"][str(h)] = out_h
    result["targets"]["prior_peak"] = pp

    # ── previous_close (shrinkage PIT) ──
    pc_rows = _previous_close_rows(rows, lens, dates_list)
    pc = {"horizons": {}}
    for h in HORIZONS:
        blk = pc_rows[h]
        if len(blk["p"]) == 0:
            continue
        dev, val = _split_masks(blk["date_s"], h)
        out_h = {}
        for name, m in (("dev", dev), ("validation", val)):
            s = _summary(blk["p"][m], blk["y"][m], blk["code"][m], blk["ep"][m], name)
            out_h[name] = s
        out_h["n_gap"] = int((~dev & ~val).sum())
        pc["horizons"][str(h)] = out_h
    result["targets"]["previous_close"] = pc

    result["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    C.write_json(r"data\phase4_p41_audit.json", result)

    print("=== P4.1 audit (n_obs | mean_p | rate | O/E) ===", file=sys.stderr)
    for tgt, blk in result["targets"].items():
        for h in HORIZONS:
            hh = blk["horizons"].get(str(h))
            if not hh:
                continue
            row_dev = hh.get("dev", {})
            row_val = hh.get("validation", {})
            print(f"{tgt:14s} h={h:>2} | dev: {row_dev.get('n_obs', 0):>7} "
                  f"p={row_dev.get('mean_p')} rate={row_dev.get('observed_rate')} "
                  f"O/E={row_dev.get('O_over_E')} | val: {row_val.get('n_obs', 0):>6} "
                  f"p={row_val.get('mean_p')} rate={row_val.get('observed_rate')} "
                  f"O/E={row_val.get('O_over_E')}", file=sys.stderr)


if __name__ == "__main__":
    main()