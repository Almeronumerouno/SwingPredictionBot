"""
_p81_rtf_forensic_analyze.py — Analisis forensik: fitur apa yang membedakan HIT vs TIDAK HIT.

Untuk tiap fitur numerik: AUC (Mann-Whitney), hit rate per kuartil, beda mean,
effect size (Cohen's d). Untuk fitur kategorik: hit rate per kategori.
Plus: klasifikasi kegagalan, distribusi days_to_hit, redundansi antar fitur.
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np

JSONL = "data/phase8_rtf_forensic.jsonl"


def load() -> list[dict]:
    rows = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def auc(score: np.ndarray, y: np.ndarray) -> float:
    """AUC = P(score_hit > score_miss), pakai Mann-Whitney via rank."""
    n_h = int(y.sum())
    n_m = len(y) - n_h
    if n_h == 0 or n_m == 0:
        return float("nan")
    r = np.argsort(np.argsort(score, kind="mergesort"), kind="mergesort") + 1.0
    rh = r[y == 1].sum()
    u = rh - n_h * (n_h + 1) / 2.0
    return float(u / (n_h * n_m))


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    s = math.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 + (len(b) - 1) * b.std(ddof=1) ** 2)
                  / (len(a) + len(b) - 2))
    if s == 0:
        return float("nan")
    return float((a.mean() - b.mean()) / s)


def main() -> None:
    rows = load()
    n = len(rows)
    y = np.array([1 if r["hit"] else 0 for r in rows])
    n_hit, n_miss = int(y.sum()), n - int(y.sum())
    print(f"N = {n} | HIT = {n_hit} ({n_hit / n * 100:.1f}%) | MISS = {n_miss}")
    print()

    numeric_feats = [
        "k_heavy", "window_days", "density_pct", "rvol", "max_rvol",
        "net_dist", "net_dist_heavy", "sma_gap_pct", "acc_density",
        "post_ara_decay", "distance_pct", "days_since_prev_ara",
        "adv_vol_20", "adv_val_20",
        "ret1", "ret5", "ret10", "ret20", "sma_slope_pct",
        "atr14_pct", "hi_lo_pct", "range_window_pct", "cv_close_window",
        "dd60_pct", "hi250_ratio", "z_vol", "cum_vol_ratio", "vol_conc_3d",
        "streak", "n_sig_same",
    ]
    # mkt = [ret_today, breadth, ret5, vol_today]
    mkt_feats = [("mkt_ret_today", 0), ("mkt_breadth", 1), ("mkt_ret5", 2), ("mkt_vol_today", 3)]

    print("=" * 100)
    print(f"{'fitur':<22}{'n':>5}{'AUC':>7}{'Q1':>8}{'Q2':>8}{'Q3':>8}{'Q4':>8}"
          f"{'HR_hit%':>9}{'HR_miss%':>10}{'d(mean diff)':>14}")
    print("-" * 100)

    def bucket_hr(vals: np.ndarray, q: np.ndarray, yq: np.ndarray) -> str:
        if len(vals) < 20:
            return "    -   "
        qq = np.quantile(vals, [0.25, 0.5, 0.75])
        parts = []
        for a, b in [(-np.inf, qq[0]), (qq[0], qq[1]), (qq[1], qq[2]), (qq[2], np.inf)]:
            m = (vals >= a) & (vals < b)
            if qq[0] == qq[2]:  # degenerate
                m = np.ones(len(vals), dtype=bool)
                break
            if m.sum() == 0:
                parts.append("   -   ")
            else:
                parts.append(f"{yq[m].mean() * 100:6.1f}")
        return " ".join(parts)

    res = []
    for name, col in mkt_feats:
        vals = np.array([(r["mk"][col] if r["mk"][0] is not None else np.nan) for r in rows], dtype=float)
        m = np.isfinite(vals) & (vals is not np.nan)
        m = np.isfinite(vals)
        if m.sum() < 30:
            continue
        v, yy = vals[m], y[m]
        res.append((name, v, yy))

    for name in numeric_feats:
        vals = np.array([r[name] for r in rows], dtype=float)
        m = np.isfinite(vals)
        if m.sum() < 30:
            continue
        v, yy = vals[m], y[m]
        res.append((name, v, yy))

    for name, v, yy in res:
        a = auc(v, yy)
        hr_hit = yy[yy == 1].mean() * 100 if (yy == 1).any() else float("nan")
        hr_miss = yy[yy == 0].mean() * 100 if (yy == 0).any() else float("nan")
        vh, vm = v[yy == 1], v[yy == 0]
        d = cohens_d(vh, vm)
        q_hr = bucket_hr(v, None, yy)
        print(f"{name:<22}{len(v):>5}{a:>7.3f}  {q_hr}"
              f"{hr_hit:>9.1f}{hr_miss:>10.1f}{d:>13.3f}")

    # ---- fitur kategorik ----
    print()
    print("=" * 100)
    print("FITUR KATEGORIK (hit rate per kategori):")
    for name in ["state_ma20", "liquidity_prima", "double_ara"]:
        from collections import Counter
        cnt = Counter(r[name] for r in rows)
        print(f"\n[{name}]")
        for cat, c in cnt.most_common():
            sub = [r for r in rows if r[name] == cat]
            h = sum(1 for r in sub if r["hit"])
            print(f"  {str(cat):<10} n={c:>4}  hit={h:>3}  ({h / c * 100:.1f}%)")

    # ---- klasifikasi kegagalan ----
    print()
    print("=" * 100)
    print("KLASIFIKASI SINYAL TIDAK HIT (max_gap_pct = puncak terbaik dalam 10 hari):")
    miss = [r for r in rows if not r["hit"]]
    buckets = {"turun (max_gap < 0%)": [], "stagnan (0-3%)": [],
               "naik tapi kurang (3-<10%)": []}
    for r in miss:
        g = r["max_gap_pct"]
        if g is None:
            buckets.setdefault("censored/0 hari", []).append(r)
        elif g < 0:
            buckets["turun (max_gap < 0%)"].append(r)
        elif g < 3:
            buckets["stagnan (0-3%)"].append(r)
        else:
            buckets["naik tapi kurang (3-<10%)"].append(r)
    for k, v in buckets.items():
        print(f"  {k:<30} n={len(v):>4} ({len(v) / len(miss) * 100:.1f}%)")

    # ---- days_to_hit utk HIT ----
    print()
    print("DISTRIBUSI days_to_hit (HIT saja) — awal vs akhir jendela:")
    hit = [r for r in rows if r["hit"]]
    dth = np.array([r["days_to_hit"] for r in hit])
    for k in range(1, 11):
        c = int((dth == k).sum())
        print(f"  hari ke-{k:<2}: {c:>3} ({c / len(hit) * 100:.1f}%)")
    early = int((dth <= 3).sum())
    print(f"  => hit <= 3 hari: {early} ({early / len(hit) * 100:.1f}%) | "
          f"hit >= 7 hari: {int((dth >= 7).sum())} ({((dth >= 7).sum()) / len(hit) * 100:.1f}%)")

    # ---- redundansi: korelasi antar fitur top ----
    print()
    print("=" * 100)
    print("KORELASI SPEARMAN antar fitur (|r| > 0.6 ditandai *):")
    top = ["density_pct", "net_dist", "net_dist_heavy", "acc_density", "k_heavy",
           "window_days", "atr14_pct", "range_window_pct", "cv_close_window",
           "ret5", "sma_slope_pct", "z_vol", "cum_vol_ratio", "streak",
           "mkt_ret_today", "mkt_breadth", "max_rvol", "dd60_pct", "distance_pct"]
    arrs = {}
    for name in top:
        v = np.array([r.get(name) for r in rows], dtype=float)
        arrs[name] = v
    names = list(arrs)
    print(f"{'':<20}" + "".join(f"{nm[:8]:>10}" for nm in names))
    for i, a in enumerate(names):
        line = f"{a:<20}"
        for j, b in enumerate(names):
            if j > i:
                break
            va, vb = arrs[a], arrs[b]
            m = np.isfinite(va) & np.isfinite(vb)
            if m.sum() < 30 or a == b:
                r = 1.0 if a == b else float("nan")
            else:
                ra = np.argsort(np.argsort(va[m], kind="mergesort"))
                rb = np.argsort(np.argsort(vb[m], kind="mergesort"))
                r = float(np.corrcoef(ra, rb)[0, 1])
            star = "*" if (a != b and abs(r) > 0.6) else " "
            line += f"{r:>9.2f}{star}"
        print(line)

    # ---- interaksi penting ----
    print()
    print("=" * 100)
    print("INTERAKSI KUNCI:")
    # net_dist sign
    nd = np.array([r["net_dist"] if r["net_dist"] is not None else np.nan for r in rows])
    for lab, m in [("net_dist >= 0", nd >= 0), ("net_dist < 0", (nd < 0) & np.isfinite(nd))]:
        if m.sum() >= 10:
            sub = [r for r, mm in zip(rows, m) if mm]
            h = sum(1 for r in sub if r["hit"])
            print(f"  {lab:<18} n={len(sub):>4}  hit={h:>3} ({h / len(sub) * 100:.1f}%)")
    # window_days timing
    wd = np.array([r["window_days"] for r in rows], dtype=float)
    for lab, m in [("window 1-2", wd <= 2), ("window 3-5", (wd >= 3) & (wd <= 5)),
                   ("window 6-10", (wd >= 6) & (wd <= 10)), ("window >10", wd > 10)]:
        if m.sum() >= 10:
            sub = [r for r, mm in zip(rows, m) if mm]
            h = sum(1 for r in sub if r["hit"])
            print(f"  {lab:<14} n={len(sub):>4}  hit={h:>3} ({h / len(sub) * 100:.1f}%)")
    # streak
    st = np.array([r["streak"] for r in rows], dtype=float)
    for lab, m in [("streak=1", st == 1), ("streak=2", st == 2), ("streak>=3", st >= 3)]:
        if m.sum() >= 10:
            sub = [r for r, mm in zip(rows, m) if mm]
            h = sum(1 for r in sub if r["hit"])
            print(f"  {lab:<12} n={len(sub):>4}  hit={h:>3} ({h / len(sub) * 100:.1f}%)")
    # volume besar tapi harga turun (false accumulation?)
    vbig = np.array([r["z_vol"] if r["z_vol"] is not None else np.nan for r in rows])
    r5a = np.array([r["ret5"] if r["ret5"] is not None else np.nan for r in rows])
    for lab, m in [
        ("z_vol>=1 & ret5<0", (vbig >= 1) & (r5a < 0)),
        ("z_vol>=1 & ret5>=0", (vbig >= 1) & (r5a >= 0)),
        ("z_vol<1 & ret5<0", (vbig < 1) & (r5a < 0)),
    ]:
        if m.sum() >= 10:
            sub = [r for r, mm in zip(rows, m) if mm]
            h = sum(1 for r in sub if r["hit"])
            print(f"  {lab:<22} n={len(sub):>4}  hit={h:>3} ({h / len(sub) * 100:.1f}%)")
    # mkt regime
    mb = np.array([r["mk"][1] if r["mk"][0] is not None else np.nan for r in rows])
    mr = np.array([r["mk"][0] if r["mk"][0] is not None else np.nan for r in rows])
    for lab, m in [("breadth>50%", mb >= 0.5), ("breadth<50%", (mb < 0.5) & np.isfinite(mb)),
                   ("mkt ret>0", mr > 0), ("mkt ret<=0", (mr <= 0) & np.isfinite(mr))]:
        if m.sum() >= 10:
            sub = [r for r, mm in zip(rows, m) if mm]
            h = sum(1 for r in sub if r["hit"])
            print(f"  {lab:<16} n={len(sub):>4}  hit={h:>3} ({h / len(sub) * 100:.1f}%)")


if __name__ == "__main__":
    sys.exit(main())