"""
Threshold tuning: uji berbagai threshold gorengan score terhadap Top 10 Gainers.
Metodologi:
  1. Setiap saham di Top Gainers harian di-score menggunakan data hingga tanggal tsb.
  2. Forward-check: apakah saham beneran dump >10% dalam waktu yg tersisa?
  3. Hitung precision, recall, F1 untuk tiap threshold.
"""
import config
import numpy as np
import gorengan
import indicators as ind
from data_source.yahoo_client import fetch_trading_info
from data_source.gainers import get_or_fetch_securities_list
from concurrent.futures import ThreadPoolExecutor, as_completed

# Top 10 Gainers harian (Juli 2026)
DAILY_GAINERS = {
    "2026-07-01": ["COCO", "BBRM", "PADI", "BEEF", "CSMI", "RATU", "CUAN", "SHIP", "ARTA", "RSGK"],
    "2026-07-02": ["COCO", "BEEF", "MMIX", "TRUS", "RMKO", "KDTN", "BNBR", "VKTR", "BGTG"],
    "2026-07-06": ["LAPD", "NTBK", "BELL", "YUPI", "SKBM", "ERTX", "INOV", "ASPI", "ESTI", "BUVA"],
    "2026-07-07": ["APLN", "LAND", "NTBK", "BIPP", "RODA", "PGJO", "JATI", "FORU", "JELI", "MINA"],
    "2026-07-13": ["BKDP", "LAND", "VKTR", "PRDL", "ATAP", "OASA", "KIOS", "MHKI", "SMLE", "SQMI"],
    "2026-07-14": ["AGAR", "PRDL", "SKBM", "VERN", "ENRG", "BRNA", "ADMG", "VKTR", "SGER", "BAPA"],
    "2026-07-15": ["INAI", "RANS", "PRDL", "AGAR", "GDST", "ALKA", "BAPA", "GTRA", "MMIX", "LION"],
    "2026-07-16": ["KBLV", "CTTH", "RONY", "AGAR", "MLPT", "RBMS", "DOOH", "SSIA", "ARTA", "LPPS"],
    "2026-07-17": ["KOKA", "KBLV", "AGAR", "HOPE", "ECII", "MLPT", "BACA", "LION", "SQMI", "BBYB"],
    "2026-07-20": ["RONY", "BNBR", "PAMG", "OMRE", "FWCT", "RISE", "SQMI", "KOKA", "GULA", "PRAY"],
}

THRESHOLDS = list(range(50, 96))  # 50 hingga 95

DUMP_THRESHOLD = -10  # drawdown >10% = dump


def find_date_idx(bars, target_date):
    """Cari index baris terakhir dengan date <= target_date."""
    for i, b in enumerate(bars):
        if b.date > target_date:
            return i
    return len(bars)


def max_drawdown(prices):
    if len(prices) < 2:
        return 0.0
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (p - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd
    return max_dd


def compute_for_stock(date, code, sec_map):
    s = sec_map.get(code)
    shares = s.shares if s and s.shares else None
    board = s.listing_board if s else None

    try:
        bars = fetch_trading_info(code, length=500)
        if len(bars) < config.MIN_TRADING_DAYS:
            return None

        split_idx = find_date_idx(bars, date)
        train_bars = bars[:split_idx]
        future_bars = bars[split_idx:]

        if len(train_bars) < config.MIN_TRADING_DAYS:
            return None
        if len(future_bars) < 2:
            return None

        close = np.array([b.close for b in train_bars])
        open_ = np.array([b.open_price for b in train_bars])
        high = np.array([b.high for b in train_bars])
        low = np.array([b.low for b in train_bars])
        volume = np.array([b.volume for b in train_bars])

        atr_val = ind.atr(high, low, close)
        adx_val = ind.adx(high, low, close)
        rvol_val = ind.rvol(volume, config.RVOL_WINDOW)

        gor = gorengan.compute_gorengan(
            close=close, open_=open_, high=high, low=low, volume=volume,
            atr_arr=atr_val, adx_arr=adx_val["adx"],
            rvol_arr=rvol_val, shares=shares, listing_board=board,
        )

        future_close = np.array([b.close for b in future_bars])
        dd = max_drawdown(future_close)
        is_dump = dd <= DUMP_THRESHOLD

        return {
            "code": code,
            "date": date,
            "score": gor["score"],
            "level": gor["level"],
            "max_dd": round(dd, 1),
            "is_dump": is_dump,
        }
    except Exception as e:
        return None


def print_table(rows, headers):
    col_widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_widths))
    for r in rows:
        print(fmt.format(*(str(x) for x in r)))


def main():
    securities = get_or_fetch_securities_list()
    sec_map = {s.code: s for s in securities}

    all_tasks = []
    for date, codes in DAILY_GAINERS.items():
        for code in codes:
            all_tasks.append((date, code))
    print(f"Total tasks: {len(all_tasks)}")

    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut_map = {ex.submit(compute_for_stock, date, code, sec_map): (date, code) for date, code in all_tasks}
        for fut in as_completed(fut_map):
            date, code = fut_map[fut]
            res = fut.result()
            if res:
                results.append(res)
                print(f"  {date} {code:6s} score={res['score']:5.1f} {res['level']:8s} dd={res['max_dd']:5.1f}% {'DUMP' if res['is_dump'] else ''}")
            else:
                print(f"  {date} {code:6s} SKIP")

    print(f"\n{'='*100}")
    print(f"HASIL: {len(results)} saham berhasil di-scan")
    print(f"{'='*100}")

    # Show per-stock detail sorted by score
    results.sort(key=lambda r: r["score"], reverse=True)
    print(f"\n{'='*100}")
    print(f"ALL SCORES SORTED:")
    print(f"{'='*100}")
    rows = [(r["date"], r["code"], f"{r['score']:.1f}", r["level"], f"{r['max_dd']:.1f}%", "DUMP" if r["is_dump"] else "") for r in results]
    print_table(rows, ["Date", "Code", "Score", "Level", "Max DD", "Dump?"])

    # Threshold analysis
    print(f"\n{'='*100}")
    print(f"THRESHOLD ANALYSIS")
    print(f"{'='*100}")

    total_dumped = sum(1 for r in results if r["is_dump"])
    print(f"\nTotal saham: {len(results)}")
    print(f"Total beneran dump: {total_dumped} ({total_dumped/len(results)*100:.1f}%)")
    print(f"Total tidak dump: {len(results) - total_dumped} ({100 - total_dumped/len(results)*100:.1f}%)")

    print(f"\n{'='*100}")
    print(f"THRESHOLD TABLE (precision = % yang dump dari yg lolos)")
    print(f"{'='*100}")
    thresh_rows = []
    for t in THRESHOLDS:
        passed = [r for r in results if r["score"] >= t]
        if not passed:
            continue
        n = len(passed)
        tp = sum(1 for r in passed if r["is_dump"])
        fp = n - tp
        precision = tp / n * 100 if n > 0 else 0
        fp_rate = fp / (len(results) - total_dumped) * 100 if (len(results) - total_dumped) > 0 else 0
        recall = tp / total_dumped * 100 if total_dumped > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        thresh_rows.append((t, n, tp, fp, f"{precision:.1f}", f"{recall:.1f}", f"{fp_rate:.1f}", f"{f1:.1f}"))

    print_table(thresh_rows, ["Thresh", "N Pass", "TP_dump", "FP_no", "Perc(%)", "Recall(%)", "FPR(%)", "F1"])

    # Fine-tune around best threshold
    print(f"\n{'='*100}")
    print(f"BEST THRESHOLDS (by F1 score)")
    print(f"{'='*100}")
    best = sorted(thresh_rows, key=lambda r: float(r[7]), reverse=True)[:10]
    print_table(best, ["Thresh", "N Pass", "TP_dump", "FP_no", "Perc(%)", "Recall(%)", "FPR(%)", "F1"])

    # Also check fine-tune band around best
    best_t = int(best[0][0])
    lower = max(50, best_t - 5)
    upper = min(95, best_t + 5)
    fine_range = list(range(lower, upper + 1))
    print(f"\n{'='*100}")
    print(f"FINE-TUNE ({lower}-{upper})")
    print(f"{'='*100}")
    fine_rows = [r for r in thresh_rows if r[0] in fine_range]
    print_table(fine_rows, ["Thresh", "N Pass", "TP_dump", "FP_no", "Perc(%)", "Recall(%)", "FPR(%)", "F1"])

    # Final conclusion
    print(f"\n{'='*100}")
    print(f"CONCLUSION")
    print(f"{'='*100}")
    for t in [90, 85, 80, 75, 70, 65, 60, 55, 50]:
        passed = [r for r in results if r["score"] >= t]
        n = len(passed)
        tp = sum(1 for r in passed if r["is_dump"])
        pct = tp / n * 100 if n > 0 else 0
        print(f"  Score >= {t:2d} -> {tp:2d}/{n:2d} benar-benar jadi saham gorengan ({pct:.0f}%)")

    if best:
        print(f"\n  Rekomendasi threshold optimal: {best_t}")
        print(f"  Alasan: F1={best[0][7]}, Precision={best[0][4]}%, Recall={best[0][5]}%")
        print(f"  Jumlah sampel: {best[0][1]} stocks")


if __name__ == "__main__":
    main()
