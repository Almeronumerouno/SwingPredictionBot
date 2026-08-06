"use client";

import type { GorenganScannerEntry } from "@/types/api";
import Link from "next/link";

const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

function GorenganBadge({ level, score }: { level: string; score: number }) {
  const isExtreme = level === "EXTREME";
  const isHigh = level === "HIGH";
  
  const colorClass = isExtreme 
    ? "bg-red-500/10 text-red-700 border-red-500/20" 
    : isHigh 
      ? "bg-orange-500/10 text-orange-700 border-orange-500/20" 
      : "bg-yellow-500/10 text-yellow-700 border-yellow-500/20";

  const icon = isExtreme ? (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  ) : isHigh ? (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
    </svg>
  ) : (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
  
  const pctVal = score.toFixed(0);
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-bold tabular-nums tracking-wide ${colorClass}`} title={level}>
      {icon}
      {pctVal}
    </span>
  );
}

export default function GorenganTable({ data, date }: { data: GorenganScannerEntry[], date?: string }) {
  if (!data.length) {
    return (
      <div className="border border-[var(--color-border)] rounded-xl p-12 bg-[var(--color-surface)] shadow-sm flex flex-col items-center justify-center text-center">
        <p className="text-sm font-medium text-[var(--color-text-muted)] mb-1">Tidak ada data saham gorengan saat ini.</p>
        <p className="text-xs text-[var(--color-text-muted)]">Coba klik Scrape Gorengan atau pilih tanggal lain.</p>
      </div>
    );
  }
  
  const qs = date ? `?date=${date}` : "";

  return (
    <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted-bg)]/30">
              <th className="py-3 px-3 sm:px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider whitespace-nowrap">Risiko</th>
              <th className="py-3 px-3 sm:px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider whitespace-nowrap">Kode</th>
              <th className="py-3 px-3 sm:px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider hidden md:table-cell">Nama</th>
              <th className="py-3 px-3 sm:px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Harga</th>
              <th className="py-3 px-3 sm:px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Change</th>
              <th className="py-3 px-3 sm:px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap hidden sm:table-cell">Volume</th>
              <th className="py-3 px-3 sm:px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap hidden lg:table-cell">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {data.map((g) => (
              <tr
                key={g.code}
                className="group hover:bg-[var(--color-muted-bg)]/50 transition-colors duration-150"
              >
                <td className="py-3 px-3 sm:px-5 whitespace-nowrap">
                  <GorenganBadge level={g.gorengan_level} score={g.gorengan_score} />
                </td>
                <td className="py-3 px-3 sm:px-5 whitespace-nowrap">
                  <Link
                    prefetch={false}
                    href={`/saham/${g.code}${qs}`}
                    className="font-bold text-[var(--color-text-primary)] hover:text-[var(--color-primary)] transition-colors"
                  >
                    {g.code}
                  </Link>
                </td>
                <td className="py-3 px-3 sm:px-5 text-[var(--color-text-secondary)] truncate max-w-[220px] font-medium hidden md:table-cell">{g.name}</td>
                <td className="py-3 px-3 sm:px-5 text-right tabular-nums text-[var(--color-text-primary)] font-medium">{fmtIdr(g.close)}</td>
                <td className={`py-3 px-3 sm:px-5 text-right tabular-nums font-bold ${g.pct_change >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>
                  {pct(g.pct_change)}
                </td>
                <td className="py-3 px-3 sm:px-5 text-right tabular-nums text-[var(--color-text-secondary)] hidden sm:table-cell">{fmt(g.volume)}</td>
                <td className="py-3 px-3 sm:px-5 text-right tabular-nums text-[var(--color-text-secondary)] hidden lg:table-cell">{fmtIdr(g.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
