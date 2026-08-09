"use client";

import type { GainerEntry } from "@/types/api";
import Link from "next/link";

const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

function SignalBadge({ rec, score }: { rec: string | null; score: number | null }) {
  if (!rec) {
    return <span className="text-[var(--color-text-muted)] text-xs font-medium px-2 py-1 rounded bg-[var(--color-muted-bg)] border border-[var(--color-border)]/50 tracking-wide">N/A</span>;
  }
  const isBuy = rec === "BUY";
  const isSell = rec === "SELL";
  const colorClass = isBuy 
    ? "bg-[var(--color-up-bg)] text-[var(--color-up)] border-[var(--color-up)]/20" 
    : isSell 
      ? "bg-[var(--color-down-bg)] text-[var(--color-down)] border-[var(--color-down)]/20" 
      : "bg-[var(--color-muted-bg)] text-[var(--color-text-secondary)] border-[var(--color-border)]";
  
  const pctVal = score != null ? score.toFixed(0) : "";
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs font-bold tabular-nums tracking-wide ${colorClass}`}>
      {isBuy ? (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" /></svg>
      ) : isSell ? (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" /></svg>
      ) : (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" /></svg>
      )}
      {pctVal}
    </span>
  );
}

export default function GainersTable({ data, date }: { data: GainerEntry[], date?: string }) {
  if (!data.length) {
    return (
      <div className="border border-[var(--color-border)] rounded-lg p-12 bg-[var(--color-surface)] flex flex-col items-center justify-center text-center">
        <p className="text-sm font-medium text-[var(--color-text-muted)] mb-1">Tidak ada data saham gainer saat ini.</p>
        <p className="text-xs text-[var(--color-text-muted)]">Coba pilih tanggal lain atau tunggu update bursa.</p>
      </div>
    );
  }
  
  const qs = date ? `?date=${date}` : "";

  return (
    <div className="border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted-bg)]">
              <th className="py-2.5 px-3 sm:px-4 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider whitespace-nowrap">Signal</th>
              <th className="py-2.5 px-3 sm:px-4 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider whitespace-nowrap">Kode</th>
              <th className="py-2.5 px-3 sm:px-4 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider hidden md:table-cell">Nama</th>
              <th className="py-2.5 px-3 sm:px-4 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Harga</th>
              <th className="py-2.5 px-3 sm:px-4 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Change</th>
              <th className="py-2.5 px-3 sm:px-4 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap hidden sm:table-cell">Volume</th>
              <th className="py-2.5 px-3 sm:px-4 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap hidden lg:table-cell">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {data.map((g) => (
              <tr
                key={g.code}
                className="group hover:bg-[var(--color-muted-bg)]/50 transition-colors duration-150"
              >
                <td className="py-2.5 px-3 sm:px-4 whitespace-nowrap">
                  <SignalBadge rec={g.recommendation} score={g.swing_score} />
                </td>
                <td className="py-2.5 px-3 sm:px-4 whitespace-nowrap">
                  <Link
                    prefetch={false}
                    href={`/saham/${g.code}${qs}`}
                    className="font-bold text-[var(--color-text-primary)] hover:text-[var(--color-primary)] transition-colors"
                  >
                    {g.code}
                  </Link>
                </td>
                <td className="py-2.5 px-3 sm:px-4 text-[var(--color-text-secondary)] truncate max-w-[220px] font-medium hidden md:table-cell">{g.name}</td>
                <td className="py-2.5 px-3 sm:px-4 text-right tabular-nums text-[var(--color-text-primary)] font-medium">{fmtIdr(g.close)}</td>
                <td className={`py-2.5 px-3 sm:px-4 text-right tabular-nums font-bold ${g.pct_change >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>
                  {pct(g.pct_change)}
                </td>
                <td className="py-2.5 px-3 sm:px-4 text-right tabular-nums text-[var(--color-text-secondary)] hidden sm:table-cell">{fmt(g.volume)}</td>
                <td className="py-2.5 px-3 sm:px-4 text-right tabular-nums text-[var(--color-text-secondary)] hidden lg:table-cell">{fmtIdr(g.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
