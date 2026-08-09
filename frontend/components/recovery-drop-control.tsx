"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export default function RecoveryDropControl({ kode, dropPct }: { kode: string; dropPct?: number }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<"auto" | "manual">(dropPct ? "manual" : "auto");
  const [drop, setDrop] = useState(dropPct ? String(dropPct) : "5");
  const [isTyping, setIsTyping] = useState(false);

  const [prevDropPct, setPrevDropPct] = useState(dropPct);
  if (dropPct !== prevDropPct) {
    setPrevDropPct(dropPct);
    if (dropPct !== undefined) {
      setMode("manual");
      if (!isTyping) {
        setDrop(String(dropPct));
      }
    } else {
      setMode("auto");
    }
  }

  const apply = () => {
    const params = new URLSearchParams(searchParams.toString());

    if (mode === "manual") {
      const val = Number(drop);
      if (val && val > 0 && val <= 50) params.set("drop_pct", String(val));
    } else {
      params.delete("drop_pct");
    }

    const qs = params.toString();
    router.replace(`/saham/${kode}${qs ? `?${qs}` : ""}`);
  };

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4 bg-[var(--color-surface)]">
      <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Recovery Setup</h3>

      {/* Mode toggle */}
      <div className="flex rounded-md border border-[var(--color-border)] overflow-hidden mb-3">
        <button
          onClick={() => setMode("auto")}
          aria-pressed={mode === "auto"}
          className={`flex-1 h-8 text-xs font-medium transition-colors duration-150 cursor-pointer ${
            mode === "auto"
              ? "bg-[var(--color-primary)] text-white"
              : "text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)]"
          }`}
        >
          Otomatis
        </button>
        <button
          onClick={() => setMode("manual")}
          aria-pressed={mode === "manual"}
          className={`flex-1 h-8 text-xs font-medium transition-colors duration-150 cursor-pointer ${
            mode === "manual"
              ? "bg-[var(--color-primary)] text-white"
              : "text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)]"
          }`}
        >
          Manual
        </button>
      </div>

      {mode === "auto" ? (
        <div>
          <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
            Threshold dihitung otomatis dari volatilitas saham ini (2.5× σ harian).
          </p>
          <p className="text-[10px] text-[var(--color-text-muted)] mt-1.5 mb-2.5">
            Dibatasi 2% hingga 13% (ARB flat 15% untuk semua tier harga IDX sejak April 2025).
          </p>
          <button
            onClick={apply}
            className="w-full h-8 text-xs font-medium bg-[var(--color-primary)] text-white rounded-md hover:opacity-90 transition-opacity duration-150 cursor-pointer"
          >
            Apply
          </button>
        </div>
      ) : (
        <div>
          <label className="text-xs text-[var(--color-text-secondary)] block mb-1" htmlFor="recovery-drop-pct">
            Drop threshold (%)
          </label>
          <input
            id="recovery-drop-pct"
            type="number"
            min={0.5}
            max={50}
            step={0.5}
            inputMode="decimal"
            value={drop}
            onChange={(e) => setDrop(e.target.value)}
            onFocus={() => setIsTyping(true)}
            onBlur={() => setIsTyping(false)}
            className="w-full h-8 px-2.5 text-xs border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-[var(--color-text-primary)] tabular-nums focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-primary)]/40 transition-all duration-150"
          />
          <p className="text-[10px] text-[var(--color-text-muted)] mt-1.5 mb-2.5">
            Peluang dihitung untuk saham yang turun ≥ X% di bawah previous close.
          </p>
          <button
            onClick={apply}
            className="w-full h-8 text-xs font-medium bg-[var(--color-primary)] text-white rounded-md hover:opacity-90 transition-opacity duration-150 cursor-pointer"
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
}
