"""P8 backtest resmi: BEFORE vs AFTER gate anti-repetisi (RTF_MAX_STREAK_DAYS).

Sumber: data/phase8_rtf_forensic.jsonl (456 sinyal RTF mentah 1-Jul s/d 14-Agu-2026,
label b10 high-based 10 hari — definisi sama dgn _baseline_compare.py).
AFTER = filter streak <= RTF_MAX_STREAK_DAYS (3) — sinyal hari ke-4+ berturut-turut
di-invalidasi. Filter TIDAK menambah sinyal, jadi TIDAK ada transisi TIDAK->HIT;
semua perubahan = penghapusan.

Output: tabel per tanggal + ringkasan + data/phase8_rtf_before_after.json
"""
import json
import sys
from collections import OrderedDict

sys.path.insert(0, ".")
import config

MAX_STREAK = config.RTF_MAX_STREAK_DAYS

rows = [json.loads(l) for l in open("data/phase8_rtf_forensic.jsonl", encoding="utf-8")]
rows.sort(key=lambda r: (r["date"], r["code"]))

def hit(r):
    return bool(r["hit"])

# ---- klasifikasi perubahan ----
kept_hit = [r for r in rows if r["streak"] <= MAX_STREAK and hit(r)]
removed = [r for r in rows if r["streak"] > MAX_STREAK]
removed_hit = [r for r in removed if hit(r)]
removed_miss = [r for r in removed if not hit(r)]

codes_kept_hit = {r["code"] for r in kept_hit}
codes_removed_hit = {r["code"] for r in removed_hit}
lost_all = sorted(codes_removed_hit - codes_kept_hit)

# ---- tabel per tanggal ----
dates = OrderedDict()
for r in rows:
    d = r["date"]
    x = dates.setdefault(d, {"before_n": 0, "before_h": 0, "after_n": 0, "after_h": 0})
    x["before_n"] += 1
    x["before_h"] += int(hit(r))
    if r["streak"] <= MAX_STREAK:
        x["after_n"] += 1
        x["after_h"] += int(hit(r))

print(f"GATE: streak <= {MAX_STREAK}  (sumber: forensic.jsonl, 1 Jul - 14 Agu 2026, label b10)")
print(f"{'tanggal':<12}{'sebelum':>14}{'sesudah':>14}")
print(f"{'':<12}{'n/hit':>14}{'n/hit':>14}")
tot_b = [0, 0]
tot_a = [0, 0]
for d, x in dates.items():
    tot_b[0] += x["before_n"]; tot_b[1] += x["before_h"]
    tot_a[0] += x["after_n"];  tot_a[1] += x["after_h"]
    print(f"{d:<12}{x['before_n']:>3}/{x['before_h']:>3}{x['after_n']:>8}/{x['after_h']:>3}")
print("-" * 40)
print(f"{'TOTAL':<12}{tot_b[0]:>3}/{tot_b[1]:>3}{tot_a[0]:>8}/{tot_a[1]:>3}")
print(f"  winrate : {tot_b[1]/tot_b[0]*100:.1f}% -> {tot_a[1]/tot_a[0]*100:.1f}%  ({(tot_a[1]/tot_a[0]-tot_b[1]/tot_b[0])*100:+.1f}pp)")
jul_b = sum(1 for r in rows if r["date"] < "2026-08-01" and hit(r)); jul_n = sum(1 for r in rows if r["date"] < "2026-08-01")
jul_ab = sum(1 for r in rows if r["date"] < "2026-08-01" and r["streak"] <= MAX_STREAK and hit(r)); jul_an = sum(1 for r in rows if r["date"] < "2026-08-01" and r["streak"] <= MAX_STREAK)
agu_b = sum(1 for r in rows if r["date"] >= "2026-08-01" and hit(r)); agu_n = sum(1 for r in rows if r["date"] >= "2026-08-01")
agu_ab = sum(1 for r in rows if r["date"] >= "2026-08-01" and r["streak"] <= MAX_STREAK and hit(r)); agu_an = sum(1 for r in rows if r["date"] >= "2026-08-01" and r["streak"] <= MAX_STREAK)
print(f"  Juli   : {jul_n}->{jul_an} sinyal, {jul_b/jul_n*100:.1f}% -> {jul_ab/jul_an*100:.1f}% ({(jul_ab/jul_an-jul_b/jul_n)*100:+.1f}pp)")
print(f"  Agustus: {agu_n}->{agu_an} sinyal, {agu_b/agu_n*100:.1f}% -> {agu_ab/agu_an*100:.1f}% ({(agu_ab/agu_an-agu_b/agu_n)*100:+.1f}pp)")

# ---- perubahan sinyal ----
print()
print("=== PERUBAHAN SINYAL (AFTER) ===")
print(f"HIT dipertahankan : {len(kept_hit)}/{tot_b[1]} ({len(kept_hit)/tot_b[1]*100:.0f}%)")
print(f"HIT -> dibuang    : {len(removed_hit)}  ({len(removed_hit)/tot_b[1]*100:.0f}% dari HIT; {len(removed_hit)}/{len(removed)} = {len(removed_hit)/len(removed)*100:.0f}% dari yang dibuang)")
print(f"TIDAK -> dibuang  : {len(removed_miss)}  (false positive berkurang)")
print(f"TIDAK -> HIT      : 0 (filter hanya menyaring, tidak menambah sinyal)")
print(f"saham unik HIT total: {len(codes_kept_hit | codes_removed_hit)}; kehilangan SEMUA HIT: {len(lost_all)} -> {lost_all}")
print()
print("HIT yang dibuang (streak>3), timing days_to_hit:")
dth = sorted(r["days_to_hit"] for r in removed_hit)
b3 = sum(1 for x in dth if x <= 3); b6 = sum(1 for x in dth if 4 <= x <= 6); b9 = sum(1 for x in dth if x >= 7)
print(f"  <=3: {b3} | 4-6: {b6} | >=7: {b9}  (n={len(dth)})")
for r in sorted(removed_hit, key=lambda x: (x["code"], x["date"])):
    print(f"  {r['code']} {r['date']} streak={r['streak']} days_to_hit={r['days_to_hit']} max_gap={r['max_gap_pct']:.1f}%")

out = {
    "gate": {"name": "RTF_MAX_STREAK_DAYS", "value": MAX_STREAK, "desc": "sinyal hari ke-(max+1)+ berturut-turut di-invalidasi"},
    "dataset": "1 Jul - 14 Agu 2026, forensic.jsonl, label b10 (high-based +10% / 10 hari)",
    "before": {"n": tot_b[0], "hit": tot_b[1], "winrate": round(tot_b[1] / tot_b[0] * 100, 1)},
    "after": {"n": tot_a[0], "hit": tot_a[1], "winrate": round(tot_a[1] / tot_a[0] * 100, 1)},
    "delta_pp": round(tot_a[1] / tot_a[0] * 100 - tot_b[1] / tot_b[0] * 100, 1),
    "per_bulan": {
        "juli": {"before": round(jul_b / jul_n * 100, 1), "after": round(jul_ab / jul_an * 100, 1), "n": [jul_n, jul_an]},
        "agustus": {"before": round(agu_b / agu_n * 100, 1), "after": round(agu_ab / agu_an * 100, 1), "n": [agu_n, agu_an]},
    },
    "perubahan": {
        "hit_dipertahankan": len(kept_hit),
        "hit_dibuang": len(removed_hit),
        "miss_dibuang": len(removed_miss),
        "tidakhit_ke_hit": 0,
        "saham_kehilangan_semua_hit": lost_all,
    },
    "catatan": "n kecil (456 sinyal / 2 bulan); bootstrap 5k gain mean +4.31pp, CI95 [-1.17,+9.61], P(gain>0)=94%. "
               "Wajib validasi ulang dataset penuh 800 hari sebelum klaim resmi baru.",
}
with open("data/phase8_rtf_before_after.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print()
print("saved: data/phase8_rtf_before_after.json")