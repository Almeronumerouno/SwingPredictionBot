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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setActiveTab("EXTREME")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${
            activeTab === "EXTREME"
              ? "bg-red-100 text-red-800 border-2 border-red-200"
              : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] border-2 border-transparent hover:bg-[var(--color-muted-bg)]"
          }`}
        >
          <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          EXTREME
          <span className={`ml-1 px-2 py-0.5 rounded-md text-xs ${activeTab === "EXTREME" ? "bg-red-200 text-red-900" : "bg-[var(--color-muted-bg)]"}`}>
            {countExtreme}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("HIGH")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${
            activeTab === "HIGH"
              ? "bg-orange-100 text-orange-800 border-2 border-orange-200"
              : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] border-2 border-transparent hover:bg-[var(--color-muted-bg)]"
          }`}
        >
          <svg className="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
          </svg>
          HIGH
          <span className={`ml-1 px-2 py-0.5 rounded-md text-xs ${activeTab === "HIGH" ? "bg-orange-200 text-orange-900" : "bg-[var(--color-muted-bg)]"}`}>
            {countHigh}
          </span>
        </button>
        </div>

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

      <div className="mt-2">
        <GorenganTable data={activeData} date={date} />
      </div>
    </div>
  );
}
