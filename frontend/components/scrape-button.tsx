"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchMarketStatus, triggerScrape } from "@/lib/api/scrape";
import type { MarketStatusResponse } from "@/lib/api/scrape";

type Toast = { message: string; type: "success" | "error" } | null;

function Toast({ toast, onDone }: { toast: NonNullable<Toast>; onDone: () => void }) {
  setTimeout(onDone, 4000);

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

function MarketModal({
  status,
  loading,
  onConfirm,
  onCancel,
}: {
  status: MarketStatusResponse;
  loading: boolean;
  onConfirm: (source: string) => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-scale-in">
        <div className="px-6 pt-6 pb-4 text-center">
          <div className={`w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center ${
            status.is_open ? "bg-emerald-100" : "bg-gray-100"
          }`}>
            {status.is_open ? (
              <svg className="w-8 h-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            ) : (
              <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            )}
          </div>
          <p className="text-lg font-bold text-gray-900 mb-1">{status.is_open ? "Pasar Sedang Buka" : "Pasar Sedang Tutup"}</p>
          <p className="text-sm font-medium text-gray-500">{status.message}</p>
        </div>

        <div className="px-6 pb-2">
          <div className={`rounded-xl border p-4 ${
            status.is_open
              ? "bg-amber-50 border-amber-200"
              : "bg-blue-50 border-blue-200"
          }`}>
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">Sumber Data</p>
            <p className="text-sm font-bold text-gray-800">
              {status.is_open
                ? "Yahoo Finance (real-time, pasar buka)"
                : "IDX (EOD snapshot, pasar tutup)"}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {status.is_open
                ? "Data streaming langsung dari Yahoo Finance."
                : "Data ringkasan harian dari Bursa Efek Indonesia."}
            </p>
          </div>
        </div>

        <div className="flex gap-3 px-6 pb-6 pt-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-all"
          >
            Batal
          </button>
          <button
            onClick={() => onConfirm(status.suggested_source)}
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl bg-gray-900 text-sm font-semibold text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
                Scraping...
              </>
            ) : (
              "Lanjutkan Scrape"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ScrapeButton() {
  const [loading, setLoading] = useState(false);
  const [marketStatus, setMarketStatus] = useState<MarketStatusResponse | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const router = useRouter();

  const dismissToast = useCallback(() => setToast(null), []);

  async function handleScrape() {
    setLoading(true);
    try {
      const status = await fetchMarketStatus();
      setMarketStatus(status);
      setShowModal(true);
    } catch {
      setToast({ message: "Gagal cek status pasar", type: "error" });
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm(source: string) {
    setLoading(true);
    setShowModal(false);
    try {
      const res = await triggerScrape(source);
      setToast({ message: res.message, type: "success" });
      router.refresh();
    } catch (e) {
      setToast({
        message: e instanceof Error ? e.message : "Scrape gagal",
        type: "error",
      });
    } finally {
      setLoading(false);
      setMarketStatus(null);
    }
  }

  function handleCancel() {
    setShowModal(false);
    setMarketStatus(null);
  }

  return (
    <>
      {toast && <Toast toast={toast} onDone={dismissToast} />}
      {showModal && marketStatus && (
        <MarketModal
          status={marketStatus}
          loading={loading}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
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