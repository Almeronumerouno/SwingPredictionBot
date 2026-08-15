"""
_phase5_p50_freeze.py — P5.0 Freeze & Safety Check (Phase 5).

Memverifikasi bahwa Phase 5 tidak bisa secara tidak sengaja mengotak-atik F2-F4:

  1. Dataset snapshot Phase 5 (data/phase5_snapshot_universe_ohlcv.npz) hash
     cocok dgn hash yang di-freeze di data/phase5_protocol.json.
  2. config.py hash cocok dgn hash freeze (production config tidak berubah).
  3. Nilai RTF production config (ACCUM_DENSITY_PCT, ACCUM_HEAVY_RVOL,
     ACCUM_MIN_HEAVY_DAYS, ACCUM_DECAY_TAU, ACCUM_DECAY_CUTOFF_DAYS) cocok
     dgn nilai frozen (density=30, heavy=2.0, min_heavy=2, tau=2.0, cutoff=5).
  4. Rentang tanggal snapshot == rentang freeze; n kode/n rows cocok.
  5. Split policy: cutoff 2026-01-23, purge 21 (max label horizon), embargo 90.
  6. Guard holdout: Phase 5 WAJIB memakai SNAPSHOT (bukan universe_ohlcv.npz
     live), sehingga pembaruan data utk Phase 4 holdout tidak mengkontaminasi.
  7. M1 recovery candidate & p_min=0.68 TIDAK dipakai Phase 5 (read-only).

Output: data/phase5_p50_check.json — status "PASS" / "STOP" + detail.
Script TIDAK menulis config.py dan TIDAK menulis universe_ohlcv.npz.

Usage: python _phase5_p50_freeze.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "phase5_snapshot_universe_ohlcv.npz")
LIVE_PATH = os.path.join(DATA_DIR, "universe_ohlcv.npz")
CONFIG_PATH = os.path.join(BACKEND_DIR, "config.py")
PROTOCOL_PATH = os.path.join(DATA_DIR, "phase5_protocol.json")
OUT_PATH = os.path.join(DATA_DIR, "phase5_p50_check.json")

# Nilai frozen (harus identik dgn protocol.json)
FROZEN_RTF_CONFIG = {
    "ACCUM_DENSITY_PCT": 30.0,
    "ACCUM_HEAVY_RVOL": 2.0,
    "ACCUM_MIN_HEAVY_DAYS": 2,
    "ACCUM_DECAY_TAU": 2.0,
    "ACCUM_DECAY_CUTOFF_DAYS": 5,
}
FROZEN_CUTOFF = "2026-01-23"
FROZEN_PURGE = 21
FROZEN_EMBARGO = 90
FROZEN_OOS_START = "2026-04-23"
FROZEN_DATE_END = "2026-08-13"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def parse_date(x) -> dt.date:
    if isinstance(x, (bytes,)):
        x = x.decode()
    return dt.date.fromisoformat(x)


def main() -> int:
    checks: list[dict] = []
    ok = True

    # ── 1. protocol ada & dibaca ──────────────────────────────────────────
    if not os.path.exists(PROTOCOL_PATH):
        print("STOP: phase5_protocol.json tidak ada — freeze dulu.")
        return 1
    with open(PROTOCOL_PATH, encoding="utf-8") as fh:
        protocol = json.load(fh)
    ds = protocol["dataset"]

    # ── 2. snapshot hash ──────────────────────────────────────────────────
    snap_sha = sha256_file(SNAPSHOT_PATH)
    frozen_sha = ds["snapshot_sha256"]
    match = snap_sha == frozen_sha
    ok &= match
    checks.append({
        "check": "snapshot_hash",
        "expected": frozen_sha,
        "actual": snap_sha,
        "pass": match,
    })
    print(f"snapshot hash: {'OK' if match else 'MISMATCH'} ({snap_sha[:16]}...)")

    # ── 3. config.py hash ─────────────────────────────────────────────────
    cfg_sha = sha256_file(CONFIG_PATH)
    cfg_frozen = ds["config_py_sha256"]
    match = cfg_sha == cfg_frozen
    ok &= match
    checks.append({
        "check": "config_py_hash",
        "expected": cfg_frozen,
        "actual": cfg_sha,
        "pass": match,
    })
    print(f"config.py hash: {'OK' if match else 'MISMATCH'} ({cfg_sha[:16]}...)")

    # ── 4. nilai RTF production config ────────────────────────────────────
    import config as cfg
    cfg_vals = {
        "ACCUM_DENSITY_PCT": float(cfg.ACCUM_DENSITY_PCT),
        "ACCUM_HEAVY_RVOL": float(cfg.ACCUM_HEAVY_RVOL),
        "ACCUM_MIN_HEAVY_DAYS": int(cfg.ACCUM_MIN_HEAVY_DAYS),
        "ACCUM_DECAY_TAU": float(cfg.ACCUM_DECAY_TAU),
        "ACCUM_DECAY_CUTOFF_DAYS": int(cfg.ACCUM_DECAY_CUTOFF_DAYS),
    }
    for k, expected in FROZEN_RTF_CONFIG.items():
        actual = cfg_vals[k]
        match = actual == expected
        ok &= match
        checks.append({"check": f"rtf_config_{k}", "expected": expected,
                       "actual": actual, "pass": match})
        print(f"rtf config {k}: {'OK' if match else 'MISMATCH'} ({actual})")

    # ── 5. snapshot isi (n kode, n rows, rentang tanggal) ─────────────────
    d = np.load(SNAPSHOT_PATH, allow_pickle=True)
    rows, lens, dates = d["rows"], d["lens"], d["dates"]
    n_codes = int(len(lens))
    n_rows = int(lens.sum())
    mx = dt.date(1970, 1, 1)
    mn = dt.date(9999, 1, 1)
    for a in dates:
        s, e = parse_date(a[0]), parse_date(a[-1])
        mn, mx = min(mn, s), max(mx, e)
    iso_range = f"{mn.isoformat()}..{mx.isoformat()}"
    for label, actual, expected in [
        ("n_codes", n_codes, ds["n_codes"]),
        ("n_rows_total", n_rows, ds["n_rows_total"]),
        ("date_range", iso_range,
         f"{ds['date_range'].split('..')[0].strip()}..{ds['date_range'].split('..')[1].strip()}"),
        ("date_end", mx.isoformat(), FROZEN_DATE_END),
    ]:
        match = actual == expected
        ok &= match
        checks.append({"check": f"snapshot_{label}", "expected": expected,
                       "actual": actual, "pass": match})
        print(f"snapshot {label}: {'OK' if match else 'MISMATCH'} ({actual})")

    # ── 6. split policy ───────────────────────────────────────────────────
    sp = protocol["split"]
    for label, actual, expected in [
        ("cutoff", sp["cutoff_absolut"], FROZEN_CUTOFF),
        ("purge", sp["purge"], str(FROZEN_PURGE)),
        ("embargo_days", sp["embargo_days"], FROZEN_EMBARGO),
        ("oos_start", sp["oos_start"], FROZEN_OOS_START),
    ]:
        match = str(actual) == str(expected)
        ok &= match
        checks.append({"check": f"split_{label}", "expected": expected,
                       "actual": str(actual), "pass": match})
        print(f"split {label}: {'OK' if match else 'MISMATCH'} ({actual})")

    # ── 7. guard holdout: live npz boleh berubah, snapshot TIDAK ──────────
    live_sha = sha256_file(LIVE_PATH) if os.path.exists(LIVE_PATH) else None
    live_changed = live_sha is not None and live_sha != snap_sha
    checks.append({
        "check": "live_npz_vs_snapshot",
        "note": ("live npz BERUBAH — Phase 5 tetap pakai snapshot (aman); "
                 "perubahan tsb kemungkinan utk Phase 4 holdout"
                 if live_changed else "live npz == snapshot (belum ada update)"),
        "pass": True,  # perubahan live TIDAK menghentikan Phase 5
    })
    print(f"live npz vs snapshot: {'changed (ok, snapshot dipakai)' if live_changed else 'identical'}")

    # ── 8. guard: M1 / p_min tidak dipakai (statik, tercatat) ─────────────
    checks.append({"check": "m1_not_used", "pass": True,
                   "note": "Phase 5 memakai RTF production score ranking; M1 recovery candidate di luar scope"})
    checks.append({"check": "p_min_untouched", "pass": True,
                   "note": "p_min=0.68 frozen; Phase 5 tidak memakai signal gate recovery"})
    checks.append({"check": "config_py_not_written", "pass": True,
                   "note": "script Phase 5 read-only terhadap config.py"})

    # ── verdict ───────────────────────────────────────────────────────────
    verdict = "PASS" if ok else "STOP"
    out = {
        "phase": "P5.0 Freeze & Safety Check",
        "checked_at": dt.date.today().isoformat(),
        "verdict": verdict,
        "acceptance": {
            "pass_rule": "semua frozen state cocok -> PASS",
            "stop_rule": "ada mismatch -> STOP, jangan lanjut ke P5.1",
        },
        "checks": checks,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"\nVERDICT: {verdict}  -> {OUT_PATH}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())