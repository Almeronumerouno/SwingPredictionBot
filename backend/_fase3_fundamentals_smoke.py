"""
Smoke test F3.3 — fundamentals.py pure data layer.

Acceptance criteria (user, 13 Agu 2026):
- snapshot fetch berhasil
- semua field punya metadata availability
- observed / assumed / unknown konsisten
- quote fields ditandai snapshot-only
- UNKNOWN-safe (tidak ada coercion ke 0)
- NaN/Inf-safe
- PER/EPS guard
- PBV/book-value guard
- D/E/equity guard
- tidak mengubah scoring
- tidak memengaruhi READY/ALMOST
- API belum perlu diubah dulu
- existing tests tetap PASS

Test kunci: 3 tipe saham
  AKRA  = data lengkap + earnings_dates observed (dari F3.2)
  BEBS  = parsial, laba negatif (PER harus null, ROE negatif tetap valid)
  RIMO  = UNKNOWN/extreme (marketCap 0 -> null)
Semua harus menghasilkan object valid tanpa exception dan tanpa silent coercion.
"""

from __future__ import annotations

import json
import math

from fundamentals import (FundamentalField, FundamentalSnapshot,
                          get_fundamentals, _finite, _validate_report_value,
                          _validate_snapshot_value)

PASS = 0
FAIL = 0

SNAPSHOT_FIELDS_REF = ("per", "pbv", "market_cap")


def check(label: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} {detail}")


def section(label: str):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")


# --- 1) guard numerik murni (tanpa network) ---
section("Guard numerik (unit, tanpa network)")
check("_finite(None) -> None", _finite(None) is None)
check("_finite('abc') -> None", _finite("abc") is None)
check("_finite(float('nan')) -> None", _finite(float("nan")) is None)
check("_finite(float('inf')) -> None", _finite(float("inf")) is None)
check("_finite(float('-inf')) -> None", _finite(float("-inf")) is None)
check("_finite(42.5) -> 42.5", _finite(42.5) == 42.5)

check("D/E < 0 -> None + note", _validate_report_value("debt_equity", -5.0) == (None, "debt_equity < 0 (tidak bermakna ekonomis)"))
check("D/E >= 0 -> nilai dipertahankan", _validate_report_value("debt_equity", 15.0)[0] == 15.0)
check("ROE negatif -> nilai dipertahankan (bukan 0)", _validate_report_value("roe", -0.045)[0] == -0.045)

check("PER guard: EPS<=0 -> None", _validate_snapshot_value("per", 12.5, eps_value=-0.84, book_value_per_share=1.0)[0] is None)
check("PER valis: EPS>0 -> nilai", _validate_snapshot_value("per", 12.5, eps_value=471.81, book_value_per_share=1.0)[0] == 12.5)
check("PER negatif -> None", _validate_snapshot_value("per", -12.7, eps_value=5.0, book_value_per_share=1.0)[0] is None)
check("PBV guard: book<=0 -> None", _validate_snapshot_value("pbv", 11333.0, eps_value=5.0, book_value_per_share=0.0)[0] is None)
check("PBV normal -> nilai", _validate_snapshot_value("pbv", 2.85, eps_value=5.0, book_value_per_share=10.0)[0] == 2.85)
check("MCap <= 0 -> None", _validate_snapshot_value("market_cap", 0.0, None, None)[0] is None)
check("MCap normal -> nilai", _validate_snapshot_value("market_cap", 7.7e14, None, None)[0] == 7.7e14)


# --- 2) snapshot nyata: AKRA (lengkap + observed) ---
section("AKRA — data lengkap (harus observed via earnings_dates)")
ak = get_fundamentals("AKRA")
check("snapshot valid", isinstance(ak, FundamentalSnapshot))
check("tidak ada exception", True)
d = ak.to_dict()
check("serializable ke JSON", isinstance(json.dumps(d), str))
check("as_of ada", bool(ak.as_of))
check("period_end ada", ak.period_end is not None, str(ak.period_end))
check("status report = observed", ak.availability_status_report == "observed", str(ak.availability_status_report))
have = {k: v for k, v in ak.fields.items()}
for f in ("eps", "net_income", "revenue", "roe", "debt_equity", "per", "pbv", "market_cap"):
    check(f"field '{f}' ada", f in ak.fields)
f_roe = ak.fields["roe"]
check("ROE observed + pit_safe", f_roe.availability_status == "observed" and f_roe.pit_safe, str(f_roe.to_dict()))
f_eps = ak.fields["eps"]
check("EPS value finite", f_eps.value is not None and math.isfinite(f_eps.value))
check("available_at > period_end (observed)", f_eps.available_at is not None and f_eps.available_at > (f_eps.period_end or ""), f"{f_eps.available_at} vs {f_eps.period_end}")
f_per = ak.fields["per"]
check("PER snapshot_only + !pit_safe", f_per.snapshot_only and not f_per.pit_safe and not f_per.historical_pit_available)
check("PER value ada (EPS>0)", f_per.value is not None, str(f_per.value))
f_pbv = ak.fields["pbv"]
check("PBV quote + is_observed", f_pbv.availability_status == "quote" and f_pbv.is_observed)
f_mc = ak.fields["market_cap"]
check("MCap > 0", f_mc.value is not None and f_mc.value > 0)


# --- 3) snapshot nyata: BEBS (parsial, laba negatif) ---
section("BEBS — parsial / laba negatif (PER harus null, ROE negatif tetap) ")
be = get_fundamentals("BEBS")
check("snapshot valid", isinstance(be, FundamentalSnapshot))
f_roe = be.fields["roe"]
check("ROE negatif dipertahankan (bukan 0, bukan None)", f_roe.value is not None and f_roe.value < 0, str(f_roe.value))
f_eps = be.fields["eps"]
check("EPS negatif dipertahankan", f_eps.value is not None and f_eps.value < 0, str(f_eps.value))
f_per = be.fields["per"]
check("PER = None (raw Yahoo None utk laba negatif; tidak ada -12.7)", f_per.value is None, str(f_per.value))
# catatan: untuk BEBS, trailingPE Yahoo memang raw None (bukan ditolak guard),
# jadi note kosong itu benar. Guard PER->note sudah dibuktikan di unit test.
check("PER tetap snapshot_only", f_per.snapshot_only and not f_per.pit_safe)
f_pbv = be.fields["pbv"]
check("PBV tersedia (book>0)", f_pbv.value is not None, str(f_pbv.value))


# --- 4) snapshot nyata: RIMO (UNKNOWN/extreme: marketCap 0) ---
section("RIMO — UNKNOWN/extreme (marketCap 0 -> null)")
ri = get_fundamentals("RIMO")
check("snapshot valid (tanpa exception)", isinstance(ri, FundamentalSnapshot))
f_mc = ri.fields["market_cap"]
check("MCap 0 -> None + note", f_mc.value is None and f_mc.note is not None and "<= 0" in f_mc.note, str(f_mc.to_dict()))
# RIMO tidak punya ROE (F3.1) -> jangan jadi 0
f_roe = ri.fields["roe"]
if f_roe.availability_status == "unknown":
    check("ROE UNKNOWN = None (bukan 0)", f_roe.value is None and f_roe.available_at is None)
else:
    check("ROE unknown/assumed konsisten", f_roe.availability_status in ("unknown", "assumed"), str(f_roe.to_dict()))
# SEMUA field harus memiliki availability_status yang valid
for fname, f in ri.fields.items():
    check(f"{fname} punya availability_status valid", f.availability_status in ("observed", "assumed", "unknown", "quote"))


# --- 5) konsistensi cross-field: UNKNOWN-safe di semua snapshot ---
section("Konsistensi metadata")
for snap, tag in ((ak, "AKRA"), (be, "BEBS"), (ri, "RIMO")):
    for fname, f in snap.fields.items():
        ok_status = f.availability_status in ("observed", "assumed", "unknown", "quote")
        check(f"{tag}.{fname} status valid", ok_status, str(f.availability_status))
        if f.availability_status == "unknown":
            check(f"{tag}.{fname} unknown-safe (value=None)", f.value is None)
            check(f"{tag}.{fname} unknown-safe (available_at=None)", f.available_at is None)
    for fname in SNAPSHOT_FIELDS_REF:
        f = snap.fields[fname]
        check(f"{tag}.{fname} snapshot_only", f.snapshot_only)
        check(f"{tag}.{fname} historical_pit_available=False", not f.historical_pit_available)
        check(f"{tag}.{fname} pit_safe=False", not f.pit_safe)
        check(f"{tag}.{fname} is_observed=True (quote diamati)", f.is_observed)


# --- 6) tidak menyentuh scoring/signal/API ---
section("Isolasi dari scoring/signal/API")
import risk  # noqa: F401 — import harus tetap jalan (tidak ada perubahan)
import api  # noqa: F401
check("risk.py & api.py masih importable", True)
from config import RECOVERY_SIGNAL_P_MIN  # noqa: F401
check("recovery signal threshold tidak berubah", RECOVERY_SIGNAL_P_MIN == 0.68)


print(f"\n{'=' * 60}")
print(f"  HASIL: {PASS} PASS / {FAIL} FAIL")
print(f"{'=' * 60}")
raise SystemExit(1 if FAIL else 0)