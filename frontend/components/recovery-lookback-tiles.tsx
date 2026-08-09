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

  const currentRefDays = searchParams.get("ref_days");
  const parsedCurrentRefDays = currentRefDays ? parseInt(currentRefDays, 10) : null;

  const handleClick = (days: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("ref_days", String(days));
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  return (
    <div>
      <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">
        Posisi vs Harga Acuan: sudah balik atau masih di bawah?
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {lookbacks.map((v) => {
          const above = v.status === "above";
          const absDist = Math.abs(v.distance_pct);
          const isActive = parsedCurrentRefDays !== null && parsedCurrentRefDays === v.days;

          return (
            <button
              key={v.days}
              onClick={() => handleClick(v.days)}
              aria-pressed={isActive}
              className={`text-left w-full rounded-lg border p-3 transition-all ${
                above ? "border-[var(--color-up)]/20 bg-[var(--color-up-bg)]/60 hover:bg-[var(--color-up-bg)]" : "border-[var(--color-down)]/20 bg-[var(--color-down-bg)]/60 hover:bg-[var(--color-down-bg)]"
              } ${isActive ? "ring-2 ring-offset-1 ring-blue-500" : ""}`}
            >
              <div className="flex items-center justify-between mb-1.5 gap-2">
                <span className="text-xs font-bold text-[var(--color-text-primary)]">{v.label}</span>
                <span className={`inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded border ${above ? "bg-[var(--color-up-bg)] text-[var(--color-up)] border-[var(--color-up)]/20" : "bg-[var(--color-down-bg)] text-[var(--color-down)] border-[var(--color-down)]/20"}`}>
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
                <p className={`text-sm font-bold tabular-nums ${above ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>
                  <svg className="w-3 h-3 inline mr-0.5 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {above ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                    )}
                  </svg>
                  {absDist.toFixed(2)}%
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
