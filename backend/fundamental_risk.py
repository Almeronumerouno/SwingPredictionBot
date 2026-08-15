"""
F3.4 — fundamental_risk.py: risk-context classifier MURNI (keputusan user, 13 Agu 2026).

"Bodoh tapi jujur": empat flag sebagai risk-CONTEXT classifier, bukan fundamental
score, bukan predictor, BUKAN penalty. Tidak menyentuh score/READY/ALMOST/strength/
recovery_probability/Swing Score apa pun.

Output:
    fundamental_health   HEALTHY | NEUTRAL | RISK | UNKNOWN
    data_quality         GOOD | PARTIAL | LOW   (terpisah dari health!)
    flags                subset dari {NEGATIVE_EARNINGS, HIGH_LEVERAGE,
                                      EXTREME_VALUATION, LOW_COVERAGE}
    reasons              human-readable per flag (interpretability)
    coverage             {observed, assumed, unknown, required, ratio}
    context              market_cap dsb — DITAMPILKAN, bukan flag (anti double-count
                         dengan liquidity engine yang sudah ada)

Aturan (contract user):
1. HEALTHY bukan "fundamentally good stock"; RISK bukan "jangan beli". Hanya
   contextual risk classification dari data yang tersedia sekarang.
2. NEGATIVE_EARNINGS: EPS < 0 OR Net Income < 0. EPS=None -> UNKNOWN (bukan flag).
   PER < 0 BUKAN trigger (F3.3 sudah null-kan PER tak bermakna).
3. HIGH_LEVERAGE: DER > config.FUNDAMENTAL_FLAG_DER_HARD_EXTREME (heuristic guard,
   bukan threshold universal). Threshold di config.py, bukan hardcoded.
4. EXTREME_VALUATION: PER/PBV > threshold SANGAT ekstrem (heuristic). PER=None
   karena EPS<=0 TIDAK boleh jadi EXTREME_VALUATION (itu domain NEGATIVE_EARNINGS).
5. LOW_COVERAGE: coverage_ratio < config.FUNDAMENTAL_COVERAGE_LOW, dengan
   weight observed=1.0, assumed=0.5, unknown=0.0 atas REPORT_FIELDS.
   Ini data-quality dimension, bukan probability.
6. Hierarchy health (hindari HEALTHY jadi default):
       coverage < UNKNOWN threshold -> UNKNOWN
       elif material risk flag ada  -> RISK
       elif coverage >= HEALTHY     -> HEALTHY
       else                         -> NEUTRAL
   unknown data != healthy company; no detected risk != proven healthy.
7. Market Cap TIDAK jadi risk flag (double-count dengan liquidity risk).
8. Tidak ada penalty / perubahan score apa pun.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional

import config
from fundamentals import (REPORT_FIELDS, FundamentalField, FundamentalSnapshot,
                          get_fundamentals)

# ---------------------------------------------------------------------------
# Flag definitions
# ---------------------------------------------------------------------------
FLAG_NEGATIVE_EARNINGS = "NEGATIVE_EARNINGS"
FLAG_HIGH_LEVERAGE = "HIGH_LEVERAGE"
FLAG_EXTREME_VALUATION = "EXTREME_VALUATION"
FLAG_LOW_COVERAGE = "LOW_COVERAGE"

# Material flags memicu RISK; LOW_COVERAGE hanya data-quality dimension
MATERIAL_FLAGS = {FLAG_NEGATIVE_EARNINGS, FLAG_HIGH_LEVERAGE, FLAG_EXTREME_VALUATION}


@dataclass
class RiskFlag:
    flag: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"flag": self.flag, "reason": self.reason}


@dataclass
class FundamentalRiskAssessment:
    code: str
    as_of: str
    fundamental_health: str                     # HEALTHY | NEUTRAL | RISK | UNKNOWN
    data_quality: str                           # GOOD | PARTIAL | LOW
    coverage: dict[str, Any]                    # observed/assumed/unknown/required/ratio
    flags: list[str] = dc_field(default_factory=list)
    reasons: list[RiskFlag] = dc_field(default_factory=list)
    context: dict[str, Any] = dc_field(default_factory=dict)
    fetch_errors: list[str] = dc_field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "as_of": self.as_of,
            "fundamental_health": self.fundamental_health,
            "data_quality": self.data_quality,
            "coverage": self.coverage,
            "flags": self.flags,
            "reasons": [r.to_dict() for r in self.reasons],
            "context": self.context,
            "fetch_errors": self.fetch_errors,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt(v: Optional[float], nd: int = 2) -> str:
    return f"{v:.{nd}f}" if v is not None else "None"


def _coverage_ratio(snapshot: FundamentalSnapshot) -> dict[str, Any]:
    """Weighted coverage atas REPORT_FIELDS: observed=1.0, assumed=0.5, unknown=0.0."""
    required = list(REPORT_FIELDS)
    n_obs = n_assumed = n_unknown = 0
    for f in required:
        fld = snapshot.fields.get(f)
        if fld is None:
            n_unknown += 1
            continue
        st = fld.availability_status
        if st == "observed":
            n_obs += 1
        elif st == "assumed":
            n_assumed += 1
        else:
            n_unknown += 1
    total = len(required)
    ratio = (n_obs + 0.5 * n_assumed) / total if total else 0.0
    return {"observed": n_obs, "assumed": n_assumed, "unknown": n_unknown,
            "required": total, "ratio": round(ratio, 4)}


def _data_quality_label(ratio: float) -> str:
    if ratio >= config.FUNDAMENTAL_COVERAGE_HEALTHY:
        return "GOOD"
    if ratio >= config.FUNDAMENTAL_COVERAGE_LOW:
        return "PARTIAL"
    return "LOW"


# ---------------------------------------------------------------------------
# Per-flag checks
# ---------------------------------------------------------------------------
def _check_negative_earnings(snapshot: FundamentalSnapshot) -> Optional[RiskFlag]:
    eps = snapshot.fields.get("eps")
    ni = snapshot.fields.get("net_income")
    if eps is not None and eps.value is not None and eps.value < 0:
        return RiskFlag(FLAG_NEGATIVE_EARNINGS,
                        f"EPS < 0 (trailing EPS {_fmt(eps.value)})")
    if ni is not None and ni.value is not None and ni.value < 0:
        return RiskFlag(FLAG_NEGATIVE_EARNINGS,
                        f"Net Income < 0 ({_fmt(ni.value, 0)} IDR)")
    return None  # None -> UNKNOWN-safe, bukan flag


def _check_high_leverage(snapshot: FundamentalSnapshot) -> Optional[RiskFlag]:
    de = snapshot.fields.get("debt_equity")
    if de is None or de.value is None:
        return None  # unknown -> bukan flag
    thr = config.FUNDAMENTAL_FLAG_DER_HARD_EXTREME
    if de.value > thr:
        return RiskFlag(FLAG_HIGH_LEVERAGE,
                        f"Debt/Equity {_fmt(de.value)} > threshold {thr:g} "
                        f"(heuristic guard, config.FUNDAMENTAL_FLAG_DER_HARD_EXTREME)")
    return None


def _check_extreme_valuation(snapshot: FundamentalSnapshot) -> Optional[RiskFlag]:
    per = snapshot.fields.get("per")
    pbv = snapshot.fields.get("pbv")
    parts = []
    if per is not None and per.value is not None:
        thr = config.FUNDAMENTAL_FLAG_PER_EXTREME
        if per.value > thr:
            parts.append(f"PER {_fmt(per.value)} > {thr:g}")
    if pbv is not None and pbv.value is not None:
        thr = config.FUNDAMENTAL_FLAG_PBV_EXTREME
        if pbv.value > thr:
            parts.append(f"PBV {_fmt(pbv.value)} > {thr:g}")
    if not parts:
        return None
    return RiskFlag(FLAG_EXTREME_VALUATION,
                    " + ".join(parts) + " (heuristic guard; valuation ekstrem "
                    "bisa = overvaluation ATAU growth pricing ATAU distorsi "
                    "sementara — bukan penentu fair value)")


def _check_low_coverage(coverage: dict[str, Any]) -> Optional[RiskFlag]:
    ratio = coverage["ratio"]
    thr = config.FUNDAMENTAL_COVERAGE_LOW
    if ratio < thr:
        return RiskFlag(
            FLAG_LOW_COVERAGE,
            f"coverage ratio {ratio:.2f} < {thr:.2f} "
            f"(observed={coverage['observed']}, assumed={coverage['assumed']}, "
            f"unknown={coverage['unknown']}, required={coverage['required']}; "
            f"weight observed=1.0, assumed=0.5, unknown=0.0)")
    return None


# ---------------------------------------------------------------------------
# API publik
# ---------------------------------------------------------------------------
def classify_fundamental_snapshot(snapshot: FundamentalSnapshot) -> FundamentalRiskAssessment:
    """Risk-context classification MURNI dari snapshot (tanpa network, tanpa score impact)."""
    coverage = _coverage_ratio(snapshot)
    ratio = coverage["ratio"]

    flags: list[RiskFlag] = []
    flags += [f for f in (
        _check_negative_earnings(snapshot),
        _check_high_leverage(snapshot),
        _check_extreme_valuation(snapshot),
        _check_low_coverage(coverage),
    ) if f is not None]

    material = [f.flag for f in flags if f.flag in MATERIAL_FLAGS]

    # Hierarchy (hindari HEALTHY jadi default):
    if ratio < config.FUNDAMENTAL_COVERAGE_UNKNOWN:
        health = "UNKNOWN"
    elif material:
        health = "RISK"
    elif ratio >= config.FUNDAMENTAL_COVERAGE_HEALTHY:
        health = "HEALTHY"
    else:
        health = "NEUTRAL"

    # Market Cap hanya konteks — BUKAN flag (anti double-count dgn liquidity engine)
    mc = snapshot.fields.get("market_cap")
    context: dict[str, Any] = {
        "market_cap": mc.value if mc else None,
        "market_cap_idr_b": round(mc.value / 1e9, 2) if (mc and mc.value) else None,
        "note": "liquidity/size context only — bukan risk flag F3.4 "
                "(anti double-count dengan liquidity engine)",
    }

    return FundamentalRiskAssessment(
        code=snapshot.code,
        as_of=snapshot.as_of,
        fundamental_health=health,
        data_quality=_data_quality_label(ratio),
        coverage=coverage,
        flags=[f.flag for f in flags],
        reasons=flags,
        context=context,
        fetch_errors=list(snapshot.fetch_errors),
    )


def assess_fundamental_risk(code: str, session=None) -> FundamentalRiskAssessment:
    """Fetch snapshot (F3.3) lalu klasifikasi risiko (F3.4). Tanpa score impact."""
    snapshot = get_fundamentals(code, session=session)
    return classify_fundamental_snapshot(snapshot)