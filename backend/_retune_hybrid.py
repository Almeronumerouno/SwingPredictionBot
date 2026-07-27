"""
Retune hybrid: test berbagai RVOL threshold buat trigger Active Pump fallback.
"""
import config
import numpy as np
import gorengan as gor
import indicators as ind
from data_source.yahoo_client import fetch_trading_info
from data_source.gainers import get_or_fetch_securities_list
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def compute_zscore(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board):
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
    w = {"hist": 0.20, "liq": 0.20, "vol": 0.10, "mom": 0.10, "vola": 0.10,
         "mcap": 0.10, "tg": 0.10, "dist": 0.10}
    raw = (w["hist"]*hist_score + w["liq"]*liq_score + w["vol"]*vol_score
           + w["mom"]*mom_score + w["vola"]*vola_score + w["mcap"]*mcap_score
           + w["tg"]*tg + w["dist"]*dist_score)
    if board == "Pemantauan Khusus":
        raw += 10
    return float(np.clip(raw, 0, 100))

def compute_active(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board):
    r = gor.compute_gorengan(close=close, open_=open_, high=high, low=low, volume=volume,
        atr_arr=atr_arr, adx_arr=np.array([]), rvol_arr=rvol_arr,
        shares=shares, listing_board=board)
    return r["score"]

def make_hybrid(rvol_mean_threshold):
    def hybrid(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board):
        rv = rvol_arr[~np.isnan(rvol_arr)]
        if len(rv) < 60:
            return compute_zscore(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board)
        baseline = float(np.mean(rv[-60:]))
        if baseline > rvol_mean_threshold:
            return compute_active(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board)
        return compute_zscore(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board)
    return hybrid

def score_stock(code, sec_map, fn):
    s = sec_map.get(code)
    shares = s.shares if s and s.shares else None
    board = s.listing_board if s else None
    try:
        bars = fetch_trading_info(code, length=400)
        if len(bars) < config.MIN_TRADING_DAYS: return None
        close = np.array([b.close for b in bars])
        open_ = np.array([b.open_price for b in bars])
        high = np.array([b.high for b in bars])
        low = np.array([b.low for b in bars])
        volume = np.array([b.volume for b in bars])
        atr_arr = ind.atr(high, low, close)
        rvol_arr = ind.rvol(volume, config.RVOL_WINDOW)
        return fn(close, open_, high, low, volume, atr_arr, rvol_arr, shares, board)
    except Exception:
        return None

def worker(code, sec_map, fns):
    results = []
    for fn in fns:
        score = score_stock(code, sec_map, fn)
        if score is None:
            return None
        results.append(score)
    return (code, *results)

# Test Active + 4 hybrid variants
VARIANTS = {
    "Active Pump (full)": compute_active,
    "Hybrid RVOL>1.5": make_hybrid(1.5),
    "Hybrid RVOL>1.2": make_hybrid(1.2),
    "Hybrid RVOL>1.0": make_hybrid(1.0),
    "Hybrid RVOL>0.8": make_hybrid(0.8),
}
variant_keys = list(VARIANTS.keys())
variant_fns = list(VARIANTS.values())

def main():
    securities = get_or_fetch_securities_list()
    sec_map = {s.code: s for s in securities}
    all_stocks = list(dict.fromkeys(UMA + NORMAL))
    print(f"Scan {len(all_stocks)} stocks across {len(variant_keys)} variants...\n")

    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        fut_map = {ex.submit(worker, code, sec_map, variant_fns): code for code in all_stocks}
        for fut in as_completed(fut_map):
            r = fut.result()
            if r is None: continue
            results.append(r)
            print(f"  {r[0]:6s} " + "  ".join(f"{s:5.1f}" for s in r[1:]))

    uma_set, norm_set = set(UMA), set(NORMAL)
    uma_r = [r for r in results if r[0] in uma_set]
    norm_r = [r for r in results if r[0] in norm_set]

    print(f"\n{'='*120}")
    print(f"COMPARISON: Active Pump vs 4 Hybrid variants")
    print(f"{'='*120}")

    headers = ["Method"] + [f"v{i+1}" for i in range(len(variant_keys))]
    print(f"\n{'='*120}")
    print(f"RECALL @ HIGH+ (UMA = {len(uma_r)} stocks)")
    print(f"{'='*120}")
    rows = []
    for vi, name in enumerate(variant_keys):
        idx = vi + 1
        scores = [r[idx] for r in uma_r]
        high = sum(1 for s in scores if s > 45)
        ext = sum(1 for s in scores if s > 65)
        rows.append((name, ext, high, len(uma_r)-high, f"{high/len(uma_r)*100:.1f}%"))
    col_w = [max(len(str(r[i])) for r in rows + [["Method","EXT","HIGH+","LOW-","Recall"]]) for i in range(5)]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_w)
    print(fmt.format("Method","EXT","HIGH+","LOW-","Recall"))
    print(fmt.format(*["-"*w for w in col_w]))
    for r in rows: print(fmt.format(*r))

    print(f"\n{'='*120}")
    print(f"FALSE POSITIVE @ HIGH+ (NORMAL = {len(norm_r)} stocks)")
    print(f"{'='*120}")
    rows2 = []
    for vi, name in enumerate(variant_keys):
        idx = vi + 1
        scores = [r[idx] for r in norm_r]
        high = sum(1 for s in scores if s > 45)
        ext = sum(1 for s in scores if s > 65)
        rows2.append((name, ext, high, f"{high/len(norm_r)*100:.1f}%"))
    w2 = [max(len("Method"), max(len(r[0]) for r in rows2)),
          max(len("EXT"), 3),
          max(len("HIGH+"), 5),
          max(len("FP Rate"), 7)]
    fmt2 = "  ".join(f"{{:<{w}}}" for w in w2)
    print(fmt2.format("Method","EXT","HIGH+","FP Rate"))
    print(fmt2.format(*["-"*w for w in w2]))
    for r in rows2: print(fmt2.format(*r))

    print(f"\n{'='*120}")
    print(f"PRECISION (UMA=positive, NORMAL=negative)")
    print(f"{'='*120}")
    rows3 = []
    for vi, name in enumerate(variant_keys):
        idx = vi + 1
        uma_high = sum(1 for r in uma_r if r[idx] > 45)
        norm_high = sum(1 for r in norm_r if r[idx] > 45)
        total = uma_high + norm_high
        prec = uma_high / total * 100 if total else 0
        rows3.append((name, uma_high, norm_high, total, f"{prec:.1f}%"))
    print(fmt.format("Method","TP","FP","Total","Precision"))
    print(fmt.format(*["-"*w for w in col_w]))
    for r in rows3: print(fmt.format(*r))

    print(f"\n{'='*120}")
    print(f"BHAT SCORES PER VARIANT")
    print(f"{'='*120}")
    for b in [r for r in results if r[0] == "BHAT"]:
        for vi, name in enumerate(variant_keys):
            print(f"  {name:25s}: {b[vi+1]:.1f}")


if __name__ == "__main__":
    main()
