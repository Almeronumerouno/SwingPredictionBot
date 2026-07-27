"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { GainerEntry } from "@/types/api";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

export default function SignalScreener({ data, date }: { data: GainerEntry[], date?: string }) {
  const [activeTab, setActiveTab] = useState<"buy" | "sell">("buy");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const itemsPerPage = 10;

  // Filter based on criteria
  const filteredData = useMemo(() => {
    let filtered = data;
    
    // Apply category filter
    if (activeTab === "buy") {
      filtered = filtered.filter(g => (g.swing_score ?? 0) >= 75);
      filtered.sort((a, b) => (b.swing_score ?? 0) - (a.swing_score ?? 0));
    } else {
      filtered = filtered.filter(g => (g.swing_score ?? 100) < 35);
      filtered.sort((a, b) => (a.swing_score ?? 100) - (b.swing_score ?? 100));
    }

    // Apply search filter
    if (search.trim()) {
      const q = search.toLowerCase();
      filtered = filtered.filter(g => 
        g.code.toLowerCase().includes(q) || g.name.toLowerCase().includes(q)
      );
    }

    return filtered;
  }, [data, activeTab, search]);

  const totalPages = Math.ceil(filteredData.length / itemsPerPage);
  const paginatedData = filteredData.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  const qs = date ? `?date=${date}` : "";

  return (
    <div className="lg:col-span-2 flex flex-col h-full">
      <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm flex flex-col flex-1 overflow-hidden">
        {/* Main Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] flex items-center gap-2">
            <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
            Screener Sinyal Top 15 Gainers
          </h2>
          <span className="text-xs font-medium text-[var(--color-text-muted)] bg-[var(--color-muted-bg)] px-2 py-1 rounded-md border border-[var(--color-border)]/50">
            {filteredData.length} Saham
          </span>
        </div>

        {/* Toolbar & Tabs */}
        <div className="px-5 py-3 border-b border-[var(--color-border)] bg-[#FAFAFA] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex bg-[var(--color-border)]/50 p-1 rounded-lg w-full sm:w-auto">
            <button
              onClick={() => { setActiveTab("buy"); setPage(1); }}
              className={`flex-1 sm:flex-none px-4 py-1.5 text-xs font-bold rounded-md transition-all ${
                activeTab === "buy" 
                  ? "bg-[var(--color-surface)] text-[var(--color-up)] shadow-sm ring-1 ring-black/5" 
                  : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
              }`}
            >
              Signal Buy (&gt; 75)
            </button>
            <button
              onClick={() => { setActiveTab("sell"); setPage(1); }}
              className={`flex-1 sm:flex-none px-4 py-1.5 text-xs font-bold rounded-md transition-all ${
                activeTab === "sell" 
                  ? "bg-[var(--color-surface)] text-[var(--color-down)] shadow-sm ring-1 ring-black/5" 
                  : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
              }`}
            >
              Signal Sell (&lt; 35)
            </button>
          </div>
          
          <div className="relative w-full sm:w-56">
            <svg className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input 
              type="text" 
              placeholder="Cari saham (mis: BBCA)" 
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="pl-9 pr-4 py-1.5 text-xs font-medium bg-white border border-[var(--color-border)] focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)] rounded-lg outline-none transition-all w-full text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] shadow-sm"
            />
          </div>
        </div>

        {/* List */}
        <div className="flex-1 min-h-[300px]">
          {filteredData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-6 py-12 text-center">
              <p className="text-sm font-medium text-[var(--color-text-muted)]">
                Tidak ada saham dengan signal {activeTab === "buy" ? "buy kuat (>65)" : "sell kuat (<35)"} saat ini.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--color-border)]">
              {paginatedData.map((g, i) => (
                <Link 
                  prefetch={false} 
                  key={g.code} 
                  href={`/saham/${g.code}${qs}`} 
                  className="flex items-center gap-4 px-6 py-3.5 hover:bg-[var(--color-muted-bg)]/50 transition-colors group"
                >
                  <span className="w-7 h-7 rounded-lg bg-[var(--color-muted-bg)] flex items-center justify-center text-xs font-bold text-[var(--color-text-muted)] flex-shrink-0">
                    {(page - 1) * itemsPerPage + i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">{g.code}</p>
                    <p className="text-xs font-medium text-[var(--color-text-muted)] truncate">{g.name}</p>
                  </div>
                  <div className="text-right hidden sm:block">
                    <p className="text-sm font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIdr(g.close)}</p>
                    <p className={`text-xs font-semibold tabular-nums ${g.pct_change >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>{pct(g.pct_change)}</p>
                  </div>
                  <div className="flex items-center gap-1.5 pl-2 flex-shrink-0 w-[60px] justify-end">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-bold tabular-nums border ${
                      activeTab === "buy" 
                        ? "bg-[var(--color-up)]/10 text-[var(--color-up)] border-[var(--color-up)]/20" 
                        : "bg-[var(--color-down)]/10 text-[var(--color-down)] border-[var(--color-down)]/20"
                    }`}>
                      {activeTab === "buy" ? "▲" : "▼"} {g.swing_score?.toFixed(0) ?? "-"}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
        
        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-[var(--color-border)] flex items-center justify-between bg-[var(--color-muted-bg)]/30">
            <p className="text-xs font-medium text-[var(--color-text-muted)]">
              Menampilkan {(page - 1) * itemsPerPage + 1} - {Math.min(page * itemsPerPage, filteredData.length)} dari {filteredData.length}
            </p>
            <div className="flex items-center gap-1">
              <button 
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="w-7 h-7 flex items-center justify-center rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
              </button>
              <span className="text-xs font-bold text-[var(--color-text-primary)] px-2">{page} / {totalPages}</span>
              <button 
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="w-7 h-7 flex items-center justify-center rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
