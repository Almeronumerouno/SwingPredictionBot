"""
Validasi Gorengan Engine — scan seluruh IDX + UMA stocks.
"""
import config
import numpy as np
import gorengan
import indicators as ind
from data_source.yahoo_client import fetch_trading_info
from data_source.gainers import get_or_fetch_securities_list

UMA_STOCKS = [
    "APII", "ARTA", "ASLI", "BBRM", "BHAT", "BIPP", "BISS", "BMSR",
    "BSML", "BTON", "BUVA", "CARE", "CASS", "CPRT", "DNYA", "ELIT",
    "ENVY", "ETWA", "FORU", "GAMA", "GOLD", "HADE", "IKBI", "INDO",
    "KOTA", "LRNA", "META", "MINA", "MITI", "MPRO", "MTFN", "NEST",
    "NEXA", "NPGF", "OCAP", "OPMS", "PAMG", "PANG", "PBSA", "PURI",
    "RAPC", "RELI", "RISE", "ROTI", "SCBD", "SDPC", "SOSS", "SULI",
    "TAMA", "TIRT", "TRIO", "TRIS", "UNIQ", "WAPO", "WOWS", "YPAS",
]

CONTROL_STOCKS = [
    "BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "ADRO", "BYAN",
    "PGAS", "CPIN", "ICBP", "INDF", "SMGR", "GGRM", "KLBF",
]


def analyze_stock_gorengan(kode: str, shares: float | None = None, board: str | None = None):
    bars = fetch_trading_info(kode, length=config.HISTORY_LOOKBACK_DAYS)
    if len(bars) < config.MIN_TRADING_DAYS:
        return None
    close = np.array([b.close for b in bars])
    open_ = np.array([b.open_price for b in bars])
    high = np.array([b.high for b in bars])
    low = np.array([b.low for b in bars])
    volume = np.array([b.volume for b in bars])
    atr_val = ind.atr(high, low, close)
    adx_val = ind.adx(high, low, close)
    rvol_val = ind.rvol(volume, config.RVOL_WINDOW)
    return gorengan.compute_gorengan(
        close=close, open_=open_, high=high, low=low, volume=volume,
        atr_arr=atr_val, adx_arr=adx_val["adx"],
        rvol_arr=rvol_val, shares=shares, listing_board=board,
    )


def main():
    securities = get_or_fetch_securities_list()
    sec_map = {s.code: s for s in securities}

    all_codes = [s.code for s in securities]
    subsample = UMA_STOCKS + CONTROL_STOCKS

    print(f"\n{'='*80}")
    print(f"VALIDASI GORENGAN — {len(subsample)} saham")
    print(f"{'='*80}\n")

    results = []
    for code in subsample:
        s = sec_map.get(code)
        shares = s.shares if s and s.shares else None
        board = s.listing_board if s else None
        res = analyze_stock_gorengan(code, shares, board)
        if res is None:
            print(f"  {code:6s} — SKIP (data insufficient)")
            continue
        results.append((code, board or "", res))

    by_level = {}
    for code, board, r in results:
        level = r["level"]
        by_level.setdefault(level, []).append(code)

    print(f"\n{'='*80}")
    print(f"DISTRIBUSI LEVEL ({len(results)} saham):")
    print(f"{'='*80}")
    for level in ["EXTREME", "HIGH", "MEDIUM", "LOW"]:
        lst = by_level.get(level, [])
        print(f"  {level:8s}: {len(lst):3d} saham ({len(lst)/len(results)*100:.1f}%)")

    print(f"\n{'='*80}")
    print(f"TOP SCORES (HIGH + EXTREME + MEDIUM):")
    print(f"{'='*80}")
    top = [r for r in results if r[2]["level"] in ("EXTREME", "HIGH", "MEDIUM")]
    top.sort(key=lambda t: t[2]["score"], reverse=True)
    for code, board, r in top:
        f = r["factors"]
        print(f"  {code:6s} [{board:22s}] {r['level']:8s} score={r['score']:5.1f}"
              f"  active={f['active_pump']:4.1f}  hist={f['historical_pump_dump_risk']:4.1f}"
              f"  mcap={f['market_cap_risk']:4.1f}  liq={f['liquidity_risk']:4.1f}")

    print(f"\n{'='*80}")
    print(f"LOW SCORES:")
    print(f"{'='*80}")
    low = [r for r in results if r[2]["level"] == "LOW"]
    low.sort(key=lambda t: t[2]["score"])
    for code, board, r in low[:20]:
        f = r["factors"]
        print(f"  {code:6s} [{board:22s}] score={r['score']:5.1f}"
              f"  active={f['active_pump']:4.1f}  hist={f['historical_pump_dump_risk']:4.1f}")

    uma_codes = set(UMA_STOCKS)
    control_codes = set(CONTROL_STOCKS)
    uma_results = [r for r in results if r[0] in uma_codes]
    control_results = [r for r in results if r[0] in control_codes]

    print(f"\n{'='*80}")
    print(f"UMA STOCKS ({len(uma_results)} saham):")
    print(f"{'='*80}")
    uma_by_level = {}
    for code, board, r in uma_results:
        uma_by_level.setdefault(r["level"], []).append(code)
    for level in ["EXTREME", "HIGH", "MEDIUM", "LOW"]:
        lst = uma_by_level.get(level, [])
        pct = len(lst)/len(uma_results)*100 if uma_results else 0
        print(f"  {level:8s}: {len(lst):3d}/{len(uma_results):3d} ({pct:.1f}%) — {', '.join(lst[:8])}{'...' if len(lst)>8 else ''}")

    print(f"\n{'='*80}")
    print(f"CONTROL STOCKS ({len(control_results)} saham):")
    print(f"{'='*80}")
    for code, board, r in sorted(control_results, key=lambda t: t[2]["score"], reverse=True):
        f = r["factors"]
        print(f"  {code:6s} [{board:22s}] {r['level']:8s} score={r['score']:5.1f}"
              f"  active={f['active_pump']:4.1f}  hist={f['historical_pump_dump_risk']:4.1f}")

    print(f"\n{'='*80}")
    print(f"SUMMARY:")
    print(f"  UMA HIGH+  : {len(uma_by_level.get('EXTREME',[])) + len(uma_by_level.get('HIGH',[]))}/{len(uma_results)} ({100*(len(uma_by_level.get('EXTREME',[])) + len(uma_by_level.get('HIGH',[])))/len(uma_results):.1f}%)")
    print(f"  UMA MEDIUM+: {len(uma_results) - len(uma_by_level.get('LOW',[]))}/{len(uma_results)} ({100*(len(uma_results) - len(uma_by_level.get('LOW',[])))/len(uma_results):.1f}%)")
    print(f"  Control HIGH: {len([r for r in control_results if r[2]['level'] in ('HIGH','EXTREME')])}/{len(control_results)}")


if __name__ == "__main__":
    main()
