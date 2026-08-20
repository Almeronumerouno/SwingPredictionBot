"""P8: backtest logika RTF SEKARANG (gate anti-repetisi AKTIF, streak <= RTF_MAX_STREAK_DAYS).

Sumber: data/phase8_rtf_forensic_jan_aug.jsonl (1774 sinyal RTF mentah 2-Jan s/d 14-Agu-2026,
label b10 = max high[+1..+10]/close0 >= 10%; semua gate lain — density, heavy, MA20,
likuiditas — sudah terpasang di dalam sinyal mentah, identik dgn deteksi produksi).
Logika sekarang = detect_accumulation(..., apply_streak_gate=True) -> filter streak <= 3.

Output: tabel ringkasan + data/phase8_rtf_backtest_now.json + data/phase8_rtf_backtest_now_hits.csv
"""
import csv
import json
import sys
from collections import OrderedDict

sys.path.insert(0, ".")
import config  # noqa: E402

MAX_STREAK = config.RTF_MAX_STREAK_DAYS
SRC = sys.argv[1] if len(sys.argv) > 1 else "data/phase8_rtf_forensic_jan_aug.jsonl"
OUT_JSON = "data/phase8_rtf_backtest_now.json"
OUT_CSV = "data/phase8_rtf_backtest_now_hits.csv"

rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
rows.sort(key=lambda r: (r["date"], r["code"]))

# logika SEKARANG: gate anti-repetisi -> sinyal streak <= MAX_STREAK
cur = [r for r in rows if r["streak"] <= MAX_STREAK]
# label fair: hanya sinyal dengan jendela 10 hari penuh (horizon >= 10)
fair = [r for r in cur if r["horizon"] >= 10]


def rate(xs):
    n = len(xs)
    return (sum(1 for r in xs if r["hit"]), n, sum(1 for r in xs if r["hit"]) / n * 100 if n else 0.0)


def pct(xs):
    h, n, p = rate(xs)
    return f"{h}/{n} = {p:.1f}%"


# ---- ringkasan ----
print(f"LOGIKA SEKARANG: detect_accumulation(apply_streak_gate=True) -> streak <= {MAX_STREAK}")
print(f"sumber       : {SRC}")
print()
h, n, p = rate(rows)
print(f"MENTAH (tanpa gate)        : {pct(rows)}")
print(f"SEKARANG (streak<={MAX_STREAK}): {pct(cur)}")
print(f"SEKARANG, horizon penuh    : {pct(fair)}  (buang {len(cur)-len(fair)} sinyal <10 hari forward)")
print(f"  HIT dipertahankan: {sum(1 for r in cur if r['hit'])}/{h} ({sum(1 for r in cur if r['hit'])/h*100:.0f}% dari HIT mentah)")
print()

# ---- per bulan (logika sekarang, horizon penuh) ----
print("=== PER BULAN (logika sekarang, horizon penuh) ===")
months = OrderedDict()
for r in fair:
    months.setdefault(r["date"][:7], []).append(r)
print(f"{'bulan':<8}{'n':>5}{'hit':>5}{'rate':>8}")
tot_h = tot_n = 0
for m, xs in months.items():
    hh, nn, pp = rate(xs)
    tot_h += hh; tot_n += nn
    print(f"{m:<8}{nn:>5}{hh:>5}{pp:>7.1f}%")
print(f"{'TOTAL':<8}{tot_n:>5}{tot_h:>5}{tot_h/tot_n*100:>7.1f}%")
print()

# ---- per streak day ----
print("=== WINRATE PER HARI STREAK (mentah; dasar gate anti-repetisi) ===")
by_streak = OrderedDict()
for r in rows:
    by_streak.setdefault(r["streak"], []).append(r)
for s in sorted(by_streak):
    hh, nn, pp = rate(by_streak[s])
    mark = " <- GATE" if s <= MAX_STREAK else " <- di-invalidasi"
    print(f"streak {s:<3}: {hh:>3}/{nn:<4} = {pp:>5.1f}%{mark}")
print()

# ---- daftar sinyal yang HIT (logika sekarang) ----
hits = sorted([r for r in fair if r["hit"]], key=lambda r: (r["date"], r["code"]))
print(f"=== SINYAL HIT (logika sekarang, horizon penuh): {len(hits)} ===")
print(f"{'kode':<7}{'tanggal':<12}{'streak':>7}{'days_to_hit':>12}{'max_gap%':>10}")
for r in hits:
    print(f"{r['code']:<7}{r['date']:<12}{r['streak']:>7}{r['days_to_hit']:>12}{r['max_gap_pct']:>9.1f}%")
print()

# ---- agregat per saham ----
print("=== SAHAM PALING SERING HIT (logika sekarang, horizon penuh) ===")
by_code = OrderedDict()
for r in fair:
    by_code.setdefault(r["code"], []).append(r)
ranked = sorted(by_code.items(), key=lambda kv: (-sum(1 for r in kv[1] if r["hit"]), kv[0]))
print(f"{'kode':<7}{'sinyal':>7}{'hit':>5}{'rate':>8}")
for code, xs in ranked[:20]:
    hh, nn, pp = rate(xs)
    print(f"{code:<7}{nn:>7}{hh:>5}{pp:>7.1f}%")

# ---- simpan ----
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump({
        "logic": f"detect_accumulation(apply_streak_gate=True); RTF_MAX_STREAK_DAYS={MAX_STREAK}",
        "source": SRC,
        "label": "b10: max(high[+1..+10])/close0 >= 10%",
        "raw": {"n": n, "hit": h, "winrate": round(p, 1)},
        "current_all": {"n": len(cur), "hit": sum(1 for r in cur if r["hit"]),
                        "winrate": round(sum(1 for r in cur if r["hit"]) / len(cur) * 100, 1)},
        "current_full_horizon": {"n": tot_n, "hit": tot_h, "winrate": round(tot_h / tot_n * 100, 1),
                                 "excluded_truncated": len(cur) - len(fair)},
        "per_month": {m: {"n": len(xs), "hit": rate(xs)[0], "winrate": round(rate(xs)[2], 1)}
                      for m, xs in months.items()},
        "per_streak_day": {s: {"n": len(xs), "hit": rate(xs)[0], "winrate": round(rate(xs)[2], 1)}
                           for s, xs in by_streak.items()},
        "hit_count": len(hits),
    }, f, indent=2, ensure_ascii=False)

with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["code", "date", "streak", "days_to_hit", "max_gap_pct", "close0", "density_pct", "window_days"])
    for r in hits:
        w.writerow([r["code"], r["date"], r["streak"], r["days_to_hit"],
                    r["max_gap_pct"], r["close0"], r["density_pct"], r["window_days"]])

print()
print(f"saved: {OUT_JSON}")
print(f"saved: {OUT_CSV}")