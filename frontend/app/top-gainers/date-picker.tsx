"use client";

export default function DatePicker({ selected }: { selected: string }) {
  return (
    <input
      type="date"
      defaultValue={selected}
      onChange={(e) => {
        const v = e.target.value;
        window.location.href = v ? `/top-gainers?date=${v}` : "/top-gainers";
      }}
      className="h-9 px-3 text-sm font-medium border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-primary)]/40 transition-all duration-200 shadow-sm hover:border-[var(--color-text-muted)] cursor-pointer"
    />
  );
}
