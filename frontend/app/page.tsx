import Link from "next/link";
import { Suspense } from "react";
import type { GainersResponse, GorenganScannerResponse, ReadyToFlyScannerResponse } from "@/types/api";
import { fetchGainers } from "@/lib/api/gainers";
import { fetchGorengan } from "@/lib/api/gorengan";
import { fetchReadyToFly } from "@/lib/api/readytofly";
import ScrapeAllButton from "@/components/scrape-all-button";
import DateSelector from "@/components/date-selector";
import SignalScreener from "@/components/signal-screener";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;

  // Fetch all data sources in parallel
  const [gainers, gorenganRes, rtfRes] = await Promise.all([
    safeFetch(() => fetchGainers(date)),
    safeFetch(() => fetchGorengan(date)),
    safeFetch(() => fetchReadyToFly(date)),
  ]);

  const gainerData = gainers?.data ?? [];
  const gorenganData = gorenganRes?.data ?? [];
  const rtfData = rtfRes?.data ?? [];

  // Gainer stats
  const topBuy = gainerData.filter((g) => g.recommendation === "BUY").sort((a, b) => (b.swing_score ?? 0) - (a.swing_score ?? 0));
  const avgChange = gainerData.length > 0 ? gainerData.reduce((acc, g) => acc + g.pct_change, 0) / gainerData.length : 0;
  const totalVolume = gainerData.reduce((acc, g) => acc + g.volume, 0);
  const totalValue = gainerData.reduce((acc, g) => acc + g.value, 0);
  const maxGainer = gainerData.length > 0 ? gainerData.reduce((a, b) => (a.pct_change > b.pct_change ? a : b)) : null;

  // Gorengan stats
  const countExtreme = gorenganData.filter((g) => g.gorengan_level === "EXTREME").length;
  const countHigh = gorenganData.filter((g) => g.gorengan_level === "HIGH").length;

  // Ready To Fly stats
  const countReady = rtfData.filter((e) => e.status === "ready").length;
  const countAlmost = rtfData.filter((e) => e.status === "almost").length;

  return (
    <>
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-start justify-between mb-8 lg:mb-10 gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--color-text-primary)]">Dashboard</h1>
          </div>
          <p className="text-xs sm:text-sm font-medium text-[var(--color-text-secondary)]">
            Pusat kendali — scan market, pantau sinyal, dan ringkasan seluruh analisis.
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <Suspense fallback={<div className="h-9 w-40 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DateSelector selected={date || ""} basePath="/" />
          </Suspense>
        </div>
      </header>

      {/* ─── Scan Control Panel ─── */}
      <section className="border border-[var(--color-border)] rounded-xl p-5 bg-[var(--color-surface)] shadow-sm mb-8 lg:mb-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <div>
              <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Scan Market Keseluruhan</h2>
              <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Jalankan seluruh scanner sekaligus (Top Gainers, Gorengan, Ready To Fly) untuk hari ini.</p>
            </div>
          </div>
          <div className="flex-shrink-0">
            <Suspense fallback={<div className="h-9 w-32 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
              <ScrapeAllButton />
            </Suspense>
          </div>
        </div>
      </section>

      {/* ─── Market Overview (Gainers) ─── */}
      {gainerData.length > 0 && (
        <section className="mb-8 lg:mb-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-[var(--color-text-primary)]">Market Overview</h2>
            <Link href={`/top-gainers${date ? `?date=${date}` : ""}`} className="text-xs font-semibold text-[var(--color-primary)] hover:underline flex items-center gap-1">
              Lihat Semua
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </Link>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 mb-6">
            <div className="group border border-[var(--color-border)] rounded-xl px-5 py-5 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
                  <svg className="w-5 h-5 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Total Saham</p>
              </div>
              <p className="text-2xl sm:text-3xl font-extrabold tabular-nums text-[var(--color-text-primary)] tracking-tight">{gainerData.length}</p>
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

          {/* Top Gainer + Signal Screener */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
            {maxGainer && (
              <div className="lg:col-span-1 border border-[var(--color-up)]/20 rounded-xl p-6 bg-gradient-to-br from-[var(--color-surface)] to-[var(--color-up)]/[0.03] shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">🔥 Top Gainer</h2>
                  <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-md bg-[var(--color-up)]/10 text-[var(--color-up)] border border-[var(--color-up)]/20">
                    {pct(maxGainer.pct_change)}
                  </span>
                </div>
                <Link prefetch={false} href={`/saham/${maxGainer.code}${date ? `?date=${date}` : ""}`} className="group block">
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
                  href={`/saham/${maxGainer.code}${date ? `?date=${date}` : ""}`}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--color-primary)] hover:text-[var(--color-text-primary)] transition-colors"
                >
                  Lihat Analisis
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                </Link>
              </div>
            )}
            <SignalScreener data={gainerData} date={date} />
          </div>
        </section>
      )}

      {/* ─── Market Alerts: Gorengan + Ready To Fly ─── */}
      <section className="mb-8 lg:mb-10">
        <h2 className="text-base font-bold text-[var(--color-text-primary)] mb-4">Market Alerts</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">

          {/* Gorengan Card */}
          <Link href={`/gorengan${date ? `?date=${date}` : ""}`} className="group border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center group-hover:bg-orange-500/20 transition-colors">
                <svg className="w-6 h-6 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-base font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">Scanner Gorengan</p>
                <p className="text-xs font-medium text-[var(--color-text-muted)] truncate">Deteksi pump-and-dump &amp; aktivitas bandar</p>
              </div>
              <svg className="w-5 h-5 text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
            {gorenganData.length > 0 ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-red-50 rounded-lg px-3 py-2.5">
                  <p className="text-[10px] font-semibold text-red-400 uppercase tracking-wider mb-0.5">Extreme</p>
                  <p className="text-xl font-extrabold tabular-nums text-red-600">{countExtreme}</p>
                </div>
                <div className="bg-orange-50 rounded-lg px-3 py-2.5">
                  <p className="text-[10px] font-semibold text-orange-400 uppercase tracking-wider mb-0.5">High</p>
                  <p className="text-xl font-extrabold tabular-nums text-orange-600">{countHigh}</p>
                </div>
              </div>
            ) : (
              <div className="bg-[var(--color-muted-bg)] rounded-lg px-3 py-3 text-center">
                <p className="text-xs text-[var(--color-text-muted)]">Belum di-scan — klik &quot;Scrape Gorengan&quot; di atas</p>
              </div>
            )}
          </Link>

          {/* Ready To Fly Card */}
          <Link href={`/ready-to-fly${date ? `?date=${date}` : ""}`} className="group border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-xl bg-violet-500/10 flex items-center justify-center group-hover:bg-violet-500/20 transition-colors">
                <svg className="w-6 h-6 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l7 7m0 0l7-7m-7 7v11" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-base font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">Ready To Fly</p>
                <p className="text-xs font-medium text-[var(--color-text-muted)] truncate">Akumulasi post-ARA — siap terbang</p>
              </div>
              <svg className="w-5 h-5 text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
            {rtfData.length > 0 ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-violet-50 rounded-lg px-3 py-2.5">
                  <p className="text-[10px] font-semibold text-violet-400 uppercase tracking-wider mb-0.5">Siap Terbang</p>
                  <p className="text-xl font-extrabold tabular-nums text-violet-600">{countReady}</p>
                </div>
                <div className="bg-amber-50 rounded-lg px-3 py-2.5">
                  <p className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider mb-0.5">Hampir Siap</p>
                  <p className="text-xl font-extrabold tabular-nums text-amber-600">{countAlmost}</p>
                </div>
              </div>
            ) : (
              <div className="bg-[var(--color-muted-bg)] rounded-lg px-3 py-3 text-center">
                <p className="text-xs text-[var(--color-text-muted)]">Belum di-scan — klik &quot;Scan Ready To Fly&quot; di atas</p>
              </div>
            )}
          </Link>
        </div>
      </section>

      {/* ─── Quick Access ─── */}
      <section>
        <h2 className="text-base font-bold text-[var(--color-text-primary)] mb-4">Akses Cepat</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-5">
          <Link href={`/top-gainers${date ? `?date=${date}` : ""}`} className="group border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
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
      </section>
    </>
  );
}
