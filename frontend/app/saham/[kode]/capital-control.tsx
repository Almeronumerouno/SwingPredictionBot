"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

function fmt(n: string) {
  const num = parseInt(n.replace(/\D/g, ""), 10);
  if (isNaN(num)) return "";
  return new Intl.NumberFormat("id-ID").format(num);
}

function unfmt(s: string) {
  return s.replace(/\./g, "");
}

export default function CapitalControl({ kode, capital }: { kode: string; capital?: number }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [modal, setModal] = useState(capital ? fmt(String(capital)) : "10.000.000");
  const [length, setLength] = useState("250");

  const apply = () => {
    const params = new URLSearchParams(searchParams.toString());
    const modalNum = parseInt(unfmt(modal), 10);
    const lengthNum = Number(length);

    if (modalNum && modalNum !== 10000000) params.set("capital", String(modalNum));
    else params.delete("capital");
    
    if (lengthNum && lengthNum !== 250) params.set("length", String(lengthNum));
    else params.delete("length");
    
    const qs = params.toString();
    router.replace(`/saham/${kode}${qs ? `?${qs}` : ""}`);
  };

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4 bg-[var(--color-surface)]">
      <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Parameters</h3>
      <div className="space-y-3">
        <div>
          <label className="text-xs text-[var(--color-text-secondary)] block mb-1">Modal (Rp)</label>
          <input
            type="text"
            inputMode="numeric"
            value={modal}
            onChange={(e) => setModal(fmt(e.target.value))}
            className="w-full h-8 px-2.5 text-xs border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-[var(--color-text-primary)] tabular-nums focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-primary)]/40 transition-all duration-150"
          />
        </div>
        <div>
          <label className="text-xs text-[var(--color-text-secondary)] block mb-1">History (hari)</label>
          <input
            type="number"
            min={30}
            max={365}
            step={1}
            value={length}
            onChange={(e) => setLength(e.target.value)}
            className="w-full h-8 px-2.5 text-xs border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-[var(--color-text-primary)] tabular-nums focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-primary)]/40 transition-all duration-150"
          />
        </div>
        <button
          onClick={apply}
          className="w-full h-8 text-xs font-medium bg-[var(--color-primary)] text-white rounded-md hover:opacity-90 transition-opacity duration-150 cursor-pointer"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
