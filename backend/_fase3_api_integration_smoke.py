"""
Smoke test F3.5 — integrasi fundamental risk context ke api.analyze_stock.

Acceptance criteria (user, 13 Agu 2026 — auto DONE + REPORT):
- fundamental_status + fundamental_flags TERPISAH dari skor (field baru top-level)
- TANPA penalty / perubahan swing_score, recommendation, confidence, risk_level
- fetch fundamental gagal TIDAK boleh membuat endpoint rusak (status UNKNOWN)
- fundamental_flags berisi {flag, reason} human-readable
- fundamental_meta meng-expose data_quality/coverage/context/fetch_errors
"""

from __future__ import annotations

from api import analyze_stock, InsufficientDataError

PASS = 0
FAIL = 0


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


SCORE_KEYS = {"valid", "swing_score", "components", "recommendation",
              "confidence", "risk_level", "prob_continuation",
              "prob_reversal", "regime"}


def run(code: str, expect_status: str | None, expect_flags: list[str] | None):
    section(f"analyze_stock({code})")
    try:
        res = analyze_stock(code, capital=100_000_000)
    except InsufficientDataError as exc:
        check(f"{code}: data harga tidak cukup (skip)", True, str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        check(f"{code}: analyze tanpa exception", False, f"{type(exc).__name__}: {exc}")
        return None

    check(f"{code}: field fundamental_status ada", "fundamental_status" in res, str(res.keys()))
    check(f"{code}: field fundamental_flags ada", "fundamental_flags" in res)
    check(f"{code}: field fundamental_meta ada", "fundamental_meta" in res)
    # valid=False BISA terjadi (perilaku existing scoring.py utk data tipis/NaN,
    # contoh BEBS) — yang diverifikasi: struktur score TIDAK berubah oleh F3.5.
    check(f"{code}: score tetap ada dgn kunci original (tidak berubah)",
          set(res["score"].keys()) == SCORE_KEYS, str(res["score"].keys()))
    check(f"{code}: score TIDAK mengandung kunci fundamental (terpisah)",
          not any(k.startswith("fundamental") for k in res["score"].keys()),
          str(res["score"].keys()))
    check(f"{code}: swing_score None ATAU numeric (nilai asli scoring, bukan penalty)",
          res["score"].get("swing_score") is None or isinstance(res["score"].get("swing_score"), (int, float)))
    check(f"{code}: fundamental_status bukan None", res["fundamental_status"] is not None)

    if expect_status is not None:
        check(f"{code}: fundamental_status == {expect_status}",
              res["fundamental_status"] == expect_status, res["fundamental_status"])
    if expect_flags is not None:
        got = {f["flag"] for f in res["fundamental_flags"]}
        check(f"{code}: flags mengandung {expect_flags}", set(expect_flags) <= got, str(got))
        check(f"{code}: semua flag punya reason non-kosong",
              all(f.get("reason") for f in res["fundamental_flags"]))
    check(f"{code}: fundamental_meta meng-expose data_quality",
          "data_quality" in res["fundamental_meta"], str(res["fundamental_meta"].keys()))
    check(f"{code}: fundamental_meta meng-expose coverage",
          "coverage" in res["fundamental_meta"])
    check(f"{code}: fundamental_meta meng-expose context (market_cap bukan flag)",
          isinstance(res["fundamental_meta"].get("context"), dict))
    return res


print("F3.5 — integrasi fundamental risk ke api.analyze_stock")
print("(fetch nyata: AKRA/BEBS, bisa butuh ~5-15 detik per kode)")

r_akra = run("AKRA", expect_status="HEALTHY", expect_flags=[])
if r_akra:
    check("AKRA: fundamental_flags kosong", r_akra["fundamental_flags"] == [])
    check("AKRA: data_quality == GOOD", r_akra["fundamental_meta"]["data_quality"] == "GOOD",
          str(r_akra["fundamental_meta"]["data_quality"]))
    check("AKRA: recommendation tetap HOLD/BUY/SELL normal",
          r_akra["score"]["recommendation"] in ("HOLD", "BUY", "SELL"),
          str(r_akra["score"]["recommendation"]))

r_bebs = run("BEBS", expect_status="RISK", expect_flags=["NEGATIVE_EARNINGS"])

# RIMO: data harga mungkin tidak cukup (delisted) -> skip dianggap OK
run("RIMO", expect_status=None, expect_flags=None)

print(f"\n{'=' * 60}")
print(f"  HASIL: {PASS} PASS / {FAIL} FAIL")
print(f"{'=' * 60}")
raise SystemExit(1 if FAIL else 0)