import Link from "next/link";
import { Suspense } from "react";
import type { GorenganScannerResponse } from "@/types/api";
import { fetchGorengan } from "@/lib/api/gorengan";
import DateSelector from "@/components/date-selector";
import GorenganTabs from "@/components/gorengan-tabs";

export default async function GorenganPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;
  let gorenganRes: GorenganScannerResponse | null = null;
  let error: string | null = null;

  try {
    gorenganRes = await fetchGorengan(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Gagal memuat data";
  }

  const data = gorenganRes?.data ?? [];
  const countExtreme = data.filter((g) => g.gorengan_level === "EXTREME").length;
  const countHigh = data.filter((g) => g.gorengan_level === "HIGH").length;
  const avgScore = data.length > 0 ? data.reduce((acc, g) => acc + g.gorengan_score, 0) / data.length : 0;

  return (
    <>
      <header className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 lg:mb-8 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)] mb-0.5">Scanner Gorengan</h1>
          <p className="text-[11px] sm:text-xs font-medium text-[var(--color-text-secondary)]">
            Deteksi saham dengan indikasi pump-and-dump atau aktivitas bandar.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <Suspense fallback={<div className="h-9 w-40 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DateSelector selected={date || ""} basePath="/gorengan" />
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
                <div className="w-8 h-8 rounded-md bg-[var(--color-down)]/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-[var(--color-down)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Risiko EXTREME</p>
              </div>
              <p className="text-2xl font-extrabold tabular-nums text-[var(--color-down)] tracking-tight">{countExtreme}</p>
              <p className="text-[11px] font-medium text-[var(--color-text-muted)] mt-0.5">saham terdeteksi</p>
            </div>

            <div className="border border-[var(--color-border)] rounded-lg px-4 py-4 bg-[var(--color-surface)]">
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-8 h-8 rounded-md bg-[var(--color-warning)]/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-[var(--color-warning)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
                  </svg>
                </div>
                <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Risiko HIGH</p>
              </div>
              <p className="text-2xl font-extrabold tabular-nums text-[var(--color-warning)] tracking-tight">{countHigh}</p>
              <p className="text-[11px] font-medium text-[var(--color-text-muted)] mt-0.5">saham terdeteksi</p>
            </div>

            <div className="border border-[var(--color-border)] rounded-lg px-4 py-4 bg-[var(--color-surface)]">
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-8 h-8 rounded-md bg-slate-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Rata-rata Skor</p>
              </div>
              <p className="text-2xl font-extrabold tabular-nums text-[var(--color-text-primary)] tracking-tight">{avgScore.toFixed(1)}</p>
              <p className="text-[11px] font-medium text-[var(--color-text-muted)] mt-0.5">dari semua hasil scan</p>
            </div>
          </div>

          <GorenganTabs data={data} date={date} />
        </>
      )}
    </>
  );
}
