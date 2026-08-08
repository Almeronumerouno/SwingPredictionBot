"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import Link from "next/link";

const POPULAR_STOCKS = ["BBCA", "BMRI", "BBNI", "BBRI", "TLKM", "ASII"];

const HISTORY_KEY = "swingbot-search-history";
const HISTORY_LIMIT = 8;

function AnalisisContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  
  const initialDate = searchParams.get("date") || "";
  const [code, setCode] = useState("");
  const [selectedDate, setSelectedDate] = useState(initialDate);
  const [isFocused, setIsFocused] = useState(false);
  const [searchHistory, setSearchHistory] = useState<string[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyClosing, setHistoryClosing] = useState(false);
  const closeTimerRef = useRef<number | null>(null);

  // Buka dropdown (batal fase penutupan kalau lagi jalan)
  function openHistory() {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setHistoryClosing(false);
    setHistoryOpen(true);
  }

  // Tutup dropdown dengan animasi exit dulu, baru buang dari DOM
  function closeHistory() {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
    }
    if (!historyOpen) return;
    setHistoryClosing(true);
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null;
      setHistoryClosing(false);
      setHistoryOpen(false);
    }, 150);
  }

  // Bersihkan timer saat unmount
  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  // Muat riwayat pencarian dari localStorage (client-only)
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(HISTORY_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setSearchHistory(parsed.filter((k) => typeof k === "string").slice(0, HISTORY_LIMIT));
        }
      }
    } catch {
      // localStorage tidak tersedia / corrupt: abaikan
    }
  }, []);

  // Sync date changes to URL so that back button restores it
  function handleDateChange(newDate: string) {
    setSelectedDate(newDate);
    const params = new URLSearchParams(searchParams.toString());
    if (newDate) {
      params.set("date", newDate);
    } else {
      params.delete("date");
    }
    const qs = params.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`);
  }

  function saveSearchHistory(kodeRaw: string) {
    const kode = kodeRaw.trim().toUpperCase();
    if (!kode) return;
    const next = [kode, ...searchHistory.filter((k) => k !== kode)].slice(0, HISTORY_LIMIT);
    setSearchHistory(next);
    try {
      window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    } catch {
      // storage penuh / mode privat: riwayat tetap hidup di state sesi ini
    }
  }

  function removeFromHistory(kode: string) {
    const next = searchHistory.filter((k) => k !== kode);
    setSearchHistory(next);
    try {
      window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    } catch {
      // abaikan
    }
  }

  function clearAllHistory() {
    setSearchHistory([]);
    try {
      window.localStorage.removeItem(HISTORY_KEY);
    } catch {
      // abaikan
    }
  }

  function goToStock(kode: string) {
    saveSearchHistory(kode);
    const dateParam = selectedDate ? `?date=${selectedDate}` : "";
    router.push(`/saham/${kode}${dateParam}`);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const kode = code.trim().toUpperCase();
    if (kode) {
      goToStock(kode);
    }
  }

  function navigateStock(stock: string) {
    const dateParam = selectedDate ? `?date=${selectedDate}` : "";
    return `/saham/${stock}${dateParam}`;
  }

  const query = code.trim().toUpperCase();
  const visibleHistory = (query ? searchHistory.filter((k) => k.includes(query)) : searchHistory).slice(0, 5);

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-2xl text-center mb-10">
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-4">
          Analisis Saham
        </h1>
        <p className="text-base sm:text-lg font-medium text-[var(--color-text-secondary)]">
          Cari saham di Bursa Efek Indonesia dan dapatkan analisis teknikal komprehensif, sinyal swing trading, dan trading plan otomatis.
        </p>
      </div>

      <div className="w-full max-w-xl">
        {/* Date Picker */}
        <div className="flex items-center justify-center gap-3 mb-5">
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm">
            <svg className="w-4 h-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-sm font-semibold text-[var(--color-text-secondary)]">Tanggal Data:</span>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => handleDateChange(e.target.value)}
              max={new Date().toISOString().slice(0, 10)}
              className="h-8 px-2 text-sm font-bold border-none bg-transparent text-[var(--color-text-primary)] focus:outline-none focus:ring-0 cursor-pointer"
            />
            {selectedDate && (
              <button
                onClick={() => handleDateChange("")}
                className="ml-1 w-5 h-5 rounded-full flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-muted-bg)] transition-colors"
                title="Reset ke hari ini"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

        </div>

        {/* Search bar */}
        <form onSubmit={handleSubmit} className="relative group">
          <div className={`absolute inset-0 bg-gradient-to-r from-blue-500/20 to-[var(--color-up)]/20 rounded-2xl blur-xl transition-opacity duration-500 ${isFocused ? 'opacity-100' : 'opacity-0'}`}></div>
          <div className="relative bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl shadow-sm transition-all duration-300 hover:shadow-md focus-within:shadow-lg focus-within:border-[var(--color-primary)]/30 p-2 flex items-center">
            <div className="pl-4 pr-2 text-[var(--color-text-muted)]">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/[^a-zA-Z]/g, "").slice(0, 4))}
              onFocus={() => {
                setIsFocused(true);
                openHistory();
              }}
              onBlur={() => {
                setIsFocused(false);
                closeHistory();
              }}
              placeholder="Masukkan kode saham (cth: BBCA)"
              maxLength={4}
              className="w-full py-4 px-2 text-lg font-bold tracking-wider uppercase text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] placeholder:font-medium placeholder:normal-case placeholder:tracking-normal bg-transparent border-none focus:outline-none focus:ring-0"
              autoFocus
            />
            <button
              type="submit"
              disabled={!code.trim()}
              className="px-6 py-3 bg-[var(--color-text-primary)] text-white font-bold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity whitespace-nowrap"
            >
              Cari
            </button>
          </div>
        </form>

        {/* Search history dropdown */}
        {(historyOpen || historyClosing) && visibleHistory.length > 0 && (
          <div
            className={`mt-4 border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] shadow-sm overflow-hidden text-left ${
              historyClosing ? "animate-dropdown-exit" : "animate-dropdown-in"
            }`}
          >
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--color-border)] animate-dropdown-header">
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Pencarian Terakhir
              </p>
              <button
                type="button"
                onClick={clearAllHistory}
                className="text-[11px] font-semibold text-red-500 hover:text-red-700 transition-colors"
              >
                Hapus Semua
              </button>
            </div>
            <ul>
              {visibleHistory.map((kode, i) => (
                <li
                  key={kode}
                  className="animate-history-item group flex items-center border-b last:border-b-0 border-[var(--color-border)]/50"
                  style={{ animationDelay: `${i * 30}ms` }}
                >
                  <button
                    type="button"
                    onClick={() => goToStock(kode)}
                    className="flex-1 flex items-center gap-2.5 px-4 py-2.5 text-left hover:bg-[var(--color-muted-bg)] transition-all duration-150 hover:translate-x-0.5"
                  >
                    <svg className="w-4 h-4 text-[var(--color-text-muted)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-sm font-bold uppercase tracking-wider text-[var(--color-text-primary)]">{kode}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => removeFromHistory(kode)}
                    aria-label={`Hapus ${kode} dari pencarian terakhir`}
                    className="mr-1.5 w-8 h-8 flex items-center justify-center rounded-lg text-[var(--color-text-muted)] hover:text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-8 text-center">
          <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">
            Pencarian Populer
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {POPULAR_STOCKS.map((stock) => (
              <Link
                prefetch={false}
                key={stock}
                href={navigateStock(stock)}
                onClick={() => saveSearchHistory(stock)}
                className="px-4 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm font-bold text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] hover:border-[var(--color-primary)]/30 hover:shadow-sm transition-all"
              >
                {stock}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AnalisisPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm font-medium text-[var(--color-text-muted)]">Memuat...</div>}>
      <AnalisisContent />
    </Suspense>
  );
}
