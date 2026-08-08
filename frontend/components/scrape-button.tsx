"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { triggerScrape } from "@/lib/api/scrape";

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

type ModalStep = "choose" | "pick-date";

function MarketChoiceModal({
  loading,
  globalDate,
  onConfirm,
  onCancel,
}: {
  loading: boolean;
  globalDate: string | null;
  onConfirm: (source: "yahoo" | "idx", date?: string) => void;
  onCancel: () => void;
}) {
  const [step, setStep] = useState<ModalStep>("choose");
  const [selectedDate, setSelectedDate] = useState(globalDate || "");

  const today = new Date().toISOString().slice(0, 10);
  const isPastDate = Boolean(globalDate && globalDate !== today);

  useEffect(() => {
    function handleKeydown(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) onCancel();
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [loading, onCancel]);

  function handleBack() {
    setStep("choose");
    setSelectedDate("");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-scale-in">
        {step === "choose" && (
          <>
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
                disabled={loading || isPastDate}
                title={isPastDate ? "Market Buka tidak tersedia untuk tanggal historis" : ""}
                className={`group flex flex-col items-start text-left p-4 rounded-xl border-2 transition-all ${
                  isPastDate
                    ? "border-gray-200 bg-gray-50 opacity-60 cursor-not-allowed grayscale"
                    : "border-emerald-200 bg-emerald-50 hover:bg-emerald-100 hover:border-emerald-300 disabled:opacity-50 disabled:cursor-not-allowed"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isPastDate ? "bg-gray-200" : "bg-emerald-500/15"}`}>
                    <svg className={`w-5 h-5 ${isPastDate ? "text-gray-400" : "text-emerald-600"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                    </svg>
                  </div>
                  <span className={`text-sm font-bold uppercase tracking-wider ${isPastDate ? "text-gray-400" : "text-emerald-700"}`}>Buka</span>
                </div>
                <p className={`text-sm font-bold leading-tight ${isPastDate ? "text-gray-500" : "text-gray-900"}`}>Pakai Yahoo Finance</p>
                <p className={`text-xs mt-1 ${isPastDate ? "text-gray-400" : "text-gray-600"}`}>
                  {isPastDate ? "Dinonaktifkan pada tanggal historis." : "Data real-time saat pasar buka."}
                </p>
              </button>

              <button
                onClick={() => setStep("pick-date")}
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
                <p className="text-xs text-gray-600 mt-1">Pilih tanggal, lalu scrape dari IDX.</p>
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
          </>
        )}

        {step === "pick-date" && (
          <>
            <div className="px-6 pt-6 pb-2 text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-blue-50 flex items-center justify-center">
                <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <p className="text-lg font-bold text-gray-900 mb-1">Pilih Tanggal</p>
              <p className="text-sm font-medium text-gray-500">Data akan di-scrape dari IDX untuk tanggal yang dipilih.</p>
            </div>

            <div className="px-6 py-4">
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                max={new Date().toISOString().slice(0, 10)}
                autoFocus
                className="w-full h-12 px-4 text-base font-semibold border-2 border-blue-200 rounded-xl bg-blue-50/50 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-blue-400 transition-all cursor-pointer"
              />
              {selectedDate && (
                <p className="mt-3 text-center text-sm font-medium text-gray-600">
                  Scrape data untuk:{" "}
                  <span className="font-bold text-gray-900">
                    {new Date(selectedDate + "T00:00:00").toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
                  </span>
                </p>
              )}
            </div>

            <div className="px-6 pb-6 pt-2 flex gap-3">
              <button
                onClick={handleBack}
                disabled={loading}
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-all"
              >
                ← Kembali
              </button>
              <button
                onClick={() => onConfirm("idx", selectedDate)}
                disabled={loading || !selectedDate}
                className="flex-1 px-4 py-2.5 rounded-xl bg-gray-900 text-white text-sm font-bold hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                    Scraping...
                  </span>
                ) : (
                  "Scrape Sekarang"
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ScrapeButton() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const globalDate = searchParams.get("date");

  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const router = useRouter();

  const dismissToast = useCallback(() => setToast(null), []);

  async function handleConfirm(source: "yahoo" | "idx", date?: string) {
    setLoading(true);
    setShowModal(false);
    try {
      const res = await triggerScrape(source, date);
      setToast({ message: res.message, type: "success" });
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
        <MarketChoiceModal
          loading={loading}
          globalDate={globalDate}
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
