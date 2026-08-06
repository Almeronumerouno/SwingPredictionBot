import Link from "next/link";
import { Suspense } from "react";
import type { GainersResponse } from "@/types/api";
import { fetchGainers } from "@/lib/api/gainers";
import ScrapeButton from "@/components/scrape-button";
import DateSelector from "@/components/date-selector";
import SignalScreener from "@/components/signal-screener";
const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;
  let gainers: GainersResponse | null = null;
  let error: string | null = null;

  try {
    gainers = await fetchGainers(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Gagal memuat data";
  }

  const data = gainers?.data ?? [];
  const topBuy = data.filter((g) => g.recommendation === "BUY").sort((a, b) => (b.swing_score ?? 0) - (a.swing_score ?? 0));
  const topSell = data.filter((g) => g.recommendation === "SELL");
  const avgChange = data.length > 0 ? data.reduce((acc, g) => acc + g.pct_change, 0) / data.length : 0;
  const totalVolume = data.reduce((acc, g) => acc + g.volume, 0);
  const totalValue = data.reduce((acc, g) => acc + g.value, 0);
  const maxGainer = data.length > 0 ? data.reduce((a, b) => (a.pct_change > b.pct_change ? a : b)) : null;

  return (
    <>
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-start justify-between mb-8 lg:mb-10 gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--color-text-primary)]">Dashboard</h1>
          </div>
          <p className="text-xs sm:text-sm font-medium text-[var(--color-text-secondary)]">
            Ringkasan seluruh saham gainer di Bursa Efek Indonesia hari ini, termasuk sinyal swing trading, volume, dan nilai transaksi.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <Suspense fallback={<div className="h-9 w-28 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <ScrapeButton />
          </Suspense>
          <Suspense fallback={<div className="h-9 w-40 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DateSelector selected={date || ""} basePath="/" />
          </Suspense>
        </div>
      </header>

      {error ? (
        <div className="border border-[var(--color-down)]/30 bg-red-50 rounded-xl px-5 py-4 text-sm text-[var(--color-down)] shadow-sm">
          {error}
        </div>
      ) : (
        <>
          {/* Stats Overview */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 mb-8 lg:mb-10">
            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Total Saham</p>
              </div>
              <p className="text-2xl sm:text-3xl font-extrabold tabular-nums text-[var(--color-text-primary)] tracking-tight">{data.length}</p>
              <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">saham gainer terdeteksi</p>
            </div>

            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-[var(--color-up)]/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-[var(--color-up)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Sinyal Buy</p>
              </div>
              <p className="text-2xl sm:text-3xl font-extrabold tabular-nums text-[var(--color-up)] tracking-tight">{topBuy.length}</p>
              <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">rekomendasi beli aktif</p>
            </div>

            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Total Value</p>
              </div>
              <p className="text-lg sm:text-2xl font-extrabold tabular-nums text-[var(--color-text-primary)] tracking-tight">{fmtIdr(totalValue)}</p>
              <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">volume transaksi: {fmt(totalVolume)}</p>
            </div>

            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Rata-rata Change</p>
              </div>
              <p className={`text-2xl sm:text-3xl font-extrabold tabular-nums tracking-tight ${avgChange >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>{pct(avgChange)}</p>
              <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">dari seluruh gainer</p>
            </div>
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 mb-8 lg:mb-10">
            
            {/* Top Pick - Featured */}
            {maxGainer && (
              <div className="lg:col-span-1 border border-[var(--color-up)]/20 rounded-xl p-6 bg-gradient-to-br from-[var(--color-surface)] to-[var(--color-up)]/[0.03] shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">🔥 Top Gainer</h2>
                  <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-md bg-[var(--color-up)]/10 text-[var(--color-up)] border border-[var(--color-up)]/20">
                    {pct(maxGainer.pct_change)}
                  </span>
                </div>
                <Link prefetch={false} href={`/saham/${maxGainer.code}${date ? `?date=${date}` : ''}`} className="group block">
                  <p className="text-3xl font-extrabold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors tracking-tight">{maxGainer.code}</p>
                  <p className="text-sm font-medium text-[var(--color-text-secondary)] mt-1 truncate">{maxGainer.name}</p>
                </Link>
                <div className="mt-5 pt-4 border-t border-[var(--color-border)]/50 grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-0.5">Harga</p>
                    <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIdr(maxGainer.close)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-0.5">Volume</p>
                    <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)]">{fmt(maxGainer.volume)}</p>
                  </div>
                </div>
                <Link
                  href={`/saham/${maxGainer.code}${date ? `?date=${date}` : ''}`}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--color-primary)] hover:text-[var(--color-text-primary)] transition-colors"
                >
                  Lihat Analisis
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                </Link>
              </div>
            )}

            {/* Signal Screener */}
            <SignalScreener data={data} date={date} />
          </div>

          {/* Quick Access */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-5">
            <Link href={`/top-gainers${date ? `?date=${date}` : ''}`} className="group border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-[var(--color-up)]/10 flex items-center justify-center group-hover:bg-[var(--color-up)]/20 transition-colors">
                  <svg className="w-6 h-6 text-[var(--color-up)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div>
                  <p className="text-base font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">Top Gainers</p>
                  <p className="text-sm font-medium text-[var(--color-text-muted)]">Lihat semua saham naik hari ini dengan detail lengkap</p>
                </div>
                <svg className="w-5 h-5 text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors ml-auto flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </Link>

            <Link href="/analisis" className="group border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
                  <svg className="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-base font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">Analisis Saham</p>
                  <p className="text-sm font-medium text-[var(--color-text-muted)]">Cari dan analisis saham apapun di Bursa Efek Indonesia</p>
                </div>
                <svg className="w-5 h-5 text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors ml-auto flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </Link>
          </div>
        </>
      )}
    </>
  );
}
