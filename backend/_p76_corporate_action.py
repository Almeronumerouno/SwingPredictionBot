"""
_p76_corporate_action.py — P7.6: Corporate-Action Integrity audit.

Audit dampak corporate action (split/bonus/rights/dividen) terhadap
pipeline RAW (produksi): drawdown & recovery signal yg dibangun dari
raw close (kolom 3) vs normalized (adj_close, kolom 4, Yahoo Adj Close
= disesuaikan split+dividen).

Deteksi event: lompatan faktor adj f = raw/adj antar bar berurutan
(|Δf/f| > 1% = material utk state drawdown; > 5% = split/bonus/rights/
dividen besar).

Kuantifikasi:
  - statistik event per saham & agregat
  - episode drawdown (run dd_raw>0, definisi F2.2) yg overlap event
    (±3 bar) — artificial drawdown candidates
  - bar CA-artifact: dd_raw > 0.05 TAPI dd_adj < 0.01 (drawdown hanya
    karena CA, bukan penurunan nilai pasar)
  - dampak sinyal: P(h21) model produksi pd bar CA-artifact vs
    counterfactual dd_adj; jumlah bar yg memenuhi ambang sinyal API
    (drop >= 5%) hanya karena CA
  - state error material: bar dgn |dd_raw - dd_adj| > 0.05

Policy (ditetapkan di MD P7.6 & data contract): raw = execution/event
semantics (harga aktual eksekusi, % change riil); adj = historical
statistical state bila dipakai model statistik.

Usage: python _p76_corporate_action.py [--no-save]
Output: data/phase7_p76_corporate_action.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
OUT_JSON = os.path.join(DATA_DIR, "phase7_p76_corporate_action.json")
PROD_PARAMS = os.path.join(DATA_DIR, "recovery_model_params.json")

PEAK_LOOKBACK = 252
DD_CLAMP = 0.85
CA_THRESHOLD = 0.01      # |Δf/f| material utk state
CA_BIG_THRESHOLD = 0.05  # split/bonus/rights/dividen besar
ARTIFACT_DD = 0.05       # dd raw dianggap sinyal (ambang API drop_pct default)
ARTIFACT_ADJ = 0.01      # dd adj harus di bawah ini utk disebut artifact
EVENT_WINDOW = 3         # bar ±3 dari event


def _trailing_peak(close: np.ndarray, window: int) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    if n < window:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    sw = sliding_window_view(close, window)
    out[window - 1:] = sw.max(axis=1)
    return out


def _dd_series(close: np.ndarray, peak: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.clip(1.0 - close / peak, 0.0, DD_CLAMP)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=NPZ_PATH)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    d = np.load(args.npz, allow_pickle=True)
    rows, lens, dates = d["rows"], d["lens"], d["dates"]
    codes = [(c.decode() if isinstance(c, bytes) else str(c)) for c in d["codes"]]
    n_codes = len(lens)
    print(f"Dataset: {n_codes} kode", flush=True)

    # ── 1. deteksi corporate action events ─────────────────────────────
    ev_all: list[dict] = []
    n_stock_with_ca = 0
    f_jumps = []
    n_ara_palsu_adj = 0  # bar: adj change >= +9.9% (ARA palsu) tapi raw < 9.9%
    n_ara_raw_real = 0   # bar: raw change >= +9.9% (ARA riil)
    for c in range(n_codes):
        m = int(lens[c])
        raw = rows[c, :m, 3]
        adj = rows[c, :m, 4]
        ok = (adj > 0) & np.isfinite(adj)
        if not ok.any():
            continue
        f = np.full(m, np.nan)
        f[ok] = raw[ok] / adj[ok]
        logf = np.log(f)
        with np.errstate(invalid="ignore"):
            dl = np.diff(logf)
        jumps = np.where(np.abs(dl) > np.log1p(CA_THRESHOLD))[0] + 1
        if len(jumps) == 0:
            continue
        n_stock_with_ca += 1
        for j in jumps:
            mag = abs(float(np.expm1(dl[j - 1])))
            ev_all.append({
                "code": codes[c], "bar": int(j),
                "date": str(dates[c][j])[:10] if dates[c] is not None and len(dates[c]) > j else None,
                "jump_pct": round(mag * 100.0, 3),
                "big": bool(mag > CA_BIG_THRESHOLD),
            })
            f_jumps.append(mag)
        # ARA palsu di adjusted vs riil di raw (re-test RTF policy, kasus DUTI)
        with np.errstate(divide="ignore", invalid="ignore"):
            chg_raw = np.full(m, np.nan)
            chg_raw[1:] = raw[1:] / raw[:-1] - 1.0
            chg_adj = np.full(m, np.nan)
            chg_adj[1:] = adj[1:] / adj[:-1] - 1.0
        n_ara_raw_real += int((chg_raw >= 0.099).sum())
        n_ara_palsu_adj += int(((chg_adj >= 0.099) & (chg_raw < 0.099)).sum())
    f_jumps = np.asarray(f_jumps or [0.0])
    n_big = sum(1 for e in ev_all if e["big"])
    print(f"CA events (>1%): {len(ev_all):,} di {n_stock_with_ca} saham "
          f"| big (>5%): {n_big:,} | median jump {np.median(f_jumps)*100:.2f}% "
          f"| p95 {np.percentile(f_jumps, 95)*100:.2f}%")
    print(f"ARA: raw >= +9.9%: {n_ara_raw_real:,} | adjusted palsu (adj>=9.9% "
          f"tapi raw<9.9%): {n_ara_palsu_adj:,}", flush=True)

    # ── 2. dd raw vs adj + episode overlap ──────────────────────────────
    stat = {"bars": 0, "dd_raw_gt5pct": 0, "dd_adj_gt5pct": 0,
            "state_error_gt5pct": 0, "ca_artifact_bars": 0,
            "ca_artifact_signal_bars": 0,
            "episodes_total": 0, "episodes_ca_overlap": 0,
            "episodes_artifact": 0,
            "p21_on_artifact_raw": [], "p21_on_artifact_adj": []}
    by_code = {}
    prod = json.load(open(PROD_PARAMS, encoding="utf-8"))
    h21 = prod["horizons"].get("21", {})
    a21, b21 = h21.get("a"), h21.get("b")

    for c in range(n_codes):
        m = int(lens[c])
        if m < PEAK_LOOKBACK + 5:
            continue
        raw = rows[c, :m, 3]
        adj = rows[c, :m, 4]
        adj_use = np.where((adj > 0) & np.isfinite(adj), adj, raw)
        peak_r = _trailing_peak(raw, PEAK_LOOKBACK)
        peak_a = _trailing_peak(adj_use, PEAK_LOOKBACK)
        dd_r = _dd_series(raw, peak_r)
        dd_a = _dd_series(adj_use, peak_a)
        ev_bars = {e["bar"] for e in ev_all if e["code"] == codes[c]}

        valid = np.isfinite(dd_r) & np.isfinite(dd_a)
        stat["bars"] += int(valid.sum())
        stat["dd_raw_gt5pct"] += int((valid & (dd_r > ARTIFACT_DD)).sum())
        stat["dd_adj_gt5pct"] += int((valid & (dd_a > ARTIFACT_DD)).sum())
        state_err = valid & (np.abs(dd_r - dd_a) > ARTIFACT_DD)
        stat["state_error_gt5pct"] += int(state_err.sum())
        artifact = valid & (dd_r > ARTIFACT_DD) & (dd_a < ARTIFACT_ADJ)
        stat["ca_artifact_bars"] += int(artifact.sum())
        stat["ca_artifact_signal_bars"] += int((artifact & (dd_r > ARTIFACT_DD)).sum())
        if a21 is not None and artifact.any():
            pr = 1.0 / (1.0 + np.exp(-(a21 + b21 * dd_r[artifact])))
            pa = 1.0 / (1.0 + np.exp(-(a21 + b21 * dd_a[artifact])))
            stat["p21_on_artifact_raw"].extend(pr.tolist())
            stat["p21_on_artifact_adj"].extend(pa.tolist())

        # episode dd_raw>0 (F2.2) + overlap event
        pos = np.flatnonzero(valid & (dd_r > 0))
        if len(pos):
            run_breaks = np.flatnonzero(np.diff(pos) != 1)
            runs = np.split(pos, run_breaks + 1)
            for run in runs:
                stat["episodes_total"] += 1
                s, e = run[0], run[-1]
                overlap = any(s - EVENT_WINDOW <= eb <= e + EVENT_WINDOW
                              for eb in ev_bars)
                if overlap:
                    stat["episodes_ca_overlap"] += 1
                    # artifact = seluruh episode dd_adj kecil
                    if np.all(dd_a[s:e + 1] < ARTIFACT_ADJ):
                        stat["episodes_artifact"] += 1
        by_code[codes[c]] = {
            "n_events": len(ev_bars),
            "ca_artifact_bars": int(artifact.sum()),
            "state_error_bars": int(state_err.sum()),
        }

    n_bars = max(1, stat["bars"])
    n_ep = max(1, stat["episodes_total"])
    print(f"\nBars valid: {stat['bars']:,}")
    print(f"dd_raw > 5%: {stat['dd_raw_gt5pct']:,} "
          f"({stat['dd_raw_gt5pct']/n_bars*100:.2f}%) | "
          f"dd_adj > 5%: {stat['dd_adj_gt5pct']:,} "
          f"({stat['dd_adj_gt5pct']/n_bars*100:.2f}%)")
    print(f"State error |dd_raw-dd_adj| > 5%: {stat['state_error_gt5pct']:,} "
          f"({stat['state_error_gt5pct']/n_bars*100:.3f}%)")
    print(f"CA-artifact bars (dd_raw>5% & dd_adj<1%): "
          f"{stat['ca_artifact_bars']:,} "
          f"({stat['ca_artifact_bars']/n_bars*100:.3f}%)")
    print(f"Episode drawdown: {stat['episodes_total']:,} | "
          f"overlap event ±3 bar: {stat['episodes_ca_overlap']:,} "
          f"({stat['episodes_ca_overlap']/n_ep*100:.2f}%) | "
          f"episode murni artifact: {stat['episodes_artifact']:,} "
          f"({stat['episodes_artifact']/n_ep*100:.3f}%)")
    if stat["p21_on_artifact_raw"]:
        pr = np.asarray(stat["p21_on_artifact_raw"])
        pa = np.asarray(stat["p21_on_artifact_adj"])
        print(f"\nP(h21) pada CA-artifact bars: raw mean {pr.mean():.3f} "
              f"(median {np.median(pr):.3f}) vs adj-counterfactual mean "
              f"{pa.mean():.3f} (median {np.median(pa):.3f})")
        print(f"  -> {int((pr > pa + 0.05).sum())}/{len(pr)} bar ter-overestimasi "
              f">5pp vs counterfactual")

    worst = sorted(by_code.items(), key=lambda kv: kv[1]["ca_artifact_bars"],
                   reverse=True)[:10]
    print("\nTop-10 saham CA-artifact bars:")
    for code, v in worst:
        if v["ca_artifact_bars"] > 0:
            print(f"  {code:>6}: events={v['n_events']} "
                  f"artifact_bars={v['ca_artifact_bars']} "
                  f"state_err_bars={v['state_error_bars']}")

    out = {
        "method": "P7.6 corporate-action integrity (raw vs adj_close)",
        "ca_detection": ("jump faktor f=raw/adj antar bar |dlogf| > log(1.01); "
                         "big > 5% (split/bonus/rights/dividen besar)"),
        "window": {"peak_lookback": PEAK_LOOKBACK, "event_window_bars": EVENT_WINDOW,
                   "artifact_definition": "dd_raw>0.05 & dd_adj<0.01"},
        "stats": {k: (round(float(np.mean(v)), 4) if isinstance(v, list) and v
                      else int(v) if isinstance(v, int) else v)
                  for k, v in stat.items()},
        "n_events": len(ev_all),
        "n_stocks_with_ca": n_stock_with_ca,
        "n_big_events": n_big,
        "n_ara_raw_real": int(n_ara_raw_real),
        "n_ara_palsu_adj": int(n_ara_palsu_adj),
        "median_jump_pct": round(float(np.median(f_jumps) * 100), 3),
        "p95_jump_pct": round(float(np.percentile(f_jumps, 95) * 100), 3),
        "top_artifact_stocks": [
            {"code": str(k), **{kk: int(vv) for kk, vv in v.items()}}
            for k, v in sorted(by_code.items(),
                               key=lambda kv: kv[1]["ca_artifact_bars"],
                               reverse=True)[:10]],
        "policy": "raw = execution/event semantics (harga eksekusi aktual, "
                  "deteksi ARA, gate RTF); adj_close = historical statistical "
                  "state bila dipakai model statistik (tidak dipakai di jalur "
                  "produksi saat ini); CA terdeteksi via flag ca_note di "
                  "build_recovery_analysis (P7.6)",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not args.no_save:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nTersimpan: {args.out}")
    else:
        print("\n(no-save: tidak menulis file)")


if __name__ == "__main__":
    sys.exit(main())