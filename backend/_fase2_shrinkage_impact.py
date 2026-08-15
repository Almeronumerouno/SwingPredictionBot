"""
_fase2_shrinkage_impact.py — F2.4 POST: Dampak nyata shrinkage ke sinyal.

Replikasi jalur sinyal produksi recovery.py utk SELURUH universe pada bar
terakhir tiap saham, lalu bandingkan klasifikasi sinyal (POTENTIAL vs WATCH,
p_min sesuai basis) antara:
  - BASELINE: hard switch lama (n>=5 -> rate mentah; n<5 -> model global)
  - F2.4     : shrinkage Beta-Binomial (n>=1 -> (k+a0)/(n+a0+b0); n=0 ->
               model global)
Menjawab: berapa saham yg keputusan sinyalnya berubah, berapa yang pindah
basis model<->empiris, dan seberapa besar delta p.

Output stdout ringkasan + data/recovery_shrinkage_impact.json (detail).
Usage:
    python _fase2_shrinkage_impact.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

from _fase2_temporal_split import DATA_DIR, NPZ_PATH, _load_npz
import recovery as rc
import config as cfg

OUT_JSON = os.path.join(DATA_DIR, "recovery_shrinkage_impact.json")
H_SIGNAL = cfg.RECOVERY_SIGNAL_HORIZON_DAYS


def main() -> None:
    codes, rows, lens, _dates = _load_npz(NPZ_PATH)
    shr_params = rc._load_shrinkage_params()
    model_params = rc._load_recovery_model_params()

    rows_out = []
    n_baseline_empirical = n_f24_empirical = 0
    n_pot_baseline = n_pot_f24 = 0
    n_flip_pot = n_flip_watch = 0
    deltas = []
    n_model_fallback = 0
    buckets = {}

    for c in range(len(lens)):
        m = int(lens[c])
        if m < cfg.RECOVERY_MIN_BARS:
            continue
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        price_now = float(close[-1])
        if not np.isfinite(price_now) or price_now <= 0:
            continue
        _mu, sigma = rc.estimate_gbm_params(close)
        if sigma <= 0:
            continue
        drop = rc.auto_drop_pct(sigma, price_now)

        # --- empirical base rate (produksi) ---
        emp = rc.empirical_base_rates(close, high, drop,
                                      horizons=[H_SIGNAL])
        emp_signal = emp[0] if emp else None
        k, n = (emp_signal["n_recovered"], emp_signal["n_events"]) if emp_signal else (0, 0)

        # --- model global (target prior high) ---
        p_model = None
        dd_f, _peak = rc.dd_fraction(close)
        probs = rc.recovery_model_probs(dd_f, horizons=[H_SIGNAL],
                                        params=model_params) if dd_f is not None else None
        if probs:
            p_model = probs[0]["p_hit"]

        # --- BASELINE: hard switch ---
        if n >= 5 and emp_signal is not None and emp_signal["rate"] is not None:
            p_base, basis_base = emp_signal["rate"], "empiris"
        else:
            p_base, basis_base = p_model, "model"
        p_min_base = cfg.RECOVERY_MODEL_P_MIN if basis_base == "model" \
            else cfg.RECOVERY_SIGNAL_P_MIN

        # --- F2.4: shrinkage ---
        p_f24, basis_f24 = None, "model"
        if n >= 1:
            p_s = rc._shrunk_rate(k, n, drop, H_SIGNAL, shr_params)
            if p_s is not None:
                p_f24, basis_f24 = p_s, "shrinkage"
        if p_f24 is None:
            p_f24 = p_model
        p_min_f24 = cfg.RECOVERY_MODEL_P_MIN if basis_f24 == "model" \
            else cfg.RECOVERY_SIGNAL_P_MIN

        if basis_f24 == "model":
            n_model_fallback += 1

        if p_base is None or p_f24 is None:
            continue

        pot_base = p_base >= p_min_base
        pot_f24 = p_f24 >= p_min_f24
        if basis_base == "empiris":
            n_baseline_empirical += 1
        if basis_f24 == "shrinkage":
            n_f24_empirical += 1
        if pot_base:
            n_pot_baseline += 1
        if pot_f24:
            n_pot_f24 += 1
        if pot_base and not pot_f24:
            n_flip_watch += 1
        if not pot_base and pot_f24:
            n_flip_pot += 1
        deltas.append(p_f24 - p_base)

        # agregasi per bucket drop
        bkey = None
        for lo, hi in rc._SHRINKAGE_BUCKETS:
            if lo <= drop < hi:
                bkey = f"{lo:.1f}-{hi:.1f}"
                break
        bkey = bkey or "clamp"
        b = buckets.setdefault(bkey, {"n": 0, "sum_p_base": 0.0,
                                      "sum_p_f24": 0.0, "sum_n_events": 0,
                                      "sum_delta": 0.0, "flip": 0})
        b["n"] += 1
        b["sum_p_base"] += p_base
        b["sum_p_f24"] += p_f24
        b["sum_n_events"] += n
        b["sum_delta"] += p_f24 - p_base
        if pot_base != pot_f24:
            b["flip"] += 1

        rows_out.append({
            "code": codes[c], "drop": round(drop, 2), "n_events": n,
            "k": k, "p_baseline": round(p_base, 4), "basis_baseline": basis_base,
            "p_f24": round(p_f24, 4), "basis_f24": basis_f24,
            "pot_baseline": pot_base, "pot_f24": pot_f24,
        })

    deltas = np.asarray(deltas)
    n_all = len(rows_out)
    print(f"Universe diproses: {n_all} saham (min bars {cfg.RECOVERY_MIN_BARS})")
    print(f"  baseline basis empiris (n>=5)  : {n_baseline_empirical} "
          f"({n_baseline_empirical/n_all:.0%})")
    print(f"  F2.4 basis shrinkage (n>=1)    : {n_f24_empirical} "
          f"({n_f24_empirical/n_all:.0%})")
    print(f"  F2.4 model fallback (n=0)      : {n_model_fallback} "
          f"({n_model_fallback/n_all:.0%})")
    print(f"  POTENTIAL baseline              : {n_pot_baseline} "
          f"({n_pot_baseline/n_all:.0%})")
    print(f"  POTENTIAL F2.4                  : {n_pot_f24} "
          f"({n_pot_f24/n_all:.0%})")
    print(f"  delta p: mean={deltas.mean():+.4f} sd={deltas.std(ddof=1):.4f} "
          f"min={deltas.min():+.4f} max={deltas.max():+.4f}")
    print(f"  flip POTENTIAL->WATCH           : {n_flip_watch}")
    print(f"  flip WATCH->POTENTIAL           : {n_flip_pot}")
    print(f"  total keputusan berubah         : {n_flip_watch + n_flip_pot} "
          f"({(n_flip_watch + n_flip_pot)/n_all:.1%})")

    print("\nPer bucket drop:")
    print(f"  {'bucket':>10} {'n':>5} {'mean_p_base':>12} {'mean_p_f24':>11} "
          f"{'mean_delta':>10} {'flip':>5} {'avg_n_ev':>9}")
    for bkey in sorted(buckets, key=lambda x: float(x.split('-')[0])):
        b = buckets[bkey]
        if b["n"] == 0:
            continue
        print(f"  {bkey:>10} {b['n']:>5} "
              f"{b['sum_p_base']/b['n']:>12.4f} {b['sum_p_f24']/b['n']:>11.4f} "
              f"{b['sum_delta']/b['n']:>+10.4f} {b['flip']:>5} "
              f"{b['sum_n_events']/b['n']:>9.1f}")

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "h_signal": H_SIGNAL,
        "n_saham": n_all,
        "n_baseline_empiris": n_baseline_empirical,
        "n_f24_shrinkage": n_f24_empirical,
        "n_f24_model_fallback": n_model_fallback,
        "n_pot_baseline": n_pot_baseline,
        "n_pot_f24": n_pot_f24,
        "n_flip_pot_to_watch": n_flip_watch,
        "n_flip_watch_to_pot": n_flip_pot,
        "delta_p": {"mean": round(float(deltas.mean()), 4),
                    "sd": round(float(deltas.std(ddof=1)), 4),
                    "min": round(float(deltas.min()), 4),
                    "max": round(float(deltas.max()), 4)},
        "buckets": {k: {"n": v["n"],
                        "mean_p_baseline": round(v["sum_p_base"]/v["n"], 4),
                        "mean_p_f24": round(v["sum_p_f24"]/v["n"], 4),
                        "mean_delta": round(v["sum_delta"]/v["n"], 4),
                        "flip": v["flip"],
                        "avg_n_events": round(v["sum_n_events"]/v["n"], 1)}
                    for k, v in buckets.items()},
        "per_saham": rows_out,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())