"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import Link from "next/link";

const POPULAR_STOCKS = ["BBCA", "BMRI", "BBNI", "BBRI", "TLKM", "ASII"];

function AnalisisContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  
  const initialDate = searchParams.get("date") || "";
  const [code, setCode] = useState("");
  const [selectedDate, setSelectedDate] = useState(initialDate);
  const [isFocused, setIsFocused] = useState(false);

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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const kode = code.trim().toUpperCase();
    if (kode) {
      const dateParam = selectedDate ? `?date=${selectedDate}` : "";
      router.push(`/saham/${kode}${dateParam}`);
    }
  }

  function navigateStock(stock: string) {
    const dateParam = selectedDate ? `?date=${selectedDate}` : "";
    return `/saham/${stock}${dateParam}`;
  }

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
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
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
