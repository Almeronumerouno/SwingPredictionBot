import { notFound } from "next/navigation";
import { fetchAnalisis } from "@/lib/api/analisis";
import { fetchHistory } from "@/lib/api/history";
import type { AnalisisResponse, HistoryResponse } from "@/types/api";
import ScoreCard from "@/components/score-card";
import TradePlanCard from "@/components/trade-plan-card";
import PriceChart from "@/components/price-chart";
import CapitalControl from "./capital-control";
import BackButton from "@/components/back-button";

const fmt = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

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
  let history: HistoryResponse;

  try {
    [analisis, history] = await Promise.all([
      fetchAnalisis(kode, sp.capital ? Number(sp.capital) : undefined),
      fetchHistory(kode, sp.length ? Number(sp.length) : undefined),
    ]);
  } catch {
    notFound();
  }

  const s = analisis.score;
  const rekomendasi = s.recommendation || "N/A";
  const rekomendasiColor =
    rekomendasi === "BUY"
      ? "text-[var(--color-up)]"
      : rekomendasi === "SELL"
        ? "text-[var(--color-down)]"
        : "text-[var(--color-text-muted)]";

  const chartData = history.bars.map((b) => ({
    time: b.date,
    open: b.open,
    high: b.high,
    low: b.low,
    close: b.close,
  }));

  return (
    <>
      <header className="mb-8">
        <BackButton />
        <div className="flex flex-col md:flex-row md:items-end justify-between mt-6 gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-4xl font-extrabold tracking-tight text-[var(--color-text-primary)]">{kode}</h1>
              <span className={`px-2.5 py-1 text-xs font-bold uppercase tracking-wider rounded-md border ${rekomendasi === "BUY" ? "bg-[var(--color-up)]/10 text-[var(--color-up)] border-[var(--color-up)]/20" : rekomendasi === "SELL" ? "bg-[var(--color-down)]/10 text-[var(--color-down)] border-[var(--color-down)]/20" : "bg-[var(--color-muted-bg)] text-[var(--color-text-secondary)] border-[var(--color-border)]"}`}>
                {rekomendasi}
              </span>
            </div>
            <p className="text-base font-medium text-[var(--color-text-secondary)] mt-1.5">{analisis.nama}</p>
          </div>
          <div className="md:text-right">
            <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">Harga Terakhir</p>
            <p className="text-3xl font-bold tabular-nums tracking-tight text-[var(--color-text-primary)]">{fmt(analisis.harga)}</p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8">
        <ScoreCard
          label="Swing Score"
          value={s.swing_score != null ? s.swing_score.toFixed(1) : "-"}
          positive={s.swing_score != null && s.swing_score >= 65}
          negative={s.swing_score != null && s.swing_score <= 35}
        />
        <ScoreCard label="Confidence" value={s.confidence || "-"} />
        <ScoreCard label="Risk Level" value={s.risk_level || "-"} />
        <ScoreCard
          label="Data Valid"
          value={s.valid ? "Yes" : "No"}
          positive={s.valid}
          negative={!s.valid}
        />
      </div>

      {s.components && (
        <div className="border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm mb-8">
          <h2 className="text-sm font-semibold text-[var(--color-text-primary)] mb-5">Komponen Skor</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { label: "Trend", value: s.components.trend },
              { label: "Momentum", value: s.components.momentum },
              { label: "Volume", value: s.components.volume },
              { label: "Price Action", value: s.components.price_action },
            ].map((c) => {
              const percentage = c.value * 100;
              const barColor = percentage >= 75 ? "bg-[var(--color-up)]" : percentage >= 40 ? "bg-[var(--color-primary)]" : "bg-[var(--color-down)]";
              return (
                <div key={c.label} className="group">
                  <div className="flex justify-between items-end mb-2.5">
                    <p className="text-sm font-medium text-[var(--color-text-secondary)]">{c.label}</p>
                    <p className="text-sm font-bold tabular-nums text-[var(--color-text-primary)]">{percentage.toFixed(0)}%</p>
                  </div>
                  <div className="h-2 rounded-full bg-[var(--color-muted-bg)] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ease-out ${barColor}`}
                      style={{ width: `${percentage.toFixed(0)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pb-12">
        <div className="md:col-span-2">
          <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden h-[500px]">
            <PriceChart data={chartData} />
          </div>
        </div>
        <div className="space-y-6">
          {analisis.trade_plan ? (
            <TradePlanCard plan={analisis.trade_plan} />
          ) : (
            <div className="border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)] shadow-sm flex items-center justify-center min-h-[150px]">
              <p className="text-sm font-medium text-[var(--color-text-muted)]">Tidak ada trade plan (HOLD / data tidak valid).</p>
            </div>
          )}
          <CapitalControl kode={kode} capital={sp.capital ? Number(sp.capital) : undefined} />
        </div>
      </div>
    </>
  );
}
