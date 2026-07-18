"use client";

import { useRouter } from "next/navigation";

export default function CapitalControl({ kode, capital }: { kode: string; capital?: number }) {
  const router = useRouter();

  const updateSearch = (key: string, value: string) => {
    const params = new URLSearchParams(window.location.search);
    if (value) params.set(key, value);
    else params.delete(key);
    router.replace(`/saham/${kode}?${params.toString()}`);
  };

  return (
    <div className="bg-zinc-800 rounded-lg p-4 space-y-3">
      <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">Pengaturan</h3>
      <div>
        <label className="text-xs text-zinc-400 block mb-1">Modal (Rp)</label>
        <input
          type="number"
          min={1_000_000}
          step={1_000_000}
          defaultValue={capital || 10_000_000}
          onChange={(e) => updateSearch("capital", e.target.value)}
          className="bg-zinc-900 border border-zinc-600 rounded px-3 py-1.5 text-sm w-full text-white tabular-nums"
        />
      </div>
      <div>
        <label className="text-xs text-zinc-400 block mb-1">History Length (hari)</label>
        <input
          type="number"
          min={30}
          max={365}
          step={1}
          defaultValue={250}
          onChange={(e) => updateSearch("length", e.target.value)}
          className="bg-zinc-900 border border-zinc-600 rounded px-3 py-1.5 text-sm w-full text-white tabular-nums"
        />
      </div>
    </div>
  );
}
