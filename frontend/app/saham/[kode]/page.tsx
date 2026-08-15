import { notFound } from "next/navigation";
import { fetchAnalisis } from "@/lib/api/analisis";
import { fetchHistory } from "@/lib/api/history";
import { fetchRecovery } from "@/lib/api/recovery";
import type { AnalisisResponse, HistoryResponse, RecoveryResponse } from "@/types/api";
import ScoreCard from "@/components/score-card";
import TradePlanCard from "@/components/trade-plan-card";
import PriceChart from "@/components/price-chart";
import CapitalControl from "./capital-control";
import RecoveryDropControl from "@/components/recovery-drop-control";
import RecoveryCard from "@/components/recovery-card";
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
const fmtTime = (iso?: string, delayed?: boolean) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  if (delayed) d.setMinutes(d.getMinutes() - 15);
  return `${d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })} WIB`;
};

export const dynamic = 'force-dynamic';

export default async function SahamPage({
  params,
  searchParams,
}: {
  params: Promise<{ kode: string }>;
  searchParams: Promise<{ capital?: string; length?: string; date?: string; drop_pct?: string; ref_days?: string }>;
}) {
  const { kode } = await params;
  const sp = await searchParams;

  let analisis: AnalisisResponse;
  let history: HistoryResponse;
  let recovery: RecoveryResponse | null = null;

  try {
    [analisis, history] = await Promise.all([
      fetchAnalisis(kode, sp.capital ? Number(sp.capital) : undefined, sp.date),
      fetchHistory(kode, sp.length ? Number(sp.length) : undefined, sp.date),
    ]);
  } catch {
    notFound();
  }

  try {
    recovery = await fetchRecovery(
      kode,
      sp.drop_pct ? Number(sp.drop_pct) : undefined,
      sp.date,
      sp.ref_days ? Number(sp.ref_days) : undefined,
    );
  } catch {
    recovery = null;
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
                <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-[var(--color-text-primary)]">{kode}</h1>
                <span className={`px-2 py-1 text-xs font-bold tabular-nums tracking-wide rounded border ${rekomendasi === "BUY" ? "bg-[var(--color-up-bg)] text-[var(--color-up)] border-[var(--color-up)]/20" : rekomendasi === "SELL" ? "bg-[var(--color-down-bg)] text-[var(--color-down)] border-[var(--color-down)]/20" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                  {rekomendasi}
                </span>
              </div>
              <p className="text-sm sm:text-base font-medium text-[var(--color-text-secondary)] mt-1.5">{analisis.nama}</p>
            </div>
            <div className="md:text-right flex flex-col md:items-end">
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
                Harga Terakhir, <span className="font-semibold uppercase">{fmtDate(analisis.last_updated)}</span>
              </p>
              <div className="flex items-baseline gap-3 md:justify-end mb-2">
                <p className="text-2xl sm:text-3xl font-bold tabular-nums tracking-tight text-[var(--color-text-primary)]">{fmt(analisis.harga)}</p>
                <span className={`text-sm font-bold tabular-nums ${priceChange >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>
                  <svg className="w-3.5 h-3.5 inline mr-0.5 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {priceChange >= 0 ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                    )}
                  </svg>
                  {Math.abs(pctChange).toFixed(2)}%
                </span>
              </div>
              {analisis.data_delayed !== false && (
                <p className="text-[11px] text-[var(--color-text-muted)] flex items-center gap-1.5 md:justify-end no-print">
                  <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Data dari Yahoo Finance
                  {analisis.fetched_at
                    ? ` diambil ${fmtTime(analisis.fetched_at)} (delay ±15 mnt → data ~${fmtTime(analisis.fetched_at, true)}), bukan live.`
                    : `, delay ±15 menit dari harga real-time, bukan data live.`}
                </p>
              )}
            </div>
          </div>
        </header>



      {/* Score Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 sm:gap-4 mb-6 sm:mb-8">
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

      {/* Fundamental Context (F3.6) — terpisah dari skor, tanpa penalty */}
      {analisis.fundamental_status && (
        <div className="border border-[var(--color-border)] rounded-xl p-4 sm:p-6 bg-[var(--color-surface)] shadow-sm mb-6 sm:mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
            </div>
            <div className="mr-auto">
              <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Fundamental Context</h2>
              <p className="text-xs text-[var(--color-text-muted)]">Konteks risiko fundamental — TIDAK memengaruhi skor</p>
            </div>
            {(() => {
              const st = analisis.fundamental_status || "";
              const meta: Record<string, { cls: string; sub: string }> = {
                HEALTHY: { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", sub: "Data cukup, tanpa flag material" },
                NEUTRAL: { cls: "bg-slate-100 text-slate-600 border-slate-200", sub: "Data parsial, tanpa flag material" },
                RISK: { cls: "bg-red-50 text-red-700 border-red-200", sub: "Ada flag risiko fundamental" },
                UNKNOWN: { cls: "bg-slate-50 text-slate-500 border-slate-200", sub: "Data fundamental tidak cukup" },
              };
              const m = meta[st] || meta.UNKNOWN;
              return (
                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 text-xs font-bold tracking-wide rounded border ${m.cls}`}>{st}</span>
                  {analisis.fundamental_meta?.data_quality && (
                    <span className={`px-2 py-1 text-[10px] font-bold tracking-wide rounded border ${
                      analisis.fundamental_meta.data_quality === "GOOD" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : analisis.fundamental_meta.data_quality === "PARTIAL" ? "bg-amber-50 text-amber-700 border-amber-200"
                      : "bg-slate-100 text-slate-500 border-slate-200"
                    }`}>
                      Data {analisis.fundamental_meta.data_quality}
                    </span>
                  )}
                </div>
              );
            })()}
          </div>
          <p className="text-xs text-[var(--color-text-muted)] mb-4">{(() => {
            const st = analisis.fundamental_status || "";
            const sub: Record<string, string> = {
              HEALTHY: "Data fundamental cukup dan tidak ada flag material terdeteksi.",
              NEUTRAL: "Data fundamental parsial dan tidak ada flag material terdeteksi.",
              RISK: "Terdekteksi flag risiko fundamental — periksa detail di bawah sebelum mengambil keputusan.",
              UNKNOWN: "Data fundamental tidak cukup tersedia — status tidak dapat diklasifikasikan.",
            };
            return sub[st] || "";
          })()}</p>

          {analisis.fundamental_flags && analisis.fundamental_flags.length > 0 ? (
            <ul className="space-y-2">
              {analisis.fundamental_flags.map((f) => {
                const labelMap: Record<string, { label: string; cls: string }> = {
                  NEGATIVE_EARNINGS: { label: "Laba Negatif", cls: "bg-red-50 text-red-700 border-red-200" },
                  HIGH_LEVERAGE: { label: "Leverage Tinggi", cls: "bg-orange-50 text-orange-700 border-orange-200" },
                  EXTREME_VALUATION: { label: "Valuasi Ekstrem", cls: "bg-orange-50 text-orange-700 border-orange-200" },
                  LOW_COVERAGE: { label: "Data Minim", cls: "bg-slate-100 text-slate-600 border-slate-200" },
                };
                const lm = labelMap[f.flag] || { label: f.flag, cls: "bg-slate-100 text-slate-600 border-slate-200" };
                return (
                  <li key={f.flag} className="flex items-start gap-2.5">
                    <span className={`shrink-0 px-2 py-0.5 text-[11px] font-bold tracking-wide rounded border ${lm.cls}`}>{lm.label}</span>
                    <span className="text-xs text-[var(--color-text-secondary)]">{f.reason}</span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-xs text-[var(--color-text-muted)]">Tidak ada flag risiko fundamental terdeteksi.</p>
          )}

          {analisis.fundamental_meta?.context?.market_cap_idr_b != null && (
            <p className="text-[11px] text-[var(--color-text-muted)] mt-3">
              Market Cap: Rp {new Intl.NumberFormat("id-ID").format(analisis.fundamental_meta.context.market_cap_idr_b)} miliar
              (konteks likuiditas — bukan flag risiko)
            </p>
          )}
          {analisis.fundamental_meta?.fetch_errors && analisis.fundamental_meta.fetch_errors.length > 0 && (
            <p className="text-[11px] text-amber-600 mt-3">
              Catatan fetch: {analisis.fundamental_meta.fetch_errors.join("; ")}
            </p>
          )}
        </div>
      )}

      {/* Score Components */}
      {s.components && (
        <div className="border border-[var(--color-border)] rounded-xl p-4 sm:p-6 bg-[var(--color-surface)] shadow-sm mb-6 sm:mb-8">
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 mb-6 sm:mb-8">
        <div className="lg:col-span-2 h-full">
          <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden h-full min-h-[300px] sm:min-h-[400px]">
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
          <Suspense fallback={<div className="h-12 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <RecoveryDropControl kode={kode} dropPct={sp.drop_pct ? Number(sp.drop_pct) : undefined} />
          </Suspense>
        </div>
      </div>

      {/* Recovery / Mean Reversion */}
      {recovery && <RecoveryCard data={recovery} />}

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
