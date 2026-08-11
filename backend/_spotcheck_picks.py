"""
_spotcheck_picks.py - Spot-check sinyal READY (arm) yang HIT, paling baru.

Untuk tiap kode terpilih (baris arm & b5_5==1 terbaru), fetch ulang history
(length 800, target_date 2026-08-07 = PIN window sama dengan generasi npz),
lalu petakan bar_idx -> tanggal:
  - tanggal sinyal READY (bar)
  - tanggal ARA terakhir (ref / puncak gelombang)
  - hari & tanggal HIT pertama (high >= ref*1.05 dalam [t+1..t+5])
  - gain hit vs entry, max 10/21 hari, close terakhir (7 Agu)

Invariant: close[bar]/close[ref] harus == pos_vs_ara dari npz (bukti bar_idx
& pemetaan tanggal konsisten dengan data generasi).
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import config as CFG
from data_source.yahoo_client import fetch_trading_info

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
NPZ = os.path.join(BACKEND_DIR, "data", "accum_rows.npz")
TARGET_DATE = "2026-08-07"   # generasi npz (2026-08-09, Minggu) -> last bar 7 Agu
LENGTH = 800
ARA_PCT = 10.0
REF_MULT = 1.05              # b5: balik ke ARA + 5%
HIT_HORIZON = 5              # hari trading
N_PICKS = 10


def find_ref_idx(ara: np.ndarray, bar_idx: int, rvol_period: int) -> int:
    """Replikasi logika anchor/ref _validate_accum4._events_for_code."""
    last_ara: int | None = None
    prev_ara: int | None = None
    for i in range(1, bar_idx + 1):
        if ara[i]:
            prev_ara, last_ara = last_ara, i
    assert last_ara is not None
    if prev_ara is not None and (last_ara - prev_ara) <= rvol_period:
        return last_ara  # ref = puncak gelombang (ARA terbaru); anchor = prev_ara
    return last_ara


def analyze_code(code: str, z: dict) -> dict:
    feats, outs = z["feats"], z["outs"]
    bars_idx = z["bars"]
    cidx = int(np.where(z["codes"] == code.encode())[0][0])
    rows = np.where(z["code_idx"] == cidx)[0]
    if not len(rows):
        return {"code": code, "error": "tidak ada baris di npz"}

    pos = feats[rows, 0]
    heavy = feats[rows, 1]
    dens = feats[rows, 3]
    above = feats[rows, 4] == 1.0
    hit = outs[rows, 8] == 1.0  # b5_5
    arm = (pos < 1.0) & (heavy >= 2) & (dens >= 0.30) & above & hit
    if not arm.any():
        return {"code": code, "error": "tidak ada baris arm+hit"}
    arm_rows = rows[arm]
    r = int(arm_rows[np.argmax(bars_idx[arm_rows])])
    bar = int(bars_idx[r])  # bar_idx aktual (indeks dalam window 800)

    bars = fetch_trading_info(code, length=LENGTH, target_date=TARGET_DATE)
    if not bars:
        return {"code": code, "error": "fetch kosong"}
    n = len(bars)
    if n <= bar + HIT_HORIZON:
        return {"code": code, "error": "data pendek (%d bar, bar=%d)" % (n, bar)}

    close = np.array([b.close for b in bars], dtype=float)
    high = np.array([b.high for b in bars], dtype=float)
    dates = [b.date for b in bars]

    ara = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if close[i - 1] > 0 and close[i] >= close[i - 1] * (1.0 + ARA_PCT / 100.0):
            ara[i] = True

    ref_idx = find_ref_idx(ara, bar, CFG.ACCUM_RVOL_PERIOD)
    ref = close[ref_idx]
    entry = close[bar]

    # invariant: close[bar]/ref harus ~= pos_vs_ara tersimpan
    pos_npz = float(feats[r, 0])
    pos_now = float(entry / ref) if ref > 0 else float("nan")
    ok = abs(pos_now - pos_npz) < 1e-3

    win5 = slice(bar + 1, bar + 1 + HIT_HORIZON)
    hi5 = high[win5]
    thr5 = ref * REF_MULT
    hit_off = int(np.argmax(hi5 >= thr5)) if (hi5 >= thr5).any() else None
    hit_date = dates[bar + 1 + hit_off] if hit_off is not None else None
    hit_hi = float(hi5[hit_off]) if hit_off is not None else None

    win10 = slice(bar + 1, bar + 11)
    win21 = slice(bar + 1, bar + 22)
    max10 = float(high[win10].max())
    max21 = float(high[win21].max())

    return {
        "code": code,
        "bar_idx": r,
        "signal_date": dates[bar],
        "ara_date": dates[ref_idx],
        "window": int(feats[r, 2]),
        "density": round(float(feats[r, 3]), 2),
        "entry": entry,
        "ref": ref,
        "pos_ok": ok,
        "hit_date": hit_date,
        "hit_high": hit_hi,
        "gain_hit_pct": (hit_hi / entry - 1) * 100 if hit_hi else None,
        "gain_max10_pct": (max10 / entry - 1) * 100,
        "gain_max21_pct": (max21 / entry - 1) * 100,
        "close_final": float(close[-1]),
        "gain_final_pct": (close[-1] / entry - 1) * 100,
        "n_bars": n,
    }


def main() -> None:
    with np.load(NPZ, allow_pickle=False) as z:
        zz = {k: z[k] for k in z.files}
    pos = zz["feats"][:, 0]
    heavy = zz["feats"][:, 1]
    dens = zz["feats"][:, 3]
    above = zz["feats"][:, 4] == 1.0
    arm_all = (pos < 1.0) & (heavy >= 2) & (dens >= 0.30) & above
    hit_all = arm_all & (zz["outs"][:, 8] == 1.0)
    sel = np.where(hit_all)[0]
    order = np.argsort(zz["bars"][sel])[::-1]
    seen, picks = set(), []
    for i in order:
        c = int(zz["code_idx"][sel[i]])
        if c in seen:
            continue
        seen.add(c)
        picks.append(zz["codes"][c].decode())
        if len(picks) >= N_PICKS:
            break

    print("fokus %d kode: %s" % (len(picks), ", ".join(picks)))
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(analyze_code, c, zz): c for c in picks}
        for fut in futs:
            try:
                results.append(fut.result())
            except Exception as e:  # noqa: BLE001
                results.append({"code": futs[fut], "error": str(e)})

    results.sort(key=lambda d: (d.get("signal_date") or ""))
    print()
    hdr = "%-6s %-12s %-12s %-12s %7s %9s %-12s %8s %8s %8s %8s" % (
        "KODE", "SINYAL", "ARA_TERAKHIR", "HIT", "WINDOW", "DENSITY",
        "ENTRY", "GAIN_HIT", "MAX10", "MAX21", "CLOSE_FIN")
    print(hdr)
    print("-" * len(hdr))
    for d in results:
        if "error" in d:
            print("%-6s ERROR: %s" % (d["code"], d["error"]))
            continue
        print("%-6s %-12s %-12s %-12s %7d %8.2f %10.0f %7.1f%% %7.1f%% %7.1f%% %7.1f%% %s" % (
            d["code"], d["signal_date"], d["ara_date"], d["hit_date"] or "-",
            d["window"], d["density"], d["entry"],
            d["gain_hit_pct"] or 0.0, d["gain_max10_pct"], d["gain_max21_pct"],
            d["gain_final_pct"], "" if d["pos_ok"] else "!!POS-MISMATCH"))
    n_ok = sum(1 for d in results if "error" not in d and d["pos_ok"])
    print("-" * len(hdr))
    print("invariant pos_vs_ara ok: %d/%d" % (n_ok, len(results)))


if __name__ == "__main__":
    main()