import { Suspense } from "react";
import type { Gainer } from "@/types/api";
import { fetchGainers } from "@/lib/api/gainers";
import GainersTable from "@/components/gainers-table";
import DatePicker from "./date-picker";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;
  let gainers: Gainer[] = [];
  let error: string | null = null;

  try {
    gainers = await fetchGainers(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Gagal memuat data";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Swingbot</h1>
          <p className="text-zinc-400 text-sm mt-1">Top gainers & analisis teknikal</p>
        </div>
        <Suspense fallback={<div className="h-9 w-40 bg-zinc-800 animate-pulse rounded" />}>
          <DatePicker selected={date || ""} />
        </Suspense>
      </div>

      {error ? (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-4 text-red-400 text-sm">
          {error}
        </div>
      ) : (
        <GainersTable data={gainers} />
      )}
    </div>
  );
}
