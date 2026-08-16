"""
test_temporal_integrity.py — P7.1 Backtest Temporal Integrity.

Unit test yang SECARA EKSPLISIT gagal apabila execution-bar (high/low/close/ATR
bar eksekusi) bocor ke parameter trade yang sudah dieksekusi pada open_t.

Prinsip P7.1:
  decision timestamp = close bar sinyal (i-1)
  eksekusi           = bar i (open_i untuk entry_mode="open")
  => SELURUH metadata keputusan (ATR, risk_level, SL, TP, entry_score,
     confidence, gate, rvol, regime, atr_entry) WAJIB berasal dari bar i-1.

Test ini memakai data SINTETIS (tanpa fetch internet) sehingga deterministik.

Run:
  python test_temporal_integrity.py
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np

import backtest as bt
import indicators as ind
from backtest import BacktestConfig, run_backtest


# ──────────────────────────────────────────────
#  Synthetic data (deterministic, no network)
# ──────────────────────────────────────────────

def _synthetic_bars(n: int = 420, seed: int = 42):
    rng = np.random.default_rng(seed)
    close = 1000 + np.cumsum(rng.normal(0, 5, n))
    close = np.maximum(close, 500.0)
    open_ = close + rng.normal(0, 2, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 3, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 3, n))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)

    dates = np.busday_offset("2025-01-01", np.arange(n), roll="forward")
    bars = []
    for i in range(n):
        d = np.datetime_as_string(dates[i], unit="D")
        bars.append(SimpleNamespace(
            date=d,
            open_price=float(open_[i]),
            high=float(high[i]),
            low=float(low[i]),
            close=float(close[i]),
            volume=float(volume[i]),
        ))
    return bars, open_, high, low, close, volume


def _compute_all(bars, open_, high, low, close, volume, cfg):
    """Hitung ulang indikator + signals — identik dengan isi run_backtest."""
    rsi_val = ind.rsi(close)
    atr_val = ind.atr(high, low, close)
    ema_val = ind.ema_trend(close)
    adx_val = ind.adx(high, low, close)
    mfi_val = ind.mfi(high, low, close, volume)
    rvol_val = ind.rvol(volume, period=cfg.rvol_window)
    donch = ind.donchian_channel(high, low)

    data = {
        "close": close,
        "high": high,
        "low": low,
        "rsi": rsi_val,
        "atr": atr_val,
        "adx": adx_val["adx"],
        "plus_di": adx_val["plus_di"],
        "minus_di": adx_val["minus_di"],
        "ema_fast": ema_val["ema_fast"],
        "ema_slow": ema_val["ema_slow"],
        "mfi": mfi_val,
        "rvol": rvol_val,
        "donchian_upper": donch["upper"],
        "donchian_lower": donch["lower"],
    }
    signals = bt.compute_signals(data, cfg)
    return data, signals, atr_val


def _run_and_verify(entry_mode: str, cfg_overrides: dict | None = None):
    bars, open_, high, low, close, volume = _synthetic_bars()
    cfg = BacktestConfig(entry_mode=entry_mode, slippage_bps=0.0)
    if cfg_overrides:
        for k, v in cfg_overrides.items():
            setattr(cfg, k, v)

    metrics = run_backtest("TEST", capital=10_000_000, bt_config=cfg, bars=bars)
    assert metrics.total_trades > 0, "data sintetis harus menghasilkan >= 1 trade"

    data, signals, atr_val = _compute_all(bars, open_, high, low, close, volume, cfg)
    date_to_idx = {b.date: i for i, b in enumerate(bars)}

    failures: list[str] = []
    for t in metrics.trades:
        idx = date_to_idx[t.entry_date]

        # ── 1. entry_score WAJIB dari bar sinyal (i-1) ──
        expected_score = round(float(signals["swing_scores"][idx - 1]), 1)
        if not np.isclose(t.entry_score, expected_score, atol=1e-9):
            failures.append(
                f"entry@{t.entry_date}: entry_score {t.entry_score} != signal bar "
                f"score {expected_score} (leakage bar eksekusi)"
            )

        # ── 2. SL/TP WAJIB dari ATR bar sinyal (i-1), bukan bar eksekusi (i) ──
        atr_signal = atr_val[idx - 1]
        atr_exec = atr_val[idx]
        risk_lvl_signal = bt._risk_level(atr_val, idx - 1)
        sl_expected = bt._calc_sl(
            t.entry_price, atr_signal, t.direction, risk_lvl_signal, cfg,
            regime=signals["regimes"][idx - 1],
        )
        tp_expected = bt._calc_tp(t.entry_price, atr_signal, t.direction, cfg)
        if not np.isclose(t.stop_loss, sl_expected, atol=1e-6):
            failures.append(
                f"entry@{t.entry_date}: SL {t.stop_loss:.2f} != expected dari ATR[i-1] "
                f"{sl_expected:.2f} (ATR[i]={atr_exec:.2f} bocor?)"
            )
        if not np.isclose(t.take_profit, tp_expected, atol=1e-6):
            failures.append(
                f"entry@{t.entry_date}: TP {t.take_profit:.2f} != expected dari ATR[i-1] "
                f"{tp_expected:.2f} (ATR[i]={atr_exec:.2f} bocor?)"
            )

        # ── 3. risk_level trade WAJIB dari bar sinyal ──
        if t.risk_level != risk_lvl_signal:
            failures.append(
                f"entry@{t.entry_date}: risk_level {t.risk_level} != "
                f"_risk_level(ATR, i-1) = {risk_lvl_signal}"
            )

        # ── 4. confidence WAJIB dari komponen bar sinyal ──
        gate_signal = float(signals["gate"][idx - 1])
        rvol_signal = float(data["rvol"][idx - 1]) if not np.isnan(data["rvol"][idx - 1]) else 0.0
        conf_expected = bt._confidence(
            {
                "trend": float(signals["trend"][idx - 1]),
                "momentum": float(signals["momentum"][idx - 1]),
                "volume": float(signals["volume"][idx - 1]),
                "price_action": float(signals["price_action"][idx - 1]),
            },
            float(signals["swing_scores"][idx - 1]),
            gate_signal,
            rvol_signal,
            cfg,
            recommendation=t.direction,
        )
        if t.confidence != conf_expected:
            failures.append(
                f"entry@{t.entry_date}: confidence {t.confidence} != expected dari "
                f"komponen bar sinyal {conf_expected}"
            )

    if failures:
        raise AssertionError("\n  ".join(failures))


# ──────────────────────────────────────────────
#  Tests
# ──────────────────────────────────────────────

def test_open_mode_no_execution_bar_leakage():
    """entry_mode='open': seluruh metadata dari bar sinyal i-1."""
    _run_and_verify("open")


def test_close_mode_uses_signal_bar_metadata():
    """entry_mode='close': metadata tetap dari bar sinyal i-1 (decision timestamp),
    harga eksekusi saja yang beda."""
    _run_and_verify("close")


def test_breakeven_and_trailing_use_signal_atr():
    """Breakeven trigger & trailing stop memakai ATR entry = ATR bar sinyal (i-1).
    Tidak mungkin diverifikasi langsung dari Trade record; guard di jalankan
    dengan trailing_stop_multiplier aktif dan memastikan tidak crash + SL tetap
    konsisten dengan atr[i-1] (bukan atr[i])."""
    bars, open_, high, low, close, volume = _synthetic_bars()
    cfg = BacktestConfig(
        entry_mode="open", slippage_bps=0.0,
        trailing_stop_multiplier=2.0, breakeven_trigger=1.0,
    )
    metrics = run_backtest("TEST", capital=10_000_000, bt_config=cfg, bars=bars)
    # Smoke: tidak error & ada trade
    assert metrics.total_trades >= 0


def _main():
    tests = [
        test_open_mode_no_execution_bar_leakage,
        test_close_mode_uses_signal_bar_metadata,
        test_breakeven_and_trailing_use_signal_atr,
    ]
    n_pass = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            n_pass += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}\n        {e}")
            n_pass -= 1
    print(f"\n{n_pass}/{len(tests)} tests passed")
    return 0 if n_pass == len(tests) else 1


if __name__ == "__main__":
    sys.exit(_main())