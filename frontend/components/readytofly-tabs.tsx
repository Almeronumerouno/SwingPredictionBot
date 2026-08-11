"use client";

import { useState } from "react";
import Link from "next/link";
import type { ReadyToFlyEntry } from "@/types/api";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

const fmtDate = (d?: string | null) => {
  if (!d) return "-";
  const parts = d.split("-");
  if (parts.length < 3) return d;
  const months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  const mIdx = parseInt(parts[1], 10) - 1;
  return `${parts[2]} ${months[mIdx] || parts[1]}`;
};

const fmtVol = (v?: number | null) => {
  if (v == null || v === 0) return "-";
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return new Intl.NumberFormat("id-ID").format(v);
};

type Tab = "ready" | "almost";

function GateIndicator({ label, passed }: { label: string; passed: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
      passed ? "bg-[var(--color-up-bg)] text-[var(--color-up)]" : "bg-[var(--color-down-bg)] text-[var(--color-down)]"
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

function ReadyToFlyTable({ data, date }: { data: ReadyToFlyEntry[]; date?: string }) {
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

  const qs = date ? `?date=${date}` : "";

  return (
    <div>
      <div className="mb-4">
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

      <div className="overflow-x-auto border border-[var(--color-border)] rounded-lg">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider border-b border-[var(--color-border)] bg-[var(--color-muted-bg)]">
              <th className="px-4 py-2.5">Kode</th>
              <th className="px-4 py-2.5">Nama</th>
              <th className="px-4 py-2.5 text-right">Harga</th>
              <th className="px-4 py-2.5 text-right">% Change</th>
              <th className="px-4 py-2.5 text-center">Last ARA</th>
              <th className="px-4 py-2.5 text-center">Vol Pasca-ARA</th>
              <th className="px-4 py-2.5 text-center">Jarak ARA</th>
              <th className="px-4 py-2.5 text-center">Density</th>
              <th className="px-4 py-2.5 text-center">Gates</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => {
              const pctColor = e.pct_change >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]";
              const distColor = (e.distance_pct ?? 0) >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]";
              return (
                <tr key={e.code} className="border-b border-[var(--color-border)]/60 last:border-0 hover:bg-[var(--color-muted-bg)]/40 transition-colors">
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/saham/${e.code}${qs}`}
                      className="font-bold text-[var(--color-primary)] hover:underline"
                    >
                      {e.code}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--color-text-secondary)] max-w-[180px] truncate">{e.name}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-semibold text-[var(--color-text-primary)]">{fmtIdr(e.close)}</td>
                  <td className={`px-4 py-2.5 text-right tabular-nums font-bold ${pctColor}`}>
                    {e.pct_change >= 0 ? "+" : ""}{e.pct_change.toFixed(2)}%
                  </td>
                  <td className="px-4 py-2.5 text-center tabular-nums font-semibold text-[var(--color-text-secondary)] whitespace-nowrap">
                    {fmtDate(e.ara_date)}
                  </td>
                  <td className="px-4 py-2.5 text-center tabular-nums font-semibold text-[var(--color-text-primary)] whitespace-nowrap" title={e.post_ara_volume ? `Volume: ${new Intl.NumberFormat("id-ID").format(e.post_ara_volume)} lembar | Est. Nilai: ${fmtIdr(e.post_ara_value || 0)}` : undefined}>
                    {fmtVol(e.post_ara_volume)}
                  </td>
                  <td className={`px-4 py-2.5 text-center tabular-nums font-bold ${distColor}`}>
                    {e.distance_pct != null ? `${e.distance_pct.toFixed(1)}%` : "-"}
                  </td>
                  <td className="px-4 py-2.5 text-center tabular-nums font-bold text-[var(--color-text-primary)]">
                    {e.density_pct != null ? `${e.density_pct.toFixed(0)}%` : "-"}
                  </td>
                  <td className="px-4 py-2.5">
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

export default function ReadyToFlyTabs({ data, date }: { data: ReadyToFlyEntry[]; date?: string }) {
  const [activeTab, setActiveTab] = useState<Tab>("ready");

  const readyData = data.filter((e) => e.status === "ready");
  const almostData = data.filter((e) => e.status === "almost");

  const activeData = activeTab === "ready" ? readyData : almostData;

  return (
    <div className="flex flex-col gap-4">
      {/* Segmented Control */}
      <div className="inline-flex bg-slate-100 p-1 rounded-md self-start">
        <button
          onClick={() => setActiveTab("ready")}
          className={`px-3.5 py-1.5 text-xs font-bold rounded transition-all ${
            activeTab === "ready"
              ? "bg-white text-[var(--color-up)] shadow-sm ring-1 ring-black/5"
              : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          }`}
        >
          Ready To Fly
          <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
            activeTab === "ready" ? "bg-[var(--color-up-bg)] text-[var(--color-up)]" : "bg-slate-200/70 text-slate-500"
          }`}>
            {readyData.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("almost")}
          className={`px-3.5 py-1.5 text-xs font-bold rounded transition-all ${
            activeTab === "almost"
              ? "bg-white text-[var(--color-warning)] shadow-sm ring-1 ring-black/5"
              : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          }`}
        >
          Hampir Siap
          <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
            activeTab === "almost" ? "bg-amber-100 text-amber-700" : "bg-slate-200/70 text-slate-500"
          }`}>
            {almostData.length}
          </span>
        </button>
      </div>

      <ReadyToFlyTable data={activeData} date={date} />
    </div>
  );
}
