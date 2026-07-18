"""
Client untuk endpoint www.idx.co.id (versi Nuxt.js) — KHUSUS daftar
saham terdaftar via GetSecuritiesStock.

PENTING (baca ini):
- Endpoint ini BUKAN API resmi berkontrak dari BEI, ditemukan lewat
  reverse-engineering website idx.co.id. Struktur response BISA BERUBAH
  sewaktu-waktu tanpa pemberitahuan.
- Syarat Penggunaan BEI melarang penggunaan data untuk tujuan KOMERSIAL
  tanpa izin tertulis. Untuk personal use / testing / riset ini praktik
  umum dan risikonya rendah.
- www.idx.co.id memakai proteksi Cloudflare, karena itu kita pakai
  `cloudscraper` alih-alih `requests` biasa.

ASUMSI YANG PERLU DIVALIDASI (belum ada raw JSON sample lengkap):
- Response GetSecuritiesStock diasumsikan berupa list langsung ATAU dict
  dengan key umum (data/Data/items/Items) berisi list objek dengan field
  `Code`, `Name`, `Shares`, `ListingDate`, `ListingBoard`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

import cloudscraper

import config


class IdxClientError(Exception):
    """Raised saat request ke idx.co.id gagal atau response tidak sesuai ekspektasi."""


@dataclass
class Security:
    code: str
    name: str
    listing_date: str = ""
    shares: float = 0.0
    listing_board: str = ""


_SESSION: Optional[cloudscraper.CloudScraper] = None


def _get_session() -> cloudscraper.CloudScraper:
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    session = cloudscraper.create_scraper()
    session.get(
        config.IDX_BASE_URL + config.IDX_SESSION_INIT_PATH,
        headers={"User-Agent": config.IDX_REQUEST_USER_AGENT, "Referer": config.IDX_BASE_URL},
    )
    _SESSION = session
    return session


def _request_json(session: cloudscraper.CloudScraper, url: str, params: dict, retries: int = None) -> dict:
    retries = config.IDX_REQUEST_RETRIES if retries is None else retries
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=config.IDX_REQUEST_TIMEOUT)
            resp.raise_for_status()
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 - kita mau tangkap semua & retry
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise IdxClientError(f"Gagal fetch {url} dengan params {params}: {last_err}")


def _extract_rows(result) -> list[dict]:
    """
    Normalisasi response GetSecuritiesStock yang bentuknya belum pasti (list
    langsung, atau dict dibungkus key data/Data/items/Items). Dibuat
    defensif karena field-nya baru ditemukan lewat testing manual, bukan
    dokumentasi resmi.
    """
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("data", "Data", "items", "Items", "result", "Result"):
            if key in result and isinstance(result[key], list):
                return result[key]
    raise IdxClientError(
        f"Struktur response GetSecuritiesStock tidak dikenali: {type(result)} - "
        f"kirim raw JSON-nya biar bisa disesuaikan. Sample: {str(result)[:300]}"
    )


def fetch_all_securities() -> list[Security]:
    """
    Ambil seluruh daftar saham terdaftar di BEI lewat endpoint
    GetSecuritiesStock. Dicoba single call dulu; kalau ternyata IDX
    membatasi jumlah hasil per request, perlu ditambah logic pagination
    lagi (kasih tau kalau hasilnya kurang dari ~900-965 saham).
    """
    session = _get_session()
    url = config.IDX_BASE_URL + config.IDX_SECURITIES_ENDPOINT

    result = _request_json(session, url, params={})
    rows = _extract_rows(result)

    seen: set[str] = set()
    all_securities: list[Security] = []
    for row in rows:
        code = str(row.get("Code", "")).strip()
        name = str(row.get("Name", "")).strip()
        shares = float(row.get("Shares", 0) or 0)
        listing_date = str(row.get("ListingDate", "") or "")
        listing_board = str(row.get("ListingBoard", "") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        all_securities.append(Security(code=code, name=name, shares=shares, listing_date=listing_date, listing_board=listing_board))

    return all_securities
