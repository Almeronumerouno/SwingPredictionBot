"""Smoke test Fase 4 — 3 endpoint + error paths."""

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def section(label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")


section("GET /gainers")
r = client.get("/gainers")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"  scraped_at: {d['scraped_at']}")
    print(f"  date: {d['date']}")
    print(f"  count: {d['count']}")
    if d["data"]:
        keys = list(d["data"][0].keys())
        print(f"  field keys: {keys}")
        expected = ["code", "name", "close", "pct_change", "volume", "value", "frequency", "foreign_buy", "foreign_sell"]
        print(f"  field lengkap: {all(k in keys for k in expected)}")
    else:
        print("  [WARN] data kosong (belum scan hari ini)")
else:
    print(f"  {r.json()}")
    sc = r.status_code
    print(f"  error handling: {'OK' if sc in (404, 422) else 'UNEXPECTED'}")


section("GET /history/BBCA?length=100")
r = client.get("/history/BBCA", params={"length": 100})
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"  kode: {d['kode']}")
    print(f"  jumlah bar: {len(d['bars'])}")
    if d["bars"]:
        keys = list(d["bars"][0].keys())
        print(f"  field keys: {keys}")
        no_prev = "previous" not in keys
        no_pct = "pct_change" not in keys
        print(f"  previous ter-exclude: {no_prev}")
        print(f"  pct_change ter-exclude: {no_pct}")
        print(f"  bar terakhir: {d['bars'][-1]}")
else:
    print(f"  {r.json()}")
    print(f"  error handling: {'OK' if r.status_code in (404, 502) else 'UNEXPECTED'}")


section("GET /analisis/BBCA (full flow)")
r = client.get("/analisis/BBCA")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    s = d["score"]
    print(f"  valid: {s['valid']}")
    print(f"  swing_score: {s['swing_score']}")
    print(f"  recommendation: {s['recommendation']}")
    print(f"  confidence: {s['confidence']}")
    print(f"  risk_level: {s['risk_level']}")
    tp = d["trade_plan"]
    print(f"  trade_plan: {tp}")
    if tp:
        print(f"    SL={tp['stop_loss']}, TP={tp['take_profit']}, lots={tp['lots']}, shares={tp['shares']}, R:R={tp['risk_reward_ratio']}")
    print(f"  capital_used: {d['capital_used']}")
    print(f"  last_updated: {d['last_updated']}")
else:
    print(f"  {r.json()}")
    guard_active = 'kurang dari' in str(r.json())
    print(f"  guard: {'ACTIVE (data < 150)' if guard_active else 'OTHER ERROR'}")


# fallback ke saham lain kalau BBCA gagal (Yahoo data < 150)
if r.status_code != 200:
    section("GET /analisis/ASII (fallback)")
    r2 = client.get("/analisis/ASII")
    print(f"Status: {r2.status_code}")
    if r2.status_code == 200:
        d2 = r2.json()
        s2 = d2["score"]
        print(f"  valid: {s2['valid']}")
        print(f"  swing_score: {s2['swing_score']}")
        print(f"  recommendation: {s2['recommendation']}")
        print(f"  confidence: {s2['confidence']}")
        print(f"  risk_level: {s2['risk_level']}")
        tp2 = d2["trade_plan"]
        print(f"  trade_plan: {tp2}")
        if tp2:
            print(f"    SL={tp2['stop_loss']}, TP={tp2['take_profit']}, lots={tp2['lots']}, shares={tp2['shares']}, R:R={tp2['risk_reward_ratio']}")
        print(f"  capital_used: {d2['capital_used']}")
    else:
        print(f"  {r2.json()}")
        # fallback lebih lanjut dengan saham bandar
        section("GET /analisis/TLKM (fallback 2)")
        r3 = client.get("/analisis/TLKM")
        print(f"Status: {r3.status_code}")
        if r3.status_code == 200:
            d3 = r3.json()
            s3 = d3["score"]
            print(f"  valid: {s3['valid']}")
            print(f"  swing_score: {s3['swing_score']}")
            print(f"  recommendation: {s3['recommendation']}")
            print(f"  confidence: {s3['confidence']}")
            print(f"  risk_level: {s3['risk_level']}")
            tp3 = d3["trade_plan"]
            print(f"  trade_plan: {tp3}")
            if tp3:
                print(f"    SL={tp3['stop_loss']}, TP={tp3['take_profit']}, lots={tp3['lots']}, shares={tp3['shares']}, R:R={tp3['risk_reward_ratio']}")
        else:
            print(f"  {r3.json()}")


section("Error path: kode gak eksis")
r = client.get("/analisis/XXXX")
print(f"/analisis/XXXX -> {r.status_code}")
print(f"  {r.json()}")
print(f"  -> {'PASS (404)' if r.status_code == 404 else 'FAIL'}")


section("Error path: capital=0")
r = client.get("/analisis/BBCA", params={"capital": 0})
print(f"/analisis/BBCA?capital=0 -> {r.status_code}")
print(f"  {r.json()}")
print(f"  -> {'PASS (422)' if r.status_code == 422 else 'FAIL'}")


section("Error path: history kode gak eksis")
r = client.get("/history/XXXX")
print(f"/history/XXXX -> {r.status_code}")
print(f"  {r.json()}")
print(f"  -> {'PASS (404)' if r.status_code == 404 else 'FAIL'}")


section("Error path: length=9999")
r = client.get("/history/BBCA", params={"length": 9999})
print(f"/history/BBCA?length=9999 -> {r.status_code}")
print(f"  {r.json()}")
print(f"  -> {'PASS (422)' if r.status_code == 422 else 'FAIL'}")


section("Error path: gainers date format salah")
r = client.get("/gainers", params={"date": "not-a-date"})
print(f"/gainers?date=not-a-date -> {r.status_code}")
print(f"  {r.json()}")
print(f"  -> {'PASS (422)' if r.status_code == 422 else 'FAIL'}")


print("\n[DONE] Smoke test selesai.")
