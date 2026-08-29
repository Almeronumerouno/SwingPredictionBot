import { notFound } from "next/navigation";
import { fetchAnalisis } from "@/lib/api/analisis";
import { fetchHistory } from "@/lib/api/history";
import { fetchRecovery } from "@/lib/api/recovery";
import type { AnalisisResponse, HistoryResponse, RecoveryResponse } from "@/types/api";
import ScoreCard from "@/components/score-card";
import TradePlanCard from "@/components/trade-plan-card";
import PriceChart from "@/components/price-chart";
import SimulationControls from "./simulation-controls";
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
                <span className={`px-2 py-1 text-xs font-bold tabular-nums tracking-wide rounded border ${rekomendasi === "BUY" ? "bg-[var(--color-up-bg)] text-[var(--color-up)] border-[var(--color-up)]/20" : rekomendasi === "SELL" ? "bg-[var(--color-down-bg)] text-[var(--color-down)] border-[var(--color-down)]/20" : "bg-[var(--color-warning-bg)] text-[var(--color-warning)] border-[var(--color-warning)]/20"}`}>
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
      {analisis.fundamental_status && (() => {
        const st = analisis.fundamental_status || "";
        const statusConfig: Record<string, {
          accent: string; iconBg: string; iconColor: string;
          badgeBg: string; badgeText: string; badgeBorder: string;
          icon: React.ReactNode; label: string; desc: string;
        }> = {
          HEALTHY: {
            accent: "border-l-emerald-500",
            iconBg: "bg-emerald-500/10", iconColor: "text-emerald-600",
            badgeBg: "bg-emerald-500/10", badgeText: "text-emerald-600", badgeBorder: "border-emerald-500/20",
            icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />,
            label: "Healthy",
            desc: "Data fundamental cukup dan tidak ada flag material terdeteksi.",
          },
          NEUTRAL: {
            accent: "border-l-[var(--color-text-muted)]",
            iconBg: "bg-[var(--color-muted-bg)]", iconColor: "text-[var(--color-text-muted)]",
            badgeBg: "bg-[var(--color-muted-bg)]", badgeText: "text-[var(--color-text-secondary)]", badgeBorder: "border-[var(--color-border)]",
            icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
            label: "Neutral",
            desc: "Data fundamental parsial dan tidak ada flag material terdeteksi.",
          },
          RISK: {
            accent: "border-l-red-500",
            iconBg: "bg-red-500/10", iconColor: "text-red-500",
            badgeBg: "bg-red-500/10", badgeText: "text-red-600", badgeBorder: "border-red-500/20",
            icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />,
            label: "Risk",
            desc: "Terdeteksi flag risiko fundamental — periksa detail sebelum mengambil keputusan.",
          },
          UNKNOWN: {
            accent: "border-l-[var(--color-border-strong)]",
            iconBg: "bg-[var(--color-muted-bg)]", iconColor: "text-[var(--color-text-muted)]",
            badgeBg: "bg-[var(--color-muted-bg)]", badgeText: "text-[var(--color-text-muted)]", badgeBorder: "border-[var(--color-border)]",
            icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
            label: "Unknown",
            desc: "Data fundamental tidak cukup tersedia — status tidak dapat diklasifikasikan.",
          },
        };
        const cfg = statusConfig[st] || statusConfig.UNKNOWN;
        const dq = analisis.fundamental_meta?.data_quality;
        const dqConfig: Record<string, { bg: string; text: string; border: string }> = {
          GOOD: { bg: "bg-emerald-500/10", text: "text-emerald-600", border: "border-emerald-500/20" },
          PARTIAL: { bg: "bg-amber-500/10", text: "text-amber-600", border: "border-amber-500/20" },
        };
        const dqStyle = dq ? (dqConfig[dq] || { bg: "bg-[var(--color-muted-bg)]", text: "text-[var(--color-text-muted)]", border: "border-[var(--color-border)]" }) : null;

        const flags = analisis.fundamental_flags || [];
        const flagConfig: Record<string, { label: string; dot: string }> = {
          NEGATIVE_EARNINGS: { label: "Laba Negatif", dot: "bg-red-500" },
          HIGH_LEVERAGE: { label: "Leverage Tinggi", dot: "bg-orange-500" },
          EXTREME_VALUATION: { label: "Valuasi Ekstrem", dot: "bg-orange-500" },
          LOW_COVERAGE: { label: "Data Minim", dot: "bg-[var(--color-text-muted)]" },
        };

        return (
          <div className={`rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] border-l-[3px] ${cfg.accent} shadow-sm mb-6 sm:mb-8 overflow-hidden`}>
            {/* Header */}
            <div className="px-4 sm:px-5 pt-4 sm:pt-5 pb-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-9 h-9 rounded-lg ${cfg.iconBg} flex items-center justify-center shrink-0`}>
                    <svg className={`w-[18px] h-[18px] ${cfg.iconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">{cfg.icon}</svg>
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm font-bold text-[var(--color-text-primary)] leading-tight">Fundamental Context</h2>
                    <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Konteks risiko — tidak memengaruhi skor</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={`px-2.5 py-1 text-[11px] font-bold tracking-wider uppercase rounded-md border ${cfg.badgeBg} ${cfg.badgeText} ${cfg.badgeBorder}`}>{cfg.label}</span>
                  {dq && dqStyle && (
                    <span className={`px-2 py-1 text-[10px] font-semibold tracking-wide rounded-md border ${dqStyle.bg} ${dqStyle.text} ${dqStyle.border}`}>
                      {dq === "GOOD" ? "✓ Data" : dq === "PARTIAL" ? "~ Parsial" : dq}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Description */}
            <div className="px-4 sm:px-5 pb-3">
              <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">{cfg.desc}</p>
            </div>

            {/* Flags */}
            {flags.length > 0 ? (
              <div className="mx-4 sm:mx-5 mb-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] divide-y divide-[var(--color-border)]">
                {flags.map((f) => {
                  const fc = flagConfig[f.flag] || { label: f.flag, dot: "bg-[var(--color-text-muted)]" };
                  return (
                    <div key={f.flag} className="flex items-start gap-3 px-3.5 py-2.5">
                      <div className="flex items-center gap-2 shrink-0 mt-px">
                        <span className={`w-2 h-2 rounded-full ${fc.dot}`} />
                        <span className="text-[11px] font-bold text-[var(--color-text-primary)] tracking-wide w-[100px]">{fc.label}</span>
                      </div>
                      <span className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed">{f.reason}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="mx-4 sm:mx-5 mb-4 flex items-center gap-2 px-3.5 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
                <svg className="w-3.5 h-3.5 text-[var(--color-up)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                <span className="text-[11px] text-[var(--color-text-secondary)]">Tidak ada flag risiko fundamental terdeteksi</span>
              </div>
            )}

            {/* Footer — market cap & fetch notes */}
            {(analisis.fundamental_meta?.context?.market_cap_idr_b != null || (analisis.fundamental_meta?.fetch_errors && analisis.fundamental_meta.fetch_errors.length > 0)) && (
              <div className="px-4 sm:px-5 py-2.5 border-t border-[var(--color-border)] bg-[var(--color-bg)]/50 flex flex-wrap items-center gap-x-4 gap-y-1">
                {analisis.fundamental_meta?.context?.market_cap_idr_b != null && (
                  <span className="text-[10px] text-[var(--color-text-muted)] tabular-nums">
                    Market Cap: <span className="font-semibold text-[var(--color-text-secondary)]">Rp {new Intl.NumberFormat("id-ID").format(analisis.fundamental_meta.context.market_cap_idr_b)} miliar</span>
                  </span>
                )}
                {analisis.fundamental_meta?.fetch_errors && analisis.fundamental_meta.fetch_errors.length > 0 && (
                  <span className="text-[10px] text-amber-600">
                    ⚠ {analisis.fundamental_meta.fetch_errors.join("; ")}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })()}

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

      {/* Full-width TradingView Chart [===] */}
      <div className="mb-6 sm:mb-8">
        <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden">
          <PriceChart data={chartData} />
        </div>
      </div>

      {/* 2 Balanced Cards Below Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 sm:gap-6 mb-6 sm:mb-8 items-stretch">
        {/* Card 1: Trading Plan (60% width on desktop) */}
        <div className="lg:col-span-3 h-full">
          {analisis.trade_plan ? (
            <TradePlanCard plan={analisis.trade_plan} />
          ) : (
            <div className="border border-[var(--color-border)] rounded-xl p-5 bg-[var(--color-surface)] shadow-sm h-full flex flex-col justify-center">
              <div className="flex flex-col items-center justify-center text-center py-4">
                <div className="w-12 h-12 rounded-xl bg-[var(--color-muted-bg)] flex items-center justify-center mb-3">
                  <svg className="w-5 h-5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <p className="text-sm font-bold text-[var(--color-text-primary)] mb-1">Tidak Ada Trade Plan</p>
                <p className="text-xs text-[var(--color-text-muted)]">Sinyal saat ini HOLD atau data tidak memenuhi syarat untuk membuat rencana trading.</p>
              </div>
            </div>
          )}
        </div>

        {/* Card 2: Pengaturan Simulasi Terpadu (40% width on desktop) */}
        <div className="lg:col-span-2 h-full">
          <Suspense fallback={<div className="h-full min-h-[260px] w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <SimulationControls
              kode={kode}
              capital={sp.capital ? Number(sp.capital) : undefined}
              length={sp.length ? Number(sp.length) : undefined}
              dropPct={sp.drop_pct ? Number(sp.drop_pct) : undefined}
            />
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
