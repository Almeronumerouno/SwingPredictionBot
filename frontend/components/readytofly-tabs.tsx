"use client";

import { useState } from "react";
import Link from "next/link";
import type { ReadyToFlyEntry } from "@/types/api";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

type Tab = "ready" | "almost";

function GateIndicator({ label, passed }: { label: string; passed: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
      passed ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-500"
    }`}>
      {passed ? (
        <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
        </svg>
      )}
      {label}
    </span>
  );
}

function ReadyToFlyTable({ data }: { data: ReadyToFlyEntry[] }) {
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = data.filter((e) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return e.code.toLowerCase().includes(q) || (e.name || "").toLowerCase().includes(q);
  });

  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-[var(--color-text-muted)]">
        Tidak ada saham yang terdeteksi dalam kategori ini.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <div className="relative w-full sm:w-64">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            placeholder="Cari kode saham..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl text-sm font-medium focus:outline-none focus:border-[var(--color-text-primary)] focus:ring-1 focus:ring-[var(--color-text-primary)] transition-all placeholder:text-[var(--color-text-muted)]"
          />
        </div>
      </div>

      <div className="overflow-x-auto border border-[var(--color-border)] rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider border-b border-[var(--color-border)] bg-[var(--color-muted-bg)]">
              <th className="px-4 py-3">Kode</th>
              <th className="px-4 py-3">Nama</th>
              <th className="px-4 py-3 text-right">Harga</th>
              <th className="px-4 py-3 text-right">% Change</th>
              <th className="px-4 py-3 text-right">Jarak ARA</th>
              <th className="px-4 py-3 text-right">Density</th>
              <th className="px-4 py-3 text-center">Gates</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => {
              const pctColor = e.pct_change >= 0 ? "text-emerald-600" : "text-red-500";
              const distColor = (e.distance_pct ?? 0) >= 0 ? "text-emerald-600" : "text-red-500";
              return (
                <tr key={e.code} className="border-b border-[var(--color-border)]/60 last:border-0 hover:bg-[var(--color-muted-bg)]/40 transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      href={`/saham/${e.code}`}
                      className="font-bold text-[var(--color-primary)] hover:underline"
                    >
                      {e.code}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-secondary)] max-w-[180px] truncate">{e.name}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-semibold text-[var(--color-text-primary)]">{fmtIdr(e.close)}</td>
                  <td className={`px-4 py-3 text-right tabular-nums font-bold ${pctColor}`}>
                    {e.pct_change >= 0 ? "+" : ""}{e.pct_change.toFixed(2)}%
                  </td>
                  <td className={`px-4 py-3 text-right tabular-nums font-bold ${distColor}`}>
                    {e.distance_pct != null ? `${e.distance_pct.toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-bold text-[var(--color-text-primary)]">
                    {e.density_pct != null ? `${e.density_pct.toFixed(0)}%` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center justify-center gap-1">
                      <GateIndicator label="Below" passed={e.gates?.below ?? false} />
                      <GateIndicator label="Density" passed={e.gates?.density ?? false} />
                      <GateIndicator label="Heavy" passed={e.gates?.min_heavy ?? false} />
                      <GateIndicator label="SMA20" passed={e.gates?.above_ma ?? false} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ReadyToFlyTabs({ data }: { data: ReadyToFlyEntry[] }) {
  const [activeTab, setActiveTab] = useState<Tab>("ready");

  const readyData = data.filter((e) => e.status === "ready");
  const almostData = data.filter((e) => e.status === "almost");

  const activeData = activeTab === "ready" ? readyData : almostData;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setActiveTab("ready")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${
            activeTab === "ready"
              ? "bg-violet-100 text-violet-800 border-2 border-violet-200"
              : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] border-2 border-transparent hover:bg-[var(--color-muted-bg)]"
          }`}
        >
          <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l7 7m0 0l7-7m-7 7v11" />
          </svg>
          Ready To Fly
          <span className={`ml-1 px-2 py-0.5 rounded-md text-xs ${activeTab === "ready" ? "bg-violet-200 text-violet-900" : "bg-[var(--color-muted-bg)]"}`}>
            {readyData.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("almost")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${
            activeTab === "almost"
              ? "bg-amber-100 text-amber-800 border-2 border-amber-200"
              : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] border-2 border-transparent hover:bg-[var(--color-muted-bg)]"
          }`}
        >
          <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Hampir Siap
          <span className={`ml-1 px-2 py-0.5 rounded-md text-xs ${activeTab === "almost" ? "bg-amber-200 text-amber-900" : "bg-[var(--color-muted-bg)]"}`}>
            {almostData.length}
          </span>
        </button>
      </div>

      <ReadyToFlyTable data={activeData} />
    </div>
  );
}
