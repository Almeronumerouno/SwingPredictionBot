interface Props {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
  negative?: boolean;
  icon?: React.ReactNode;
}

export default function ScoreCard({ label, value, sub, positive, negative, icon }: Props) {
  const color = positive ? "text-[var(--color-up)]" : negative ? "text-[var(--color-down)]" : "text-[var(--color-text-primary)]";
  const dotColor = positive ? "bg-[var(--color-up)]" : negative ? "bg-[var(--color-down)]" : "bg-[var(--color-text-muted)]";
  const glowColor = positive ? "shadow-[0_0_12px_rgba(5,150,105,0.08)]" : negative ? "shadow-[0_0_12px_rgba(220,38,38,0.08)]" : "shadow-sm";
  
  return (
    <div className={`group border border-[var(--color-border)] rounded-xl px-5 py-4 bg-[var(--color-surface)] ${glowColor} hover:shadow-md hover:-translate-y-1 hover:border-[var(--color-primary)]/20 transition-all duration-300 ease-out flex flex-col justify-between h-full`}>
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-1.5 h-1.5 rounded-full ${dotColor}`}></div>
        <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">{label}</p>
      </div>
      <div className="flex items-baseline gap-2">
        {icon && <span className="text-lg">{icon}</span>}
        <span className={`text-2xl font-bold tabular-nums tracking-tight ${color}`}>{value}</span>
      </div>
      {sub && <p className="text-xs font-medium text-[var(--color-text-muted)] mt-1.5">{sub}</p>}
    </div>
  );
}
