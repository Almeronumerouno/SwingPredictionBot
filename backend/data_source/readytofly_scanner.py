"""
Scanner "Ready To Fly" — scan seluruh saham IDX untuk deteksi pola
akumulasi post-ARA (siap terbang atau hampir siap).
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np

import config
from recovery import detect_accumulation
from data_source.idx_client import fetch_all_securities
from data_source.idx_trading import IdxTradingError, fetch_daily_stock_summary
from data_source.yahoo_client import YahooClientError, fetch_trading_info

WIB = ZoneInfo("Asia/Jakarta")


@dataclass
class ReadyToFlyEntry:
    code: str
    name: str
    close: float
    pct_change: float
    status: str  # "ready" | "almost"
    density_pct: float | None
    k_heavy: int
    window_days: int
    ara_date: str | None
    ara_ref_price: float | None
    distance_pct: float | None
    sma20: float | None
    state_ma20: str | None
    max_rvol: float | None
    gates: dict | None
    note: str | None
    reason: str | None
    net_dist: float | None = None        # Net Distribution window post-ARA: [-1, +1]
    net_dist_heavy: float | None = None  # heavy-day Close>Open ratio: [0,1] (definisi TODO audit)
    acc_density: float | None = None     # k * net_dist_heavy / window: [0,1] (rombak TODO)
    post_ara_decay: float | None = None  # exp(-d/tau), cutoff d>=5: ranking freshness
    strength: float | None = None        # density * net_dist_heavy * decay (skor ranking RTF)
    adv_vol_20: float | None = None      # ADV 20 hari point-in-time (lembar, tanpa hari ARA)
    adv_val_20: float | None = None      # ADV 20 hari point-in-time (Rp, tanpa hari ARA)
    liquidity_ok: bool = True            # gate likuiditas (floor BEI, rombak TODO)
    liquidity_prima: bool = False        # flag display "likuiditas prima" (1jt lbr/Rp1M)
    sma_gap_pct: float | None = None     # (harga - SMA20)/SMA20 dalam %
    post_ara_volume: float | None = 0.0
    post_ara_value: float | None = 0.0


def _ensure_cache_dir() -> None:
    os.makedirs(config.CACHE_DIR, exist_ok=True)


def _get_cache_path(date_str: str) -> str:
    return os.path.join(config.CACHE_DIR, f"readytofly_{date_str}.json")


# Gate safety (wajib lolos utk status apa pun) vs gate kualitas (rombak fase 1
# audit v2 §15): READY = semua safety + semua quality; ALMOST = semua safety +
# minimal 2/3 quality. Sebelumnya ">=3 dari 5" bisa meloloskan ALMOST walaupun
# safety gate (below) gagal — saham yang sudah recovery/di atas level event
# tidak boleh muncul sebagai pola akumulasi.
QUALITY_GATES = ("density", "min_heavy", "above_ma")
SAFETY_GATES = ("below", "liquidity")


def _count_gates_passed(gates: dict | None, keys: tuple[str, ...]) -> int:
    """Count how many of the given gate keys are True."""
    if not gates:
        return 0
    return sum(1 for k in keys if gates.get(k))


def _fetch_and_check_one(
    code: str,
    name: str,
    daily_data: dict,
    target_date: Optional[str] = None,
    bars=None,
) -> Optional[ReadyToFlyEntry]:
    """Fetch history for one stock and run accumulation detection.
    bars bolehdiberikan dari luar (dipakai scan_all agar 1 fetch dipakai 3 analisis)."""
    try:
        if bars is None:
            bars = fetch_trading_info(
                code,
                length=config.RECOVERY_HISTORY_LOOKBACK_DAYS,
                target_date=target_date,
            )
        if len(bars) < config.RECOVERY_MIN_BARS:
            return None

        # P8 (keputusan user 16-08-2026): gate anti-repetisi AKTIF di produksi —
        # sinyal hari ke-RTF_MAX_STREAK_DAYS+1 berturut-turut di-invalidasi
        # (riset forensik Agu 2026; lihat config.RTF_MAX_STREAK_DAYS).
        accum = detect_accumulation(bars, apply_streak_gate=True)

        # Determine status — rombak fase 1 (audit v2 §15):
        #   READY  = semua safety (below, liquidity) + semua quality
        #            (density, min_heavy, above_ma) — sudah dihitung engine.
        #   ALMOST = semua safety + minimal 2/3 quality.
        is_ready = accum.get("ready_to_fly", False)
        gates = accum.get("gates")
        safety_ok = gates is not None and all(gates.get(k) for k in SAFETY_GATES)
        quality_ok = _count_gates_passed(gates, QUALITY_GATES) >= 2

        # Keep if ready OR almost (all safety + >=2/3 quality)
        if not is_ready and not (safety_ok and quality_ok):
            return None

        status = "ready" if is_ready else "almost"

        close_arr = [b.close for b in bars]
        close_now = float(close_arr[-1]) if close_arr else 0.0

        prev = float(daily_data.get("Previous", 0) or 0)
        c = float(daily_data.get("Close", close_now) or close_now)

        # Mode yahoo (scan_all dengan force_source="yahoo") tidak punya snapshot
        # IDX: daily_data cuma {StockCode, StockName}, jadi Previous/Close = 0 dan
        # pct_change bakal 0.00% semua. Fallback: hitung dari dua bar terakhir
        # Yahoo (harga mentah = % change riil pasar, konsisten dgn snapshot IDX).
        if not prev and len(bars) >= 2:
            raw = [(getattr(b, "raw_close", None) or b.close) for b in bars]
            prev, c = float(raw[-2]), float(raw[-1])

        pct = ((c - prev) / prev * 100.0) if prev else 0.0

        return ReadyToFlyEntry(
            code=code,
            name=name,
            close=c,
            pct_change=pct,
            status=status,
            density_pct=accum.get("density_pct"),
            k_heavy=accum.get("k_heavy", 0),
            window_days=accum.get("window_days", 0),
            ara_date=accum.get("ara_date"),
            ara_ref_price=accum.get("ara_ref_price"),
            distance_pct=accum.get("distance_pct"),
            net_dist=accum.get("net_dist"),
            net_dist_heavy=accum.get("net_dist_heavy"),
            acc_density=accum.get("acc_density"),
            post_ara_decay=accum.get("post_ara_decay"),
            strength=accum.get("strength"),
            adv_vol_20=accum.get("adv_vol_20"),
            adv_val_20=accum.get("adv_val_20"),
            liquidity_ok=accum.get("liquidity_ok", True),
            liquidity_prima=accum.get("liquidity_prima", False),
            sma_gap_pct=accum.get("sma_gap_pct"),
            sma20=accum.get("sma20"),
            state_ma20=accum.get("state_ma20"),
            max_rvol=accum.get("max_rvol"),
            gates=gates,
            note=accum.get("note"),
            reason=accum.get("reason"),
            post_ara_volume=accum.get("post_ara_volume", 0.0),
            post_ara_value=accum.get("post_ara_value", 0.0),
        )
    except Exception:
        return None


def scan_ready_to_fly(target_date: Optional[str] = None) -> list[ReadyToFlyEntry]:
    """
    Scan seluruh saham IDX untuk deteksi pola akumulasi post-ARA.
    Returns list of ReadyToFlyEntry (ready + almost ready).
    """
    scraped_at = datetime.now(WIB)

    # 1. Ambil daftar security
    securities = fetch_all_securities()
    sec_map = {s.code: s for s in securities}

    # 2. Ambil snapshot IDX harian
    if target_date:
        start = date.fromisoformat(target_date)
    else:
        start = date.today()

    raw = []
    for offset in range(config.IDX_FALLBACK_MAX_DAYS):
        d = start - timedelta(days=offset)
        date_str = d.strftime("%Y%m%d")
        try:
            raw = fetch_daily_stock_summary(date_str)
            if raw:
                break
        except Exception:
            pass

    if not raw:
        print("[WARN] Gagal mendapatkan snapshot harian, akan mencoba full scan.")
        raw = [{"StockCode": s.code, "StockName": s.name} for s in securities]

    # Filter stocks with active volume
    active_stocks = []
    for item in raw:
        code = str(item.get("StockCode", "")).strip()
        vol = float(item.get("Volume", 0) or 0)
        if code and (vol > 0 or "Volume" not in item):
            active_stocks.append(item)

    results: list[ReadyToFlyEntry] = []

    # 3. Scan paralel
    with ThreadPoolExecutor(max_workers=config.SCAN_MAX_WORKERS) as executor:
        futures = {}
        for item in active_stocks:
            code = str(item.get("StockCode", "")).strip()
            name = str(item.get("StockName", "") or "")
            futures[
                executor.submit(_fetch_and_check_one, code, name, item, target_date)
            ] = code

        for future in as_completed(futures):
            entry = future.result()
            if entry is not None:
                results.append(entry)

    # Sort: ready first (urutkan strength = density*net_dist_heavy*decay kesegaran),
    # lalu almost by density descending. Decay membuat sinyal lama (d>=5) di bawah
    # sinyal segar — ranking = kesegaran pola, bukan hanya kepadatan volume.
    def _sort_key(x: ReadyToFlyEntry):
        score = x.strength if x.status == "ready" else (x.density_pct or 0.0)
        return (0 if x.status == "ready" else 1, -(score or 0.0))

    results.sort(key=_sort_key)

    # 4. Cache
    _ensure_cache_dir()
    file_date = target_date or scraped_at.date().isoformat()
    path = _get_cache_path(file_date)
    payload = {
        "scraped_at": scraped_at.isoformat(),
        "data": [asdict(e) for e in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return results


def get_cached_ready_to_fly(for_date: Optional[str] = None) -> Optional[dict]:
    for_date = for_date or datetime.now(WIB).date().isoformat()
    path = _get_cache_path(for_date)

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    data_rows = []
    for row in raw.get("data", []):
        row.setdefault("post_ara_volume", None)
        row.setdefault("post_ara_value", None)
        data_rows.append(ReadyToFlyEntry(**row))

    return {
        "scraped_at": raw["scraped_at"],
        "data": data_rows,
    }
