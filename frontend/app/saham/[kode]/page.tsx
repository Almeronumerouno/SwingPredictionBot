import { notFound } from "next/navigation";
import { fetchAnalisis } from "@/lib/api/analisis";
import { fetchHistory } from "@/lib/api/history";
import type { AnalisisResponse, HistoryResponse } from "@/types/api";
import ScoreCard from "@/components/score-card";
import TradePlanCard from "@/components/trade-plan-card";
import PriceChart from "@/components/price-chart";
import CapitalControl from "./capital-control";
import BackButton from "@/components/back-button";
import TechnicalIndicators from "@/components/technical-indicators";
import { Suspense } from "react";

import DownloadPdfButton from "@/components/download-pdf-button";

const fmt = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
const fmtDate = (d: string) => {
  const [y, m, day] = d.split("-");
  const months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
  return `${parseInt(day)} ${months[parseInt(m) - 1]} ${y}`;
};

export const dynamic = 'force-dynamic';

export default async function SahamPage({
  params,
  searchParams,
}: {
  params: Promise<{ kode: string }>;
  searchParams: Promise<{ capital?: string; length?: string; date?: string }>;
}) {
  const { kode } = await params;
  const sp = await searchParams;

  let analisis: AnalisisResponse;
  let history: HistoryResponse;

  try {
    [analisis, history] = await Promise.all([
      fetchAnalisis(kode, sp.capital ? Number(sp.capital) : undefined, sp.date),
      fetchHistory(kode, sp.length ? Number(sp.length) : undefined, sp.date),
    ]);
  } catch {
    notFound();
  }

  const s = analisis.score;
  const rekomendasi = s.recommendation || "N/A";

  const chartData = history.bars.map((b) => ({
    time: b.date,
    open: b.open,
    high: b.high,
    low: b.low,
    close: b.close,
  }));

  // Calculate price change
  const bars = history.bars;
  const lastClose = bars.length > 0 ? bars[bars.length - 1].close : 0;
  const prevClose = bars.length > 1 ? bars[bars.length - 2].close : lastClose;
  const priceChange = lastClose - prevClose;
  const pctChange = prevClose ? (priceChange / prevClose) * 100 : 0;

  return (
    <>
      {/* Top Navigation */}
      <div className="mb-6 no-print">
        <BackButton />
      </div>

      <div id="pdf-content" className="bg-[var(--color-bg)] pb-2 print:bg-white print:text-black">
        {/* Header */}
        <header className="mb-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-4xl font-extrabold tracking-tight text-[var(--color-text-primary)]">{kode}</h1>
                <span className={`px-2.5 py-1 text-xs font-bold uppercase tracking-wider rounded-md border ${rekomendasi === "BUY" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : rekomendasi === "SELL" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                  {rekomendasi}
                </span>
              </div>
              <p className="text-base font-medium text-[var(--color-text-secondary)] mt-1.5">{analisis.nama}</p>
            </div>
            <div className="md:text-right flex flex-col md:items-end">
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Harga Terakhir, <span className="font-semibold uppercase">{fmtDate(analisis.last_updated)}</span></p>
              <div className="flex items-baseline gap-3 md:justify-end mb-2">
                <p className="text-3xl font-bold tabular-nums tracking-tight text-[var(--color-text-primary)]">{fmt(analisis.harga)}</p>
                <span className={`text-sm font-bold tabular-nums ${priceChange >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                  {priceChange >= 0 ? "▲" : "▼"} {Math.abs(pctChange).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </header>



      {/* Score Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <ScoreCard
          label="Swing Score"
          value={s.swing_score != null ? s.swing_score.toFixed(1) : "-"}
          sub={s.swing_score != null ? (s.swing_score >= 70 ? "Sangat Bagus" : s.swing_score >= 50 ? "Cukup Baik" : s.swing_score >= 30 ? "Lemah" : "Sangat Lemah") : undefined}
          positive={s.swing_score != null && s.swing_score >= 70}
          negative={s.swing_score != null && s.swing_score <= 35}
        />
        <ScoreCard
          label="Gorengan Score"
          value={analisis.gorengan ? analisis.gorengan.score.toFixed(0) : "-"}
          sub={analisis.gorengan ? (analisis.gorengan.level === "EXTREME" ? "Pump & Dump!" : analisis.gorengan.level === "HIGH" ? "Hati-hati" : analisis.gorengan.level === "MEDIUM" ? "Spekulatif" : "Normal") : undefined}
          positive={analisis.gorengan != null && analisis.gorengan.level === "LOW"}
          warning={analisis.gorengan != null && analisis.gorengan.level === "HIGH"}
          negative={analisis.gorengan != null && analisis.gorengan.level === "EXTREME"}
        />
        <ScoreCard
          label="Confidence"
          value={s.confidence || "-"}
          sub={s.confidence === "HIGH" ? "Sinyal kuat" : s.confidence === "LOW" ? "Kurang yakin" : "Standar"}
          positive={s.confidence === "HIGH"}
          negative={s.confidence === "LOW"}
        />
        <ScoreCard
          label="Risk Level"
          value={s.risk_level || "-"}
          sub={s.risk_level === "LOW" ? "Aman" : s.risk_level === "HIGH" ? "Hati-hati" : "Moderat"}
          positive={s.risk_level === "LOW"}
          negative={s.risk_level === "HIGH"}
        />
        <ScoreCard
          label="Data Valid"
          value={s.valid ? "Yes" : "No"}
          sub={s.valid ? "Data cukup" : "Data kurang"}
          positive={s.valid}
          negative={!s.valid}
        />
      </div>

      {/* Score Components */}
      {s.components && (
        <div className="border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm mb-8">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" /></svg>
            </div>
            <div>
              <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Komponen Skor</h2>
              <p className="text-xs text-[var(--color-text-muted)]">Breakdown kontribusi setiap aspek analisis</p>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { label: "Trend", value: s.components.trend, icon: <svg className="w-4 h-4 text-[var(--color-text-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg> },
              { label: "Momentum", value: s.components.momentum, icon: <svg className="w-4 h-4 text-[var(--color-text-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg> },
              { label: "Volume", value: s.components.volume, icon: <svg className="w-4 h-4 text-[var(--color-text-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg> },
              { label: "Price Action", value: s.components.price_action, icon: <svg className="w-4 h-4 text-[var(--color-text-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" /></svg> },
            ].map((c) => {
              const percentage = c.value * 100;
              const barColor = percentage >= 75 ? "bg-emerald-500" : percentage >= 50 ? "bg-amber-400" : percentage >= 25 ? "bg-orange-400" : "bg-red-400";
              const label = percentage >= 75 ? "Kuat" : percentage >= 50 ? "Cukup" : percentage >= 25 ? "Lemah" : "Sangat Lemah";
              const labelColor = percentage >= 75 ? "text-emerald-600" : percentage >= 50 ? "text-amber-600" : percentage >= 25 ? "text-orange-500" : "text-red-500";
              return (
                <div key={c.label}>
                  <div className="flex items-center gap-2 mb-2">
                    {c.icon}
                    <p className="text-xs font-semibold text-[var(--color-text-secondary)]">{c.label}</p>
                  </div>
                  <div className="flex items-baseline gap-2 mb-1.5">
                    <p className="text-xl font-bold tabular-nums text-[var(--color-text-primary)]">{percentage.toFixed(0)}%</p>
                    <span className={`text-[10px] font-bold ${labelColor}`}>{label}</span>
                  </div>
                  <div className="h-2 rounded-full bg-[var(--color-muted-bg)] overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-700 ease-out ${barColor}`} style={{ width: `${percentage.toFixed(0)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Chart + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 h-full">
          <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden h-full min-h-[400px]">
            <PriceChart data={chartData} />
          </div>
        </div>
        <div className="space-y-5">
          {analisis.trade_plan ? (
            <TradePlanCard plan={analisis.trade_plan} />
          ) : (
            <div className="border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm">
              <div className="flex flex-col items-center justify-center text-center py-4">
                <div className="w-12 h-12 rounded-xl bg-[var(--color-muted-bg)] flex items-center justify-center mb-3">
                  <svg className="w-5 h-5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <p className="text-sm font-bold text-[var(--color-text-primary)] mb-1">Tidak Ada Trade Plan</p>
                <p className="text-xs text-[var(--color-text-muted)]">Sinyal saat ini HOLD atau data tidak memenuhi syarat untuk membuat rencana trading.</p>
              </div>
            </div>
          )}
          <Suspense fallback={<div className="h-12 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <CapitalControl kode={kode} capital={sp.capital ? Number(sp.capital) : undefined} />
          </Suspense>
        </div>
      </div>

      {/* Technical Indicators */}
      <TechnicalIndicators data={analisis.raw_indicators} />

      {/* Download PDF (Bottom) */}
      <div className="mt-12 mb-4 flex justify-end no-print">
        <DownloadPdfButton targetId="pdf-content" fileName={`Swingbot-${kode}-${analisis.last_updated}`} />
      </div>

      {/* Footer spacing */}
      <div className="pb-8" />
      </div>
    </>
  );
}
