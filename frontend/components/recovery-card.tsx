import type { RecoveryResponse } from "@/types/api";
import RecoveryLookbackTiles from "./recovery-lookback-tiles";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

const HORIZON_LABELS: Record<number, string> = {
  1: "1 Hari",
  3: "3 Hari",
  5: "1 Pekan",
  10: "2 Pekan",
  21: "1 Bulan",
  42: "2 Bulan",
  63: "3 Bulan",
};

const signalConfig: Record<string, { color: string; bg: string; border: string; label: string }> = {
  POTENTIAL: { color: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200", label: "Berpotensi Recovery" },
  WATCH: { color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", label: "Pantau" },
  NO_SETUP: { color: "text-slate-600", bg: "bg-slate-50", border: "border-slate-200", label: "Tidak Ada Setup" },
};

function pctBar(p: number): { bar: string; text: string; label: string } {
  if (p >= 0.6) return { bar: "bg-emerald-500", text: "text-emerald-600", label: "Tinggi" };
  if (p >= 0.4) return { bar: "bg-amber-400", text: "text-amber-600", label: "Sedang" };
  if (p >= 0.2) return { bar: "bg-orange-400", text: "text-orange-500", label: "Rendah" };
  return { bar: "bg-red-400", text: "text-red-500", label: "Sangat Rendah" };
}

export default function RecoveryCard({ data }: { data: RecoveryResponse }) {
  const cfg = signalConfig[data.signal] || signalConfig.NO_SETUP;
  const belowRef = data.distance_pct != null && data.distance_pct < 0;
  const refLabel = data.ref_days ? `${HORIZON_LABELS[data.ref_days] || `${data.ref_days} Hari`}` : "Previous Close";

  return (
    <div className="border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden mb-8">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Mean Reversion / Recovery</h2>
            <p className="text-xs text-[var(--color-text-muted)]">Peluang kembali ke harga acuan terpilih</p>
          </div>
        </div>
        <span className={`px-3 py-1.5 text-xs font-bold uppercase tracking-wider rounded-lg border ${cfg.bg} ${cfg.color} ${cfg.border}`}>
          {cfg.label}
        </span>
      </div>

      <div className="px-6 py-5 space-y-6">
        {!data.valid ? (
          <p className="text-sm text-[var(--color-text-secondary)]">{data.signal_reason}</p>
        ) : (
          <>
            {/* Setup line */}
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <div>
                <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-0.5">Harga Saat Ini</p>
                <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIdr(data.harga ?? 0)}</p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-0.5">Harga Acuan ({refLabel})</p>
                <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIdr(data.ref_price ?? 0)}</p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-0.5">Jarak</p>
                <p className={`text-lg font-bold tabular-nums ${belowRef ? "text-red-500" : "text-emerald-600"}`}>
                  {belowRef ? "▼" : "▲"} {Math.abs(data.distance_pct ?? 0).toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-0.5">Threshold Setup</p>
                <p className="text-lg font-bold tabular-nums text-[var(--color-text-primary)]">
                  -{data.drop_pct.toFixed(1)}%
                  <span className="ml-1.5 align-middle text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-[var(--color-muted-bg)] text-[var(--color-text-muted)]">
                    {data.drop_source === "auto" ? "otomatis" : "manual"}
                  </span>
                </p>
              </div>
            </div>

            {/* Signal reason */}
            <p className="text-xs leading-relaxed text-[var(--color-text-secondary)] border-l-2 border-[var(--color-border)] pl-3">
              {data.signal_reason}
            </p>

            {/* Posisi vs Harga Acuan */}
            {data.vs_lookbacks && data.vs_lookbacks.length > 0 && (
              <RecoveryLookbackTiles lookbacks={data.vs_lookbacks} />
            )}

            {/* Volume & Akumulasi */}
            {data.accumulation && (
              <div
                className={`rounded-lg border p-4 ${
                  data.accumulation.ready_to_fly
                    ? "border-violet-300 bg-violet-50/70"
                    : "border-[var(--color-border)] bg-[var(--color-surface)]"
                }`}
              >
                <div className="flex items-center justify-between gap-3 mb-2.5">
                  <p className={`text-[10px] font-semibold uppercase tracking-wider ${
                    data.accumulation.ready_to_fly ? "text-violet-700" : "text-[var(--color-text-muted)]"
                  }`}>
                    Volume & Akumulasi
                  </p>
                  {data.accumulation.ready_to_fly && (
                    <span className="inline-flex items-center gap-1 text-[9px] font-bold px-2 py-1 rounded bg-violet-100 text-violet-700 uppercase tracking-wide">
                      <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 10l7 7 7-7" />
                      </svg>
                      Siap Terbang
                    </span>
                  )}
                </div>

                {data.accumulation.ready_to_fly ? (
                  <>
                    <p className="text-xs leading-relaxed text-violet-900/80 mb-2.5">
                      {data.accumulation.note}
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                      <div>
                        <p className="text-[10px] text-violet-700/70 mb-0.5">Hari Sejak ARA</p>
                        <p className="text-sm font-bold tabular-nums text-violet-900">
                          {data.accumulation.window_days}d{data.accumulation.ara_date ? ` · ${data.accumulation.ara_date.slice(8, 10)}/${data.accumulation.ara_date.slice(5, 7)}` : ""}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-violet-700/70 mb-0.5">Kepadatan Heavy</p>
                        <p className="text-sm font-bold tabular-nums text-violet-900">
                          {data.accumulation.density_pct != null ? `${data.accumulation.density_pct.toFixed(0)}%` : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-violet-700/70 mb-0.5">Hari Volume Tinggi</p>
                        <p className="text-sm font-bold tabular-nums text-violet-900">
                          {data.accumulation.k_heavy} hari
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-violet-700/70 mb-0.5">RVOL Maks (sejak ARA)</p>
                        <p className="text-sm font-bold tabular-nums text-violet-900">
                          {data.accumulation.max_rvol != null ? `${data.accumulation.max_rvol.toFixed(1)}x` : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-violet-700/70 mb-0.5">SMA20</p>
                        <p className="text-sm font-bold tabular-nums text-violet-900">
                          {data.accumulation.state_ma20 === "breakout" ? (
                            <span className="inline-flex items-center gap-1 text-emerald-700">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" />
                              </svg>
                              baru cross
                            </span>
                          ) : data.accumulation.sma20 != null ? (
                            `di atas ${fmtIdr(data.accumulation.sma20)}`
                          ) : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-violet-700/70 mb-0.5">Level ARA (ref)</p>
                        <p className="text-sm font-bold tabular-nums text-violet-900">
                          {data.accumulation.ara_ref_price != null ? fmtIdr(data.accumulation.ara_ref_price) : "—"}
                        </p>
                      </div>
                    </div>
                    {data.accumulation.warning && (
                      <p className="text-[11px] text-violet-800/60 mt-2.5 leading-relaxed">{data.accumulation.warning}</p>
                    )}
                  </>
                ) : (
                  <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">
                    {data.accumulation.reason || "Belum terlihat pola akumulasi post-ARA."}
                  </p>
                )}
              </div>
            )}

            {/* Exit plan */}
            {data.exit_plan && (
              <div className="border border-emerald-200 bg-emerald-50/60 rounded-lg p-4">
                <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wider mb-2.5">Exit Plan (Bila Entry)</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <p className="text-[10px] text-emerald-700/80 mb-0.5">Target Recovery</p>
                    <p className="text-sm font-bold tabular-nums text-emerald-800">{fmtIdr(data.exit_plan.target)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-emerald-700/80 mb-0.5">Time Stop</p>
                    <p className="text-sm font-bold tabular-nums text-emerald-800">{data.exit_plan.time_stop_days} hari (~3 bulan)</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-emerald-700/80 mb-0.5">Stop Loss Proteksi</p>
                    <p className="text-sm font-bold tabular-nums text-emerald-800">{fmtIdr(data.exit_plan.stop_loss)}</p>
                  </div>
                </div>
                <p className="text-[11px] text-emerald-700/70 mt-2.5 leading-relaxed">{data.exit_plan.note}</p>
              </div>
            )}

            {/* GBM probabilities */}
            {data.gbm && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
                    Probabilitas Model GBM (First-Passage Time)
                  </p>
                  <p className="text-[11px] text-[var(--color-text-muted)] tabular-nums">
                    P(hit kapan pun): <span className="font-bold text-[var(--color-text-primary)]">{Math.round((data.gbm.p_hit_ever ?? 0) * 100)}%</span>
                  </p>
                </div>
                <div className="space-y-2.5">
                  {data.gbm.probabilities.map((p) => {
                    const c = pctBar(p.p_hit);
                    const pct = Math.round(p.p_hit * 100);
                    return (
                      <div key={p.horizon_days} className="flex items-center gap-3">
                        <span className="w-16 shrink-0 text-xs text-[var(--color-text-secondary)]">{HORIZON_LABELS[p.horizon_days] || `${p.horizon_days} Hari`}</span>
                        <div className="flex-1 h-2 rounded-full bg-[var(--color-muted-bg)] overflow-hidden">
                          <div className={`h-full rounded-full transition-all duration-700 ease-out ${c.bar}`} style={{ width: `${pct}%` }} />
                        </div>
                        <span className={`w-12 shrink-0 text-right text-sm font-bold tabular-nums ${c.text}`}>{pct}%</span>
                      </div>
                    );
                  })}
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-2.5 tabular-nums">
                  Drift μ {((data.gbm.mu_annual ?? 0) * 100).toFixed(1)}% / th · Vol σ {(data.gbm.sigma_annual ?? 0) * 100 >= 100 ? ((data.gbm.sigma_annual ?? 0) * 100).toFixed(0) : ((data.gbm.sigma_annual ?? 0) * 100).toFixed(1)}% / th
                </p>
              </div>
            )}

            {/* Empirical base rates */}
            {data.empirical.some((e) => e.n_events > 0) && (
              <div>
                <p className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">
                  Base Rate Historis Saham Ini
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                        <th className="py-2 pr-4 font-semibold">Horizon</th>
                        <th className="py-2 pr-4 font-semibold text-right">Event</th>
                        <th className="py-2 pr-4 font-semibold text-right">Recovery</th>
                        <th className="py-2 font-semibold text-right">Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.empirical.map((e) => (
                        <tr key={e.horizon_days} className="border-b border-[var(--color-border)]/60 last:border-0">
                          <td className="py-2 pr-4 text-[var(--color-text-secondary)]">{HORIZON_LABELS[e.horizon_days] || `${e.horizon_days} Hari`}</td>
                          <td className="py-2 pr-4 text-right tabular-nums text-[var(--color-text-primary)]">{e.n_events || "—"}</td>
                          <td className="py-2 pr-4 text-right tabular-nums text-[var(--color-text-primary)]">{e.n_events ? e.n_recovered : "—"}</td>
                          <td className="py-2 text-right tabular-nums font-bold">
                            {e.rate != null ? (
                              <span className={e.rate >= 0.6 ? "text-emerald-600" : e.rate >= 0.4 ? "text-amber-600" : "text-red-500"}>
                                {Math.round(e.rate * 100)}%
                              </span>
                            ) : (
                              <span className="text-[var(--color-text-muted)]">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-2">
                  Event = close turun ≥ {data.drop_pct.toFixed(1)}% di bawah previous close dalam 500 hari terakhir. Recovery = high menyentuh previous close.
                </p>
              </div>
            )}

            {/* Disclaimer */}
            <p className="text-[11px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-3">
              Estimasi probabilistik berbasis model GBM dan data historis — bukan jaminan. Bukan rekomendasi beli/jual.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
