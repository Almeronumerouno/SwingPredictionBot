"""
local_dataset.py — Akses dataset OHLCV lokal (universe_ohlcv.npz).

Dataset dibuat oleh _build_recovery_dataset.py:
  963 saham IDX, 900 bar terakhir per saham, kolom per baris:
  [open, high, low, close(raw), adj_close, volume]

Dipakai oleh walkforward.py (walk-forward validation offline) dan
_correlate_signals.py supaya TIDAK fetch Yahoo (anti rate-limit) dan
data point-in-time konsisten dengan kalibrasi model recovery.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Optional

import numpy as np

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_NPZ = os.path.join(BACKEND_DIR, "data", "universe_ohlcv.npz")

# Kolom per baris: 0=open, 1=high, 2=low, 3=close(raw), 4=adj_close, 5=volume
COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_ADJ, COL_VOL = 0, 1, 2, 3, 4, 5


def make_local_bar(i: int, rows: np.ndarray, n_fields: int,
                   dates: Optional[list] = None) -> SimpleNamespace:
    """Bangun objek mirip DailyBar dari baris npz (index relatif ke awal seri).

    dates: daftar tanggal ISO nyata per bar (opsional). Bila diberikan, dipakai
    sebagai date bar (bukan tanggal sintetis). Fallback: sintetis urut
    (hanya utk pemanggil lama yang tidak menyediakan dates).
    """
    r = rows[i]
    if dates is not None and i < len(dates):
        bar_date = dates[i]
    else:
        bar_date = (date(2020, 1, 1) + timedelta(days=i)).isoformat()  # sintetis, urut saja
    # previous = close bar sebelumnya (fix audit v2 §21: sebelumnya
    # r[COL_OPEN-1] = r[-1] = volume, bukan previous close).
    prev_close = float(rows[i - 1, COL_CLOSE]) if i > 0 else float(r[COL_CLOSE])
    return SimpleNamespace(
        date=bar_date,
        previous=prev_close,
        open_price=float(r[COL_OPEN]),
        high=float(r[COL_HIGH]),
        low=float(r[COL_LOW]),
        close=float(r[COL_CLOSE]),
        raw_close=float(r[COL_CLOSE]),
        adj_close=float(r[COL_ADJ]) if n_fields > COL_ADJ else float(r[COL_CLOSE]),
        volume=float(r[COL_VOL]) if n_fields > COL_VOL else 0.0,
        approx_value=0.0,
        frequency="1d",
        bid=0.0,
        offer=0.0,
        foreign_buy=0.0,
        foreign_sell=0.0,
    )


def load_local_bars(code: str, npz_path: Optional[str] = None) -> list:
    """Muat bar historis satu saham dari dataset lokal (anti-Yahoo fetch).

    Args:
        code: Kode saham, "BBRI" atau "BBRI.JK" (akhiran .JK diabaikan).
        npz_path: Path universe_ohlcv.npz (default: data/universe_ohlcv.npz).

    Returns:
        List objek mirip DailyBar (SimpleNamespace) — atribut date/open_price/
        high/low/close/raw_close/adj_close/volume.

    Raises:
        ValueError: dataset tidak ada / saham tidak ditemukan / data < minimum.
    """
    npz_path = npz_path or DEFAULT_NPZ
    if not os.path.exists(npz_path):
        raise ValueError(f"Dataset lokal tidak ada: {npz_path}")

    d = np.load(npz_path, allow_pickle=True)
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    target = code.upper().removesuffix(".JK")
    if target not in codes:
        raise ValueError(f"{code} tidak ada di dataset lokal ({len(codes)} kode)")

    i = codes.index(target)
    m = int(d["lens"][i])
    rows = d["rows"][i]
    n_fields = int(rows.shape[1])
    # Tanggal trading NYATA per bar (disimpan _build_recovery_dataset.py saat
    # build npz) — ganti tanggal sintetis (audit v2 §21/Phase-1).
    dates_i = list(d["dates"][i]) if i < len(d["dates"]) else None
    return [make_local_bar(j, rows, n_fields, dates_i) for j in range(m)]


def load_local_universe(npz_path: Optional[str] = None) -> dict:
    """Muat seluruh dataset lokal: codes, rows, lens, ok, dates."""
    npz_path = npz_path or DEFAULT_NPZ
    d = np.load(npz_path, allow_pickle=True)
    return {
        "codes": [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]],
        "rows": d["rows"],
        "lens": d["lens"].astype(int),
        "ok": d["ok"],
        "dates": d["dates"],
    }
