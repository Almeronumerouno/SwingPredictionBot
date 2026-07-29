import { Suspense } from "react";
import type { GainersResponse } from "@/types/api";
import { fetchGainers } from "@/lib/api/gainers";
import GainersTable from "@/components/gainers-table";
import ScrapeButton from "@/components/scrape-button";
import DatePicker from "./date-picker";

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
      <header className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-1">Top Gainers</h1>
          <p className="text-sm font-medium text-[var(--color-text-secondary)]">Saham dengan kenaikan tertinggi hari ini &middot; Bursa Efek Indonesia</p>
        </div>
        <div className="flex items-center gap-3">
          <Suspense fallback={<div className="h-9 w-28 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <ScrapeButton />
          </Suspense>
          <Suspense fallback={<div className="h-9 w-40 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DatePicker selected={date || ""} />
          </Suspense>
        </div>
      </header>

      {error ? (
        <div className="border border-[var(--color-down)]/30 bg-red-50 rounded-lg px-4 py-3 text-sm text-[var(--color-down)]">
          {error}
        </div>
      ) : gainers ? (
        <section>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <div className="border border-[var(--color-border)] rounded-xl px-5 py-4 bg-[var(--color-surface)] shadow-sm">
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Tanggal Data</p>
              <p className="text-xl font-bold tabular-nums text-[var(--color-text-primary)] tracking-tight">{gainers.date}</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-xl px-5 py-4 bg-[var(--color-surface)] shadow-sm">
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Total Saham Gainer</p>
              <p className="text-xl font-bold tabular-nums text-[var(--color-text-primary)] tracking-tight">{gainers.count}</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-xl px-5 py-4 bg-[var(--color-surface)] shadow-sm">
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Terakhir Diambil</p>
              <p className="text-xl font-bold tabular-nums text-[var(--color-text-primary)] tracking-tight">
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
