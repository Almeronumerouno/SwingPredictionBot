"""
_p81_rtf_improve.py — Evaluasi kandidat improvement RTF dengan validasi silang.

Prinsip: tiap kandidat = gate/filter sederhana berprinsip (bukan grid-search
optimalisasi). Stabilitas diuji: fit di Juli -> tes di Agustus, dan sebaliknya.
Metrik: precision (hit rate), coverage, HIT lama dipertahankan, HIT baru,
TIDAK-HIT yang terbuang.

Kandidat (semua tetap dalam filosofi akumulasi/kompresi -> expansion):
  F1 freshness : window_days <= W  (sinyal basi: akumulasi > W hari tanpa expansion)
  F2 anti-streak: streak <= S       (sinyal ke-S+1 berturut-turut = pengulangan yg lemah)
  F3 density   : density_pct >= D   (kepadatan heavy-day lebih tinggi)
  F4 anti-chase: mkt_ret5 <= M      (market sudah naik 5 hari = sinyal datang telat)
  F5 aktivitas : hi_lo_pct >= H     (range intraday hari sinyal besar = aktivitas nyata)
  F6 cum_vol   : cum_vol_ratio >= C (volume window kumulatif besar relatif pre-event)
"""

from __future__ import annotations

import json
import sys

import numpy as np

JSONL = "data/phase8_rtf_forensic.jsonl"
JUL = "2026-07-01"
AGU = "2026-08-01"


def load() -> list[dict]:
    rows = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def split(rows):
    jul = [r for r in rows if r["date"] < AGU]
    agu = [r for r in rows if r["date"] >= AGU]
    return jul, agu


def gate(r, name, v) -> bool:
    if name == "F1":
        return r["window_days"] is not None and r["window_days"] <= v
    if name == "F2":
        return r["streak"] <= v
    if name == "F3":
        return r["density_pct"] is not None and r["density_pct"] >= v
    if name == "F4":
        return r["mk"][2] is not None and r["mk"][2] <= v
    if name == "F5":
        return r["hi_lo_pct"] is not None and r["hi_lo_pct"] >= v
    if name == "F6":
        return r["cum_vol_ratio"] is not None and r["cum_vol_ratio"] >= v
    raise ValueError(name)


def stats(rows):
    n = len(rows)
    if n == 0:
        return None
    h = sum(1 for r in rows if r["hit"])
    return {"n": n, "hit": h, "hr": h / n}


def main() -> None:
    rows = load()
    jul, agu = split(rows)
    base_j, base_a = stats(jul), stats(agu)
    print(f"BASELINE: Juli n={base_j['n']} hr={base_j['hr'] * 100:.1f}% | "
          f"Agu n={base_a['n']} hr={base_a['hr'] * 100:.1f}% | "
          f"TOTAL n={len(rows)} hr={sum(1 for r in rows if r['hit']) / len(rows) * 100:.1f}%")
    print()

    cands = [
        ("F1", "freshness  window_days<=10", 10),
        ("F1", "freshness  window_days<=8", 8),
        ("F1", "freshness  window_days<=6", 6),
        ("F2", "anti-streak streak<=2", 2),
        ("F2", "anti-streak streak<=1", 1),
        ("F3", "density>=40", 40.0),
        ("F3", "density>=45", 45.0),
        ("F4", "anti-chase mkt_ret5<=+2%", 2.0),
        ("F4", "anti-chase mkt_ret5<=0%", 0.0),
        ("F5", "aktivitas hi_lo>=3%", 3.0),
        ("F5", "aktivitas hi_lo>=4%", 4.0),
        ("F6", "cum_vol_ratio>=6", 6.0),
        ("F6", "cum_vol_ratio>=8", 8.0),
    ]

    print(f"{'kandidat':<34}{'Juli':>16}{'Agustus':>16}{'TOTAL':>16}{'stabil?':>8}")
    print(f"{'':<34}{'n/hr%':>16}{'n/hr%':>16}{'n/hr%':>16}")
    print("-" * 90)
    for name, label, v in cands:
        jf = [r for r in jul if gate(r, name, v)]
        af = [r for r in agu if gate(r, name, v)]
        tf = [r for r in rows if gate(r, name, v)]
        sj, sa, st = stats(jf), stats(af), stats(tf)
        if sj is None or sa is None or st is None:
            sj_s = "0" if sj is None else "%5d/%5.1f%%" % (sj["n"], sj["hr"] * 100)
            sa_s = "0" if sa is None else "%5d/%5.1f%%" % (sa["n"], sa["hr"] * 100)
            st_s = "0" if st is None else "%5d/%5.1f%%" % (st["n"], st["hr"] * 100)
            print(f"{label:<34}{sj_s:>16}{sa_s:>16}{st_s:>16}  -")
            continue
        up_j = sj["hr"] > base_j["hr"]
        up_a = sa["hr"] > base_a["hr"]
        gain = (st["hr"] - sum(1 for r in rows if r["hit"]) / len(rows)) * 100
        print(f"{label:<34}"
              f"{sj['n']:>5d}/{sj['hr'] * 100:>5.1f}%{up_j and ' +' or '  '}"
              f"{sa['n']:>8d}/{sa['hr'] * 100:>5.1f}%{up_a and ' +' or '  '}"
              f"{st['n']:>8d}/{st['hr'] * 100:>5.1f}%{gain:>+6.1f}pp"
              f"{'  YA' if up_j and up_a else '  TIDAK'}")

    # ---- kombinasi berprinsip ----
    print()
    print("KOMBINASI (urutan berprinsip, bukan optimalisasi):")
    combos = [
        ("F1<=10", lambda r: gate(r, "F1", 10)),
        ("F1<=10 & F2<=2", lambda r: gate(r, "F1", 10) and gate(r, "F2", 2)),
        ("F1<=10 & F2<=2 & F3>=40", lambda r: gate(r, "F1", 10) and gate(r, "F2", 2) and gate(r, "F3", 40)),
        ("F1<=10 & F2<=2 & F4<=2", lambda r: gate(r, "F1", 10) and gate(r, "F2", 2) and gate(r, "F4", 2.0)),
        ("F1<=10 & F3>=40", lambda r: gate(r, "F1", 10) and gate(r, "F3", 40)),
        ("F1<=10 & F5>=3", lambda r: gate(r, "F1", 10) and gate(r, "F5", 3.0)),
        ("F1<=10 & F2<=2 & F5>=3", lambda r: gate(r, "F1", 10) and gate(r, "F2", 2) and gate(r, "F5", 3.0)),
    ]
    print(f"{'kombinasi':<30}{'Juli':>16}{'Agustus':>16}{'TOTAL':>16}{'stabil?':>8}")
    print("-" * 90)
    for label, fn in combos:
        jf = [r for r in jul if fn(r)]
        af = [r for r in agu if fn(r)]
        tf = [r for r in rows if fn(r)]
        sj, sa, st = stats(jf), stats(af), stats(tf)
        gain = (st["hr"] - sum(1 for r in rows if r["hit"]) / len(rows)) * 100
        up_j = sj["hr"] > base_j["hr"]
        up_a = sa["hr"] > base_a["hr"]
        print(f"{label:<30}"
              f"{sj['n']:>5d}/{sj['hr'] * 100:>5.1f}%{up_j and ' +' or '  '}"
              f"{sa['n']:>8d}/{sa['hr'] * 100:>5.1f}%{up_a and ' +' or '  '}"
              f"{st['n']:>8d}/{st['hr'] * 100:>5.1f}%{gain:>+6.1f}pp"
              f"{'  YA' if up_j and up_a else '  TIDAK'}")

    # ---- detail kombinasai terpilih: perubahan sinyal ----
    print()
    print("DETAIL per kandidat tunggal (HIT lama dipertahankan / TIDAK-HIT terbuang):")
    for name, label, v in cands:
        tf = [r for r in rows if gate(r, name, v)]
        removed = [r for r in rows if not gate(r, name, v)]
        keep_hit = sum(1 for r in tf if r["hit"])
        drop_miss = sum(1 for r in removed if not r["hit"])
        print(f"  {label:<34} tetap={len(tf):>4} | HIT dipertahankan={keep_hit:>3} "
              f"({keep_hit / 248 * 100:.0f}%) | MISS terbuang={drop_miss:>3} "
              f"({drop_miss / 208 * 100:.0f}%)")

    # ---- analisis kombinasi terbaik: siapa yg berubah ----
    print()
    print("SINYAL YANG BERUBAH (kandidat F1<=10 & F2<=2):")
    fn = lambda r: gate(r, "F1", 10) and gate(r, "F2", 2)
    removed = [r for r in rows if not fn(r)]
    kept_hit = [r for r in rows if fn(r) and r["hit"]]
    removed_hit = [r for r in removed if r["hit"]]
    removed_miss = [r for r in removed if not r["hit"]]
    print(f"  HIT lama yang DIPERTAHANKAN: {len(kept_hit)}")
    print(f"  HIT lama yang TERBUANG (akan jadi false positive): {len(removed_hit)} "
          f"({len(removed_hit) / 248 * 100:.1f}% dari semua HIT)")
    print(f"  TIDAK-HIT yang terbuang (false positive berkurang): {len(removed_miss)}")
    from collections import Counter
    why = Counter()
    for r in removed_hit:
        why[(r["window_days"] > 10, r["streak"] > 2)] += 1
    print(f"  rincian HIT terbuang (window>10, streak>2): {dict(why)}")


if __name__ == "__main__":
    sys.exit(main())