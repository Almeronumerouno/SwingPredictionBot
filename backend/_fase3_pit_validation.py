"""
F3.2 — Point-in-time / availability-date validation (per keputusan user, 13 Agu 2026).

Tujuan: membangun **availability metadata yang trustworthy** per kode, per field —
BUKAN model baru.

Tiga status availability (dipertahankan sampai storage F3.3, untuk M1/M2 di F3.6):

    observed  -> availability_source="earnings_dates",      is_observed=true
    assumed   -> availability_source="conservative_lag",    is_observed=false
    unknown   -> available_at=null, source="unknown",       is_observed=false

KEPUTUSAN DESAIN (dari user):
1. `earnings_dates` -> sanity check -> accept/reject. earningsTimestampEnd Yahoo
   TIDAK dipakai sebagai primary PIT source (F3.1: tidak sinkron, AKRA 2025-07-28
   vs aktual 2026-07-23) — hanya dicatat sebagai observasi inkonsistensi.
2. `period_end + lag` = ASUMSI konservatif, bukan fakta. Bila dipakai, wajib
   availability_source="conservative_lag", is_observed=false. UNKNOWN tetap
   UNKNOWN; dilarang mengisi unknown -> period_end+lag hanya supaya dataset penuh.
3. Per-field matrix, BUKAN satu tanggal untuk semua field:
   - report-based fields (EPS, Net Income, Revenue, ROE, D/E): berbagi tanggal
     announcement laporan yang sama, TAPI dihitung per field (bisa beda bila
     restatement / beda lag resmi).
   - snapshot fields (PER, PBV, Market Cap): available_at = waktu fetch,
     availability_source="quote", is_observed=true, TAPI pit_safe=false
     ("No historical PIT" — tidak pernah dipakai sebagai PIT backtest).
4. Field `pit_safe` = hanya true bila observed (earnings_dates accepted). Ini yang
   nanti memisahkan M1 (observed-only) vs M2 (observed+assumed) di F3.6.

Output: data/fundamental_pit_validation.json + ringkasan stdout.
"""

from __future__ import annotations

import datetime as dt
import json
import random
import sys
import time
from typing import Any, Optional

import requests
import yfinance as yf

import config

N_SAMPLE = 50
SEED = 42
OUT_PATH = "data/fundamental_pit_validation.json"
LOG_TAG = "[F3.2]"

# Field yang divalidasi: (nama log, tipe)
# tipe "report" = berbagi tanggal announcement laporan keuangan
# tipe "snapshot" = nilai saat ini dari quote, tanpa PIT historis
FIELDS = [
    ("EPS", "report"),
    ("Net Income", "report"),
    ("Revenue", "report"),
    ("ROE", "report"),
    ("Debt/Equity", "report"),
    ("PER", "snapshot"),
    ("PBV", "snapshot"),
    ("Market Cap", "snapshot"),
]

REPORT_FIELDS = [f for f, t in FIELDS if t == "report"]
SNAPSHOT_FIELDS = [f for f, t in FIELDS if t == "snapshot"]


def _epoch_to_iso(epoch: Any) -> Optional[str]:
    if epoch is None:
        return None
    try:
        return dt.datetime.fromtimestamp(float(epoch), tz=dt.timezone.utc).isoformat()
    except (ValueError, OSError, TypeError, OverflowError):
        return None


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _new_session() -> requests.Session:
    """Session dengan cookie + crumb Yahoo (pola yang terbukti lolos 429)."""
    s = requests.Session()
    s.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
    try:
        s.get("https://fc.yahoo.com", timeout=15)  # seed cookie A3
    except Exception as exc:  # noqa: BLE001
        print(f"{LOG_TAG}   (cookie seed gagal: {exc})", flush=True)
    return s


def _fetch_with_retry(fn, desc: str, result: dict, max_attempts: int = 2):
    """Jalankan fn dengan retry sekali saat rate-limit; tulis error ke result."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            if attempt < max_attempts and "Rate limit" in str(exc):
                print(f"{LOG_TAG}   rate-limit saat {desc}, retry dalam 8s ...", flush=True)
                time.sleep(8)
                continue
            result[f"error_{desc}"] = err
            return None
    return None


def _lag_days_for(period_end: Optional[dt.date]) -> int:
    """Lag konservatif (kebijakan F3.2) berdasarkan bulan period_end."""
    if period_end is None:
        return config.FUNDAMENTAL_LAG_DEFAULT_DAYS
    return config.FUNDAMENTAL_LAG_DAYS_BY_MONTH.get(period_end.month, config.FUNDAMENTAL_LAG_DEFAULT_DAYS)


def _sanity_check_earnings_dates(rows_iso: list[str], period_end: Optional[dt.date]) -> tuple[bool, str]:
    """
    Accept/reject earnings_dates sebagai observed.
    - minimal FUNDAMENTAL_EARNINGS_MIN_ROWS baris
    - available_at SETELAH period_end (tolak yang tidak sinkron — kasus AKRA)
    - available_at <= hari ini + toleransi (bukan jadwal masa depan)
    - lag (available_at - period_end) >= 1 hari
    """
    now = _now_utc().date()
    if not rows_iso:
        return False, "no rows"
    if period_end is None:
        return False, "period_end missing (tidak bisa divalidasi relatif terhadap periode)"

    dates = []
    for iso in rows_iso:
        try:
            d = dt.datetime.fromisoformat(iso)
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            dates.append(d.astimezone(dt.timezone.utc).date())
        except ValueError:
            continue
    if not dates:
        return False, "no parseable rows"

    tol = dt.timedelta(days=config.FUNDAMENTAL_AVAILABLE_FUTURE_TOLERANCE_DAYS)
    # Yahoo kadang menyertakan JADWAL rilis masa depan di earnings_dates
    # (kasus MDKA: baris 2026-09-24 = jadwal, belum terjadi). Baris masa depan
    # TIDAK boleh dipakai — ambil max hanya dari baris yang sudah lewat.
    past_dates = [d for d in dates if d <= _now_utc().date() + tol]
    if not past_dates:
        return False, "semua earnings_dates di masa depan (jadwal, belum terjadi)"
    avail = max(past_dates)  # announcement terakhir yang SUDAH terjadi

    if avail <= period_end:
        return False, f"available_at={avail} <= period_end={period_end} (tidak sinkron)"
    if avail > _now_utc().date() + tol:
        return False, f"available_at={avail} > hari ini+{tol.days}d (masa depan)"
    lag = (avail - period_end).days
    if lag < 1:
        return False, f"lag={lag}d < 1 (tanggal sama/aneh)"
    return True, f"ok (lag={lag}d)"


def validate_ticker(code: str, session: requests.Session) -> dict:
    """Validasi availability-date satu kode -> matrix per field."""
    ticker = yf.Ticker(code + ".JK", session=session)
    res: dict[str, Any] = {"code": code, "ticker": code + ".JK", "ok": False}

    # --- 1) info: period_end + earningsTimestampEnd (hanya sebagai observasi) ---
    info = _fetch_with_retry(lambda: ticker.info, "info", res)
    if info is None:
        return res
    if not isinstance(info, dict) or not info:
        res["error_info"] = "info kosong / tidak tersedia"
        return res

    period_end_epoch = info.get("mostRecentQuarter") or info.get("lastFiscalQuarterEnd")
    period_end_iso = _epoch_to_iso(period_end_epoch)
    period_end_date = None
    if period_end_iso:
        try:
            d = dt.datetime.fromisoformat(period_end_iso)
            period_end_date = d.date()
        except ValueError:
            pass

    ts_end_iso = _epoch_to_iso(info.get("earningsTimestampEnd"))
    ts_end_date = None
    if ts_end_iso:
        try:
            ts_end_date = dt.datetime.fromisoformat(ts_end_iso).date()
        except ValueError:
            pass

    # --- 2) earnings_dates (primary PIT candidate) ---
    ed_rows: list[str] = []
    ed = _fetch_with_retry(lambda: ticker.earnings_dates, "earnings_dates", res)
    if ed is not None and hasattr(ed, "iterrows"):
        for idx, _row in ed.iterrows():
            try:
                ts = idx
                if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.timezone.utc)
                ed_rows.append(ts.isoformat())
            except Exception:  # noqa: BLE001
                continue

    accepted, reason = _sanity_check_earnings_dates(ed_rows, period_end_date)

    # --- 3) matrix per field ---
    now_iso = _now_utc().isoformat()
    fields: dict[str, Any] = {}

    if accepted:
        avail_iso = ed_rows[0]  # placeholder; dipilih max yang valid (sudah lewat)
        parsed = []
        tol = dt.timedelta(days=config.FUNDAMENTAL_AVAILABLE_FUTURE_TOLERANCE_DAYS)
        for iso in ed_rows:
            try:
                d = dt.datetime.fromisoformat(iso)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=dt.timezone.utc)
                d = d.astimezone(dt.timezone.utc)
                if d.date() <= _now_utc().date() + tol:
                    parsed.append(d)
            except ValueError:
                continue
        if parsed:
            avail_iso = max(parsed).isoformat()
        for f in REPORT_FIELDS:
            fields[f] = {
                "period_end": period_end_iso,
                "available_at": avail_iso,
                "availability_source": "earnings_dates",
                "availability_is_observed": True,
                "confidence": "high",
                "pit_safe": True,
            }
    elif period_end_date is not None:
        lag = _lag_days_for(period_end_date)
        avail = (period_end_date + dt.timedelta(days=lag)).isoformat()
        for f in REPORT_FIELDS:
            fields[f] = {
                "period_end": period_end_iso,
                "available_at": avail,
                "availability_source": "conservative_lag",
                "availability_is_observed": False,
                "confidence": "low",
                "pit_safe": False,
                "lag_days": lag,
            }
    else:
        for f in REPORT_FIELDS:
            fields[f] = {
                "period_end": None,
                "available_at": None,
                "availability_source": "unknown",
                "availability_is_observed": False,
                "confidence": "low",
                "pit_safe": False,
            }

    # Snapshot fields: nilai saat ini dari quote. available_at = waktu fetch
    # (kapan nilai diambil), TAPI pit_safe=false — BUKAN PIT historis.
    for f in SNAPSHOT_FIELDS:
        fields[f] = {
            "period_end": None,
            "available_at": now_iso,
            "availability_source": "quote",
            "availability_is_observed": True,
            "confidence": "low",
            "pit_safe": False,
            "note": "snapshot current value; no historical PIT",
        }

    res.update({
        "ok": True,
        "period_end": period_end_iso,
        "period_end_date": period_end_date.isoformat() if period_end_date else None,
        "earnings_timestamp_end": ts_end_iso,          # observasi saja, BUKAN primary
        "earnings_timestamp_end_date": ts_end_date.isoformat() if ts_end_date else None,
        "earnings_dates": {"n_rows": len(ed_rows), "rows": ed_rows[:6]},
        "earnings_dates_accepted": accepted,
        "earnings_dates_reason": reason,
        "fields": fields,
    })
    return res


def main() -> int:
    print(f"{LOG_TAG} mulai — sample {N_SAMPLE} kode (seed={SEED})", flush=True)
    with open("data/universe_meta.json", encoding="utf-8") as f:
        codes = json.load(f)["codes"]
    print(f"{LOG_TAG} universe: {len(codes)} kode", flush=True)

    rng = random.Random(SEED)
    sample = rng.sample(sorted(codes), N_SAMPLE)
    print(f"{LOG_TAG} sample: {', '.join(sample)}", flush=True)

    session = _new_session()
    results = []
    t0 = time.time()
    for i, code in enumerate(sample, 1):
        print(f"{LOG_TAG} [{i}/{N_SAMPLE}] {code}.JK ...", flush=True)
        try:
            res = validate_ticker(code, session)
        except Exception as exc:  # noqa: BLE001
            res = {"code": code, "ticker": code + ".JK", "ok": False,
                   "error_unhandled": f"{type(exc).__name__}: {exc}"}
        results.append(res)
        print(f"{LOG_TAG}   -> ok={res['ok']} ed={res.get('earnings_dates', {}).get('n_rows', '?')} accepted={res.get('earnings_dates_accepted', '?')}",
              flush=True)
        time.sleep(1.2)

    elapsed = time.time() - t0

    # --- ringkasan distribusi status per field ---
    per_field: dict[str, dict[str, int]] = {}
    for f, _t in FIELDS:
        cnt = {"observed": 0, "assumed": 0, "unknown": 0, "quote": 0}
        for r in results:
            fld = r.get("fields", {}).get(f, {})
            src = fld.get("availability_source")
            if src == "earnings_dates":
                cnt["observed"] += 1
            elif src == "conservative_lag":
                cnt["assumed"] += 1
            elif src == "quote":
                cnt["quote"] += 1
            else:
                cnt["unknown"] += 1
        per_field[f] = cnt

    # inkonsistensi earningsTimestampEnd vs earnings_dates (observasi)
    n_cmp = 0
    n_mismatch = 0
    mismatch_codes = []
    for r in results:
        ed = r.get("earnings_dates", {})
        tsd = r.get("earnings_timestamp_end_date")
        if not r.get("ok") or not ed.get("rows") or tsd is None:
            continue
        n_cmp += 1
        # bandingkan dengan max earnings_dates
        parsed = []
        for iso in ed["rows"]:
            try:
                parsed.append(dt.datetime.fromisoformat(iso).date())
            except ValueError:
                continue
        if not parsed:
            continue
        if max(parsed) != tsd:
            n_mismatch += 1
            mismatch_codes.append({"code": r["code"], "earnings_dates_max": max(parsed).isoformat(),
                                   "earningsTimestampEnd": tsd})

    summary = {
        "seed": SEED,
        "n_sample": N_SAMPLE,
        "n_codes_universe": len(codes),
        "sample": sample,
        "elapsed_sec": round(elapsed, 1),
        "per_field": per_field,
        "earnings_dates_accepted_codes": sum(1 for r in results if r.get("earnings_dates_accepted")),
        "earnings_timestamp_mismatch": {
            "n_compared": n_cmp,
            "n_mismatch": n_mismatch,
            "codes": mismatch_codes,
        },
    }

    out = {"generated": _now_utc().isoformat(),
           "policy": {
               "lag_days_by_month": config.FUNDAMENTAL_LAG_DAYS_BY_MONTH,
               "lag_default_days": config.FUNDAMENTAL_LAG_DEFAULT_DAYS,
               "note": "ASUMSI konservatif, bukan fakta market; is_observed=false",
           },
           "summary": summary,
           "tickers": results}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # --- cetak ringkasan ---
    print(f"\n{LOG_TAG} ====== RINGKASAN (n={N_SAMPLE}) ======", flush=True)
    print(f"elapsed: {elapsed:.1f}s | earnings_dates accepted: {summary['earnings_dates_accepted_codes']}/{N_SAMPLE}")
    print("\nstatus availability per field (observed | assumed | quote | unknown):")
    for f, _t in FIELDS:
        c = per_field[f]
        print(f"  {f:<14} obs={c['observed']:<3} assumed={c['assumed']:<3} quote={c['quote']:<3} unknown={c['unknown']}")
    print(f"\ninkonsistensi earningsTimestampEnd vs earnings_dates: {n_mismatch}/{n_cmp} kode dibandingkan")
    for m in mismatch_codes[:5]:
        print(f"  {m['code']}: ed={m['earnings_dates_max']} vs tsEnd={m['earningsTimestampEnd']}")

    print(f"\n{LOG_TAG} selesai. output: {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
