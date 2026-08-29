"use client";

import { useState } from "react";
import Link from "next/link";
import type { ReadyToFlyEntry } from "@/types/api";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

const fmtDate = (d?: string | null) => {
  if (!d) return "-";
  const parts = d.split("-");
  if (parts.length < 3) return d;
  const months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  const mIdx = parseInt(parts[1], 10) - 1;
  return `${parts[2]} ${months[mIdx] || parts[1]}`;
};

const fmtVol = (v?: number | null) => {
  if (v == null || v === 0) return "-";
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return new Intl.NumberFormat("id-ID").format(v);
};

type Tab = "ready" | "almost";

/* ── Gate Dot: compact dot indicator with tooltip ── */
function GateDot({ label, passed, title }: { label: string; passed: boolean; title?: string }) {
  return (
    <span
      className="relative group cursor-default"
      title={title || `${label}: ${passed ? "Terpenuhi" : "Belum terpenuhi"}`}
    >
      <span
        className={`inline-block w-2 h-2 rounded-full transition-colors ${
          passed ? "bg-[var(--color-up)]" : "bg-[var(--color-down)]/35"
        }`}
      />
    </span>
  );
}

/* ── Density Bar: visual progress bar ── */
function DensityBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-[var(--color-text-muted)]">-</span>;
  const clamped = Math.min(Math.max(value, 0), 100);
  const color =
    clamped >= 80 ? "bg-[var(--color-up)]" :
    clamped >= 40 ? "bg-[var(--color-warning)]" :
    "bg-[var(--color-text-muted)]";
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="text-[11px] font-bold tabular-nums text-[var(--color-text-primary)] w-8 text-right flex-shrink-0">
        {value.toFixed(0)}%
      </span>
    </div>
  );
}

/* ── Detail Metric: label + value pair for expanded section ── */
function DetailMetric({ label, value, valueClass, title }: {
  label: string;
  value: string;
  valueClass?: string;
  title?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5" title={title}>
      <span className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">{label}</span>
      <span className={`text-xs font-bold tabular-nums ${valueClass || "text-[var(--color-text-primary)]"}`}>{value}</span>
    </div>
  );
}

/* ── Expandable Row Card ── */
function RTFRowCard({ e, qs, isReady }: { e: ReadyToFlyEntry; qs: string; isReady: boolean }) {
  const [expanded, setExpanded] = useState(false);

  const pctColor = e.pct_change >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]";
  const distColor = (e.distance_pct ?? 0) >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]";
  const netDistColor = (e.net_dist ?? 0) > 0.05 ? "text-[var(--color-up)]" : (e.net_dist ?? 0) < -0.05 ? "text-[var(--color-down)]" : "text-[var(--color-text-secondary)]";
  const dirNetColor = (e.net_dist_heavy ?? 0) > 0.5 ? "text-[var(--color-up)]" : "text-[var(--color-down)]";

  const gates = e.gates || {};
  const gateList = [
    { key: "below", label: "Below", passed: gates.below ?? false },
    { key: "density", label: "Density", passed: gates.density ?? false },
    { key: "min_heavy", label: "Heavy", passed: gates.min_heavy ?? false },
    { key: "above_ma", label: "SMA20", passed: gates.above_ma ?? false },
    { key: "liquidity", label: "Liq", passed: gates.liquidity ?? true },
  ];
  const gatesPassed = gateList.filter(g => g.passed).length;

  return (
    <div
      className={`border rounded-lg bg-[var(--color-surface)] transition-all duration-200 ${
        isReady
          ? "border-l-[3px] border-l-[var(--color-up)] border-[var(--color-border)] hover:border-[var(--color-border-strong)]"
          : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]"
      } ${expanded ? "shadow-[var(--shadow-card-hover)]" : "hover:shadow-[var(--shadow-panel)]"}`}
    >
      {/* ── Level 1: Primary Row (Always Visible) ── */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-4 py-3 cursor-pointer focus:outline-none"
      >
        <div className="flex items-center gap-3 lg:gap-4 flex-wrap sm:flex-nowrap w-full">
          {/* 1. Kode + Nama */}
          <div className="flex flex-col w-[140px] sm:w-[150px] lg:w-[170px] flex-shrink-0">
            <Link
              href={`/saham/${e.code}${qs}`}
              onClick={(ev) => ev.stopPropagation()}
              className="text-sm font-bold text-[var(--color-primary)] hover:underline leading-tight"
            >
              {e.code}
            </Link>
            <span className="text-[11px] text-[var(--color-text-muted)] truncate leading-tight mt-0.5">
              {e.name}
            </span>
          </div>

          {/* 2. Harga + % Change */}
          <div className="flex items-baseline gap-1.5 w-[105px] lg:w-[120px] flex-shrink-0">
            <span className="text-sm font-bold tabular-nums text-[var(--color-text-primary)]">
              {fmtIdr(e.close)}
            </span>
            <span className={`text-[11px] font-bold tabular-nums ${pctColor}`}>
              {e.pct_change >= 0 ? "+" : ""}{e.pct_change.toFixed(1)}%
            </span>
          </div>

          {/* 3. Last ARA & Jarak */}
          <div className="hidden sm:flex flex-col items-center w-[85px] lg:w-[95px] flex-shrink-0">
            <span className="text-xs font-semibold tabular-nums text-[var(--color-text-primary)]">
              {fmtDate(e.ara_date)}
            </span>
            <span className={`text-[10px] font-semibold tabular-nums ${distColor}`}>
              {e.distance_pct != null ? `${e.distance_pct >= 0 ? "+" : ""}${e.distance_pct.toFixed(1)}%` : "-"}
            </span>
          </div>

          {/* 4. Density Bar */}
          <div className="w-[110px] lg:w-[130px] flex-shrink-0">
            <DensityBar value={e.density_pct} />
          </div>

          {/* 5. Gap SMA20 */}
          <div className="hidden md:flex flex-col items-center w-[75px] lg:w-[85px] flex-shrink-0">
            <span className={`text-xs font-bold tabular-nums ${(e.sma_gap_pct ?? 0) >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}`}>
              {e.sma_gap_pct != null ? `${e.sma_gap_pct >= 0 ? "+" : ""}${e.sma_gap_pct.toFixed(1)}%` : "-"}
            </span>
            <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider font-medium">
              {e.state_ma20 === "above" ? "Above" : e.state_ma20 === "breakout" ? "Breakout" : e.state_ma20 === "below" ? "Below" : "SMA20"}
            </span>
          </div>

          {/* 6. Vol Pasca-ARA */}
          <div className="hidden lg:flex flex-col items-center w-[80px] lg:w-[90px] flex-shrink-0">
            <span className="text-xs font-semibold tabular-nums text-[var(--color-text-primary)]">
              {fmtVol(e.post_ara_volume)}
            </span>
            <span className="text-[10px] text-[var(--color-text-muted)]">
              {e.k_heavy}x heavy
            </span>
          </div>

          {/* 7. Setup & Signal Badges (Fills the center-right space cleanly) */}
          <div className="hidden sm:flex items-center gap-1.5 flex-1 min-w-[110px] flex-wrap">
            {e.vcp_ok && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20" title={`VCP Ratio: ${e.vcp_ratio?.toFixed(2)} (Kontraksi Volatilitas Minervini)`}>
                VCP
              </span>
            )}
            {e.dryup_ok && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20" title={`Dry-Up Ratio: ${e.dryup_ratio?.toFixed(2)} (Volume Mengering Wyckoff)`}>
                Dry-Up
              </span>
            )}
            {e.liquidity_prima && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20" title="Likuiditas Prima (ADV > Rp1M / 1Jt Lbr)">
                Prima
              </span>
            )}
            {!e.vcp_ok && !e.dryup_ok && !e.liquidity_prima && (
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${(e.net_dist ?? 0) > 0.05 ? "bg-[var(--color-up-bg)] text-[var(--color-up)]" : "bg-[var(--color-muted-bg)] text-[var(--color-text-muted)]"}`}>
                {(e.net_dist ?? 0) > 0.05 ? "Net Acc" : "Standard"}
              </span>
            )}
          </div>

          {/* 8. Skor */}
          <div className="flex flex-col items-center w-[55px] lg:w-[65px] flex-shrink-0">
            <span className="text-sm font-extrabold tabular-nums text-[var(--color-text-primary)]">
              {e.strength != null ? e.strength.toFixed(3) : "-"}
            </span>
          </div>

          {/* 9. Gates (dot indicators) */}
          <div className="flex items-center justify-center gap-1 w-[80px] lg:w-[90px] flex-shrink-0" title={`Gates: ${gatesPassed}/${gateList.length} terpenuhi`}>
            <div className="flex items-center gap-1">
              {gateList.map((g) => (
                <GateDot key={g.key} label={g.label} passed={g.passed} />
              ))}
            </div>
            <span className="text-[10px] font-bold tabular-nums text-[var(--color-text-muted)] ml-1">
              {gatesPassed}/{gateList.length}
            </span>
          </div>

          {/* 10. Expand chevron */}
          <div className="w-5 flex items-center justify-end flex-shrink-0">
            <svg
              className={`w-4 h-4 text-[var(--color-text-muted)] transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </button>

      {/* ── Level 2: Expanded Detail (On Click) ── */}
      {expanded && (
        <div className="px-4 pb-4 animate-expand-row">
          <div className="border-t border-[var(--color-border)] pt-3 mt-0">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-x-6 gap-y-3">

              {/* ── Akumulasi ── */}
              <DetailMetric
                label="Vol Pasca-ARA"
                value={fmtVol(e.post_ara_volume)}
                title={e.post_ara_volume ? `Volume: ${new Intl.NumberFormat("id-ID").format(e.post_ara_volume)} lembar | Est. Nilai: ${fmtIdr(e.post_ara_value || 0)}` : undefined}
              />
              <DetailMetric
                label="Jarak ARA"
                value={e.distance_pct != null ? `${e.distance_pct.toFixed(1)}%` : "-"}
                valueClass={distColor}
              />
              <DetailMetric
                label="Net Dist"
                value={e.net_dist != null ? `${e.net_dist >= 0 ? "+" : ""}${e.net_dist.toFixed(2)}` : "-"}
                valueClass={netDistColor}
              />
              <DetailMetric
                label="Dir Net"
                value={e.net_dist_heavy != null ? `${(e.net_dist_heavy * 100).toFixed(0)}%` : "-"}
                valueClass={dirNetColor}
                title="Proporsi heavy-day yang menutup di atas open (Close > Open)"
              />

              {/* ── Teknikal ── */}
              <DetailMetric
                label="Gap SMA20"
                value={e.sma_gap_pct != null ? `${e.sma_gap_pct >= 0 ? "+" : ""}${e.sma_gap_pct.toFixed(1)}%` : "-"}
                valueClass={(e.sma_gap_pct ?? 0) >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]"}
              />
              <DetailMetric
                label="VCP Ratio"
                value={e.vcp_ratio != null ? e.vcp_ratio.toFixed(2) : "-"}
                valueClass={e.vcp_ok ? "text-[var(--color-up)]" : "text-[var(--color-text-secondary)]"}
                title={e.vcp_ratio != null ? `Rasio volatilitas recent/past: ${e.vcp_ratio.toFixed(3)} (≤0.65 = kontraksi aktif)` : undefined}
              />
              <DetailMetric
                label="Dry-Up"
                value={e.dryup_ratio != null ? e.dryup_ratio.toFixed(2) : "-"}
                valueClass={e.dryup_ok ? "text-[var(--color-up)]" : "text-[var(--color-text-secondary)]"}
                title={e.dryup_ratio != null ? `Rasio volume recent/baseline: ${e.dryup_ratio.toFixed(3)} (≤0.50 = volume mengering)` : undefined}
              />

              {/* ── Likuiditas ── */}
              <DetailMetric
                label="ADV 20 (Vol)"
                value={e.adv_vol_20 != null ? fmtVol(e.adv_vol_20) : "-"}
              />
              <DetailMetric
                label="ADV 20 (Val)"
                value={e.adv_val_20 != null ? fmtVol(e.adv_val_20) : "-"}
              />
              <DetailMetric
                label="Likuiditas"
                value={e.liquidity_prima ? "Prima" : e.liquidity_ok ? "OK" : "Rendah"}
                valueClass={e.liquidity_prima ? "text-[var(--color-up)]" : e.liquidity_ok ? "text-[var(--color-text-primary)]" : "text-[var(--color-down)]"}
              />

              {/* ── Status MA ── */}
              <DetailMetric
                label="Status MA20"
                value={e.state_ma20 === "above" ? "Di Atas" : e.state_ma20 === "breakout" ? "Breakout" : e.state_ma20 === "below" ? "Di Bawah" : "-"}
                valueClass={e.state_ma20 === "above" || e.state_ma20 === "breakout" ? "text-[var(--color-up)]" : e.state_ma20 === "below" ? "text-[var(--color-down)]" : ""}
              />
              <DetailMetric
                label="Window"
                value={`${e.k_heavy} heavy / ${e.window_days} hari`}
              />
            </div>

            {/* ── Notes ── */}
            {(e.note || e.reason) && (
              <div className="mt-3 pt-3 border-t border-[var(--color-border)]/50">
                {e.reason && (
                  <p className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed">
                    <span className="font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Alasan:</span>{" "}
                    {e.reason}
                  </p>
                )}
                {e.note && (
                  <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed mt-1">{e.note}</p>
                )}
              </div>
            )}

            {/* ── CTA ── */}
            <div className="mt-3 pt-3 border-t border-[var(--color-border)]/50 flex items-center justify-between">
              {/* Gates detail */}
              <div className="flex flex-wrap gap-1.5">
                {gateList.map((g) => (
                  <span
                    key={g.key}
                    className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                      g.passed ? "bg-[var(--color-up-bg)] text-[var(--color-up)]" : "bg-[var(--color-down-bg)] text-[var(--color-down)]"
                    }`}
                  >
                    {g.passed ? (
                      <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                    {g.label}
                  </span>
                ))}
              </div>

              <Link
                href={`/saham/${e.code}${qs}`}
                className="flex items-center gap-1 text-xs font-semibold text-[var(--color-primary)] hover:underline flex-shrink-0"
              >
                Detail Analisis
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main Table (Card List) ── */
function ReadyToFlyTable({ data, date, isReadyTab }: { data: ReadyToFlyEntry[]; date?: string; isReadyTab: boolean }) {
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = data.filter((e) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return e.code.toLowerCase().includes(q) || (e.name || "").toLowerCase().includes(q);
  });

  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-[var(--color-text-muted)] border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)]">
        Tidak ada saham yang terdeteksi dalam kategori ini.
      </div>
    );
  }

  const qs = date ? `?date=${date}` : "";

  return (
    <div>
      {/* Search + Count */}
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="relative w-full sm:w-64">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg className="w-4 h-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            placeholder="Cari kode saham..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md text-sm font-medium focus:outline-none focus:border-[var(--color-text-primary)] focus:ring-1 focus:ring-[var(--color-text-primary)] transition-all placeholder:text-[var(--color-text-muted)]"
          />
        </div>
        <span className="text-[11px] font-semibold text-[var(--color-text-muted)] tabular-nums whitespace-nowrap">
          {filtered.length} saham
        </span>
      </div>

      {/* Column Header (Desktop) */}
      <div className="hidden sm:flex items-center gap-3 lg:gap-4 px-4 py-2 text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
        <div className="w-[140px] sm:w-[150px] lg:w-[170px] flex-shrink-0">Saham</div>
        <div className="w-[105px] lg:w-[120px] flex-shrink-0">Harga</div>
        <div className="w-[85px] lg:w-[95px] flex-shrink-0 text-center">Last ARA</div>
        <div className="w-[110px] lg:w-[130px] flex-shrink-0">Density</div>
        <div className="hidden md:block w-[75px] lg:w-[85px] flex-shrink-0 text-center">Gap SMA20</div>
        <div className="hidden lg:block w-[80px] lg:w-[90px] flex-shrink-0 text-center">Vol Pasca</div>
        <div className="hidden sm:block flex-1 min-w-[110px]">Setup / Sinyal</div>
        <div className="w-[55px] lg:w-[65px] flex-shrink-0 text-center">Skor</div>
        <div className="w-[80px] lg:w-[90px] flex-shrink-0 text-center">Gates</div>
        <div className="w-5 flex-shrink-0" />
      </div>

      {/* Card List */}
      <div className="flex flex-col gap-2">
        {filtered.map((e) => (
          <RTFRowCard key={e.code} e={e} qs={qs} isReady={isReadyTab} />
        ))}
      </div>
    </div>
  );
}

export default function ReadyToFlyTabs({ data, date }: { data: ReadyToFlyEntry[]; date?: string }) {
  const [activeTab, setActiveTab] = useState<Tab>("ready");

  const readyData = data.filter((e) => e.status === "ready");
  const almostData = data.filter((e) => e.status === "almost");

  const activeData = activeTab === "ready" ? readyData : almostData;

  return (
    <div className="flex flex-col gap-4">
      {/* Segmented Control */}
      <div className="inline-flex bg-[var(--color-muted-bg)] p-1 rounded-md self-start">
        <button
          onClick={() => setActiveTab("ready")}
          className={`px-3.5 py-1.5 text-xs font-bold rounded transition-all ${
            activeTab === "ready"
              ? "bg-[var(--color-surface)] text-[var(--color-up)] shadow-sm ring-1 ring-black/5"
              : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          }`}
        >
          Ready To Fly
          <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
            activeTab === "ready" ? "bg-[var(--color-up-bg)] text-[var(--color-up)]" : "bg-[var(--color-muted-bg)] text-[var(--color-text-muted)]"
          }`}>
            {readyData.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("almost")}
          className={`px-3.5 py-1.5 text-xs font-bold rounded transition-all ${
            activeTab === "almost"
              ? "bg-[var(--color-surface)] text-[var(--color-warning)] shadow-sm ring-1 ring-black/5"
              : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          }`}
        >
          Hampir Siap
          <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] tabular-nums ${
            activeTab === "almost" ? "bg-[var(--color-warning-bg)] text-[var(--color-warning)]" : "bg-[var(--color-muted-bg)] text-[var(--color-text-muted)]"
          }`}>
            {almostData.length}
          </span>
        </button>
      </div>

      <ReadyToFlyTable data={activeData} date={date} isReadyTab={activeTab === "ready"} />
    </div>
  );
}
