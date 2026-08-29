"use client";

import { useState } from "react";

const STOCKBIT_RULES = [
  { no: 1, name: "1 Day Price Returns (%) >= 8", desc: "Kenaikan harga minimal +8% di hari T" },
  { no: 2, name: "1 Week Price Returns >= 10", desc: "Momentum mingguan positif minimal +10%" },
  { no: 3, name: "Price >= 1.0 * High Price", desc: "Close di harga tertinggi / ARA — buyer dominan" },
  { no: 4, name: "Volume >= 1.8 * Volume MA 20", desc: "Konfirmasi lonjakan volume di atas rata-rata 20 hari" },
  { no: 5, name: "Value >= 200000000", desc: "Floor likuiditas min. transaksi Rp 200 Juta" },
];

export default function StockbitFormulaCard() {
  const [copied, setCopied] = useState(false);

  const fullText = STOCKBIT_RULES.map((r) => `RULE ${r.no}: ${r.name}`).join("\n");

  const handleCopy = () => {
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="border border-[var(--color-border)] rounded-xl p-5 bg-[var(--color-surface)] shadow-sm space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-bold text-[var(--color-text-primary)]">Formula Stockbit Screener</h3>
            <p className="text-[11px] text-[var(--color-text-secondary)]">5 rule tervalidasi backtest 73.6% WR — Sinyal aktif setiap hari bursa</p>
          </div>
        </div>

        <button
          onClick={handleCopy}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-sm ${
            copied
              ? "bg-emerald-600 text-white"
              : "bg-[var(--color-primary)] text-white hover:opacity-90"
          }`}
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Tersalin!
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
              </svg>
              Salin Rumus
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
        {STOCKBIT_RULES.map((rule) => (
          <div
            key={rule.no}
            className="flex items-start gap-2.5 p-2.5 rounded-lg bg-[var(--color-muted-bg)] border border-[var(--color-border)]/50"
          >
            <span className="flex-shrink-0 w-5 h-5 rounded bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-bold text-[10px] flex items-center justify-center">
              {rule.no}
            </span>
            <div className="min-w-0">
              <p className="font-bold text-[var(--color-text-primary)] text-[11px] truncate">{rule.name}</p>
              <p className="text-[10px] text-[var(--color-text-muted)] font-sans mt-0.5">{rule.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
