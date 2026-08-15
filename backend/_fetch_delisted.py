"""
_fetch_delisted.py — Ambil OHLCV saham IDX yang sudah DELISTED dari Yahoo
Finance, simpan dengan format identik universe_ohlcv.npz, lalu QA.

Latar belakang (riset item TODO "data delisted"):
  Model recovery (recovery_model_params.json) dikalibrasi pada universe
  963 saham yang SAAT INI masih listing. Saham yang kemudian delisted
  (bangkrut / gagal / merger) biasanya sudah jatuh duluan sebelum keluar
  dari bursa — sample bias survivorship. Dataset ini dipakai untuk
  mengukur apakah model overpredict recovery pada saham "nasib buruk".

Sumber seed list (IDX API resmi tidak bisa dipakai: Cloudflare 403/503):
  - SahamOK  (sahamok.net/emiten/saham-delisting/...) — 2017, 2018, 2019, 2020
  - IDXChannel — 2021 (FINN)
  - CNBC Indonesia (artikel Jul-2025, delisting 2020-2025) — 10 kode
  Total: 31 kode.

Output:
  data/delisted_ohlcv.npz  — format sama dgn universe_ohlcv.npz
  data/delisted_meta.json  — metadata + tanggal delisting + QA per kode

Usage:
    python _fetch_delisted.py
    python _fetch_delisted.py --skip-fetch   # pakai npz lama, cetak QA saja
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

import numpy as np

import config as CFG
from data_source.yahoo_client import DailyBar, YahooClientError, fetch_trading_info

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
NPZ_PATH = os.path.join(DATA_DIR, "delisted_ohlcv.npz")
META_PATH = os.path.join(DATA_DIR, "delisted_meta.json")

FETCH_START = date(2015, 9, 1)   # ~3.5 tahun sebelum jendela universe; max 900 bar
MAX_BARS = 900                   # lebar array sama dgn universe_ohlcv.npz
N_FIELDS = 6                     # open, high, low, close(raw), adj_close, volume
MIN_BARS_OK = 60                 # di bawah ini dianggap tidak berguna

# (kode, nama, tanggal_delisting ISO atau None, sumber)
SEEDS: list[tuple[str, str, str | None, str]] = [
    # ---- 2017 (SahamOK) ----
    ("CTRP", "Ciputra Property Tbk", "2017-01-19", "sahamok"),
    ("CTRS", "Ciputra Surya Tbk", "2017-01-19", "sahamok"),
    ("SOBI", "Sorini Agro Asia Corporindo Tbk", "2017-07-03", "sahamok"),
    ("CPGT", "Citra Maharlika Nusantara Corpora Tbk", "2017-10-19", "sahamok"),
    ("INVS", "Inovisi Infracom Tbk", "2017-10-23", "sahamok"),
    ("BRAU", "Berau Coal Energy Tbk", "2017-11-16", "sahamok"),
    ("TKGA", "Permata Prima Sakti Tbk", "2017-11-16", "sahamok"),
    ("LAMI", "Lamicitra Nusantara Tbk", "2017-12-28", "sahamok"),
    # ---- 2018 (SahamOK) ----
    ("SQBB", "Taisho Pharmaceutical Indonesia Tbk", "2018-03-21", "sahamok"),
    ("DAJK", "Dwi Aneka Jaya Kemasindo Tbk", "2018-05-18", "sahamok"),
    ("TRUB", "Truba Alam Manunggal Engineering Tbk", "2018-09-12", "sahamok"),
    ("JPRS", "Jaya Pari Steel Tbk", "2018-10-08", "sahamok"),
    # ---- 2019 (SahamOK) ----
    ("BBNP", "Bank Nusantara Parahyangan Tbk", "2019-05-02", "sahamok"),
    ("SIAP", "Sekawan Intipratama Tbk", "2019-06-17", "sahamok"),
    ("GMCW", "Grahamas Citrawisata Tbk", "2019-08-13", "sahamok"),
    ("NAGA", "Bank Mitraniaga Tbk", "2019-08-23", "sahamok"),
    ("ATPK", "Bara Jaya Internasional Tbk", "2019-09-30", "sahamok"),
    ("TMPI", "Sigmagold Inti Perkasa Tbk", "2019-11-11", "sahamok"),
    # ---- 2020 (SahamOK) ----
    ("BORN", "Borneo Lumbung Energi & Metal Tbk", "2020-01-20", "sahamok"),
    ("ITTG", "Leo Investments Tbk", "2020-01-23", "sahamok"),
    # ---- 2021 (IDXChannel) ----
    ("FINN", "First Indo American Leasing Tbk", "2021-03-02", "idxchannel"),
    # ---- 2020-2025 (CNBC Indonesia, artikel 2025-07) ----
    ("MAMI", None, None, "cnbc"),
    ("FORZ", None, None, "cnbc"),
    ("MYRX", None, None, "cnbc"),
    ("KRAH", None, None, "cnbc"),
    ("KPAS", None, None, "cnbc"),
    ("KPAL", None, None, "cnbc"),
    ("PRAS", None, None, "cnbc"),
    ("NIPS", None, None, "cnbc"),
    ("JKSW", None, None, "cnbc"),
    ("HDTX", None, None, "cnbc"),
]

RETRIES = 3          # empty result bisa = rate-limit Yahoo, bukan "tidak ada data"
BACKOFF_S = (8.0, 16.0, 32.0)
THROTTLE_S = 0.6     # jeda antar-kode per worker (anti rate-limit)


def _fetch_with_retry(code: str, length_days: int) -> tuple[list[DailyBar], int]:
    """fetch_trading_info + retry dgn backoff. Return (bars, attempts_used)."""
    for attempt in range(RETRIES + 1):
        try:
            bars = fetch_trading_info(code, length=length_days,
                                      target_date=date.today().isoformat())
        except YahooClientError as e:
            if attempt == RETRIES:
                raise
            time.sleep(BACKOFF_S[attempt])
            continue
        if bars:
            return bars, attempt + 1
        if attempt < RETRIES:
            time.sleep(BACKOFF_S[attempt])
    return [], RETRIES + 1


def _bar_to_row(b: DailyBar) -> list[float]:
    adj = b.adj_close if getattr(b, "adj_close", 0.0) > 0 else b.close
    return [b.open_price, b.high, b.low, b.close, adj, b.volume]


def _fetch_all(workers: int, length_days: int) -> dict[str, dict]:
    n = len(SEEDS)
    out: dict[str, dict] = {}
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_fetch_with_retry, c, length_days): i
                for i, (c, *_rest) in enumerate(SEEDS)}
        for fut in as_completed(futs):
            i = futs[fut]
            code = SEEDS[i][0]
            try:
                bars, attempts = fut.result()
                out[code] = {"bars": bars, "attempts": attempts, "error": None}
            except Exception as e:  # noqa: BLE001
                out[code] = {"bars": [], "attempts": RETRIES + 1, "error": str(e)}
            done += 1
            el = time.time() - t0
            print(f"[{datetime.now():%H:%M:%S}] {done}/{n} {code} "
                  f"({el:.0f}s)", flush=True)
            time.sleep(THROTTLE_S)
    return out


def _qa(code: str, bars: list[DailyBar], meta_entry: dict) -> dict:
    """QA per kode: last date vs delisting date, zero-volume, NaN, tren harga."""
    q = {"n_bars": len(bars)}
    if not bars:
        q["status"] = "no_data"
        return q
    last_date = bars[-1].date
    q["last_date"] = last_date
    q["first_date"] = bars[0].date
    q["status"] = "ok"
    n_nan = 0
    n_zero_vol = 0
    for b in bars:
        for v in (b.open_price, b.high, b.low, b.close, b.adj_close):
            if not np.isfinite(v):
                n_nan += 1
        if b.volume <= 0:
            n_zero_vol += 1
    q["nan_cells"] = n_nan
    q["zero_vol_bars"] = n_zero_vol
    dd = meta_entry.get("delisting_date")
    if dd:
        try:
            gap = (date.fromisoformat(dd) - date.fromisoformat(last_date)).days
            q["gap_last_vs_delisting_days"] = gap
            q["gap_ok"] = 0 <= gap <= 45
        except ValueError:
            q["gap_last_vs_delisting_days"] = None
            q["gap_ok"] = None
    if len(bars) > 5:
        q["price_start"] = round(float(bars[0].close), 4)
        q["price_end"] = round(float(bars[-1].close), 4)
        q["drawdown_end_vs_start"] = round(
            float(bars[-1].close / bars[0].close - 1.0), 4)
    if len(bars) < MIN_BARS_OK:
        q["status"] = "too_short"
    return q


def _save(rows: np.ndarray, lens: np.ndarray, ok: np.ndarray,
          dates: list[object], codes: list[str]) -> None:
    dates_arr = np.empty(len(codes), dtype=object)
    for i, dl in enumerate(dates):
        dates_arr[i] = dl
    np.savez_compressed(
        NPZ_PATH,
        codes=np.array(codes, dtype="S12"),
        rows=rows, lens=lens, ok=ok,
        dates=dates_arr,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-fetch", action="store_true",
                    help="pakai delisted_ohlcv.npz yg sudah ada, hanya QA/report")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    codes = [c for c, *_rest in SEEDS]
    meta_entries = [
        {"kode": c, "nama": n, "delisting_date": d, "sumber": s}
        for c, n, d, s in SEEDS
    ]

    if args.skip_fetch:
        if not os.path.exists(NPZ_PATH):
            print(f"{NPZ_PATH} tidak ada — jalankan tanpa --skip-fetch")
            return 1
        print(f"Skip fetch: pakai {NPZ_PATH}")
        d = np.load(NPZ_PATH, allow_pickle=True)
        rows, lens, ok = d["rows"], d["lens"], d["ok"]
        codes_loaded = [c.decode() if isinstance(c, bytes) else str(c)
                        for c in d["codes"]]
        dates = list(d["dates"])
    else:
        length_days = (date.today() - FETCH_START).days + 5
        print(f"Fetch {len(codes)} kode delisted "
              f"(length={length_days} kalender, workers={args.workers})…", flush=True)
        fetched = _fetch_all(args.workers, length_days)

        n = len(codes)
        rows = np.zeros((n, MAX_BARS, N_FIELDS), dtype=np.float64)
        lens = np.zeros(n, dtype=np.int32)
        ok = np.zeros(n, dtype=bool)
        dates: list[object] = []
        for i, code in enumerate(codes):
            bars = fetched[code]["bars"]
            if not bars:
                dates.append([])
                continue
            nb = min(len(bars), MAX_BARS)
            tail = bars[-nb:]
            dates.append([b.date for b in tail])
            for j, b in enumerate(tail):
                rows[i, j] = _bar_to_row(b)
            lens[i] = nb
            ok[i] = True
        _save(rows, lens, ok, dates, codes)
        print(f"Tersimpan: {NPZ_PATH}", flush=True)

        # simpan juga attempts/error ke meta
        for e in meta_entries:
            fc = fetched[e["kode"]]
            e["fetch_attempts"] = fc["attempts"]
            e["fetch_error"] = fc["error"]

    # ---- QA ----
    print("\n" + "=" * 108)
    print(f"{'KODE':>6} {'NAMA':<38} {'DELIST':<11} {'BARS':>5} "
          f"{'LAST':<11} {'GAP':>5} {'ZVOL':>5} {'DRAW':>8}")
    print("-" * 108)
    report: dict[str, dict] = {}
    for i, code in enumerate(codes):
        m = int(lens[i])
        # bangun list bar tiruan utk QA (mirip make_local_bar) dari rows
        bars_tmp = []
        for j in range(m):
            r = rows[i, j]
            bars_tmp.append(type("B", (), {
                "date": (dates[i][j] if len(dates[i]) > j else ""),
                "open_price": float(r[0]), "high": float(r[1]),
                "low": float(r[2]), "close": float(r[3]),
                "adj_close": float(r[4]), "volume": float(r[5]),
            })())
        q = _qa(code, bars_tmp, meta_entries[i])
        report[code] = q
        dd = meta_entries[i]["delisting_date"] or "-"
        nama = (meta_entries[i]["nama"] or "?")[:38]
        gap = q.get("gap_last_vs_delisting_days", "-")
        zvol = q.get("zero_vol_bars", "-")
        draw = q.get("drawdown_end_vs_start", "-")
        if draw != "-":
            draw = f"{draw:+.1%}"
        print(f"{code:>6} {nama:<38} {dd:<11} {q.get('n_bars', 0):>5} "
              f"{str(q.get('last_date', '-')):<11} {gap!s:>5} {zvol!s:>5} "
              f"{draw:>8}")
    print("=" * 108)

    n_ok = sum(1 for q in report.values() if q.get("status") == "ok")
    n_nodata = sum(1 for q in report.values() if q.get("status") == "no_data")
    n_short = sum(1 for q in report.values() if q.get("status") == "too_short")
    gaps_bad = [c for c, q in report.items()
                if q.get("gap_ok") is False]
    print(f"QA: ok={n_ok} no_data={n_nodata} too_short={n_short} "
          f"gap_mencurigakan={gaps_bad}")

    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": os.path.basename(NPZ_PATH),
        "n_seeds": len(codes),
        "n_ok": n_ok,
        "max_bars": MAX_BARS,
        "fields": ["open", "high", "low", "close_raw", "adj_close", "volume"],
        "fetch_start": FETCH_START.isoformat(),
        "sumber": "SahamOK 2017-2020, IDXChannel 2021, CNBC 2020-2025; "
                  "IDX API resmi tidak dapat diakses (Cloudflare 403/503)",
        "entries": meta_entries,
        "qa": report,
        "catatan": "gap_ok=False = bar terakhir Yahoo lebih dari 45 hari "
                   "sebelum tanggal delisting resmi (cek manual: bisa karena "
                   "suspensi panjang / data Yahoo tidak lengkap). "
                   "zero_vol_bars = indikasi hari suspensi.",
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
