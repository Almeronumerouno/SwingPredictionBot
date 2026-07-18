"use client";

import type { GainerEntry } from "@/types/api";
import Link from "next/link";

const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

function SignalBadge({ rec, score }: { rec: string | null; score: number | null }) {
  if (!rec) {
    return <span className="text-[var(--color-text-muted)] text-xs font-medium px-2.5 py-1 rounded-md bg-[var(--color-muted-bg)] border border-[var(--color-border)]/50 tracking-wide">N/A</span>;
  }
  const isBuy = rec === "BUY";
  const isSell = rec === "SELL";
  const colorClass = isBuy 
    ? "bg-[var(--color-up)]/10 text-[var(--color-up)] border-[var(--color-up)]/20" 
    : isSell 
      ? "bg-[var(--color-down)]/10 text-[var(--color-down)] border-[var(--color-down)]/20" 
      : "bg-[var(--color-muted-bg)] text-[var(--color-text-secondary)] border-[var(--color-border)]";
  
  const arrow = isBuy ? "\u25B2" : isSell ? "\u25BC" : "\u25C6";
  const pctVal = score != null ? score.toFixed(0) : "";
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-bold tabular-nums tracking-wide ${colorClass}`}>
      <span className="text-[10px]">{arrow}</span> {pctVal}
    </span>
  );
}

export default function GainersTable({ data }: { data: GainerEntry[] }) {
  if (!data.length) {
    return (
      <div className="border border-[var(--color-border)] rounded-xl p-12 bg-[var(--color-surface)] shadow-sm flex flex-col items-center justify-center text-center">
        <p className="text-sm font-medium text-[var(--color-text-muted)] mb-1">Tidak ada data saham gainer saat ini.</p>
        <p className="text-xs text-[var(--color-text-muted)]">Coba pilih tanggal lain atau tunggu update bursa.</p>
      </div>
    );
  }
  
  return (
    <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted-bg)]/30">
              <th className="py-3 px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider whitespace-nowrap">Signal</th>
              <th className="py-3 px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider whitespace-nowrap">Kode</th>
              <th className="py-3 px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Nama</th>
              <th className="py-3 px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Harga</th>
              <th className="py-3 px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Change</th>
              <th className="py-3 px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Volume</th>
              <th className="py-3 px-5 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider text-right whitespace-nowrap">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {data.map((g) => (
              <tr
                key={g.code}
                className="group hover:bg-[var(--color-muted-bg)]/50 transition-colors duration-150"
              >
                <td className="py-3 px-5 whitespace-nowrap">
                  <SignalBadge rec={g.recommendation} score={g.swing_score} />
                </td>
                <td className="py-3 px-5 whitespace-nowrap">
                  <Link
                    href={`/saham/${g.code}`}
                    className="font-bold text-[var(--color-text-primary)] hover:text-[var(--color-primary)] transition-colors"
                  >
                    {g.code}
                  </Link>
                </td>
                <td className="py-3 px-5 text-[var(--color-text-secondary)] truncate max-w-[220px] font-medium">{g.name}</td>
                <td className="py-3 px-5 text-right tabular-nums text-[var(--color-text-primary)] font-medium">{fmtIdr(g.close)}</td>
                <td className={`py-3 px-5 text-right tabular-nums font-bold ${g.pct_change >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>
                  {pct(g.pct_change)}
                </td>
                <td className="py-3 px-5 text-right tabular-nums text-[var(--color-text-secondary)]">{fmt(g.volume)}</td>
                <td className="py-3 px-5 text-right tabular-nums text-[var(--color-text-secondary)]">{fmtIdr(g.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
