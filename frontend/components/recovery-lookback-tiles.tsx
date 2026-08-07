"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { RecoveryVsLookback } from "@/types/api";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

export default function RecoveryLookbackTiles({
  lookbacks,
}: {
  lookbacks: RecoveryVsLookback[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentDropPct = searchParams.get("drop_pct");
  const parsedCurrentDropPct = currentDropPct ? parseFloat(currentDropPct) : null;

  const handleClick = (distancePct: number) => {
    const absDist = Math.abs(distancePct).toFixed(2);
    const params = new URLSearchParams(searchParams.toString());
    params.set("drop_pct", absDist);
    router.replace(`${pathname}?${params.toString()}`);
  };

  return (
    <div>
      <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">
        Posisi vs Harga Acuan — udah balik atau masih di bawah?
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {lookbacks.map((v) => {
          const above = v.status === "above";
          const absDist = Math.abs(v.distance_pct);
          const isActive = parsedCurrentDropPct !== null && Math.abs(parsedCurrentDropPct - absDist) < 0.05;
          
          return (
            <button
              key={v.days}
              onClick={() => handleClick(v.distance_pct)}
              aria-pressed={isActive}
              className={`text-left w-full rounded-lg border p-3 transition-all ${
                above ? "border-emerald-200 bg-emerald-50/60 hover:bg-emerald-100/60" : "border-red-200 bg-red-50/60 hover:bg-red-100/60"
              } ${isActive ? "ring-2 ring-offset-1 ring-blue-500" : ""}`}
            >
              <div className="flex items-center justify-between mb-1.5 gap-2">
                <span className="text-xs font-bold text-[var(--color-text-primary)]">{v.label}</span>
                <span className={`inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded ${above ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-600"}`}>
                  <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {above ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                    )}
                  </svg>
                  {above ? "Udah di Atas" : "Masih di Bawah"}
                </span>
              </div>
              <p className="text-[10px] text-[var(--color-text-muted)] tabular-nums mb-1">Acuan {fmtIdr(v.ref_price)}</p>
              <div className="flex items-center justify-between mt-1">
                <p className={`text-sm font-bold tabular-nums ${above ? "text-emerald-600" : "text-red-500"}`}>
                  {above ? "▲" : "▼"} {absDist.toFixed(2)}%
                </p>
                {v.threshold_pct != null && (
                  <span className="text-[9px] text-[var(--color-text-muted)]">
                    ambang -{v.threshold_pct.toFixed(1)}%
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
