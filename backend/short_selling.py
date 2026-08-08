"""
short_selling.py — Filter kelayakan short selling sesuai regulasi BEI.

Latar belakang (audit fix #2): sistem men-generate sinyal SELL sebagai entry
short untuk seluruh universe scan, padahal short selling di BEI SANGAT
dibatasi (Peraturan II-H BEI — SK Direksi Kep-00157/BEI/10-2024, POJK
No. 6/2024):

  - Hanya saham dalam "Daftar Efek Short Selling" yang diterbitkan &
    direview BEI SETIAP BULAN yang boleh di-short (Maret 2025: cuma ~237
    saham dari 900+).
  - Syarat: free float >= 20% (6 bulan terakhir), jaminan awal >= 50%,
    volume short dibatasi ketat (0.01%-0.04% saham beredar/hari).
  - Naked short selling dilarang.

Daftar bulanan tidak bisa di-fetch otomatis dari BEI secara stabil, jadi
modul ini membaca daftar dari cache lokal (JSON array kode saham). Admin
menyalin daftar terbaru ke `SHORT_SELLING_LIST_FILE` setiap bulan.

Perilaku konservatif:
  - File daftar tersedia  -> eligible hanya untuk kode yang ada di daftar.
  - File daftar absent    -> TIDAK ada yang eligible (default aman):
    sinyal SELL ditampilkan sebagai ADVISORY / exit-only, bukan entry short.
  - config.SHORT_SELLING_ENFORCE=False -> semua eligible (bypass).

Dependensi: stdlib + config saja.
"""

from __future__ import annotations

import json
import os
import threading

import config


_ELIGIBLE: set[str] | None = None
_LOAD_LOCK = threading.Lock()
_LIST_VERSION = None  # (mtime, size) utk cache invalidasi


def _load_list() -> set[str]:
    """Baca daftar eligible dari cache lokal; None = daftar tidak tersedia."""
    global _ELIGIBLE, _LIST_VERSION
    path = config.SHORT_SELLING_LIST_FILE

    with _LOAD_LOCK:
        try:
            mtime = os.path.getmtime(path)
            size = os.path.getsize(path)
        except OSError:
            _ELIGIBLE = None
            _LIST_VERSION = None
            return None

        if _LIST_VERSION == (mtime, size) and _ELIGIBLE is not None:
            return _ELIGIBLE

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = data.get("codes", [])
            codes = {
                str(c).strip().upper()
                for c in data
                if isinstance(c, str) and c.strip()
            }
            _ELIGIBLE = codes
            _LIST_VERSION = (mtime, size)
            return _ELIGIBLE
        except (OSError, ValueError) as e:
            # Cache korup -> treat sebagai tidak tersedia (konservatif)
            print(f"[short_selling] Gagal baca {path}: {e}")
            _ELIGIBLE = None
            _LIST_VERSION = None
            return None


def is_short_selling_eligible(code: str) -> bool:
    """
    True jika kode saham boleh di-short menurut daftar BEI bulan berjalan.

    Args:
        code: kode saham IDX tanpa suffix (mis. "BBCA")

    Returns:
        bool — konservatif: tanpa daftar (atau enforce off) -> per config.
    """
    if not config.SHORT_SELLING_ENFORCE:
        return True
    eligible = _load_list()
    if eligible is None:
        return config.SHORT_SELLING_DEFAULT_ELIGIBLE
    return code.strip().upper() in eligible


def short_selling_status(code: str) -> dict:
    """
    Ringkasan status short selling untuk satu saham (dipakai di API).

    Returns:
        {
          "code": str,
          "enforce": bool,
          "list_available": bool,
          "eligible": bool,
          "note": str  # human-readable alasan
        }
    """
    enforce = config.SHORT_SELLING_ENFORCE
    eligible = is_short_selling_eligible(code)
    list_available = _load_list() is not None

    if not enforce:
        note = "Filter short selling dimatikan (SHORT_SELLING_ENFORCE=False)."
    elif not list_available:
        note = (
            f"Daftar Efek Short Selling BEI belum tersedia di "
            f"{os.path.basename(config.SHORT_SELLING_LIST_FILE)} — default "
            "konservatif: SELL hanya advisory (exit-only), bukan entry short."
        )
    elif eligible:
        note = "Ada di Daftar Efek Short Selling BEI — sinyal SELL dapat dieksekusi sebagai short."
    else:
        note = (
            "TIDAK ada di Daftar Efek Short Selling BEI — sinyal SELL "
            "bersifat advisory (exit-only untuk posisi long yang ada), "
            "tidak bisa dieksekusi sebagai entry short."
        )

    return {
        "code": code.strip().upper(),
        "enforce": enforce,
        "list_available": list_available,
        "eligible": eligible,
        "note": note,
    }


if __name__ == "__main__":
    import sys

    codes = sys.argv[1:] or ["BBCA"]
    for c in codes:
        print(short_selling_status(c))
