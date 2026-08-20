"use client";

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { triggerScrapeAll } from "@/lib/api/scan-all";

type Toast = { message: string; type: "success" | "error" } | null;

function ToastNotification({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(onDone, 4000);
    return () => clearTimeout(timer);
  }, [toast, onDone]);

  if (!toast) return null;

  const isSuccess = toast.type === "success";

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-slide-in max-w-sm">
      <div
        className={`flex items-start gap-3 p-4 rounded-lg shadow-lg border text-sm font-medium ${
          isSuccess
            ? "bg-[var(--color-up-bg)] border-emerald-200 text-emerald-900"
            : "bg-[var(--color-down-bg)] border-red-200 text-red-900"
        }`}
      >
        <div className="flex-shrink-0 mt-0.5">
          {isSuccess ? (
            <svg className="w-5 h-5 text-[var(--color-up)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-[var(--color-down)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>
        <p className="flex-1 text-xs leading-relaxed">{toast.message}</p>
        <button onClick={onDone} className="text-gray-400 hover:text-gray-600 p-0.5 rounded">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

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
  const todayStr = new Date().toISOString().slice(0, 10);
  const isPastDate = Boolean(globalDate && globalDate < todayStr);
  const [step, setStep] = useState<"choose-source" | "confirm">("choose-source");
  const [selectedSource, setSelectedSource] = useState<"yahoo" | "idx" | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(
    globalDate || todayStr
  );

  function selectSource(source: "yahoo" | "idx") {
    if (source === "yahoo" && isPastDate) return; // histori cuma bisa via IDX
    setSelectedSource(source);
  }

  function proceedToConfirm() {
    if (!selectedSource) return;
    setStep("confirm");
  }

  // Keyboard shortcut ESC to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) {
        onCancel();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [loading, onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs transition-opacity duration-200"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onCancel();
      }}
    >
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-2xl max-w-md w-full overflow-hidden animate-scale-in transition-all">
        {/* Header */}
        <div className="px-5 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-[var(--color-text-primary)]">Scan Market Keseluruhan</h3>
              <span className="text-[10px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded bg-[var(--color-primary)]/[0.08] text-[var(--color-primary)]">
                Langkah {step === "choose-source" ? "1" : "2"} / 2
              </span>
            </div>
            <p className="text-[11px] font-medium text-[var(--color-text-muted)] mt-0.5">
              Pilih sumber data, lalu konfirmasi untuk memulai scan.
            </p>
          </div>
          <button
            onClick={onCancel}
            disabled={loading}
            className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--color-text-muted)] hover:bg-[var(--color-muted-bg)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
            aria-label="Tutup modal"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {step === "choose-source" && (
          <>
            <div className="p-5 grid grid-cols-1 gap-3">
              {/* Option 1: Yahoo Finance */}
              <button
                onClick={() => selectSource("yahoo")}
                disabled={loading || isPastDate}
                className={`group relative flex items-start gap-3 p-3.5 rounded-md border text-left w-full transition-all duration-150 cursor-pointer ${
                  isPastDate
                    ? "opacity-50 cursor-not-allowed border-[var(--color-border)] bg-[var(--color-muted-bg)]"
                    : selectedSource === "yahoo"
                    ? "border-emerald-500 bg-[var(--color-up-bg)] shadow-xs"
                    : "border-emerald-200 bg-[var(--color-up-bg)] hover:border-emerald-400 hover:shadow-xs"
                }`}
              >
                {selectedSource === "yahoo" && (
                  <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                <div className="w-8 h-8 rounded-md bg-[var(--color-up)]/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg className="w-4 h-4 text-[var(--color-up)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-[var(--color-text-primary)]">Yahoo Finance</span>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                      Real-Time
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--color-text-secondary)] mt-1 leading-relaxed">
                    {isPastDate
                      ? "Hanya tersedia untuk data hari ini (bukan tanggal historis)."
                      : "Scan data LIVE hari ini dari Yahoo Finance — bar intraday terbaru (bisa dipakai kapan saja, sebelum & sesudah market tutup)."}
                  </p>
                </div>
              </button>

              {/* Option 2: IDX EOD */}
              <button
                onClick={() => selectSource("idx")}
                disabled={loading}
                className={`group relative flex items-start gap-3 p-3.5 rounded-md border transition-all duration-150 cursor-pointer text-left w-full ${
                  selectedSource === "idx"
                    ? "border-[var(--color-primary)] bg-[var(--color-muted-bg)] shadow-xs"
                    : "border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-muted-bg)] hover:border-[var(--color-border-strong)]"
                }`}
              >
                {selectedSource === "idx" && (
                  <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-[var(--color-primary)] flex items-center justify-center">
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                <div className="w-8 h-8 rounded-md bg-slate-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg className="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-[var(--color-text-primary)]">IDX (EOD)</span>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                      Pilih Tanggal
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--color-text-secondary)] mt-1 leading-relaxed">
                    Scrape data resmi penutupan bursa (End of Day) untuk tanggal spesifik.
                  </p>
                </div>
              </button>
            </div>

            <div className="px-5 pb-4 flex items-center justify-between border-t border-[var(--color-border)] pt-3">
              <button
                onClick={onCancel}
                disabled={loading}
                className="px-4 py-1.5 text-xs font-semibold text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)] rounded-md transition-colors cursor-pointer"
              >
                Batal
              </button>
              <button
                onClick={proceedToConfirm}
                disabled={loading || !selectedSource}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] rounded-md transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-xs"
              >
                Lanjut ke Konfirmasi
              </button>
            </div>
          </>
        )}

        {step === "confirm" && selectedSource && (
          <>
            <div className="p-5">
              {selectedSource === "yahoo" ? (
                <div className="rounded-md border border-emerald-200 bg-[var(--color-up-bg)] p-4">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-[var(--color-text-primary)]">Yahoo Finance</span>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                      Real-Time
                    </span>
                  </div>
                  <p className="text-xs text-[var(--color-text-secondary)] mt-1.5 leading-relaxed">
                    Scan data pasar real-time <span className="font-semibold text-[var(--color-text-primary)]">hari ini </span> untuk
                    memperbarui Top Gainers, Gorengan, &amp; Ready To Fly secara serentak.
                  </p>
                </div>
              ) : (
                <>
                  <label className="block text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">
                    Tanggal Bursa IDX (EOD)
                  </label>
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    max={todayStr}
                    autoFocus
                    className="w-full h-10 px-3 text-xs font-semibold border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-primary)] transition-all cursor-pointer"
                  />
                  {selectedDate && (
                    <p className="mt-3 text-center text-xs font-medium text-[var(--color-text-secondary)]">
                      Target tanggal:{" "}
                      <span className="font-bold text-[var(--color-text-primary)]">
                        {new Date(selectedDate + "T00:00:00").toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
                      </span>
                    </p>
                  )}
                  <p className="mt-3 text-[11px] font-medium text-[var(--color-text-muted)] leading-relaxed">
                    Data resmi penutupan bursa (End of Day). Akan memperbarui Top Gainers,
                    Gorengan, &amp; Ready To Fly untuk tanggal tersebut.
                  </p>
                </>
              )}
            </div>

            <div className="px-5 pb-4 flex gap-2 border-t border-[var(--color-border)] pt-3">
              <button
                onClick={() => setStep("choose-source")}
                disabled={loading}
                className="flex-1 px-4 py-2 text-xs font-semibold text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)] rounded-md transition-colors cursor-pointer"
              >
                Kembali
              </button>
              <button
                onClick={() => onConfirm(selectedSource, selectedSource === "idx" ? selectedDate : undefined)}
                disabled={loading || (selectedSource === "idx" && !selectedDate)}
                className="flex-1 px-4 py-2 text-xs font-semibold text-white bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] rounded-md transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-xs"
              >
                {loading ? "Scanning..." : "Konfirmasi & Scan"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ScrapeAllButton() {
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
      const res = await triggerScrapeAll(source, date);
      setToast({ message: res.message, type: "success" });
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
      {/* Modal & toast di-render via PORTAL ke document.body.
          Tanpa portal, `position: fixed` di dalamnya patah karena section
          dashboard memakai animate-rise (fill-mode `both` mempertahankan
          transform, sehingga section jadi containing block → fixed ke-resolve
          relatif ke section: modal muncul miring/kepotong di atas layar). */}
      {toast &&
        createPortal(
          <ToastNotification toast={toast} onDone={dismissToast} />,
          document.body
        )}
      {showModal &&
        createPortal(
          <MarketChoiceModal
            loading={loading}
            globalDate={globalDate}
            onConfirm={handleConfirm}
            onCancel={handleCancel}
          />,
          document.body
        )}
      <button
        onClick={() => setShowModal(true)}
        disabled={loading}
        className="group h-9 px-3.5 inline-flex items-center gap-2 rounded-md text-xs font-semibold text-white bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] active:scale-[0.98] transition-all duration-150 disabled:opacity-70 disabled:cursor-not-allowed shadow-xs cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 border border-slate-800"
      >
        {loading ? (
          <>
            <svg className="animate-spin -ml-0.5 h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Scanning...
          </>
        ) : (
          <>
            <svg className="w-3.5 h-3.5 text-white transition-transform duration-500 ease-out group-hover:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Scan Market
          </>
        )}
      </button>
    </>
  );
}