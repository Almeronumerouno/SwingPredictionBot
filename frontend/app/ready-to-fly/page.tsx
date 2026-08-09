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
      <header className="flex flex-col sm:flex-row sm:items-start justify-between mb-8 lg:mb-10 gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--color-text-primary)]">Ready To Fly</h1>
          </div>
          <p className="text-xs sm:text-sm font-medium text-[var(--color-text-secondary)]">
            Saham dengan pola akumulasi post-ARA — volume tinggi konsisten + konfirmasi SMA20 = siap terbang.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <Suspense fallback={<div className="h-9 w-40 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DateSelector selected={date || ""} basePath="/ready-to-fly" />
          </Suspense>
        </div>
      </header>

      {error ? (
        <div className="border border-violet-200 bg-violet-50 rounded-xl px-5 py-4 text-sm text-violet-800 shadow-sm mb-8">
          <p className="font-bold mb-1">Data Belum Tersedia</p>
          <p>{error}</p>
          <p className="mt-2 text-xs opacity-80">Lakukan scan dari halaman <a href="/" className="underline font-bold">Dashboard</a> terlebih dahulu.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-5 mb-8 lg:mb-10">
            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-violet-500/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l7 7m0 0l7-7m-7 7v11" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Siap Terbang</p>
              </div>
              <p className="text-2xl sm:text-3xl font-extrabold tabular-nums text-violet-600 tracking-tight">{countReady}</p>
              <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">saham terdeteksi</p>
            </div>

            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Hampir Siap</p>
              </div>
              <p className="text-2xl sm:text-3xl font-extrabold tabular-nums text-amber-600 tracking-tight">{countAlmost}</p>
              <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">saham hampir terpenuhi</p>
            </div>

            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Rata-rata Density</p>
              </div>
              <p className="text-2xl sm:text-3xl font-extrabold tabular-nums text-[var(--color-text-primary)] tracking-tight">{avgDensity.toFixed(1)}%</p>
              <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">kepadatan volume heavy</p>
            </div>
          </div>

          <ReadyToFlyTabs data={data} />
        </>
      )}
    </>
  );
}
