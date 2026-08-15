"""
F3.3 — fundamentals.py: pure fundamental data layer (Yahoo snapshot).

Contract (keputusan user, 13 Agu 2026):

    fetch -> normalize -> validate -> attach metadata -> return

TANPA risk logic (itu F3.4), TANPA perubahan score/signal, TANPA menyentuh API.

Setiap field menghasilkan FundamentalField dengan metadata availability:

    value                nilai numerik valid, atau None
    period_end           akhir periode laporan (ISO), atau None
    available_at         tanggal informasi diketahui market (ISO), atau None
    availability_status  observed | assumed | unknown | quote
    availability_source  earnings_dates | conservative_lag | quote | None
    is_observed          True hanya bila ada bukti tanggal publikasi
    pit_safe             True HANYA untuk observed (boleh masuk M1 di F3.6)
    snapshot_only        True untuk PER/PBV/Market Cap (quote)
    historical_pit_available  selalu False untuk snapshot fields

Aturan wajib (dari F3.2/F3.3):
1. Jangan menghapus metadata assumed — assumed != invalid, ia = perkiraan
   conservative policy, bukan observasi.
2. Jangan pernah mengubah UNKNOWN menjadi 0 (ROE=UNKNOWN bukan ROE=0).
3. PER/PBV/Market Cap = snapshot-only; ditandai eksplisit:
   snapshot_only=True, historical_pit_available=False, pit_safe=False.
4. Guard numerik: finite(value) — reject NaN/inf/-inf.
5. Guard D/E: equity <= 0 -> value technically computable but economically
   unstable -> None + note.
6. Guard PER: EPS <= 0 -> PER = None ("not meaningful"), jangan -12.7.
7. Guard PBV: book value <= 0 -> PBV = None ("not meaningful").
   (Kasus BLTA PBV=11333 / BBRM PBV=19167 adalah alasan guard ini.)
8. Coverage observed ~6% (F3.2) adalah TEMUAN RISET, BUKAN bug. Tidak ada
   usaha melonggarkan policy untuk "memperbaiki" coverage.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional

import requests
import yfinance as yf

import config

# ---------------------------------------------------------------------------
# Mapping field internal -> key info Yahoo
# ---------------------------------------------------------------------------
FIELD_INFO_KEY = {
    "eps": "trailingEps",
    "net_income": "netIncomeToCommon",
    "revenue": "totalRevenue",
    "roe": "returnOnEquity",
    "debt_equity": "debtToEquity",
    "per": "trailingPE",
    "pbv": "priceToBook",
    "market_cap": "marketCap",
}

# Field yang nilainya dari laporan keuangan (berbagi tanggal announcement)
REPORT_FIELDS = ("eps", "net_income", "revenue", "roe", "debt_equity")

# Field snapshot-only: nilai saat ini dari quote, TANPA historical PIT
SNAPSHOT_FIELDS = ("per", "pbv", "market_cap")

DEFAULT_FIELDS = REPORT_FIELDS + SNAPSHOT_FIELDS


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _finite(value: Any) -> Optional[float]:
    """Guard numerik: reject NaN/inf/-inf; None bila tidak valid."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def _epoch_to_iso(epoch: Any) -> Optional[str]:
    if epoch is None:
        return None
    try:
        return dt.datetime.fromtimestamp(float(epoch), tz=dt.timezone.utc).isoformat()
    except (ValueError, OSError, TypeError, OverflowError):
        return None


def _new_session() -> requests.Session:
    """Session dengan cookie + crumb Yahoo (pola yang terbukti lolos 429)."""
    s = requests.Session()
    s.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
    try:
        s.get("https://fc.yahoo.com", timeout=15)  # seed cookie A3
    except Exception:  # noqa: BLE001 — non-fatal, coba lanjut tanpa cookie
        pass
    return s


def _lag_days_for(period_end: Optional[dt.date]) -> int:
    """Lag konservatif (kebijakan F3.2) berdasarkan bulan period_end."""
    if period_end is None:
        return config.FUNDAMENTAL_LAG_DEFAULT_DAYS
    return config.FUNDAMENTAL_LAG_DAYS_BY_MONTH.get(period_end.month, config.FUNDAMENTAL_LAG_DEFAULT_DAYS)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
@dataclass
class FundamentalField:
    field: str
    value: Optional[float]
    period_end: Optional[str]
    available_at: Optional[str]
    availability_status: str                     # observed | assumed | unknown | quote
    availability_source: Optional[str]           # earnings_dates | conservative_lag | quote | None
    is_observed: bool
    pit_safe: bool
    snapshot_only: bool = False
    historical_pit_available: bool = False
    note: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "period_end": self.period_end,
            "available_at": self.available_at,
            "availability_status": self.availability_status,
            "availability_source": self.availability_source,
            "is_observed": self.is_observed,
            "pit_safe": self.pit_safe,
            "snapshot_only": self.snapshot_only,
            "historical_pit_available": self.historical_pit_available,
            "note": self.note,
        }


@dataclass
class FundamentalSnapshot:
    code: str
    as_of: str                                   # waktu fetch (ISO UTC)
    fields: dict[str, FundamentalField]
    period_end: Optional[str] = None
    available_at_report: Optional[str] = None    # tanggal announcement laporan (jika observed)
    availability_status_report: Optional[str] = None
    fetch_errors: list[str] = dc_field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "as_of": self.as_of,
            "period_end": self.period_end,
            "available_at_report": self.available_at_report,
            "availability_status_report": self.availability_status_report,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "fetch_errors": self.fetch_errors,
        }


# ---------------------------------------------------------------------------
# Sanity check earnings_dates (dari F3.2, dipakai ulang)
# ---------------------------------------------------------------------------
def _sanity_check_earnings_dates(rows_iso: list[str], period_end: Optional[dt.date]) -> tuple[Optional[str], str]:
    """
    Accept/reject earnings_dates sebagai observed -> (available_at_iso, reason).
    - minimal FUNDAMENTAL_EARNINGS_MIN_ROWS baris
    - available_at SETELAH period_end (tolak yang tidak sinkron — kasus AKRA)
    - available_at <= hari ini + toleransi (tolak jadwal masa depan — kasus MDKA)
    - lag (available_at - period_end) >= 1 hari
    """
    now = _now_utc().date()
    if not rows_iso:
        return None, "no rows"
    if period_end is None:
        return None, "period_end missing (tidak bisa divalidasi relatif terhadap periode)"

    tol = dt.timedelta(days=config.FUNDAMENTAL_AVAILABLE_FUTURE_TOLERANCE_DAYS)
    dates = []
    for iso in rows_iso:
        try:
            d = dt.datetime.fromisoformat(iso)
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            d = d.astimezone(dt.timezone.utc)
            if d.date() <= now + tol:            # filter jadwal masa depan
                dates.append(d)
        except ValueError:
            continue
    if not dates:
        return None, "semua earnings_dates di masa depan (jadwal, belum terjadi)"
    avail = max(dates).date()                     # announcement terakhir yang SUDAH terjadi
    if avail <= period_end:
        return None, f"available_at={avail} <= period_end={period_end} (tidak sinkron)"
    lag = (avail - period_end).days
    if lag < 1:
        return None, f"lag={lag}d < 1 (tanggal sama/aneh)"
    return max(dates).isoformat(), f"ok (lag={lag}d)"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def _fetch_info(ticker, errors: list[str]) -> Optional[dict]:
    """Fetch info Yahoo dengan retry rate-limit; None bila gagal."""
    for attempt in (1, 2):
        try:
            info = ticker.info
            if isinstance(info, dict) and info:
                return info
            errors.append("info kosong / tidak tersedia")
            return None
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            if attempt == 1 and "Rate limit" in str(exc):
                import time
                time.sleep(8)
                continue
            errors.append(err)
            return None
    return None


def _fetch_earnings_dates(ticker) -> list[str]:
    """Earnings_dates historis (primary PIT candidate). [] bila tidak tersedia."""
    try:
        ed = ticker.earnings_dates
        rows = []
        if ed is not None and hasattr(ed, "iterrows"):
            for idx, _row in ed.iterrows():
                try:
                    ts = idx
                    if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                        ts = ts.replace(tzinfo=dt.timezone.utc)
                    rows.append(ts.isoformat())
                except Exception:  # noqa: BLE001
                    continue
        return rows
    except Exception:  # noqa: BLE001 — "No earnings dates found" dll: bukan fatal
        return []


# ---------------------------------------------------------------------------
# Validasi nilai per field
# ---------------------------------------------------------------------------
def _validate_report_value(field: str, raw: Any) -> tuple[Optional[float], Optional[str]]:
    """Guard numerik + guard ekonomis untuk report fields. (value, note)"""
    v = _finite(raw)
    if v is None:
        return None, None

    if field == "debt_equity":
        # Guard D/E: angka ekstrem tidak otomatis salah di sini, tetapi
        # equity <= 0 membuat rasio tidak stabil secara ekonomis. Guard ini
        # dialog di F3.4 (risk flags), di sini hanya data layer.
        if v < 0:
            return None, "debt_equity < 0 (tidak bermakna ekonomis)"
    return v, None


def _validate_snapshot_value(field: str, raw: Any, eps_value: Optional[float],
                             book_value_per_share: Optional[float]) -> tuple[Optional[float], Optional[str]]:
    """Guard numerik + guard ekonomis untuk snapshot fields. (value, note)"""
    v = _finite(raw)
    if v is None:
        return None, None

    if field == "per":
        # Guard PER: EPS <= 0 -> PER tidak bermakna (jangan -12.7).
        # PER juga tidak bermakna bila nilai itu sendiri negatif.
        if eps_value is not None and eps_value <= 0:
            return None, "EPS <= 0 -> PER not meaningful"
        if v < 0:
            return None, "PER < 0 -> not meaningful"
    elif field == "pbv":
        # Guard PBV: book value (per share) <= 0 -> PBV tidak bermakna.
        # (Kasus BLTA PBV=11333 / BBRM PBV=19167 berasal dari book value ~0.)
        if book_value_per_share is not None and book_value_per_share <= 0:
            return None, "book value <= 0 -> PBV not meaningful"
        if v < 0:
            return None, "PBV < 0 -> not meaningful"
    elif field == "market_cap":
        if v <= 0:
            return None, "marketCap <= 0 (tidak bermakna)"
    return v, None


# ---------------------------------------------------------------------------
# API publik
# ---------------------------------------------------------------------------
def get_fundamentals(code: str, session: Optional[requests.Session] = None,
                     fields: tuple[str, ...] = DEFAULT_FIELDS) -> FundamentalSnapshot:
    """
    Snapshot fundamentals satu kode + availability metadata.

    - Tidak memodifikasi score/signal/API apa pun.
    - Tidak pernah raise untuk data yang "jelek" — data jelek menjadi
      unknown/None + note. Fetch total gagal => snapshot dengan semua field
      unknown + fetch_errors (masih object valid).
    """
    own_session = session is None
    if own_session:
        session = _new_session()

    as_of = _now_utc().isoformat()
    errors: list[str] = []
    ticker = yf.Ticker(code + ".JK", session=session)

    info = _fetch_info(ticker, errors)
    out: dict[str, FundamentalField] = {}

    if info is None:
        # Fetch gagal total: semua field unknown-safe, bukan 0.
        for f in fields:
            out[f] = FundamentalField(
                field=f, value=None, period_end=None, available_at=None,
                availability_status="unknown", availability_source=None,
                is_observed=False, pit_safe=False,
            )
        return FundamentalSnapshot(code=code, as_of=as_of, fields=out,
                                   fetch_errors=errors)

    # --- metadata laporan ---
    period_end_epoch = info.get("mostRecentQuarter") or info.get("lastFiscalQuarterEnd")
    period_end_iso = _epoch_to_iso(period_end_epoch)
    period_end_date = None
    if period_end_iso:
        try:
            period_end_date = dt.datetime.fromisoformat(period_end_iso).date()
        except ValueError:
            pass

    ed_rows = _fetch_earnings_dates(ticker)
    avail_iso, reason = _sanity_check_earnings_dates(ed_rows, period_end_date)
    if avail_iso is None and ed_rows and reason:
        errors.append(f"earnings_dates rejected: {reason}")

    # --- nilai mentah + guard ---
    eps_value = _finite(info.get("trailingEps"))
    book_value_per_share = _finite(info.get("bookValue"))

    raw_report = {f: info.get(FIELD_INFO_KEY[f]) for f in REPORT_FIELDS if f in fields}
    raw_snapshot = {f: info.get(FIELD_INFO_KEY[f]) for f in SNAPSHOT_FIELDS if f in fields}

    # --- build per-field ---
    for f in REPORT_FIELDS:
        if f not in fields:
            continue
        value, note = _validate_report_value(f, raw_report.get(f))
        if avail_iso is not None:
            out[f] = FundamentalField(
                field=f, value=value, period_end=period_end_iso,
                available_at=avail_iso, availability_status="observed",
                availability_source="earnings_dates", is_observed=True,
                pit_safe=True, note=note,
            )
        elif period_end_iso is not None:
            # assumed: asumsi conservative, BUKAN observasi
            lag = _lag_days_for(period_end_date)
            assumed_at = (period_end_date + dt.timedelta(days=lag)).isoformat()
            out[f] = FundamentalField(
                field=f, value=value, period_end=period_end_iso,
                available_at=assumed_at, availability_status="assumed",
                availability_source="conservative_lag", is_observed=False,
                pit_safe=False, note=note,
            )
        else:
            out[f] = FundamentalField(
                field=f, value=value, period_end=None, available_at=None,
                availability_status="unknown", availability_source=None,
                is_observed=False, pit_safe=False, note=note,
            )

    for f in SNAPSHOT_FIELDS:
        if f not in fields:
            continue
        value, note = _validate_snapshot_value(f, raw_snapshot.get(f), eps_value, book_value_per_share)
        out[f] = FundamentalField(
            field=f, value=value, period_end=None,
            available_at=as_of,                    # waktu fetch, bukan tanggal publish
            availability_status="quote",
            availability_source="quote",
            is_observed=True,                      # nilai benar-benar diamati saat fetch
            pit_safe=False,
            snapshot_only=True,
            historical_pit_available=False,
            note=note,
        )

    return FundamentalSnapshot(
        code=code,
        as_of=as_of,
        fields=out,
        period_end=period_end_iso,
        available_at_report=avail_iso,
        availability_status_report="observed" if avail_iso else
        ("assumed" if period_end_iso else "unknown"),
        fetch_errors=errors,
    )