import { notFound } from "next/navigation";
import { fetchAnalisis } from "@/lib/api/analisis";
import { fetchHistory } from "@/lib/api/history";
import type { AnalisisResponse, PriceHistoryResponse } from "@/types/api";
import ScoreCard from "@/components/score-card";
import TradePlanCard from "@/components/trade-plan-card";
import PriceChart from "@/components/price-chart";
import CapitalControl from "./capital-control";

const fmt = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 }).format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

export default async function SahamPage({
  params,
  searchParams,
}: {
  params: Promise<{ kode: string }>;
  searchParams: Promise<{ capital?: string; length?: string }>;
}) {
  const { kode } = await params;
  const sp = await searchParams;

  let analisis: AnalisisResponse;
  let history: PriceHistoryResponse;

  try {
    [analisis, history] = await Promise.all([
      fetchAnalisis(kode),
      fetchHistory(kode, sp.length ? Number(sp.length) : undefined),
    ]);
  } catch {
    notFound();
  }

  const s = analisis.score;
  const rekomendasiColor =
    analisis.rekomendasi === "STRONG BUY"
      ? "text-green-400"
      : analisis.rekomendasi === "BUY"
        ? "text-lime-400"
        : analisis.rekomendasi === "HOLD"
          ? "text-yellow-400"
          : "text-red-400";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <a href="/" className="text-zinc-500 hover:text-zinc-300 text-sm">&larr; Kembali</a>
        <div>
          <h1 className="text-2xl font-bold">{kode}</h1>
          <p className="text-zinc-400 text-sm">{analisis.nama}</p>
        </div>
        <div className="ml-auto text-right">
          <p className="text-xl font-bold tabular-nums">{fmt(analisis.harga)}</p>
          <p className={`text-sm font-semibold ${rekomendasiColor}`}>{analisis.rekomendasi}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <ScoreCard label="Support" value={fmt(analisis.support)} />
        <ScoreCard label="Resist" value={fmt(analisis.resist)} />
        <ScoreCard label="Total Score" value={s.total.toFixed(2)} />
        <ScoreCard label="Win Rate" value={pct(analisis.history.win_rate)} positive={analisis.history.win_rate >= 50} negative={analisis.history.win_rate < 50} />
        <ScoreCard label="Avg P&L" value={pct(analisis.history.avg_pnl)} positive={analisis.history.avg_pnl >= 0} negative={analisis.history.avg_pnl < 0} />
        <ScoreCard label="Max Win" value={pct(analisis.history.max_win)} positive />
        <ScoreCard label="Max Loss" value={pct(analisis.history.max_loss)} negative />
        <ScoreCard label="Avg Hold" value={`${analisis.history.avg_holding_days.toFixed(1)} hari`} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-2">Price History</h2>
          <div className="bg-zinc-900 rounded-lg p-2">
            <PriceChart data={history.data} />
          </div>
        </div>
        <div className="space-y-4">
          <TradePlanCard plan={analisis.trading_plan} />
          <CapitalControl kode={kode} capital={sp.capital ? Number(sp.capital) : undefined} />
        </div>
      </div>

      <div className="bg-zinc-900 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">Score Breakdown</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
          <div><span className="text-zinc-500">Trend EMA:</span> <span className="tabular-nums">{s.trend_ema.toFixed(1)}</span></div>
          <div><span className="text-zinc-500">Trend MA:</span> <span className="tabular-nums">{s.trend_ma.toFixed(1)}</span></div>
          <div><span className="text-zinc-500">Vol Ratio:</span> <span className="tabular-nums">{s.volume_ratio.toFixed(1)}</span></div>
          <div><span className="text-zinc-500">Vol Trend:</span> <span className="tabular-nums">{s.volume_trend.toFixed(1)}</span></div>
          <div><span className="text-zinc-500">Volatilitas:</span> <span className="tabular-nums">{s.volatilitas.toFixed(1)}</span></div>
          <div><span className="text-zinc-500">Momentum:</span> <span className="tabular-nums">{s.momentum.toFixed(1)}</span></div>
          <div><span className="text-zinc-500">WSP:</span> <span className="tabular-nums">{s.wsp.toFixed(1)}</span></div>
          <div><span className="text-zinc-500">ATR Band:</span> <span className="tabular-nums">{s.atr_band.toFixed(1)}</span></div>
        </div>
      </div>

      <div className="bg-zinc-900 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">Trading History ({analisis.history.total_trades} trades)</h2>
        {analisis.history.results.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-700 text-zinc-400 text-left">
                  <th className="pb-2 pr-3">Entry</th>
                  <th className="pb-2 pr-3">Exit</th>
                  <th className="pb-2 pr-3 text-right">Entry Price</th>
                  <th className="pb-2 pr-3 text-right">Exit Price</th>
                  <th className="pb-2 pr-3 text-right">P&L</th>
                  <th className="pb-2 text-right">Hold</th>
                </tr>
              </thead>
              <tbody>
                {analisis.history.results.slice(0, 20).map((t, i) => (
                  <tr key={i} className="border-b border-zinc-800">
                    <td className="py-1.5 pr-3 text-zinc-300">{t.entry}</td>
                    <td className="py-1.5 pr-3 text-zinc-300">{t.exit}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(t.entry_price)}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(t.exit_price)}</td>
                    <td className={`py-1.5 pr-3 text-right tabular-nums ${t.pnl_persen >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {pct(t.pnl_persen)}
                    </td>
                    <td className="py-1.5 text-right tabular-nums text-zinc-400">{t.holding_days}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-zinc-500 text-sm">Belum ada riwayat trading.</p>
        )}
      </div>
    </div>
  );
}
