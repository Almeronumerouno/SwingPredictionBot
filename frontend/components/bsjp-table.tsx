"use client";

import { useState } from "react";
import type { BSJPEntry } from "@/types/api";
import Link from "next/link";

const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

function BSJPBadge({ status }: { status: "TOP_PICK" | "STRONG" | "SIGNAL" }) {
  if (status === "TOP_PICK") {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        TOP PICK
      </span>
    );
  }
  if (status === "STRONG") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30">
        STRONG
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--color-muted-bg)] text-[var(--color-text-secondary)] border border-[var(--color-border)]">
      SIGNAL
    </span>
  );
}

export default function BSJPTable({ data, date }: { data: BSJPEntry[]; date?: string }) {
  const [filter, setFilter] = useState<"ALL" | "TOP_PICK" | "HIGH_VAL">("ALL");

  const filteredData = data.filter((item) => {
    if (filter === "TOP_PICK") return item.status === "TOP_PICK";
    if (filter === "HIGH_VAL") return item.value >= 2_000_000_000;
    return true;
  });

  if (!data.length) {
    return (
      <div className="border border-[var(--color-border)] rounded-xl p-12 bg-[var(--color-surface)] shadow-sm flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 rounded-full bg-[var(--color-muted-bg)] flex items-center justify-center mb-3 text-[var(--color-text-muted)]">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <p className="text-sm font-semibold text-[var(--color-text-primary)] mb-1">Belum ada sinyal BSJP untuk tanggal ini.</p>
        <p className="text-xs text-[var(--color-text-secondary)]">Pastikan data pasar sudah diperbarui atau pilih tanggal hari bursa sebelumnya.</p>
      </div>
    );
  }

  const qs = date ? `?date=${date}` : "";

  return (
    <div className="space-y-3">
      {/* Filter Tabs */}
      <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1">
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[var(--color-muted-bg)] border border-[var(--color-border)]/60 text-xs">
          <button
            onClick={() => setFilter("ALL")}
            className={`px-3 py-1.5 rounded-md font-medium transition-all ${
              filter === "ALL"
                ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-sm font-bold"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            Semua Sinyal ({data.length})
          </button>
          <button
            onClick={() => setFilter("TOP_PICK")}
            className={`px-3 py-1.5 rounded-md font-medium transition-all ${
              filter === "TOP_PICK"
                ? "bg-[var(--color-surface)] text-emerald-600 dark:text-emerald-400 shadow-sm font-bold"
                : "text-[var(--color-text-secondary)] hover:text-emerald-600"
            }`}
          >
            Top Picks ({data.filter((d) => d.status === "TOP_PICK").length})
          </button>
          <button
            onClick={() => setFilter("HIGH_VAL")}
            className={`px-3 py-1.5 rounded-md font-medium transition-all ${
              filter === "HIGH_VAL"
                ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-sm font-bold"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            Likuiditas &ge; 2M ({data.filter((d) => d.value >= 2_000_000_000).length})
          </button>
        </div>
        <span className="text-[11px] text-[var(--color-text-muted)] hidden sm:inline">
          Menampilkan {filteredData.length} saham lolos filter
        </span>
      </div>

      {/* Main Table */}
      <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted-bg)]/50 text-[var(--color-text-secondary)] font-semibold uppercase tracking-wider text-[10px]">
                <th className="py-3 px-4">Saham</th>
                <th className="py-3 px-3 text-right">Harga Close</th>
                <th className="py-3 px-3 text-right">Return 1D</th>
                <th className="py-3 px-3 text-right">Return 1W</th>
                <th className="py-3 px-3 text-center">RSI (14)</th>
                <th className="py-3 px-3 text-right">Nilai Transaksi</th>
                <th className="py-3 px-3 text-center">Status</th>
                <th className="py-3 px-4 text-center">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {filteredData.map((item) => (
                <tr
                  key={item.code}
                  className="hover:bg-[var(--color-muted-bg)]/40 transition-colors group"
                >
                  <td className="py-3.5 px-4 font-medium text-[var(--color-text-primary)]">
                    <Link
                      href={`/saham/${item.code}${qs}`}
                      className="flex items-center gap-2 group-hover:text-[var(--color-primary)] transition-colors"
                    >
                      <span className="font-bold text-sm text-[var(--color-primary)]">
                        {item.code}
                      </span>
                      {item.name && (
                        <span className="text-[11px] text-[var(--color-text-muted)] truncate max-w-[140px] sm:max-w-[200px]">
                          {item.name}
                        </span>
                      )}
                    </Link>
                  </td>
                  <td className="py-3.5 px-3 text-right font-bold tabular-nums text-[var(--color-text-primary)]">
                    Rp {fmt(item.close)}
                  </td>
                  <td className="py-3.5 px-3 text-right font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                    +{item.pct_change.toFixed(2)}%
                  </td>
                  <td className="py-3.5 px-3 text-right font-bold tabular-nums text-blue-600 dark:text-blue-400">
                    +{item.ret1w.toFixed(2)}%
                  </td>
                  <td className="py-3.5 px-3 text-center font-semibold tabular-nums">
                    <span className="px-2 py-0.5 rounded bg-[var(--color-muted-bg)] text-[var(--color-text-primary)] text-[11px]">
                      {item.rsi.toFixed(1)}
                    </span>
                  </td>
                  <td className="py-3.5 px-3 text-right font-medium tabular-nums text-[var(--color-text-secondary)]">
                    {item.value >= 1_000_000_000
                      ? `Rp ${(item.value / 1_000_000_000).toFixed(2)} M`
                      : `Rp ${(item.value / 1_000_000).toFixed(0)} Jt`}
                  </td>
                  <td className="py-3.5 px-3 text-center">
                    <BSJPBadge status={item.status} />
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <Link
                      href={`/saham/${item.code}${qs}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-[var(--color-primary)]/10 text-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-white transition-all shadow-sm"
                    >
                      Detail
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
