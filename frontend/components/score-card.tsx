interface Props {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
  negative?: boolean;
}

export default function ScoreCard({ label, value, sub, positive, negative }: Props) {
  const color = positive ? "text-[var(--color-up)]" : negative ? "text-[var(--color-down)]" : "text-[var(--color-text-primary)]";
  
  return (
    <div className="group border border-[var(--color-border)] rounded-xl px-5 py-4 bg-[var(--color-surface)] shadow-sm hover:shadow-md hover:-translate-y-1 hover:border-[var(--color-primary)]/20 transition-all duration-300 ease-out flex flex-col justify-between h-full">
      <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">{label}</p>
      <div className="flex items-baseline gap-2">
        <span className={`text-2xl font-bold tabular-nums tracking-tight ${color}`}>{value}</span>
      </div>
      {sub && <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1">{sub}</p>}
    </div>
  );
}
