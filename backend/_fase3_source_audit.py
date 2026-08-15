"""
F3.1 — Fundamental source audit (Opsi A, per keputusan user).

Pertanyaan inti audit BUKAN "berapa banyak field yang tersedia", melainkan:
    > kapan angka tersebut benar-benar diketahui market?

Untuk 10 kode acak dari universe, audit ini mencatat per field:
    - coverage               (ada / None)
    - nilai raw
    - period_end             (fiscal period: mostRecentQuarter / lastFiscalQuarterEnd)
    - available_at           (announcement date: earningsTimestamp — bukan tanggal fetch!)
    - source_timestamp       (kapan Yahoo update snapshot ini, kalau tersedia)
    - age_days               (available_at -> hari ini, indikator freshness)

Plus pemeriksaan struktural untuk kesiapan F3.2 / F3.6 (backtest OOS):
    - earnings_dates historis: apakah Yahoo menyediakan RIWAYAT tanggal
      announcement per kuartal (syarat point-in-time backtest)?
    - fundamentals-timeseries endpoint: probe 1-2 kode, apakah tersedia
      data historis dengan asOfDate (syarat F3.6 incremental test)?

Hasil ditulis ke data/fundamental_source_audit.json + ringkasan ke stdout.

Catatan jujur yang sudah diketahui sejak awal (akan diverifikasi di sini):
    - Yahoo `info` adalah SNAPSHOT saat ini, bukan timeseries; nilai
      historis tidak tersedia lewat info (hanya lewat fundamentals-timeseries
      yang butuh crumb dan belum tentu jalan untuk .JK).
    - `earningsTimestamp` di info = tanggal announcement kuartal terakhir =
      kandidat `available_at` terbaik dari sumber ini.
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

N_SAMPLE = 10
SEED = 42
OUT_PATH = "data/fundamental_source_audit.json"
LOG_TAG = "[F3.1]"

# Field yang diaudit: (nama log, key di info Yahoo)
FIELDS = [
    ("PER", "trailingPE"),
    ("PBV", "priceToBook"),
    ("ROE", "returnOnEquity"),
    ("Debt/Equity", "debtToEquity"),
    ("Market Cap", "marketCap"),
    ("Earnings (EPS)", "trailingEps"),
    ("Earnings (Net Income)", "netIncomeToCommon"),
    ("Revenue", "totalRevenue"),
]

# Field metadata point-in-time yang dicari di info
PIT_KEYS = {
    "period_end": "mostRecentQuarter",          # epoch fiscal period end
    "period_end_alt": "lastFiscalQuarterEnd",   # alternatif
    "fiscal_year_end": "lastFiscalYearEnd",
    "available_at": "earningsTimestamp",        # epoch announcement date
    "available_at_end": "earningsTimestampEnd", # kisaran akhir announce window
    "source_timestamp": "timestamp",            # kapan snapshot di-generate Yahoo
}


def _epoch_to_iso(epoch: Any) -> Optional[str]:
    if epoch is None:
        return None
    try:
        return dt.datetime.fromtimestamp(float(epoch), tz=dt.timezone.utc).isoformat()
    except (ValueError, OSError, TypeError, OverflowError):
        return None


def _age_days(epoch: Any) -> Optional[float]:
    iso = _epoch_to_iso(epoch)
    if iso is None:
        return None
    try:
        ts = dt.datetime.fromisoformat(iso)
        return (dt.datetime.now(dt.timezone.utc) - ts).total_seconds() / 86400.0
    except ValueError:
        return None


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f
    except (ValueError, TypeError):
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
    except Exception as exc:  # noqa: BLE001
        print(f"{LOG_TAG}   (cookie seed gagal: {exc})", flush=True)
    return s


def audit_ticker(code: str, session: requests.Session) -> dict:
    """Audit satu kode: snapshot info + riwayat earnings dates."""
    ticker = yf.Ticker(code + ".JK", session=session)
    result: dict[str, Any] = {"code": code, "ticker": code + ".JK", "ok": False}

    # --- 1) snapshot info (field coverage + nilai + PIT metadata) ---
    info = None
    for attempt in (1, 2):
        try:
            info = ticker.info
            break
        except Exception as exc:  # noqa: BLE001 — audit harus survive kegagalan apapun
            result["error_info"] = f"{type(exc).__name__}: {exc}"
            if attempt == 1 and "Rate limit" in str(exc):
                print(f"{LOG_TAG}   rate-limit, retry dalam 8s ...", flush=True)
                time.sleep(8)
            else:
                return result
    if info is None:
        return result

    if not isinstance(info, dict) or not info:
        result["error_info"] = "info kosong / tidak tersedia"
        return result

    fields = {}
    for label, key in FIELDS:
        fields[label] = {
            "coverage": key in info and info.get(key) is not None,
            "value": _safe_float(info.get(key)),
        }
    result["fields"] = fields

    pit = {}
    for label, key in PIT_KEYS.items():
        raw = info.get(key)
        pit[label] = {
            "raw": raw,
            "iso": _epoch_to_iso(raw),
            "age_days": _age_days(raw),
        }
    result["pit"] = pit

    result["sector"] = info.get("sector")
    result["industry"] = info.get("industry")
    result["fetch_time_iso"] = dt.datetime.now(dt.timezone.utc).isoformat()
    result["ok"] = True

    # --- 2) riwayat earnings dates (syarat F3.2: announcement date historis) ---
    try:
        ed = ticker.earnings_dates
        rows = []
        if ed is not None and len(ed) > 0:
            for idx, row in ed.head(8).iterrows():
                rows.append({
                    "quarter_iso": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                    "eps_estimate": _safe_float(getattr(row, "epsEstimate", None) or row.get("epsEstimate") if hasattr(row, "get") else None),
                    "eps_actual": _safe_float(getattr(row, "epsActual", None) or row.get("epsActual") if hasattr(row, "get") else None),
                    "surprise_pct": _safe_float(getattr(row, "surprisePercent", None) or row.get("surprisePercent") if hasattr(row, "get") else None),
                })
        result["earnings_dates"] = {"available": len(rows) > 0, "n_rows": len(rows), "rows": rows}
    except Exception as exc:  # noqa: BLE001
        result["earnings_dates"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    # --- 3) probe fundamentals-timeseries (syarat F3.6 backtest historis) ---
    try:
        ts = ticker.get_fundamentals_timeseries("trailingPE", "marketCap", "debtToEquity")
        result["fundamentals_timeseries"] = {
            "available": bool(ts),
            "sample": ts if isinstance(ts, (dict, list)) else str(ts)[:300],
        }
    except Exception as exc:  # noqa: BLE001
        result["fundamentals_timeseries"] = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    return result


def main() -> int:
    print(f"{LOG_TAG} mulai audit — sample {N_SAMPLE} kode dari universe (seed={SEED})", flush=True)

    with open("data/universe_meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    codes = meta["codes"]
    print(f"{LOG_TAG} universe: {len(codes)} kode", flush=True)

    rng = random.Random(SEED)
    sample = rng.sample(sorted(codes), N_SAMPLE)
    print(f"{LOG_TAG} sample: {', '.join(sample)}", flush=True)

    session = _new_session()
    results = []
    t0 = time.time()
    for i, code in enumerate(sample, 1):
        print(f"{LOG_TAG} [{i}/{N_SAMPLE}] audit {code}.JK ...", flush=True)
        try:
            res = audit_ticker(code, session)
        except Exception as exc:  # noqa: BLE001
            res = {"code": code, "ticker": code + ".JK", "ok": False,
                   "error_info": f"unhandled {type(exc).__name__}: {exc}"}
        results.append(res)
        print(f"{LOG_TAG}   -> ok={res['ok']}", flush=True)
        time.sleep(1.2)  # hormati rate limit Yahoo

    elapsed = time.time() - t0

    # --- ringkasan coverage ---
    coverage = {}
    for label, _key in FIELDS:
        n = sum(1 for r in results if r.get("fields", {}).get(label, {}).get("coverage"))
        coverage[label] = f"{n}/{len(results)}"

    n_ed = sum(1 for r in results if r.get("earnings_dates", {}).get("available"))
    n_ts = sum(1 for r in results if r.get("fundamentals_timeseries", {}).get("available"))

    summary = {
        "seed": SEED,
        "n_sample": N_SAMPLE,
        "n_codes_universe": len(codes),
        "sample": sample,
        "elapsed_sec": round(elapsed, 1),
        "coverage_per_field": coverage,
        "earnings_dates_available": f"{n_ed}/{len(results)}",
        "fundamentals_timeseries_available": f"{n_ts}/{len(results)}",
    }

    out = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(),
           "summary": summary, "tickers": results}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # --- cetak ringkasan ke stdout ---
    print(f"\n{LOG_TAG} ====== RINGKASAN ======", flush=True)
    print(f"elapsed: {elapsed:.1f}s | universe: {len(codes)} | sample: {N_SAMPLE}")
    print("\ncoverage per field (yang tersedia di snapshot info Yahoo):")
    for label, cov in coverage.items():
        print(f"  {label:<22} {cov}")
    print(f"\nriwayat earnings dates historis   : {n_ed}/{len(results)} kode")
    print(f"fundamentals-timeseries historis  : {n_ts}/{len(results)} kode")
    print("\nper-kode PIT metadata (period_end vs available_at):")
    for r in results:
        pit = r.get("pit", {})
        pe = pit.get("period_end", {}).get("iso") or pit.get("period_end_alt", {}).get("iso")
        aa = pit.get("available_at", {}).get("iso") or pit.get("available_at_end", {}).get("iso")
        age = pit.get("available_at", {}).get("age_days")
        print(f"  {r['code']:<6} ok={r['ok']!s:<5} period_end={pe}  available_at={aa}  age={age:.0f}d" if age else
              f"  {r['code']:<6} ok={r['ok']!s:<5} period_end={pe}  available_at={aa}  age=?")

    print(f"\n{LOG_TAG} selesai. output: {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
