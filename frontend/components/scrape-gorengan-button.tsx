"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { triggerScrapeGorengan } from "@/lib/api/gorengan";

type Toast = { message: string; type: "success" | "error" } | null;

function ToastNotification({ toast, onDone }: { toast: NonNullable<Toast>; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 4000);
    return () => clearTimeout(timer);
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

function GorenganConfirmModal({
  loading,
  globalDate,
  onConfirm,
  onCancel,
}: {
  loading: boolean;
  globalDate: string | null;
  onConfirm: (date?: string) => void;
  onCancel: () => void;
}) {
  const [selectedDate, setSelectedDate] = useState(globalDate || "");

  useEffect(() => {
    function handleKeydown(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) onCancel();
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [loading, onCancel]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-scale-in">
        <div className="px-6 pt-6 pb-2 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-orange-50 flex items-center justify-center">
            <svg className="w-8 h-8 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
            </svg>
          </div>
          <p className="text-lg font-bold text-gray-900 mb-1">Scrape Gorengan</p>
          <p className="text-sm font-medium text-gray-500 px-2">
            Proses ini akan mengunduh data historis dari Yahoo Finance untuk ratusan saham aktif dan memakan waktu sekitar <span className="font-bold text-orange-600">3-5 menit</span>.
          </p>
        </div>

        <div className="px-6 py-4">
          <label className="block text-sm font-semibold text-gray-700 mb-2">Pilih Tanggal (Kosongkan untuk Hari Ini)</label>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            max={new Date().toISOString().slice(0, 10)}
            className="w-full h-12 px-4 text-base font-semibold border-2 border-gray-200 rounded-xl bg-gray-50 text-gray-900 focus:outline-none focus:ring-2 focus:ring-orange-400/30 focus:border-orange-400 transition-all cursor-pointer"
          />
        </div>

        <div className="px-6 pb-6 pt-2 flex gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-all"
          >
            Batal
          </button>
          <button
            onClick={() => onConfirm(selectedDate || undefined)}
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-xl bg-orange-600 text-white text-sm font-bold hover:bg-orange-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
                Memproses...
              </span>
            ) : (
              "Mulai Scrape"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ScrapeGorenganButton() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const globalDate = searchParams.get("date");

  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const router = useRouter();

  const dismissToast = useCallback(() => setToast(null), []);

  async function handleConfirm(date?: string) {
    setLoading(true);
    // Modal keeps showing while loading
    try {
      const res = await triggerScrapeGorengan(date);
      setToast({ message: res.message, type: "success" });
      setShowModal(false);
      // Navigate to the date that was scraped on the current page
      if (date) {
        const params = new URLSearchParams(searchParams.toString());
        params.set("date", date);
        router.push(`${pathname}?${params.toString()}`);
      }
      router.refresh();
    } catch (e) {
      setToast({
        message: e instanceof Error ? e.message : "Scrape gagal",
        type: "error",
      });
      setShowModal(false);
    } finally {
      setLoading(false);
    }
  }

  function handleCancel() {
    setShowModal(false);
  }

  return (
    <>
      {toast && <ToastNotification toast={toast} onDone={dismissToast} />}
      {showModal && (
        <GorenganConfirmModal
          loading={loading}
          globalDate={globalDate}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
      <button
        onClick={() => setShowModal(true)}
        disabled={loading}
        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg border border-transparent bg-orange-100 text-orange-800 hover:bg-orange-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 shadow-sm"
      >
        {loading ? (
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
          </svg>
        )}
        {loading ? "Scraping..." : "Scrape Gorengan"}
      </button>
    </>
  );
}
