"use client";

import type { Gainer } from "@/types/api";

const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

export default function GainersTable({ data }: { data: Gainer[] }) {
  if (!data.length) {
    return <p className="text-zinc-500 text-sm">Tidak ada data gainer.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-700 text-zinc-400 text-left">
            <th className="pb-2 pr-4">Kode</th>
            <th className="pb-2 pr-4">Nama</th>
            <th className="pb-2 pr-4 text-right">Harga</th>
            <th className="pb-2 pr-4 text-right">Change</th>
            <th className="pb-2 pr-4 text-right">Volume</th>
            <th className="pb-2 pr-4 text-right">Vol Ratio</th>
            <th className="pb-2 pr-4">Kategori</th>
          </tr>
        </thead>
        <tbody>
          {data.map((g) => (
            <tr key={g.kode} className="border-b border-zinc-800 hover:bg-zinc-800/50">
              <td className="py-2 pr-4 font-medium">
                <a href={`/saham/${g.kode}`} className="text-blue-400 hover:underline">
                  {g.kode}
                </a>
              </td>
              <td className="py-2 pr-4 text-zinc-300 truncate max-w-[200px]">{g.nama}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{fmt(g.harga_sekarang)}</td>
              <td className={`py-2 pr-4 text-right tabular-nums ${g.perubahan_persen >= 0 ? "text-green-400" : "text-red-400"}`}>
                {pct(g.perubahan_persen)}
              </td>
              <td className="py-2 pr-4 text-right tabular-nums">{fmt(g.volume)}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{g.volume_ratio.toFixed(2)}x</td>
              <td className="py-2 pr-4">
                <span className="text-xs bg-zinc-700 px-1.5 py-0.5 rounded">{g.kategori}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
