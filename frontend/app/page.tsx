import Link from "next/link";
import { Suspense } from "react";
import { fetchGainers } from "@/lib/api/gainers";
import { fetchGorengan } from "@/lib/api/gorengan";
import { fetchReadyToFly } from "@/lib/api/readytofly";
import ScrapeAllButton from "@/components/scrape-all-button";
import DateSelector from "@/components/date-selector";
import SignalScreener from "@/components/signal-screener";
import AnimatedNumber from "@/components/animated-number";

const fmtIdr = (n: number) =>
  new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
const fmt = (n: number) => new Intl.NumberFormat("id-ID").format(n);
const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

const fmtStamp = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : null;

type FetchResult<T> = { ok: true; value: T } | { ok: false; status: number | null };

async function safeFetch<T>(fn: () => Promise<T>): Promise<FetchResult<T>> {
  try {
    return { ok: true, value: await fn() };
  } catch (e) {
    const status = (e as { status?: number }).status;
    return { ok: false, status: status ?? null };
  }
}

type SignalState = "unscanned" | "error" | "scanned-empty" | "has-data";

function SignalCard({
  href,
  title,
  subtitle,
  state,
  stats,
  stamp,
  noun,
  dateLabel,
  animationDelay,
}: {
  href: string;
  title: string;
  subtitle: string;
  state: SignalState;
  stats: { label: string; value: number; valueClass: string }[];
  stamp: string | null;
  noun: string;
  dateLabel: string;
  animationDelay: string;
}) {
  return (
    <Link
      prefetch={false}
      href={href}
      style={{ animationDelay }}
      className="animate-rise group border border-[var(--color-border)] rounded-lg p-5 bg-[var(--color-surface)] shadow-[var(--shadow-panel)] hover:shadow-[var(--shadow-card-hover)] hover:border-[var(--color-border-strong)] transition-all duration-200 flex flex-col justify-between"
    >
      <div>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">{title}</h3>
            <p className="text-[11px] font-medium text-[var(--color-text-secondary)] mt-0.5">{subtitle}</p>
          </div>
          <svg className="w-4 h-4 text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] group-hover:translate-x-0.5 transition-all flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>

        {state === "has-data" ? (
          <div className="grid grid-cols-2 gap-3 my-3">
            {stats.map((s) => (
              <div key={s.label} className="rounded-md bg-[var(--color-muted-bg)] px-3 py-2.5 border border-[var(--color-border)]/50">
                <p className="text-[11px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">{s.label}</p>
                <p className={`text-xl font-extrabold tabular-nums mt-0.5 tracking-tight ${s.valueClass}`}>{s.value}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-md bg-[var(--color-muted-bg)] px-3 py-3 text-center my-3 border border-[var(--color-border)]/50">
            <p className="text-xs font-semibold text-[var(--color-text-secondary)]">
              {state === "unscanned" && "Belum discan untuk tanggal ini"}
              {state === "error" && "Gagal memuat data"}
              {state === "scanned-empty" && `Tidak ada ${noun} terdeteksi`}
            </p>
            <p className="text-[11px] text-[var(--color-text-secondary)] mt-1 leading-relaxed">
              {state === "unscanned" && `Klik "Scan Market" untuk memindai seluruh pasar.`}
              {state === "error" && "Periksa koneksi server, lalu muat ulang."}
              {state === "scanned-empty" && `Scanner berjalan normal untuk ${dateLabel}.`}
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-[var(--color-border)] mt-1">
        {stamp ? (
          <span className="text-[11px] font-medium text-[var(--color-text-muted)]">
            Diperbarui {stamp}
          </span>
        ) : (
          <span />
        )}
        <svg className="w-4 h-4 text-[var(--color-text-muted)] group-hover:text-[var(--color-primary)] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
        </svg>
      </div>
    </Link>
  );
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;
  const dateLabel = date || "hari ini";

  const [gainersRes, gorenganRes, rtfRes] = await Promise.all([
    safeFetch(() => fetchGainers(date)),
    safeFetch(() => fetchGorengan(date)),
    safeFetch(() => fetchReadyToFly(date)),
  ]);

  const gainers = gainersRes.ok ? gainersRes.value : null;
  const gorengan = gorenganRes.ok ? gorenganRes.value : null;
  const rtf = rtfRes.ok ? rtfRes.value : null;

  const gainerData = gainers?.data ?? [];
  const gorenganData = gorengan?.data ?? [];
  const rtfData = rtf?.data ?? [];

  const topBuy = gainerData.filter((g) => g.recommendation === "BUY").sort((a, b) => (b.swing_score ?? 0) - (a.swing_score ?? 0));
  const avgChange = gainerData.length > 0 ? gainerData.reduce((acc, g) => acc + g.pct_change, 0) / gainerData.length : 0;
  const totalVolume = gainerData.reduce((acc, g) => acc + g.volume, 0);
  const totalValue = gainerData.reduce((acc, g) => acc + g.value, 0);
  const maxGainer = gainerData.length > 0 ? gainerData.reduce((a, b) => (a.pct_change > b.pct_change ? a : b)) : null;

  const countExtreme = gorenganData.filter((g) => g.gorengan_level === "EXTREME").length;
  const countHigh = gorenganData.filter((g) => g.gorengan_level === "HIGH").length;

  const countReady = rtfData.filter((e) => e.status === "ready").length;
  const countAlmost = rtfData.filter((e) => e.status === "almost").length;

  const gorenganState: SignalState = gorenganRes.ok
    ? (gorenganData.length > 0 ? "has-data" : "scanned-empty")
    : (gorenganRes.status === 404 ? "unscanned" : "error");
  const rtfState: SignalState = rtfRes.ok
    ? (rtfData.length > 0 ? "has-data" : "scanned-empty")
    : (rtfRes.status === 404 ? "unscanned" : "error");

  const hasGainerData = gainerData.length > 0;

  type KpiDef = {
    label: string;
    caption: string;
    value: number | null;
    valueClass: string;
    format: "id" | "idr" | "pct";
    decimals?: number;
  };

  const kpis: KpiDef[] = [
    {
      label: "Total Gainer",
      caption: "saham naik terdeteksi",
      value: hasGainerData ? gainerData.length : null,
      valueClass: "text-[var(--color-text-primary)]",
      format: "id",
    },
    {
      label: "Sinyal Buy",
      caption: "rekomendasi beli aktif",
      value: hasGainerData ? topBuy.length : null,
      valueClass: "text-[var(--color-up)]",
      format: "id",
    },
    {
      label: "Nilai Transaksi",
      caption: hasGainerData ? `volume ${fmt(totalVolume)}` : "belum ada data",
      value: hasGainerData ? totalValue : null,
      valueClass: "text-[var(--color-text-primary)]",
      format: "idr",
    },
    {
      label: "Rata-rata Naik",
      caption: hasGainerData ? "seluruh gainer" : "belum ada data",
      value: hasGainerData ? avgChange : null,
      valueClass: avgChange >= 0 ? "text-[var(--color-up)]" : "text-[var(--color-down)]",
      format: "pct",
      decimals: 2,
    },
  ];

  return (
    <>
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 lg:mb-8 gap-4 animate-rise">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)] mb-0.5">Dashboard</h1>
          <p className="text-[11px] font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
            Data Bursa IDX | {dateLabel}
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <Suspense fallback={<div className="h-9 w-40 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
            <DateSelector selected={date || ""} basePath="/" />
          </Suspense>
        </div>
      </header>

      {/* Scan Market Control */}
      <section
        style={{ animationDelay: "40ms" }}
        className="animate-rise border border-[var(--color-border)] rounded-lg p-4 sm:p-5 bg-[var(--color-surface)] mb-6 lg:mb-8"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-[var(--color-primary)]/[0.08] flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <div>
              <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Scan Market</h2>
              <p className="text-[11px] font-medium text-[var(--color-text-secondary)] mt-0.5">
                Pembaruan data bursa serentak.
              </p>
            </div>
          </div>
          <div className="flex-shrink-0 w-full sm:w-auto">
            <Suspense fallback={<div className="h-10 w-36 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse" />}>
              <ScrapeAllButton />
            </Suspense>
          </div>
        </div>
      </section>

      {/* KPI Grid */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6 lg:mb-8">
        {kpis.map((kpi, i) => (
          <div
            key={kpi.label}
            style={{ animationDelay: `${80 + i * 50}ms` }}
            className="animate-rise border border-[var(--color-border)] rounded-lg p-4 bg-[var(--color-surface)]"
          >
            <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">{kpi.label}</p>
            {kpi.value !== null ? (
              <AnimatedNumber
                value={kpi.value}
                format={kpi.format}
                decimals={kpi.decimals ?? 0}
                className={`block text-xl sm:text-2xl font-extrabold tabular-nums tracking-tight ${kpi.valueClass}`}
              />
            ) : (
              <p className="text-xl sm:text-2xl font-extrabold tabular-nums tracking-tight text-[var(--color-text-muted)]">--</p>
            )}
            <p className="text-[11px] font-medium text-[var(--color-text-secondary)] mt-1">{kpi.caption}</p>
          </div>
        ))}
      </section>

      {/* Signal Radar: Gorengan & Ready To Fly */}
      <section className="mb-6 lg:mb-8">
        <div className="mb-3">
          <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Radar Sinyal</h2>
          <p className="text-[11px] font-medium text-[var(--color-text-secondary)] mt-0.5">
            Deteksi aktivitas bandar dan pola akumulasi.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
          <SignalCard
            href={`/gorengan${date ? `?date=${date}` : ""}`}
            title="Scanner Gorengan"
            subtitle="Deteksi pump-and-dump & bandar"
            state={gorenganState}
            stamp={fmtStamp(gorengan?.scraped_at)}
            noun="gorengan"
            dateLabel={dateLabel}
            animationDelay="110ms"
            stats={[
              { label: "Extreme", value: countExtreme, valueClass: "text-[var(--color-down)]" },
              { label: "High Risk", value: countHigh, valueClass: "text-[var(--color-warning)]" },
            ]}
          />
          <SignalCard
            href={`/ready-to-fly${date ? `?date=${date}` : ""}`}
            title="Ready To Fly"
            subtitle="Akumulasi post-ARA, kandidat breakout"
            state={rtfState}
            stamp={fmtStamp(rtf?.scraped_at)}
            noun="ready to fly"
            dateLabel={dateLabel}
            animationDelay="170ms"
            stats={[
              { label: "Siap Terbang", value: countReady, valueClass: "text-[var(--color-up)]" },
              { label: "Hampir Siap", value: countAlmost, valueClass: "text-[var(--color-warning)]" },
            ]}
          />
        </div>
      </section>

      {/* Market Overview & Top Gainers */}
      <section className="mb-8 lg:mb-10">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-bold text-[var(--color-text-primary)]">Market Overview</h2>
              {gainers && fmtStamp(gainers.scraped_at) && (
                <span className="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">
                  {fmtStamp(gainers.scraped_at)}
                </span>
              )}
            </div>
          </div>
          <Link
            href={`/top-gainers${date ? `?date=${date}` : ""}`}
            className="flex items-center gap-1 text-xs font-semibold text-[var(--color-primary)] hover:underline"
          >
            Lihat Semua Gainers
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
 
        {!gainersRes.ok ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-8 text-center">
            <p className="text-sm font-semibold text-[var(--color-text-primary)]">
              {gainersRes.status === 404 ? "Data gainers belum discan untuk tanggal ini" : "Gagal memuat data gainers"}
            </p>
            <p className="mx-auto mt-1 max-w-md text-xs text-[var(--color-text-secondary)]">
              {gainersRes.status === 404
                ? `Gunakan tombol "Scan Market" di atas untuk memulai scanning data ${dateLabel}.`
                : "Periksa koneksi ke server API backend, lalu muat ulang halaman ini."}
            </p>
          </div>
        ) : gainerData.length === 0 ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-8 text-center">
            <p className="text-sm font-medium text-[var(--color-text-secondary)]">
              Belum ada data gainer untuk {dateLabel}. Jalankan &quot;Scan Market&quot; di atas.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:gap-4 lg:grid-cols-3">
            {maxGainer && (
              <Link
                prefetch={false}
                href={`/saham/${maxGainer.code}${date ? `?date=${date}` : ""}`}
                className="group flex flex-col justify-between rounded-lg border border-l-4 border-[var(--color-border)] border-l-[var(--color-up)] bg-[var(--color-surface)] p-5 transition-colors hover:border-[var(--color-border-strong)] hover:border-l-[var(--color-up)] lg:col-span-1"
              >
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Top Gainer</h3>
                    <span className="rounded-md border border-[var(--color-up)]/20 bg-[var(--color-up-bg)] px-2 py-0.5 font-mono text-[11px] font-bold tabular-nums text-[var(--color-up)]">
                      {pct(maxGainer.pct_change)}
                    </span>
                  </div>
                  <p className="font-mono text-2xl font-extrabold tracking-tight text-[var(--color-text-primary)] transition-colors group-hover:text-[var(--color-primary)]">
                    {maxGainer.code}
                  </p>
                  <p className="mt-0.5 truncate text-xs font-medium text-[var(--color-text-secondary)]">{maxGainer.name}</p>
                  <div className="mt-4 grid grid-cols-2 gap-3 border-t border-[var(--color-border)] pt-3">
                    <div>
                      <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Harga</p>
                      <p className="font-mono text-sm font-bold tabular-nums text-[var(--color-text-primary)]">{fmtIdr(maxGainer.close)}</p>
                    </div>
                    <div>
                      <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Volume</p>
                      <p className="font-mono text-sm font-bold tabular-nums text-[var(--color-text-primary)]">{fmt(maxGainer.volume)}</p>
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-[var(--color-border)] pt-3">
                  <span className="text-xs font-semibold text-[var(--color-primary)]">Lihat detail analisis</span>
                  <svg className="h-3.5 w-3.5 text-[var(--color-primary)] transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </div>
              </Link>
            )}
            <div className="lg:col-span-2">
              <SignalScreener data={gainerData} date={date} />
            </div>
          </div>
        )}
      </section>
    </>
  );
}
 