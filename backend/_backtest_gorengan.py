"""
Backtest: apakah gorengan HIGH+ pada tgl 1 Juli beneran prediksi dump
dalam 5/10/20 hari ke depan?
"""
import config
import numpy as np
import gorengan
import indicators as ind
from data_source.yahoo_client import fetch_trading_info
from data_source.gainers import get_or_fetch_securities_list

TARGET_DATE = "2026-07-01"
FORWARD_CHECK = [5, 10, 17]  # trading days to check forward (max 17 dari tgl 1 ke 24)

# Delisted/not-found di Yahoo (dari validasi sebelumnya)
DELISTED = {"BISS", "CPRT", "DNYA", "ENVY", "GAMA", "NEXA",
            "OCAP", "PANG", "RAPC", "SCBD", "TRIO"}

UMA_STOCKS = [
    "APII", "ARTA", "ASLI", "BBRM", "BHAT", "BIPP", "BMSR",
    "BSML", "BTON", "BUVA", "CARE", "CASS", "ELIT", "ETWA",
    "FORU", "GOLD", "HADE", "IKBI", "INDO", "KOTA", "LRNA",
    "META", "MINA", "MITI", "MPRO", "MTFN", "NEST", "NPGF",
    "OPMS", "PAMG", "PBSA", "PURI", "RELI", "RISE", "ROTI",
    "SDPC", "SOSS", "SULI", "TAMA", "TIRT", "TRIS", "UNIQ",
    "WAPO", "WOWS", "YPAS",
]

CONTROL_STOCKS = [
    "BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "ADRO", "BYAN",
    "PGAS", "CPIN", "ICBP", "INDF", "SMGR", "GGRM", "KLBF", "ARTO",
    "BREN", "CUAN", "AMMN", "DOID", "ADMR", "GOTO", "BUKA",
]


def find_split_idx(bars, target_date=TARGET_DATE):
    """Cari index terakhir yg <= target_date. Return (train_end, train_bars)."""
    for i, b in enumerate(bars):
        if b.date > target_date:
            return i, bars[:i]
    return len(bars), bars


def compute_max_drawdown(prices):
    """Max % drawdown dari peak ke trough dalam periode."""
    if len(prices) < 2:
        return 0.0, 0
    peak = prices[0]
    max_dd = 0.0
    max_dd_idx = 0
    for i, p in enumerate(prices):
        if p > peak:
            peak = p
        dd = (p - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd
            max_dd_idx = i
    return max_dd, max_dd_idx


def forward_hit_check(future_close, dump_threshold=-10):
    """Cek apakah forward prices menunjukkan dump."""
    max_dd, idx = compute_max_drawdown(future_close)
    hit = max_dd <= dump_threshold
    return hit, max_dd, idx


def gorengan_on_date(code, train_bars, shares=None, board=None):
    """Compute gorengan score using training data only."""
    if len(train_bars) < config.MIN_TRADING_DAYS:
        return None

    close = np.array([b.close for b in train_bars])
    open_ = np.array([b.open_price for b in train_bars])
    high = np.array([b.high for b in train_bars])
    low = np.array([b.low for b in train_bars])
    volume = np.array([b.volume for b in train_bars])

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

    all_codes = list(set(UMA_STOCKS + CONTROL_STOCKS))
    print(f"\n{'='*80}")
    print(f"BACKTEST GORENGAN — tgl {TARGET_DATE} -> 24 Juli ({FORWARD_CHECK[-1]} trading days forward)")
    print(f"Scan {len(all_codes)} saham (UMA + control + tambahan)")
    print(f"{'='*80}\n")

    results = []  # (code, gorengan_dict, forward_dict)
    for code in all_codes:
        try:
            bars = fetch_trading_info(code, length=450)
        except Exception:
            print(f"  {code:6s} — SKIP (fetch error)")
            continue

        split_idx, train_bars = find_split_idx(bars)
        future_bars = bars[split_idx:]

        if len(train_bars) < config.MIN_TRADING_DAYS:
            print(f"  {code:6s} — SKIP (cuma {len(train_bars)} train bars)")
            continue
        if len(future_bars) < FORWARD_CHECK[-1]:
            print(f"  {code:6s} — SKIP (cuma {len(future_bars)} future bars)")
            continue

        s = sec_map.get(code)
        shares = s.shares if s and s.shares else None
        board = s.listing_board if s else None

        gor = gorengan_on_date(code, train_bars, shares, board)
        if gor is None:
            continue

        # Forward performance
        future_close = np.array([b.close for b in future_bars])
        forward = {}
        for n in FORWARD_CHECK:
            prices_to_check = future_close[:n]
            hit, max_dd, idx = forward_hit_check(prices_to_check, dump_threshold=-10)
            forward[n] = {"hit": hit, "max_dd": round(max_dd, 1), "dd_idx": idx}

        results.append((code, shares, board, gor, forward))
        label = "UMA" if code in UMA_STOCKS else "CTRL"
        print(f"  {code:6s} [{label:4s}] {gor['level']:8s} score={gor['score']:5.1f}"
              f"  fwd_max_dd: {forward[FORWARD_CHECK[-1]]['max_dd']:6.1f}%"
              f"{' HIT!' if forward[FORWARD_CHECK[-1]]['hit'] else ''}")

    # Summary by gorengan level
    print(f"\n{'='*80}")
    print(f"SUMMARY BY GORENGAN LEVEL")
    print(f"{'='*80}")
    by_level = {}
    for code, shares, board, gor, fwd in results:
        lvl = gor["level"]
        by_level.setdefault(lvl, []).append((code, gor, fwd))

    for level in ["EXTREME", "HIGH", "MEDIUM", "LOW"]:
        group = by_level.get(level, [])
        if not group:
            continue
        print(f"\n--- {level} ({len(group)} stocks) ---")
        for n in FORWARD_CHECK:
            hits = sum(1 for _, _, f in group if f[n]["hit"])
            avg_dd = np.mean([f[n]["max_dd"] for _, _, f in group])
            print(f"  {n:2d}d forward: {hits:3d}/{len(group)} dumped ({hits/len(group)*100:5.1f}%)  avg max_dd={avg_dd:.1f}%")

    # Dump at >10% threshold
    N = FORWARD_CHECK[-1]
    print(f"\n{'='*80}")
    print(f"DUMP RATE BY GORENGAN LEVEL (10% threshold) — max forward {N}d")
    print(f"{'='*80}")
    print(f"{'Level':10s} {'Count':6s} {'5d dump':9s} {'10d dump':10s} {f'{N}d dump':9s}")
    for level in ["EXTREME", "HIGH", "MEDIUM", "LOW"]:
        group = by_level.get(level, [])
        if not group:
            continue
        hits_5 = sum(1 for _, _, f in group if f[5]["hit"])
        hits_10 = sum(1 for _, _, f in group if f[10]["hit"])
        hits_N = sum(1 for _, _, f in group if f[N]["hit"])
        n = len(group)
        print(f"{level:10s} {n:6d} {hits_5:3d}/{n:3d} ({hits_5/n*100:5.1f}%) {hits_10:3d}/{n:3d} ({hits_10/n*100:5.1f}%) {hits_N:3d}/{n:3d} ({hits_N/n*100:5.1f}%)")

    # Full table sorted by score descending
    print(f"\n{'='*80}")
    print(f"ALL STOCKS (sorted by gorengan score)")
    print(f"{'='*80}")
    results.sort(key=lambda t: t[3]["score"], reverse=True)
    for code, shares, board, gor, fwd in results:
        fwd_str = " | ".join([f"{n}d: {fwd[n]['max_dd']:5.1f}%{' DMP' if fwd[n]['hit'] else ''}" for n in FORWARD_CHECK])
        print(f"  {code:6s} {gor['level']:8s} score={gor['score']:5.1f}  {fwd_str}")


if __name__ == "__main__":
    main()
