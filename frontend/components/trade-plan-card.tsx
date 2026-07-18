import type { AnalisisResponse } from "@/types/api";

const fmt = (n: number) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 }).format(n);

export default function TradePlanCard({ plan }: { plan: AnalisisResponse["trading_plan"] }) {
  return (
    <div className="bg-zinc-800 rounded-lg p-4 space-y-2">
      <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">Trading Plan</h3>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <p className="text-zinc-400 text-xs">Entry Zone</p>
          <p className="text-white">{plan.entry_zone}</p>
        </div>
        <div>
          <p className="text-zinc-400 text-xs">Stop Loss</p>
          <p className="text-red-400 tabular-nums">{fmt(plan.stop_loss)}</p>
        </div>
        <div>
          <p className="text-zinc-400 text-xs">Target 1</p>
          <p className="text-green-400 tabular-nums">{fmt(plan.target_1)}</p>
        </div>
        <div>
          <p className="text-zinc-400 text-xs">Target 2</p>
          <p className="text-green-400 tabular-nums">{fmt(plan.target_2)}</p>
        </div>
        <div className="col-span-2">
          <p className="text-zinc-400 text-xs">Risk/Reward</p>
          <p className="text-white tabular-nums">{plan.risk_reward}</p>
        </div>
        <div className="col-span-2">
          <p className="text-zinc-400 text-xs">Modal Dibutuhkan</p>
          <p className="text-yellow-400 tabular-nums">{fmt(plan.modal_dibutuhkan)}</p>
        </div>
      </div>
    </div>
  );
}
