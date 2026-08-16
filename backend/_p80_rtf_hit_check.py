"""
_p80_rtf_hit_check.py — Cek langsung: tanggal signal RTF (3-14 Agu 2026) -> saham -> HIT?

Definisi yang dipakai (MENGIKUTI project, tidak membuat baru):
  - Sinyal RTF   : detect_accumulation(bars[:k+1])["valid"] == True
                   (gate produksi: density >= 30%, min 2 heavy, close >= SMA20,
                    harga di bawah level event, likuiditas ADV20 >= floor BEI).
  - HIT (b10)    : max(high[i+1..i+10]) / close[i] - 1 >= +10%
                   (definisi resmi _baseline_compare.py:13 & docstring
                    detect_accumulation: win-rate 10 hari (b10) 18.4% vs 5.4%).
                   Tanggal hit = bar pertama j>i dengan high[j] >= close[i] * 1.10.

Dataset: data/universe_ohlcv.npz (bar terakhir 2026-08-14 Jumat; 15-16 Agu = akhir
pekan, market tutup -> "sampai hari ini" = evaluasi s/d 14 Agu 2026).
"""

from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import numpy as np

from recovery import detect_accumulation

NPZ_PATH = "data/universe_ohlcv.npz"
START = sys.argv[1] if len(sys.argv) > 1 else "2026-08-03"
END = sys.argv[2] if len(sys.argv) > 2 else "2026-08-16"
OUT_JSON = sys.argv[3] if len(sys.argv) > 3 else "data/phase8_rtf_hit_check.json"

BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
         "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def fmt_id(iso: str) -> str:
    """'2026-08-03' -> '3 Agustus 2026'"""
    y, m, d = iso.split("-")
    return f"{int(d)} {BULAN[int(m)]} {y}"


def make_bars(rows, dates, c: int, m: int) -> list:
    bars = []
    cl = rows[c, :m, 3]
    for i in range(m):
        r = rows[c, i]
        prev = float(cl[i - 1]) if i > 0 else float(r[3])
        bars.append(SimpleNamespace(
            date=dates[i],
            previous=prev,
            open_price=float(r[0]),
            high=float(r[1]),
            low=float(r[2]),
            close=float(r[3]),
            raw_close=float(r[3]),
            adj_close=float(r[4]) if len(r) > 4 else float(r[3]),
            volume=float(r[5]) if len(r) > 5 else 0.0,
            approx_value=0.0,
            frequency="1d",
            bid=0.0, offer=0.0, foreign_buy=0.0, foreign_sell=0.0,
        ))
    return bars


def main() -> None:
    d = np.load(NPZ_PATH, allow_pickle=True)
    rows, lens = d["rows"], d["lens"]
    raw_dates = d["dates"]
    codes = [c.decode() if isinstance(c, bytes) else str(c) for c in d["codes"]]
    n_codes = len(codes)
    print(f"Dataset: {n_codes} kode; window {START}..{END}", flush=True)
    t0 = time.time()

    start_dt = np.datetime64(START)
    end_dt = np.datetime64(END)

    # sinyal per tanggal: {iso_date: [(code, idx, close0, ...)]}
    per_date: dict[str, list] = {}
    n_accum_calls = 0
    n_sig = 0

    for c in range(n_codes):
        m = int(lens[c])
        if m < 60:
            continue
        ds = raw_dates[c]
        if len(ds) < m:
            continue
        dt = np.asarray(ds, dtype="datetime64[D]")
        # index bar-bar dalam window
        idxs = [k for k in range(m) if start_dt <= dt[k] <= end_dt]
        if not idxs:
            continue
        close = rows[c, :m, 3]
        high = rows[c, :m, 1]
        if not np.isfinite(close[: idxs[-1] + 1]).all() or (close[: idxs[-1] + 1] <= 0).any():
            continue

        bars = make_bars(rows, [str(x)[:10] for x in ds], c, m)

        for k in idxs:
            n_accum_calls += 1
            r = detect_accumulation(bars[: k + 1])
            if r.get("valid"):
                n_sig += 1
                iso = str(bars[k].date)[:10]
                per_date.setdefault(iso, []).append(
                    {"code": codes[c], "k": k, "close0": float(close[k])})

    # evaluasi hit utk tiap sinyal (b10: high[j] >= close0 * 1.10, j = k+1..k+10)
    results: dict[str, list] = {}
    for iso in sorted(per_date):
        entries = []
        for s in per_date[iso]:
            c_i = s["k"]
            code = s["code"]
            # cari index kode utk akses high (gunakan bar list? simpan referensi)
            # -> disimpan ulang via lookup cepat: gunakan dict code->(rows idx)
            entries.append(s)
        results[iso] = entries

    # lookup index kode
    code_idx = {code: i for i, code in enumerate(codes)}

    out_lines = []
    summary = []
    for iso in sorted(results):
        entries = sorted(results[iso], key=lambda s: s["code"])
        lines = [f"{fmt_id(iso)}"]
        n_hit = 0
        for s in entries:
            c = code_idx[s["code"]]
            m = int(lens[c])
            k = s["k"]
            close0 = s["close0"]
            high = rows[c, :m, 1]
            ds = raw_dates[c]
            hit_iso = None
            horizon = min(10, m - 1 - k)  # hari trading tersedia utk evaluasi
            for j in range(k + 1, min(k + 10, m - 1) + 1):
                if high[j] >= close0 * 1.10:
                    hit_iso = str(ds[j])[:10]
                    break
            if hit_iso:
                n_hit += 1
                lines.append(f"- {s['code']} → HIT, {fmt_id(hit_iso)}")
            elif horizon < 10:
                lines.append(f"- {s['code']} → TIDAK HIT (evaluasi {horizon}/10 hari)")
            else:
                lines.append(f"- {s['code']} → TIDAK HIT")
        out_lines.append("\n".join(lines))
        summary.append((iso, len(entries), n_hit))

    print(f"accum calls: {n_accum_calls}, sinyal: {n_sig}, {time.time() - t0:.1f}s", flush=True)

    print("\n" + "=" * 62)
    print("DEFINISI (dari project, bukan baru):")
    print("  Sinyal RTF = detect_accumulation valid (density>=30%, min 2 heavy,")
    print("               SMA20, below event, likuiditas ADV20).")
    print("  HIT (b10)  = max(high[i+1..i+10])/close[i] - 1 >= +10%")
    print("               (_baseline_compare.py; sama dgn validasi 18.4% vs 5.4%).")
    print("  Evaluasi s/d 14 Agustus 2026 (bar terakhir dataset; 15-16 Agu akhir pekan).")
    print("=" * 62)
    print()
    for block in out_lines:
        print(block)
        print()
    print("=" * 62)
    print("RINGKASAN per tanggal:")
    for iso, n, nh in summary:
        print(f"  {fmt_id(iso)}: {n} sinyal, {nh} HIT")
    tot = sum(n for _, n, _ in summary)
    tot_h = sum(nh for _, _, nh in summary)
    print(f"  TOTAL: {tot} sinyal, {tot_h} HIT "
          f"({tot_h / tot * 100:.1f}%)" if tot else "  TOTAL: 0 sinyal")

    # ---- analisis per saham unik (sinyal pertama saja) ----
    first_sig: dict[str, dict] = {}
    for iso in sorted(results):
        for s in sorted(results[iso], key=lambda x: x["code"]):
            code = s["code"]
            if code in first_sig:
                continue
            c = code_idx[code]
            m = int(lens[c])
            k = s["k"]
            close0 = s["close0"]
            high = rows[c, :m, 1]
            ds = raw_dates[c]
            hit_iso = None
            horizon = min(10, m - 1 - k)
            for j in range(k + 1, min(k + 10, m - 1) + 1):
                if high[j] >= close0 * 1.10:
                    hit_iso = str(ds[j])[:10]
                    break
            first_sig[code] = {"signal_date": iso, "close0": close0,
                               "hit_date": hit_iso, "horizon": horizon}
    n_u = len(first_sig)
    n_u_hit = sum(1 for v in first_sig.values() if v["hit_date"])
    print("\n" + "=" * 62)
    print(f"PER SAHAM UNIK (sinyal pertama di window): {n_u} saham, "
          f"{n_u_hit} HIT ({n_u_hit / n_u * 100:.1f}%)" if n_u else "0 saham")
    print("  (sinyal berulang lintas tanggal utk saham yg sama dihitung sekali)")
    print("=" * 62)

    # simpan hasil
    import json
    out = {
        "definisi": {
            "sinyal": "detect_accumulation valid (density>=30%, min 2 heavy, "
                      "SMA20, below event, likuiditas ADV20)",
            "hit": "b10: max(high[i+1..i+10])/close[i]-1 >= +10% "
                   "(definisi _baseline_compare.py)",
            "window": "2026-08-03 s/d 2026-08-14 (bar terakhir dataset; "
                      "15-16 Agu akhir pekan)",
        },
        "per_tanggal": {
            iso: sorted(
                [{"code": s["code"], "close0": s["close0"]}
                 for s in results[iso]], key=lambda x: x["code"])
            for iso in sorted(results)
        },
        "hit_per_tanggal": {iso: {"n": n, "hit": nh}
                            for iso, n, nh in summary},
        "per_saham_unik": first_sig,
        "total": {"n": tot, "hit": tot_h,
                  "hit_rate": (tot_h / tot) if tot else None,
                  "n_unique": n_u,
                  "n_unique_hit": n_u_hit},
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"saved: {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())