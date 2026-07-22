"use client";

import type { RawIndicators } from "@/types/api";
import CandlestickPatterns from "./candlestick-patterns";

function SignalBadge({ label, signal }: { label: string; signal: "bullish" | "bearish" | "neutral" | "strong_bullish" | "strong_bearish" }) {
  const styles = {
    strong_bullish: "bg-emerald-50 text-emerald-700 border-emerald-200",
    bullish: "bg-emerald-50/60 text-emerald-600 border-emerald-100",
    bearish: "bg-red-50/60 text-red-600 border-red-100",
    strong_bearish: "bg-red-50 text-red-700 border-red-200",
    neutral: "bg-slate-50 text-slate-500 border-slate-200",
  };
  const icons = {
    strong_bullish: "▲▲",
    bullish: "▲",
    bearish: "▼",
    strong_bearish: "▼▼",
    neutral: "●",
  };
  const labels = {
    strong_bullish: "Strong Bullish",
    bullish: "Bullish",
    bearish: "Bearish",
    strong_bearish: "Strong Bearish",
    neutral: "Neutral",
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold rounded-full border ${styles[signal]}`}>
      <span>{icons[signal]}</span>
      {labels[signal]}
    </span>
  );
}

function GaugeBar({ value, min, max, zones }: { value: number; min: number; max: number; zones: { from: number; to: number; color: string }[] }) {
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  // Determine which zone the value falls in for the fill color
  let fillColor = "bg-slate-400";
  for (const z of zones) {
    if (value >= z.from && value <= z.to) {
      fillColor = z.color;
      break;
    }
  }

  return (
    <div className="mt-4 mb-2">
      {/* Bar container */}
      <div className="relative h-2.5 rounded-full bg-[var(--color-muted-bg)] overflow-hidden">
        {/* Zone backgrounds */}
        {zones.map((z, i) => {
          const left = ((z.from - min) / (max - min)) * 100;
          const width = ((z.to - z.from) / (max - min)) * 100;
          return <div key={i} className={`absolute h-full ${z.color} opacity-20`} style={{ left: `${left}%`, width: `${width}%` }} />;
        })}
        {/* Active fill up to current value */}
        <div className={`absolute h-full rounded-full ${fillColor} transition-all duration-700 ease-out`} style={{ width: `${pct}%` }} />
      </div>
      {/* Pointer triangle */}
      <div className="relative h-2" style={{ marginTop: "4px" }}>
        <div
          className="absolute transition-all duration-700 ease-out"
          style={{ left: `${pct}%`, transform: "translateX(-50%)" }}
        >
          <svg width="10" height="6" viewBox="0 0 10 6" className="text-[var(--color-text-primary)]">
            <polygon points="5,0 10,6 0,6" fill="currentColor" />
          </svg>
        </div>
      </div>
    </div>
  );
}

function getRsiSignal(v: number): "strong_bullish" | "bullish" | "bearish" | "strong_bearish" | "neutral" {
  if (v <= 20) return "strong_bullish";
  if (v <= 30) return "bullish";
  if (v >= 80) return "strong_bearish";
  if (v >= 70) return "bearish";
  return "neutral";
}
function getMfiSignal(v: number) {
  if (v <= 15) return "strong_bullish" as const;
  if (v <= 20) return "bullish" as const;
  if (v >= 85) return "strong_bearish" as const;
  if (v >= 80) return "bearish" as const;
  return "neutral" as const;
}
function getAdxSignal(adx: number, pdi: number, mdi: number) {
  if (adx < 20) return "neutral" as const;
  if (pdi > mdi) return adx > 40 ? "strong_bullish" as const : "bullish" as const;
  return adx > 40 ? "strong_bearish" as const : "bearish" as const;
}
function getEmaSignal(fast: number, slow: number) {
  const diff = ((fast - slow) / slow) * 100;
  if (diff > 2) return "strong_bullish" as const;
  if (diff > 0) return "bullish" as const;
  if (diff < -2) return "strong_bearish" as const;
  if (diff < 0) return "bearish" as const;
  return "neutral" as const;
}
function getRvolSignal(v: number) {
  if (v >= 2) return "strong_bullish" as const;
  if (v >= 1.3) return "bullish" as const;
  if (v <= 0.5) return "bearish" as const;
  return "neutral" as const;
}

export default function TechnicalIndicators({ data }: { data: RawIndicators | null }) {
  if (!data) return null;

  const fmt = (val: number | null, dec = 2) => val !== null ? val.toFixed(dec) : "-";
  const fmtIDR = (val: number | null) => val !== null ? Math.round(val).toLocaleString("id-ID") : "-";

  const rsiZones = [
    { from: 0, to: 30, color: "bg-emerald-500" },
    { from: 30, to: 70, color: "bg-slate-400" },
    { from: 70, to: 100, color: "bg-red-500" },
  ];
  const mfiZones = [
    { from: 0, to: 20, color: "bg-emerald-500" },
    { from: 20, to: 80, color: "bg-slate-400" },
    { from: 80, to: 100, color: "bg-red-500" },
  ];
  const adxZones = [
    { from: 0, to: 20, color: "bg-slate-400" },
    { from: 20, to: 40, color: "bg-amber-500" },
    { from: 40, to: 100, color: "bg-emerald-500" },
  ];

  const rsiSig = data.rsi !== null ? getRsiSignal(data.rsi) : "neutral";
  const mfiSig = data.mfi !== null ? getMfiSignal(data.mfi) : "neutral";
  const adxSig = data.adx !== null && data.plus_di !== null && data.minus_di !== null ? getAdxSignal(data.adx, data.plus_di, data.minus_di) : "neutral";
  const emaSig = data.ema_fast !== null && data.ema_slow !== null ? getEmaSignal(data.ema_fast, data.ema_slow) : "neutral";
  const rvolSig = data.rvol !== null ? getRvolSignal(data.rvol) : "neutral";

  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-sm mt-6 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[var(--color-border)] flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
        </div>
        <div>
          <h3 className="text-sm font-bold text-[var(--color-text-primary)]">Indikator Teknikal</h3>
          <p className="text-xs text-[var(--color-text-muted)]">Analisis sinyal momentum, tren, dan volatilitas</p>
        </div>
      </div>

      <div className="p-6">
        {/* Momentum & Oscillator Section */}
        <div className="mb-8">
          <h4 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Momentum & Oscillator</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* RSI */}
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase">RSI (14)</span>
                <SignalBadge label="RSI" signal={rsiSig} />
              </div>
              <div className="text-2xl font-bold tabular-nums text-[var(--color-text-primary)]">{fmt(data.rsi)}</div>
              {data.rsi !== null && <GaugeBar value={data.rsi} min={0} max={100} zones={rsiZones} />}
              <div className="flex justify-between mt-1.5 text-[9px] text-[var(--color-text-muted)]">
                <span>Oversold</span><span>Overbought</span>
              </div>
            </div>

            {/* MFI */}
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase">MFI (14)</span>
                <SignalBadge label="MFI" signal={mfiSig} />
              </div>
              <div className="text-2xl font-bold tabular-nums text-[var(--color-text-primary)]">{fmt(data.mfi)}</div>
              {data.mfi !== null && <GaugeBar value={data.mfi} min={0} max={100} zones={mfiZones} />}
              <div className="flex justify-between mt-1.5 text-[9px] text-[var(--color-text-muted)]">
                <span>Oversold</span><span>Overbought</span>
              </div>
            </div>

            {/* ADX */}
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase">ADX (14)</span>
                <SignalBadge label="ADX" signal={adxSig} />
              </div>
              <div className="text-2xl font-bold tabular-nums text-[var(--color-text-primary)]">{fmt(data.adx)}</div>
              {data.adx !== null && <GaugeBar value={data.adx} min={0} max={100} zones={adxZones} />}
              <div className="flex justify-between mt-1.5">
                <span className="text-[9px] text-emerald-600 font-semibold">+DI: {fmt(data.plus_di)}</span>
                <span className="text-[9px] text-red-500 font-semibold">−DI: {fmt(data.minus_di)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Trend & Volume Section */}
        <div className="mb-8">
          <h4 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Tren & Volume</h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* EMA */}
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase">EMA Cross</span>
                <SignalBadge label="EMA" signal={emaSig} />
              </div>
              <div className="mt-2 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-[var(--color-text-secondary)]">EMA 10</span>
                  <span className="text-sm font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIDR(data.ema_fast)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-[var(--color-text-secondary)]">EMA 25</span>
                  <span className="text-sm font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIDR(data.ema_slow)}</span>
                </div>
                {data.ema_fast !== null && data.ema_slow !== null && (
                  <div className="pt-2 border-t border-[var(--color-border)] flex justify-between items-center">
                    <span className="text-[10px] text-[var(--color-text-muted)]">Spread</span>
                    <span className={`text-xs font-bold ${data.ema_fast > data.ema_slow ? "text-emerald-600" : "text-red-500"}`}>
                      {data.ema_fast > data.ema_slow ? "+" : ""}{((data.ema_fast - data.ema_slow) / data.ema_slow * 100).toFixed(2)}%
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* RVOL */}
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase">RVOL (20)</span>
                <SignalBadge label="RVOL" signal={rvolSig} />
              </div>
              <div className="text-2xl font-bold tabular-nums text-[var(--color-text-primary)]">{fmt(data.rvol)}x</div>
              <div className="mt-4 mb-2 h-2.5 rounded-full bg-[var(--color-muted-bg)] overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${data.rvol && data.rvol >= 1.5 ? "bg-emerald-500" : data.rvol && data.rvol >= 1 ? "bg-amber-500" : "bg-slate-400"}`}
                  style={{ width: `${Math.min(100, (data.rvol || 0) * 40)}%` }}
                />
              </div>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-1.5">
                {data.rvol && data.rvol >= 2 ? "Volume sangat tinggi" : data.rvol && data.rvol >= 1.3 ? "Volume di atas rata-rata" : data.rvol && data.rvol <= 0.5 ? "Volume rendah" : "Volume normal"}
              </p>
            </div>

            {/* ATR */}
            <div className="p-4 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)]">
              <div className="flex justify-between items-start mb-1">
                <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase">ATR (14)</span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold rounded-full border bg-amber-50/60 text-amber-600 border-amber-100">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  Volatilitas
                </span>
              </div>
              <div className="text-2xl font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIDR(data.atr)}</div>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-2">Range harga harian rata-rata</p>
            </div>
          </div>
        </div>

        {/* Support / Resistance + Fibonacci */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* S/R */}
          <div>
            <h4 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Support & Resistance</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-red-50/40 border border-red-100">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md bg-red-100 flex items-center justify-center">
                    <svg className="w-3.5 h-3.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" /></svg>
                  </div>
                  <span className="text-sm font-medium text-[var(--color-text-secondary)]">Resistance</span>
                </div>
                <span className="text-sm font-bold tabular-nums text-red-600">{data.resistance ? fmtIDR(data.resistance) : "-"}</span>
              </div>
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-emerald-50/40 border border-emerald-100">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md bg-emerald-100 flex items-center justify-center">
                    <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" /></svg>
                  </div>
                  <span className="text-sm font-medium text-[var(--color-text-secondary)]">Support</span>
                </div>
                <span className="text-sm font-bold tabular-nums text-emerald-600">{data.support ? fmtIDR(data.support) : "-"}</span>
              </div>
            </div>
          </div>

          {/* Fibonacci */}
          {data.fibonacci && (
            <div>
              <h4 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Fibonacci Retracement</h4>
              <div className="rounded-xl border border-[var(--color-border)] overflow-hidden">
                {["100.0%", "61.8%", "50.0%", "38.2%", "0.0%"].map((ratio, i) => {
                  const val = data.fibonacci?.[ratio];
                  if (val === undefined) return null;
                  const barWidth = parseFloat(ratio);
                  const isKey = ratio === "61.8%" || ratio === "38.2%";
                  return (
                    <div key={ratio} className={`flex items-center justify-between px-4 py-2.5 ${i > 0 ? "border-t border-[var(--color-border)]" : ""} ${isKey ? "bg-amber-50/40" : "bg-[var(--color-bg)]"}`}>
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 rounded-full bg-[var(--color-muted-bg)] overflow-hidden">
                          <div className="h-full rounded-full bg-amber-400" style={{ width: `${barWidth}%` }} />
                        </div>
                        <span className={`text-xs font-semibold ${isKey ? "text-amber-700" : "text-[var(--color-text-muted)]"}`}>{ratio}</span>
                      </div>
                      <span className={`text-sm font-bold tabular-nums ${isKey ? "text-[var(--color-text-primary)]" : "text-[var(--color-text-secondary)]"}`}>{fmtIDR(val)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Candlestick Patterns */}
        {data.candlestick_patterns && data.candlestick_patterns.length > 0 && (
          <CandlestickPatterns 
            patterns={data.candlestick_patterns} 
            lastPrice={data.ema_fast || data.ema_slow || 0} 
            atr={data.atr} 
            realCandles={data.pattern_candles}
          />
        )}
      </div>
    </div>
  );
}
