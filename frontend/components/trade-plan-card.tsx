import type { TradePlanResponse } from "@/types/api";

const fmt = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

export default function TradePlanCard({ plan }: { plan: TradePlanResponse }) {
  const isBuy = plan.direction === "BUY";
  
  return (
    <div className="border border-[var(--color-border)] rounded-xl p-4 sm:p-6 bg-[var(--color-surface)] shadow-sm">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Trading Plan</h3>
        <span className={`px-2.5 py-1 text-xs font-bold uppercase tracking-wider rounded-md border ${isBuy ? "bg-[var(--color-up)]/10 text-[var(--color-up)] border-[var(--color-up)]/20" : "bg-[var(--color-down)]/10 text-[var(--color-down)] border-[var(--color-down)]/20"}`}>
          {plan.direction}
        </span>
      </div>
      
      <div className="space-y-4">
        <div className="flex justify-between items-center py-2 border-b border-[var(--color-border)]/50">
          <span className="text-sm font-medium text-[var(--color-text-secondary)]">Entry</span>
          <span className="text-base font-bold tabular-nums text-[var(--color-text-primary)]">{fmt(plan.entry)}</span>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 rounded-lg bg-[var(--color-down)]/5 border border-[var(--color-down)]/10">
            <span className="block text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Stop Loss</span>
            <span className="block text-lg font-bold tabular-nums text-[var(--color-down)]">{fmt(plan.stop_loss)}</span>
          </div>
          <div className="p-3 rounded-lg bg-[var(--color-up)]/5 border border-[var(--color-up)]/10">
            <span className="block text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Take Profit</span>
            <span className="block text-lg font-bold tabular-nums text-[var(--color-up)]">{fmt(plan.take_profit)}</span>
          </div>
        </div>

        <div className="flex justify-between items-center pt-2">
          <span className="text-sm font-medium text-[var(--color-text-secondary)]">R/R Ratio</span>
          <span className="text-sm font-semibold tabular-nums text-[var(--color-text-primary)]">{plan.risk_reward_ratio ? `1 : ${plan.risk_reward_ratio.toFixed(2)}` : "-"}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium text-[var(--color-text-secondary)]">Size</span>
          <span className="text-sm font-semibold tabular-nums text-[var(--color-text-primary)]">{plan.lots} lot <span className="text-[var(--color-text-muted)] font-normal">({plan.shares} lbr)</span></span>
        </div>
        {plan.note && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 font-medium">
            {plan.note}
          </div>
        )}
      </div>
    </div>
  );
}
