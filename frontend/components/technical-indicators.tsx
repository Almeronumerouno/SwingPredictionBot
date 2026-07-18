"use client";

import type { RawIndicators } from "@/types/api";

export default function TechnicalIndicators({ data }: { data: RawIndicators | null }) {
  if (!data) return null;

  const fmt = (val: number | null, dec = 2) => val !== null ? val.toFixed(dec) : "-";

  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6 shadow-sm mt-8">
      <h3 className="text-lg font-bold text-[var(--color-text-primary)] mb-6">Indikator Teknikal Lengkap</h3>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
        {/* RSI */}
        <div className="p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
          <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1 uppercase">RSI (14)</div>
          <div className="text-xl font-bold text-[var(--color-text-primary)]">{fmt(data.rsi)}</div>
          <div className="text-[10px] text-[var(--color-text-secondary)] mt-1">{data.rsi && data.rsi > 70 ? 'Overbought' : data.rsi && data.rsi < 30 ? 'Oversold' : 'Neutral'}</div>
        </div>

        {/* MFI */}
        <div className="p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
          <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1 uppercase">MFI (14)</div>
          <div className="text-xl font-bold text-[var(--color-text-primary)]">{fmt(data.mfi)}</div>
          <div className="text-[10px] text-[var(--color-text-secondary)] mt-1">{data.mfi && data.mfi > 80 ? 'Overbought' : data.mfi && data.mfi < 20 ? 'Oversold' : 'Neutral'}</div>
        </div>

        {/* ADX */}
        <div className="p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
          <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1 uppercase">ADX (14)</div>
          <div className="text-xl font-bold text-[var(--color-text-primary)]">{fmt(data.adx)}</div>
          <div className="text-[10px] text-[var(--color-text-secondary)] mt-1">
            +DI: {fmt(data.plus_di)} | -DI: {fmt(data.minus_di)}
          </div>
        </div>

        {/* ATR */}
        <div className="p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
          <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1 uppercase">ATR (14)</div>
          <div className="text-xl font-bold text-[var(--color-text-primary)]">{fmt(data.atr, 0)}</div>
          <div className="text-[10px] text-[var(--color-text-secondary)] mt-1">Volatilitas Harga</div>
        </div>

        {/* RVOL */}
        <div className="p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
          <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1 uppercase">RVOL (20)</div>
          <div className="text-xl font-bold text-[var(--color-text-primary)]">{fmt(data.rvol)}x</div>
          <div className="text-[10px] text-[var(--color-text-secondary)] mt-1">{data.rvol && data.rvol > 1.5 ? 'Volume Tinggi' : 'Volume Normal'}</div>
        </div>
        
        {/* EMA */}
        <div className="p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
          <div className="text-xs font-semibold text-[var(--color-text-muted)] mb-1 uppercase">EMA (10 / 25)</div>
          <div className="text-xl font-bold text-[var(--color-text-primary)]">{fmt(data.ema_fast, 0)}</div>
          <div className="text-[10px] text-[var(--color-text-secondary)] mt-1">EMA 25: {fmt(data.ema_slow, 0)}</div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        <div>
          <h4 className="text-sm font-bold text-[var(--color-text-secondary)] mb-3">Support & Resistance</h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <span className="text-sm font-medium text-[var(--color-text-muted)]">Resistance Terdekat</span>
              <span className="text-sm font-bold text-[var(--color-text-primary)]">{data.resistance ? data.resistance.toLocaleString('id-ID') : '-'}</span>
            </div>
            <div className="flex justify-between items-center p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <span className="text-sm font-medium text-[var(--color-text-muted)]">Support Terdekat</span>
              <span className="text-sm font-bold text-[var(--color-text-primary)]">{data.support ? data.support.toLocaleString('id-ID') : '-'}</span>
            </div>
          </div>
          
          {data.candlestick_patterns && data.candlestick_patterns.length > 0 && (
            <div className="mt-6">
              <h4 className="text-sm font-bold text-[var(--color-text-secondary)] mb-3">Pola Candlestick Harian</h4>
              <div className="flex flex-wrap gap-2">
                {data.candlestick_patterns.map((pattern, i) => (
                  <span key={i} className="px-3 py-1 bg-[var(--color-primary)]/10 text-[var(--color-primary)] border border-[var(--color-primary)]/20 rounded-full text-xs font-bold">
                    {pattern}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {data.fibonacci && (
          <div>
            <h4 className="text-sm font-bold text-[var(--color-text-secondary)] mb-3">Fibonacci Levels</h4>
            <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg overflow-hidden">
              <table className="w-full text-sm text-left">
                <tbody>
                  {["100.0%", "61.8%", "50.0%", "38.2%", "0.0%"].map((ratio) => {
                    const val = data.fibonacci?.[ratio];
                    if (val === undefined) return null;
                    return (
                      <tr key={ratio} className="border-b border-[var(--color-border)] last:border-0">
                        <td className="px-4 py-2 font-medium text-[var(--color-text-muted)]">{ratio}</td>
                        <td className="px-4 py-2 font-bold text-[var(--color-text-primary)] text-right">{Math.round(val).toLocaleString('id-ID')}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
