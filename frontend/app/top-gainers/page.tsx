import Link from "next/link";
import { Suspense } from "react";
import type { GainersResponse } from "@/types/api";
import { fetchGainers } from "@/lib/api/gainers";
import GainersTable from "@/components/gainers-table";
import DateSelector from "@/components/date-selector";

export default async function TopGainersPage({
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

  return (
    <>
      <header className="flex flex-col sm:flex-row sm:items-end justify-between mb-6 sm:mb-8 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)] mb-0.5">Top Gainers</h1>
          <p className="text-[11px] sm:text-xs font-medium text-[var(--color-text-secondary)]">Saham dengan kenaikan tertinggi &middot; Bursa Efek Indonesia</p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <Suspense fallback={<div className="h-9 w-40 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DateSelector selected={date || ""} basePath="/top-gainers" />
          </Suspense>
        </div>
      </header>

      {error ? (
        <div className="border border-amber-200 bg-[var(--color-warning-bg)] rounded-lg px-5 py-4 text-sm text-amber-800">
          <p className="font-bold mb-1">Data Belum Tersedia</p>
          <p>{error}</p>
          <p className="mt-2 text-xs opacity-80">Lakukan scan dari halaman <Link href="/" className="underline font-bold">Dashboard</Link> terlebih dahulu.</p>
        </div>
      ) : gainers ? (
        <section>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-6">
            <div className="border border-[var(--color-border)] rounded-lg px-4 py-3.5 bg-[var(--color-surface)]">
              <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Tanggal Data</p>
              <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)] tracking-tight">{gainers.date}</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg px-4 py-3.5 bg-[var(--color-surface)]">
              <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Total Saham Gainer</p>
              <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)] tracking-tight">{gainers.count}</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg px-4 py-3.5 bg-[var(--color-surface)]">
              <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Terakhir Diambil</p>
              <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)] tracking-tight">
                {new Date(gainers.scraped_at).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })} WIB
              </p>
            </div>
          </div>
          <GainersTable data={gainers.data} date={date} />
        </section>
      ) : null}
    </>
  );
}
