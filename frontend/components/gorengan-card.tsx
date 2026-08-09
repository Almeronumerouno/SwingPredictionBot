import type { GorenganAnalysis } from "@/types/api";

const levelConfig: Record<string, { color: string; bg: string; border: string; label: string }> = {
  LOW: { color: "text-[var(--color-up)]", bg: "bg-[var(--color-up-bg)]", border: "border-[var(--color-up)]/20", label: "Risiko Rendah" },
  MEDIUM: { color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", label: "Waspada" },
  HIGH: { color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200", label: "Risiko Tinggi" },
  EXTREME: { color: "text-red-700", bg: "bg-red-50", border: "border-red-200", label: "Sangat Berbahaya" },
};

const factorIcons: Record<string, React.ReactNode> = {
  historical_pump_dump_risk: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  liquidity_risk: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3.69l5.66 5.66a8 8 0 11-11.31 0L12 3.69z" />
    </svg>
  ),
  market_cap_risk: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  active_pump: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 17l6-6 4 4 8-8m-5 0h5v5" />
    </svg>
  ),
  mid_momentum: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3v18h18M7 14l3-3 4 4 5-5" />
    </svg>
  ),
  distribution_risk: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7l6 6 4-4 8 8m0 0v-5m0 5h-5" />
    </svg>
  ),
  turnover_gaps: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />
    </svg>
  ),
};

const factorLabels: { key: keyof GorenganAnalysis["factors"]; label: string }[] = [
  { key: "historical_pump_dump_risk", label: "Historical P&D Profile" },
  { key: "liquidity_risk", label: "Liquidity Risk" },
  { key: "market_cap_risk", label: "Market Cap Risk" },
  { key: "active_pump", label: "Active Pump" },
  { key: "mid_momentum", label: "Mid Momentum" },
  { key: "distribution_risk", label: "Distribution Risk" },
  { key: "turnover_gaps", label: "Turnover & Gaps" },
];

function getScoreColor(score: number): string {
  if (score <= 30) return "text-emerald-600";
  if (score <= 60) return "text-amber-600";
  if (score <= 80) return "text-orange-500";
  return "text-red-600";
}

function getBarColor(score: number): string {
  if (score <= 30) return "bg-emerald-500";
  if (score <= 60) return "bg-amber-400";
  if (score <= 80) return "bg-orange-500";
  return "bg-red-500";
}

export default function GorenganCard({ data }: { data: GorenganAnalysis }) {
  const cfg = levelConfig[data.level] || levelConfig.LOW;

  return (
    <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden mb-8">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Gorengan Detection</h2>
            <p className="text-xs text-[var(--color-text-muted)]">Analisis risiko pump-and-dump</p>
          </div>
        </div>
        <span className={`px-3 py-1.5 text-xs font-bold uppercase tracking-wider rounded-lg border ${cfg.bg} ${cfg.color} ${cfg.border}`}>
          {data.level}
        </span>
      </div>

      <div className="p-6">
        {/* Score Gauge */}
        <div className="flex flex-col md:flex-row gap-6 mb-6">
          {/* Big Score */}
          <div className="flex flex-col items-center justify-center min-w-[140px]">
            <div className="relative w-28 h-28 flex items-center justify-center">
              <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--color-muted-bg)" strokeWidth="8" />
                <circle
                  cx="50" cy="50" r="42"
                  fill="none"
                  stroke={data.score <= 30 ? "#059669" : data.score <= 60 ? "#f59e0b" : data.score <= 80 ? "#f97316" : "#dc2626"}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${(data.score / 100) * 264} 264`}
                />
              </svg>
              <div className="text-center">
                <p className={`text-2xl font-black tabular-nums ${getScoreColor(data.score)}`}>{data.score.toFixed(0)}</p>
                <p className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase tracking-wider">GOR</p>
              </div>
            </div>
            <p className={`text-xs font-bold mt-2 ${cfg.color}`}>{cfg.label}</p>
          </div>

          {/* Explanation */}
          <div className="flex-1 flex flex-col justify-center">
            <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{data.explanation}</p>
            {data.warnings.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {data.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <svg className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                    <span className="text-[var(--color-text-secondary)]">{w}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Factor Breakdown */}
        <div className="border-t border-[var(--color-border)] pt-5">
          <p className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Breakdown Faktor</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {factorLabels.map(({ key, label }, i) => {
              const val = data.factors[key];
              return (
                <div key={key} className="flex items-center gap-3">
                  <span className="text-[var(--color-text-muted)] flex-shrink-0">
                    {factorIcons[key] ?? factorIcons.historical_pump_dump_risk}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs font-medium text-[var(--color-text-secondary)] truncate">{label}</p>
                      <p className={`text-xs font-bold tabular-nums ${getScoreColor(val)}`}>{val.toFixed(0)}</p>
                    </div>
                    <div className="h-1.5 rounded-full bg-[var(--color-muted-bg)] overflow-hidden">
                      <div
                        className={`h-full rounded-full animate-bar-grow ${getBarColor(val)}`}
                        style={{ width: `${val}%`, animationDelay: `${i * 45}ms` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
