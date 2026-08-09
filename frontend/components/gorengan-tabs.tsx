"use client";

import { useState } from "react";
import type { GorenganScannerEntry } from "@/types/api";
import GorenganTable from "./gorengan-table";

type Tab = "EXTREME" | "HIGH";

export default function GorenganTabs({
  data,
  date,
}: {
  data: GorenganScannerEntry[];
  date?: string;
}) {
  const [activeTab, setActiveTab] = useState<Tab>("EXTREME");
  const [searchQuery, setSearchQuery] = useState("");

  const countExtreme = data.filter((g) => g.gorengan_level === "EXTREME").length;
  const countHigh = data.filter((g) => g.gorengan_level === "HIGH").length;

  const activeData = data.filter((g) => {
    let matchTab = false;
    if (activeTab === "EXTREME") matchTab = g.gorengan_level === "EXTREME";
    else if (activeTab === "HIGH") matchTab = g.gorengan_level === "HIGH";

    if (!matchTab) return false;
    if (!searchQuery) return true;

    const query = searchQuery.toLowerCase();
    return g.code.toLowerCase().includes(query) || (g.name || "").toLowerCase().includes(query);
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Segmented Control */}
        <div className="inline-flex bg-slate-100 p-1 rounded-md">
          <button
            onClick={() => setActiveTab("EXTREME")}
            className={`px-3.5 py-1.5 text-xs font-bold rounded transition-all ${
              activeTab === "EXTREME"
                ? "bg-white text-[var(--color-down)] shadow-sm ring-1 ring-black/5"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            EXTREME
            <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
              activeTab === "EXTREME" ? "bg-red-100 text-red-700" : "bg-slate-200/70 text-slate-500"
            }`}>
              {countExtreme}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("HIGH")}
            className={`px-3.5 py-1.5 text-xs font-bold rounded transition-all ${
              activeTab === "HIGH"
                ? "bg-white text-[var(--color-warning)] shadow-sm ring-1 ring-black/5"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            HIGH
            <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
              activeTab === "HIGH" ? "bg-amber-100 text-amber-700" : "bg-slate-200/70 text-slate-500"
            }`}>
              {countHigh}
            </span>
          </button>
        </div>

        <div className="relative w-full sm:w-64">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg className="w-4 h-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            placeholder="Cari kode saham..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md text-sm font-medium focus:outline-none focus:border-[var(--color-text-primary)] focus:ring-1 focus:ring-[var(--color-text-primary)] transition-all placeholder:text-[var(--color-text-muted)]"
          />
        </div>
      </div>

      <div>
        <GorenganTable data={activeData} date={date} />
      </div>
    </div>
  );
}
