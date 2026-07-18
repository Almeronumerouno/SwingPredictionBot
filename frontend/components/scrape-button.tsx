"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { triggerScrape } from "@/lib/api/scrape";

type Toast = { message: string; type: "success" | "error" } | null;

function Toast({ toast, onDone }: { toast: NonNullable<Toast>; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4000);
    return () => clearTimeout(t);
  }, [onDone]);

  return (
    <div className="fixed top-4 right-4 z-50 animate-slide-in">
      <div
        className={`flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg border text-sm font-semibold ${
          toast.type === "success"
            ? "bg-emerald-50 border-emerald-200 text-emerald-800"
            : "bg-red-50 border-red-200 text-red-800"
        }`}
      >
        {toast.type === "success" ? (
          <svg className="w-5 h-5 text-emerald-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        ) : (
          <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
        {toast.message}
      </div>
    </div>
  );
}

export default function ScrapeButton() {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const router = useRouter();

  const dismissToast = useCallback(() => setToast(null), []);

  async function handleScrape() {
    setLoading(true);
    try {
      const res = await triggerScrape();
      setToast({ message: res.message, type: "success" });
      router.refresh();
    } catch (e) {
      setToast({
        message: e instanceof Error ? e.message : "Scrape gagal",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {toast && <Toast toast={toast} onDone={dismissToast} />}
      <button
        onClick={handleScrape}
        disabled={loading}
        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] hover:bg-[var(--color-muted-bg)] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 shadow-sm"
      >
        {loading ? (
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        )}
        {loading ? "Scraping..." : "Scrape Data"}
      </button>
    </>
  );
}
