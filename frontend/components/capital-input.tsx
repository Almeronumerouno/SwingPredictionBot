"use client";

interface Props {
  value: number;
  onChange: (v: number) => void;
  label?: string;
}

export default function CapitalInput({ value, onChange, label }: Props) {
  return (
    <div className="flex items-center gap-2">
      {label && <label className="text-sm text-[var(--color-text-secondary)]">{label}</label>}
      <input
        type="number"
        min={1_000_000}
        step={1_000_000}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-8 px-2.5 text-sm border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] text-[var(--color-text-primary)] tabular-nums focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-primary)]/40 transition-all duration-150"
      />
    </div>
  );
}