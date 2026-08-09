import Link from "next/link";
import { Suspense } from "react";
import type { ReadyToFlyScannerResponse } from "@/types/api";
import { fetchReadyToFly } from "@/lib/api/readytofly";
import DateSelector from "@/components/date-selector";
import ReadyToFlyTabs from "@/components/readytofly-tabs";

export default async function ReadyToFlyPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;
  let rtfRes: ReadyToFlyScannerResponse | null = null;
  let error: string | null = null;

  try {
    rtfRes = await fetchReadyToFly(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Gagal memuat data";
  }

  const data = rtfRes?.data ?? [];
  const countReady = data.filter((e) => e.status === "ready").length;
  const countAlmost = data.filter((e) => e.status === "almost").length;
  const avgDensity = data.length > 0
    ? data.reduce((acc, e) => acc + (e.density_pct ?? 0), 0) / data.length
    : 0;

  return (
    <>
      <header className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 lg:mb-8 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)] mb-0.5">Ready To Fly</h1>
          <p className="text-[11px] sm:text-xs font-medium text-[var(--color-text-secondary)]">
            Saham dengan pola akumulasi post-ARA: volume tinggi + konfirmasi SMA20.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <Suspense fallback={<div className="h-9 w-40 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DateSelector selected={date || ""} basePath="/ready-to-fly" />
          </Suspense>
        </div>
      </header>

      {error ? (
        <div className="border border-amber-200 bg-[var(--color-warning-bg)] rounded-lg px-5 py-4 text-sm text-amber-800 mb-8">
          <p className="font-bold mb-1">Data Belum Tersedia</p>
          <p>{error}</p>
          <p className="mt-2 text-xs opacity-80">Lakukan scan dari halaman <Link href="/" className="underline font-bold">Dashboard</Link> terlebih dahulu.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-6 lg:mb-8">
            <div className="border border-[var(--color-border)] rounded-lg px-4 py-4 bg-[var(--color-surface)]">
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-8 h-8 rounded-md bg-[var(--color-up)]/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-[var(--color-up)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2 22h20" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6.36 17.4 4 17l-2-4 1.1-.55a2 2 0 0 1 1.8 0l.17.1a2 2 0 0 0 1.8 0L8 12 5 6l.9-.45a2 2 0 0 1 2.09.2l4.02 3a2 2 0 0 0 2.1.2l4.19-2.06a2.41 2.41 0 0 1 1.73-.17L21 7a1.4 1.4 0 0 1 .87 1.99l-.38.76c-.23.46-.6.84-1.07 1.08L7.58 17.2a2 2 0 0 1-1.22.18Z" />
                  </svg>
                </div>
                <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Siap Terbang</p>
              </div>
              <p className="text-2xl font-extrabold tabular-nums text-[var(--color-up)] tracking-tight">{countReady}</p>
              <p className="text-[11px] font-medium text-[var(--color-text-muted)] mt-0.5">saham terdeteksi</p>
            </div>

            <div className="border border-[var(--color-border)] rounded-lg px-4 py-4 bg-[var(--color-surface)]">
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-8 h-8 rounded-md bg-[var(--color-warning)]/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-[var(--color-warning)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Hampir Siap</p>
              </div>
              <p className="text-2xl font-extrabold tabular-nums text-[var(--color-warning)] tracking-tight">{countAlmost}</p>
              <p className="text-[11px] font-medium text-[var(--color-text-muted)] mt-0.5">saham hampir terpenuhi</p>
            </div>

            <div className="border border-[var(--color-border)] rounded-lg px-4 py-4 bg-[var(--color-surface)]">
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-8 h-8 rounded-md bg-slate-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Rata-rata Density</p>
              </div>
              <p className="text-2xl font-extrabold tabular-nums text-[var(--color-text-primary)] tracking-tight">{avgDensity.toFixed(1)}%</p>
              <p className="text-[11px] font-medium text-[var(--color-text-muted)] mt-0.5">kepadatan volume heavy</p>
            </div>
          </div>

          <ReadyToFlyTabs data={data} date={date} />
        </>
      )}
    </>
  );
}
