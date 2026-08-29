"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";

function fmt(n: string) {
  const num = parseInt(n.replace(/\D/g, ""), 10);
  if (isNaN(num)) return "";
  return new Intl.NumberFormat("id-ID").format(num);
}

function unfmt(s: string) {
  return s.replace(/\./g, "");
}

interface SimulationControlsProps {
  kode: string;
  capital?: number;
  length?: number;
  dropPct?: number;
}

export default function SimulationControls({
  kode,
  capital,
  length: initialLength,
  dropPct,
}: SimulationControlsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [modal, setModal] = useState(capital ? fmt(String(capital)) : "10.000.000");
  const [length, setLength] = useState(initialLength ? String(initialLength) : "250");
  const [mode, setMode] = useState<"auto" | "manual">(dropPct ? "manual" : "auto");
  const [drop, setDrop] = useState(dropPct ? String(dropPct) : "5");

  // Sync state if props change from URL navigation
  useEffect(() => {
    if (capital) setModal(fmt(String(capital)));
    if (initialLength) setLength(String(initialLength));
    if (dropPct) {
      setMode("manual");
      setDrop(String(dropPct));
    } else {
      setMode("auto");
    }
  }, [capital, initialLength, dropPct]);

  const handleApply = () => {
    const params = new URLSearchParams(searchParams.toString());
    const modalNum = parseInt(unfmt(modal), 10);
    const lengthNum = Number(length);

    if (modalNum && modalNum !== 10000000) params.set("capital", String(modalNum));
    else params.delete("capital");

    if (lengthNum && lengthNum !== 250) params.set("length", String(lengthNum));
    else params.delete("length");

    if (mode === "manual") {
      const val = Number(drop);
      if (val && val > 0 && val <= 50) params.set("drop_pct", String(val));
      else params.delete("drop_pct");
    } else {
      params.delete("drop_pct");
    }

    const qs = params.toString();
    router.replace(`/saham/${kode}${qs ? `?${qs}` : ""}`);
  };

  return (
    <div className="border border-[var(--color-border)] rounded-xl p-4 sm:p-5 bg-[var(--color-surface)] shadow-sm h-full flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[var(--color-primary)]/10 flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </div>
            <h3 className="text-sm font-bold text-[var(--color-text-primary)]">Pengaturan Simulasi</h3>
          </div>
          <span className="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded bg-[var(--color-muted-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)]">
            Kustom
          </span>
        </div>

        {/* Form Inputs Grid */}
        <div className="space-y-4">
          {/* Row 1: Modal & History Lookback */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider block mb-1">
                Modal Trading (Rp)
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={modal}
                onChange={(e) => setModal(fmt(e.target.value))}
                className="w-full h-9 px-3 text-xs font-bold border border-[var(--color-border)] rounded-lg bg-[var(--color-bg)] text-[var(--color-text-primary)] tabular-nums focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-border-strong)]"
                placeholder="10.000.000"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider block mb-1">
                History Bar (Hari)
              </label>
              <input
                type="number"
                min={30}
                max={365}
                step={1}
                value={length}
                onChange={(e) => setLength(e.target.value)}
                className="w-full h-9 px-3 text-xs font-bold border border-[var(--color-border)] rounded-lg bg-[var(--color-bg)] text-[var(--color-text-primary)] tabular-nums focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-border-strong)]"
                placeholder="250"
              />
            </div>
          </div>

          {/* Row 2: Recovery Drop Setup */}
          <div className="pt-3 border-t border-[var(--color-border)]">
            <div className="flex items-center justify-between mb-2">
              <label className="text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">
                Recovery Drop Threshold
              </label>
              <span className="text-[10px] font-bold text-[var(--color-text-muted)]">
                {mode === "auto" ? "Mode Otomatis" : `Manual (${drop}%)`}
              </span>
            </div>

            {/* Toggle Switch with zero layout shift */}
            <div className="grid grid-cols-2 gap-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-muted-bg)] p-1 mb-2.5">
              <button
                type="button"
                onClick={() => setMode("auto")}
                className={`h-7.5 text-xs font-bold rounded-md cursor-pointer flex items-center justify-center gap-1.5 border transition-colors duration-100 ${
                  mode === "auto"
                    ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] border-[var(--color-border)] shadow-xs"
                    : "bg-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border-transparent"
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Otomatis
              </button>
              <button
                type="button"
                onClick={() => setMode("manual")}
                className={`h-7.5 text-xs font-bold rounded-md cursor-pointer flex items-center justify-center gap-1.5 border transition-colors duration-100 ${
                  mode === "manual"
                    ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] border-[var(--color-border)] shadow-xs"
                    : "bg-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border-transparent"
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                Manual (%)
              </button>
            </div>

            {/* Threshold Content (Identical h-9 height for both modes to eliminate all layout/padding shift) */}
            <div className="h-9 w-full">
              {mode === "auto" ? (
                <div className="h-9 w-full px-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-muted-bg)]/40 flex items-center justify-between text-xs">
                  <span className="text-[var(--color-text-secondary)] font-medium">Volatilitas Dinamis (σ)</span>
                  <span className="font-bold text-[var(--color-text-primary)] px-2 py-0.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px]">
                    2.5× σ (2% – 13%)
                  </span>
                </div>
              ) : (
                <div className="h-9 w-full flex items-center gap-2">
                  <input
                    type="number"
                    min={0.5}
                    max={50}
                    step={0.5}
                    inputMode="decimal"
                    value={drop}
                    onChange={(e) => setDrop(e.target.value)}
                    className="flex-1 h-9 px-3 text-xs font-bold border border-[var(--color-border)] rounded-lg bg-[var(--color-bg)] text-[var(--color-text-primary)] tabular-nums focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-border-strong)]"
                    placeholder="5"
                  />
                  <div className="flex items-center gap-1">
                    {["3", "5", "7", "10"].map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setDrop(preset)}
                        className={`h-9 px-2.5 text-xs font-semibold rounded-lg border transition-colors duration-100 cursor-pointer ${
                          drop === preset
                            ? "bg-[var(--color-primary)]/10 text-[var(--color-primary)] border-[var(--color-primary)]/30 font-bold"
                            : "bg-[var(--color-muted-bg)] text-[var(--color-text-secondary)] border-[var(--color-border)] hover:text-[var(--color-text-primary)]"
                        }`}
                      >
                        {preset}%
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Unified Apply Button */}
      <div className="mt-5 pt-3 border-t border-[var(--color-border)]">
        <button
          onClick={handleApply}
          className="w-full h-9.5 text-xs font-bold bg-[var(--color-btn-primary-bg)] hover:bg-[var(--color-btn-primary-hover)] text-[var(--color-btn-primary-text)] border border-[var(--color-btn-primary-border)] rounded-lg transition-colors duration-100 cursor-pointer shadow-sm active:scale-[0.98] flex items-center justify-center gap-2"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
          Terapkan Pengaturan Simulasi
        </button>
      </div>
    </div>
  );
}
