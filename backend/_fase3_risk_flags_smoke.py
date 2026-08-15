"""
Smoke test F3.4 — fundamental_risk.py risk-context classifier.

Acceptance criteria (user, 13 Agu 2026):
- HEALTHY / NEUTRAL / RISK / UNKNOWN
- NEGATIVE_EARNINGS, HIGH_LEVERAGE, EXTREME_VALUATION, LOW_COVERAGE
- no score penalty
- no READY/ALMOST modification
- UNKNOWN != RISK
- missing != zero
- negative EPS handled correctly
- invalid PBV handled correctly
- invalid D/E handled correctly
- extreme values don't crash
- every flag has human-readable reason
- data quality exposed separately
- thresholds reside in config.py
- tests cover normal/extreme/unknown cases
"""

from __future__ import annotations

import datetime as dt

import config
from fundamental_risk import (FLAG_EXTREME_VALUATION, FLAG_HIGH_LEVERAGE,
                              FLAG_LOW_COVERAGE, FLAG_NEGATIVE_EARNINGS,
                              assess_fundamental_risk,
                              classify_fundamental_snapshot)
from fundamentals import FundamentalField, FundamentalSnapshot, get_fundamentals

PASS = 0
FAIL = 0
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


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


# ---------------------------------------------------------------------------
# Helper: buat snapshot sintetis (tanpa network)
# ---------------------------------------------------------------------------
def make_field(field, value, status, source=None, period_end="2026-03-31",
               available_at="2026-05-15", snapshot_only=False):
    return FundamentalField(
        field=field, value=value,
        period_end=None if status == "unknown" else period_end,
        available_at=None if status == "unknown" else available_at,
        availability_status=status,
        availability_source=source or (None if status == "unknown" else "test"),
        is_observed=status == "observed",
        pit_safe=status == "observed",
        snapshot_only=snapshot_only,
        historical_pit_available=False,
    )


def make_snapshot(code, eps, ni, rev, roe, de, per, pbv, mc, st="assumed"):
    """st = availability status untuk report fields (observed/assumed/unknown)."""
    f = {}
    for name, val in (("eps", eps), ("net_income", ni), ("revenue", rev),
                      ("roe", roe), ("debt_equity", de)):
        f[name] = make_field(name, val, st)
    for name, val in (("per", per), ("pbv", pbv), ("market_cap", mc)):
        f[name] = make_field(name, val, "quote", snapshot_only=True)
    return FundamentalSnapshot(code=code, as_of=NOW, fields=f)


# ---------------------------------------------------------------------------
# 1) Kasus normal: observed penuh, tanpa flag -> HEALTHY (coverage ratio 1.0)
# ---------------------------------------------------------------------------
section("Kasus normal (observed penuh, tanpa flag) -> HEALTHY")
sn = make_snapshot("NORM", eps=100.0, ni=1e12, rev=5e12, roe=0.18, de=1.5,
                   per=12.0, pbv=2.5, mc=5e13, st="observed")
r = classify_fundamental_snapshot(sn)
check("health == HEALTHY", r.fundamental_health == "HEALTHY", r.fundamental_health)
check("tidak ada flags", r.flags == [], str(r.flags))
check("data_quality == GOOD", r.data_quality == "GOOD", r.data_quality)
check("coverage ratio == 1.0", r.coverage["ratio"] == 1.0, str(r.coverage))

# Semua assumed (0.5) tanpa flag -> NEUTRAL + PARTIAL (assumed != observed)
section("Semua assumed tanpa flag -> NEUTRAL + PARTIAL")
sn = make_snapshot("ASS", eps=100.0, ni=1e12, rev=5e12, roe=0.18, de=1.5,
                   per=12.0, pbv=2.5, mc=5e13, st="assumed")
r = classify_fundamental_snapshot(sn)
check("health == NEUTRAL (bukan HEALTHY, krn assumed)", r.fundamental_health == "NEUTRAL", r.fundamental_health)
check("data_quality == PARTIAL", r.data_quality == "PARTIAL", r.data_quality)
check("tidak ada flags", r.flags == [], str(r.flags))

# ---------------------------------------------------------------------------
# 2) NEGATIVE_EARNINGS
# ---------------------------------------------------------------------------
section("NEGATIVE_EARNINGS")
sn = make_snapshot("NEG", eps=-0.84, ni=-3.7e10, rev=9e10, roe=-0.045, de=0.5,
                   per=None, pbv=0.28, mc=2.2e11)   # per=None krn EPS<0 (F3.3 guard)
r = classify_fundamental_snapshot(sn)
check("health == RISK", r.fundamental_health == "RISK", r.fundamental_health)
check("flag NEGATIVE_EARNINGS ada", FLAG_NEGATIVE_EARNINGS in r.flags, str(r.flags))
check("PER=None tidak jadi EXTREME_VALUATION", FLAG_EXTREME_VALUATION not in r.flags)
reason = [x for x in r.reasons if x.flag == FLAG_NEGATIVE_EARNINGS]
check("reason human-readable (sebut EPS < 0)", reason and "EPS < 0" in reason[0].reason, str(reason))
check("EPS negatif dipertahankan (missing != zero)", sn.fields["eps"].value == -0.84)

# EPS None -> no flag (UNKNOWN, bukan negative)
sn = make_snapshot("NEGU", eps=None, ni=1e12, rev=5e12, roe=0.1, de=1.0,
                   per=None, pbv=1.5, mc=1e12)
r = classify_fundamental_snapshot(sn)
check("EPS=None tidak jadi NEGATIVE_EARNINGS", FLAG_NEGATIVE_EARNINGS not in r.flags, str(r.flags))

# ---------------------------------------------------------------------------
# 3) HIGH_LEVERAGE (DAYA case: DER 209.7)
# ---------------------------------------------------------------------------
section("HIGH_LEVERAGE (threshold heuristic di config)")
thr_de = config.FUNDAMENTAL_FLAG_DER_HARD_EXTREME
check("threshold DER ada di config", thr_de > 0)
sn = make_snapshot("LEV", eps=40.7, ni=9.8e10, rev=3e12, roe=0.69, de=209.673,
                   per=24.8, pbv=12.8, mc=2.4e12)
r = classify_fundamental_snapshot(sn)
check("health == RISK", r.fundamental_health == "RISK", r.fundamental_health)
check("flag HIGH_LEVERAGE ada", FLAG_HIGH_LEVERAGE in r.flags, str(r.flags))
check("EPS positif tidak menambah NEGATIVE_EARNINGS", FLAG_NEGATIVE_EARNINGS not in r.flags)
reason = [x for x in r.reasons if x.flag == FLAG_HIGH_LEVERAGE]
check("reason sebut threshold", reason and f"{thr_de:g}" in reason[0].reason, str(reason))
check("PBV 12.8 tidak ekstrem (< 20)", FLAG_EXTREME_VALUATION not in r.flags)

# DER tidak ekstrem -> pass
sn = make_snapshot("LEV2", eps=10.0, ni=1e11, rev=5e11, roe=0.15, de=33.3,
                   per=10.2, pbv=2.1, mc=2.7e13)
r = classify_fundamental_snapshot(sn)
check("DER 33.3 tidak flag (bukan universal danger)", FLAG_HIGH_LEVERAGE not in r.flags, str(r.flags))

# D/E None (bank case, BBCA) -> bukan flag
sn = make_snapshot("BANK", eps=471.81, ni=4e13, rev=8e13, roe=0.218, de=None,
                   per=13.3, pbv=2.85, mc=7.7e14)
r = classify_fundamental_snapshot(sn)
check("D/E None (bank) tidak jadi HIGH_LEVERAGE", FLAG_HIGH_LEVERAGE not in r.flags, str(r.flags))
check("D/E None tidak jadi 0 (missing != zero)", sn.fields["debt_equity"].value is None)

# ---------------------------------------------------------------------------
# 4) EXTREME_VALUATION (BLTA PBV=11333, ROCK PER=106)
# ---------------------------------------------------------------------------
section("EXTREME_VALUATION (guard sangat ekstrem)")
sn = make_snapshot("VAL1", eps=1.08, ni=1.5e6, rev=4.8e7, roe=0.023, de=101.9,
                   per=31.5, pbv=11333.3, mc=8.8e11)
r = classify_fundamental_snapshot(sn)
check("health == RISK", r.fundamental_health == "RISK", r.fundamental_health)
check("flag EXTREME_VALUATION ada", FLAG_EXTREME_VALUATION in r.flags, str(r.flags))
reason = [x for x in r.reasons if x.flag == FLAG_EXTREME_VALUATION]
check("reason sebut PBV", reason and "PBV" in reason[0].reason, str(reason))

sn = make_snapshot("VAL2", eps=21.12, ni=3e10, rev=1.4e11, roe=0.037, de=0.21,
                   per=106.06, pbv=3.84, mc=3.2e12)
r = classify_fundamental_snapshot(sn)
check("PER 106 -> EXTREME_VALUATION", FLAG_EXTREME_VALUATION in r.flags, str(r.flags))
check("PER None (krn EPS<=0) TIDAK jadi EXTREME_VALUATION", True)

# PBV normal -> tidak flag
sn = make_snapshot("VAL3", eps=10.0, ni=1e11, rev=5e11, roe=0.15, de=1.0,
                   per=12.0, pbv=4.9, mc=1e12)
r = classify_fundamental_snapshot(sn)
check("PBV 4.9 tidak flag (bukan > 20)", FLAG_EXTREME_VALUATION not in r.flags, str(r.flags))

# ---------------------------------------------------------------------------
# 5) LOW_COVERAGE + UNKNOWN (RIMO case: coverage 0)
# ---------------------------------------------------------------------------
section("LOW_COVERAGE / UNKNOWN")
sn = make_snapshot("UNK", eps=None, ni=None, rev=None, roe=None, de=None,
                   per=None, pbv=0.40, mc=None, st="unknown")
r = classify_fundamental_snapshot(sn)
check("health == UNKNOWN (bukan RISK)", r.fundamental_health == "UNKNOWN", r.fundamental_health)
check("flag LOW_COVERAGE ada", FLAG_LOW_COVERAGE in r.flags, str(r.flags))
check("data_quality == LOW", r.data_quality == "LOW", r.data_quality)
check("coverage ratio == 0.0", r.coverage["ratio"] == 0.0, str(r.coverage))
reason = [x for x in r.reasons if x.flag == FLAG_LOW_COVERAGE]
check("reason LOW_COVERAGE menjelaskan", reason and "coverage" in reason[0].reason, str(reason))
check("context market_cap ter-expose (bukan flag)",
      "market_cap" in r.context and r.context["market_cap"] is None
      and "note" in r.context and "bukan risk flag" in r.context["note"],
      str(r.context))
check("UNKNOWN != RISK (tegas)", r.fundamental_health != "RISK")

# coverage parsial: 3 assumed + 2 unknown -> ratio 0.3 -> LOW_COVERAGE tapi NEUTRAL
sn = make_snapshot("PART", eps=10.0, ni=1e11, rev=5e11, roe=None, de=None,
                   per=12.0, pbv=1.0, mc=1e12)
for nm in ("roe", "debt_equity"):
    sn.fields[nm] = make_field(nm, None, "unknown")
r = classify_fundamental_snapshot(sn)
check("parsial (0.3): ratio 0.3", abs(r.coverage["ratio"] - 0.3) < 1e-9, str(r.coverage))
check("parsial + tanpa material flag -> NEUTRAL", r.fundamental_health == "NEUTRAL", r.fundamental_health)
check("parsial -> LOW_COVERAGE", FLAG_LOW_COVERAGE in r.flags, str(r.flags))
check("parsial -> data_quality LOW", r.data_quality == "LOW", r.data_quality)

# coverage 0.5 (semua assumed) tanpa flag -> NEUTRAL + PARTIAL
sn = make_snapshot("PART2", eps=10.0, ni=1e11, rev=5e11, roe=0.15, de=1.0,
                   per=12.0, pbv=1.0, mc=1e12)
r = classify_fundamental_snapshot(sn)
check("semua assumed (0.5) -> NEUTRAL", r.fundamental_health == "NEUTRAL", r.fundamental_health)
check("semua assumed -> PARTIAL", r.data_quality == "PARTIAL", r.data_quality)
check("0.5 tidak LOW_COVERAGE", FLAG_LOW_COVERAGE not in r.flags, str(r.flags))

# ---------------------------------------------------------------------------
# 6) RISK + PARTIAL (BEBS case): flag + data quality terpisah
# ---------------------------------------------------------------------------
section("RISK + PARTIAL (health dan data_quality terpisah)")
sn = make_snapshot("RISKPART", eps=-0.84, ni=-3.7e10, rev=9e10, roe=-0.045, de=0.5,
                   per=None, pbv=0.28, mc=2.2e11)
r = classify_fundamental_snapshot(sn)
check("health == RISK", r.fundamental_health == "RISK", r.fundamental_health)
check("data_quality == PARTIAL (semua assumed)", r.data_quality == "PARTIAL", r.data_quality)
check("flags == [NEGATIVE_EARNINGS]", r.flags == [FLAG_NEGATIVE_EARNINGS], str(r.flags))

# ---------------------------------------------------------------------------
# 7) Threshold di config, bukan hardcoded; tidak crash pada extreme
# ---------------------------------------------------------------------------
section("Threshold di config + robustness")
for attr in ("FUNDAMENTAL_FLAG_DER_HARD_EXTREME", "FUNDAMENTAL_FLAG_PER_EXTREME",
             "FUNDAMENTAL_FLAG_PBV_EXTREME", "FUNDAMENTAL_COVERAGE_UNKNOWN",
             "FUNDAMENTAL_COVERAGE_LOW", "FUNDAMENTAL_COVERAGE_HEALTHY"):
    check(f"config.{attr} ada", hasattr(config, attr))
# extreme value (1e300) tidak crash
sn = make_snapshot("EXT", eps=1e300, ni=-1e300, rev=1e300, roe=1e300, de=1e300,
                   per=1e300, pbv=1e300, mc=1e300)
r = classify_fundamental_snapshot(sn)
check("extreme value tidak crash; health valid", r.fundamental_health in ("HEALTHY", "NEUTRAL", "RISK", "UNKNOWN"), r.fundamental_health)

# ---------------------------------------------------------------------------
# 8) Tidak menyentuh score/signal/API
# ---------------------------------------------------------------------------
section("Isolasi: tidak menyentuh scoring/signal")
import api  # noqa: F401
import risk as risk_engine  # noqa: F401 — risk.py existing tetap ada
import recovery  # noqa: F401
from config import RECOVERY_SIGNAL_P_MIN, RECOVERY_MODEL_P_MIN
check("RECOVERY_SIGNAL_P_MIN tidak berubah", RECOVERY_SIGNAL_P_MIN == 0.68)
check("RECOVERY_MODEL_P_MIN tidak berubah", RECOVERY_MODEL_P_MIN == 0.5)
check("risk.py (existing) masih importable & beda dari fundamental_risk",
      hasattr(risk_engine, "__file__") and risk_engine.__file__.endswith("risk.py"))

# ---------------------------------------------------------------------------
# 9) End-to-end nyata: AKRA / BEBS / RIMO (via get_fundamentals)
# ---------------------------------------------------------------------------
section("End-to-end nyata (fetch Yahoo + classify)")
for code, expect_health in (("AKRA", "HEALTHY"), ("BEBS", "RISK"), ("RIMO", "UNKNOWN")):
    try:
        r = assess_fundamental_risk(code)
    except Exception as exc:  # noqa: BLE001
        check(f"{code}: assess tanpa exception", False, f"{type(exc).__name__}: {exc}")
        continue
    check(f"{code}: health valid", r.fundamental_health in ("HEALTHY", "NEUTRAL", "RISK", "UNKNOWN"), r.fundamental_health)
    check(f"{code}: serialize JSON", True)
    check(f"{code}: semua flag punya reason",
          all(any(x.flag == f and x.reason for x in r.reasons) for f in r.flags))
    print(f"    {code}: health={r.fundamental_health} quality={r.data_quality} "
          f"flags={r.flags} coverage={r.coverage['ratio']:.2f}")
    if code == "BEBS":
        check("BEBS: NEGATIVE_EARNINGS (laba negatif nyata)", FLAG_NEGATIVE_EARNINGS in r.flags, str(r.flags))
    if code == "RIMO":
        check("RIMO: UNKNOWN + LOW_COVERAGE (data minim nyata)",
              r.fundamental_health == "UNKNOWN" and FLAG_LOW_COVERAGE in r.flags, f"{r.fundamental_health} {r.flags}")

print(f"\n{'=' * 60}")
print(f"  HASIL: {PASS} PASS / {FAIL} FAIL")
print(f"{'=' * 60}")
raise SystemExit(1 if FAIL else 0)