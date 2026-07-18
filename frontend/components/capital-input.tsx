"use client";

interface Props {
  value: number;
  onChange: (v: number) => void;
  label?: string;
}

export default function CapitalInput({ value, onChange, label }: Props) {
  return (
    <div className="flex items-center gap-2">
      {label && <label className="text-sm text-zinc-400">{label}</label>}
      <input
        type="number"
        min={1_000_000}
        step={1_000_000}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="bg-zinc-800 border border-zinc-600 rounded px-3 py-1.5 text-sm w-40 text-white tabular-nums"
      />
    </div>
  );
}
