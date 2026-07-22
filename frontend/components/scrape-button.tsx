"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { triggerScrape } from "@/lib/api/scrape";

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

function MarketChoiceModal({
  loading,
  onConfirm,
  onCancel,
}: {
  loading: boolean;
  onConfirm: (source: "yahoo" | "idx") => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-scale-in">
        <div className="px-6 pt-6 pb-2 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-lg font-bold text-gray-900 mb-1">Status Pasar Hari Ini</p>
          <p className="text-sm font-medium text-gray-500">Pilih kondisi pasar untuk menentukan sumber data.</p>
        </div>

        <div className="px-6 py-4 grid grid-cols-2 gap-3">
          <button
            onClick={() => onConfirm("yahoo")}
            disabled={loading}
            className="group flex flex-col items-start text-left p-4 rounded-xl border-2 border-emerald-200 bg-emerald-50 hover:bg-emerald-100 hover:border-emerald-300 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <span className="text-sm font-bold text-emerald-700 uppercase tracking-wider">Buka</span>
            </div>
            <p className="text-sm font-bold text-gray-900 leading-tight">Pakai Yahoo Finance</p>
            <p className="text-xs text-gray-600 mt-1">Data real-time saat pasar buka.</p>
          </button>

          <button
            onClick={() => onConfirm("idx")}
            disabled={loading}
            className="group flex flex-col items-start text-left p-4 rounded-xl border-2 border-gray-200 bg-gray-50 hover:bg-gray-100 hover:border-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg bg-gray-500/15 flex items-center justify-center">
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
              </div>
              <span className="text-sm font-bold text-gray-600 uppercase tracking-wider">Tutup</span>
            </div>
            <p className="text-sm font-bold text-gray-900 leading-tight">Pakai IDX (EOD)</p>
            <p className="text-xs text-gray-600 mt-1">Snapshot akhir hari Bursa Efek Indonesia.</p>
          </button>
        </div>

        <div className="px-6 pb-6 pt-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-all"
          >
            Batal
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ScrapeButton() {
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const router = useRouter();

  const dismissToast = useCallback(() => setToast(null), []);

  async function handleConfirm(source: "yahoo" | "idx") {
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
    }
  }

  function handleCancel() {
    setShowModal(false);
  }

  return (
    <>
      {toast && <Toast toast={toast} onDone={dismissToast} />}
      {showModal && (
        <MarketChoiceModal
          loading={loading}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
      <button
        onClick={() => setShowModal(true)}
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
