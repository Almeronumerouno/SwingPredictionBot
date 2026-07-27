"""
Bandingkan 3 metode: Z-score vs Active Pump vs Hybrid.
Ukur recall di 45 UMA + false positive di 30 saham normal.
"""
import config
import numpy as np
import gorengan as gor
import indicators as ind
from data_source.yahoo_client import fetch_trading_info
from data_source.gainers import get_or_fetch_securities_list
from concurrent.futures import ThreadPoolExecutor, as_completed

# 45 UMA stocks (known ground truth pump)
UMA = [
    "APII","ARTA","ASLI","BBRM","BHAT","BIPP","BMSR","BSML","BTON","BUVA",
    "CARE","CASS","ELIT","ETWA","FORU","GOLD","HADE","IKBI","INDO","KOTA",
    "LRNA","META","MINA","MITI","MPRO","MTFN","NEST","NPGF","OPMS","PAMG",
    "PBSA","PURI","RELI","RISE","ROTI","SDPC","SOSS","SULI","TAMA","TIRT",
    "TRIS","UNIQ","WAPO","WOWS","YPAS",
]

NORMAL = [
    "BBCA","BBRI","BMRI","TLKM","ASII","UNVR","ADRO","PGAS","CPIN","ICBP",
    "INDF","SMGR","GGRM","KLBF","BYAN","ARTO","BREN","CUAN","AMMN","DOID",
    "ADMR","GOTO","BUKA","JPFA","LSIP","AALI","SIDO","WEGE","PTPP","WSKT",
]

def compute_zscore_version(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board):
    """Re-implement old Z-score approach within current framework."""
    liq_score, _ = gor._liquidity_risk(close, volume)
    cp = float(close[-1]) if len(close) > 0 else 0
    mcap_score, _ = gor._market_cap_risk(shares, cp)
    mom_score, _ = gor._momentum(close)
    vol_score, _ = gor._volume_anomaly(rvol_arr)
    vola_score, _ = gor._volatility(atr_arr)
    to_score, _ = gor._turnover_risk(volume, shares)
    gap_score, _ = gor._consecutive_gaps(open_, close)
    tg = max(to_score, gap_score)
    dist_score, _ = gor._distribution_risk(close, open_, high, low, volume)
    hist_score, _ = gor._historical_pump_and_dump_profile(high, low, close)

    weights = {"hist": 0.20, "liq": 0.20, "vol": 0.10, "mom": 0.10, "vola": 0.10,
               "mcap": 0.10, "tg": 0.10, "dist": 0.10}
    raw = (weights["hist"]*hist_score + weights["liq"]*liq_score + weights["vol"]*vol_score
           + weights["mom"]*mom_score + weights["vola"]*vola_score + weights["mcap"]*mcap_score
           + weights["tg"]*tg + weights["dist"]*dist_score)
    if board == "Pemantauan Khusus":
        raw += 10
    return float(np.clip(raw, 0, 100))

def compute_active_version(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board):
    """Current Active Pump version."""
    gor_result = gor.compute_gorengan(
        close=close, open_=open_, high=high, low=low, volume=volume,
        atr_arr=atr_arr, adx_arr=np.array([]), rvol_arr=rvol_arr,
        shares=shares, listing_board=board,
    )
    return gor_result["score"]

def compute_hybrid_version(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board):
    """Z-score default, fallback to raw threshold for high-baseline stocks.
    Stock dianggap high-baseline kalo RVOL rata-rata 60d > 1.5 atau
    ATR relatif > median saham sebaya.
    """
    # Deteksi high baseline
    rv = rvol_arr[~np.isnan(rvol_arr)]
    rvol_mean = float(np.mean(rv[-60:])) if len(rv) >= 60 else 0
    has_high_baseline = rvol_mean > 1.5

    if not has_high_baseline:
        return compute_zscore_version(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board)
    else:
        return compute_active_version(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board)

def score_stock(code, sec_map, version_fn):
    s = sec_map.get(code)
    shares = s.shares if s and s.shares else None
    board = s.listing_board if s else None
    try:
        bars = fetch_trading_info(code, length=400)
        if len(bars) < config.MIN_TRADING_DAYS:
            return None
        close = np.array([b.close for b in bars])
        open_ = np.array([b.open_price for b in bars])
        high = np.array([b.high for b in bars])
        low = np.array([b.low for b in bars])
        volume = np.array([b.volume for b in bars])
        atr_arr = ind.atr(high, low, close)
        rvol_arr = ind.rvol(volume, config.RVOL_WINDOW)
        score = version_fn(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board)
        return score
    except Exception:
        return None

def classify(score):
    if score > 65: return "EXTREME"
    if score > 45: return "HIGH"
    if score > 20: return "MEDIUM"
    return "LOW"

def print_table(rows, headers):
    col_widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_widths))
    for r in rows:
        print(fmt.format(*(str(x) for x in r)))

def worker(code, sec_map):
    z = score_stock(code, sec_map, compute_zscore_version)
    a = score_stock(code, sec_map, compute_active_version)
    h = score_stock(code, sec_map, compute_hybrid_version)
    return code, z, a, h

def main():
    securities = get_or_fetch_securities_list()
    sec_map = {s.code: s for s in securities}

    all_stocks = list(dict.fromkeys(UMA + NORMAL))  # unique, preserve order
    print(f"Scan {len(all_stocks)} stocks (45 UMA + 30 normal)...\n")

    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        fut_map = {ex.submit(worker, code, sec_map): code for code in all_stocks}
        for fut in as_completed(fut_map):
            code, z, a, h = fut.result()
            if z is None:
                print(f"  {code:6s} SKIP")
                continue
            results.append((code, z, a, h))
            print(f"  {code:6s} Z={z:5.1f}({classify(z):8s})  A={a:5.1f}({classify(a):8s})  H={h:5.1f}({classify(h):8s})")

    # Split into UMA vs normal
    uma_set, norm_set = set(UMA), set(NORMAL)
    uma_r = [r for r in results if r[0] in uma_set]
    norm_r = [r for r in results if r[0] in norm_set]

    print(f"\n{'='*100}")
    print("PERBANDINGAN 3 METODE: Z-score vs Active Pump vs Hybrid")
    print(f"{'='*100}")

    for label, group, is_uma in [("UMA (45 stocks)", uma_r, True), ("NORMAL (30 stocks)", norm_r, False)]:
        print(f"\n--- {label} ---")
        rows = []
        for method_name, idx in [("Z-score", 1), ("Active Pump", 2), ("Hybrid", 3)]:
            scores = [r[idx] for r in group]
            n = len(scores)
            ext = sum(1 for s in scores if s > 65)
            high = sum(1 for s in scores if s > 45)
            med = sum(1 for s in scores if s > 20)
            low = sum(1 for s in scores if s <= 20)
            rows.append((method_name, n, ext, high, med, low,
                         f"{ext/n*100:.1f}%" if n else "-",
                         f"{(ext+high)/n*100:.1f}%" if n else "-"))
        print_table(rows, ["Method", "N", "EXTREME", "HIGH", "MEDIUM", "LOW", "EXT%", "HIGH+%"])

    # Highlight specific stocks that differ
    print(f"\n{'='*100}")
    print("STOCKS WITH BIG METHOD DIFFERENCES (|Z - A| > 15)")
    print(f"{'='*100}")
    diff_rows = []
    for code, z, a, h in results:
        if abs(z - a) > 15:
            tag = "UMA" if code in uma_set else "NORM"
            diff_rows.append((code, tag, z, a, h, a - z))
    diff_rows.sort(key=lambda r: abs(r[5]), reverse=True)
    print_table(diff_rows[:20], ["Code", "Grp", "Z-score", "Active", "Hybrid", "A-Z"])

    # Summary table
    print(f"\n{'='*100}")
    print("SUMMARY TABLE")
    print(f"{'='*100}")
    sum_rows = []
    for method_name, idx in [("Z-score", 1), ("Active Pump", 2), ("Hybrid", 3)]:
        uma_scores = [r[idx] for r in uma_r]
        norm_scores = [r[idx] for r in norm_r]
        uma_high = sum(1 for s in uma_scores if s > 45)
        norm_high = sum(1 for s in norm_scores if s > 45)
        fp_rate = norm_high / len(norm_r) * 100 if norm_r else 0
        recall = uma_high / len(uma_r) * 100 if uma_r else 0
        sum_rows.append((method_name, len(uma_r), uma_high, f"{recall:.1f}%",
                         len(norm_r), norm_high, f"{fp_rate:.1f}%"))
    print_table(sum_rows, ["Method", "UMA-N", "UMA-HIGH+", "Recall", "Norm-N", "Norm-FP", "FP Rate"])

    # Precision estimate
    print(f"\n{'='*100}")
    print("PRECISION ESTIMATE (asumsi: UMA=positive, NORMAL=negative)")
    print(f"{'='*100}")
    prec_rows = []
    for method_name, idx in [("Z-score", 1), ("Active Pump", 2), ("Hybrid", 3)]:
        uma_high = sum(1 for r in uma_r if r[idx] > 45)
        norm_high = sum(1 for r in norm_r if r[idx] > 45)
        total_pos = uma_high + norm_high
        precision = uma_high / total_pos * 100 if total_pos > 0 else 0
        prec_rows.append((method_name, uma_high, norm_high, total_pos, f"{precision:.1f}%"))
    print_table(prec_rows, ["Method", "TP (UMA HIGH+)", "FP (NORM HIGH+)", "Total Positive", "Precision"])


if __name__ == "__main__":
    main()
