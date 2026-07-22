"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const POPULAR_STOCKS = ["BBCA", "BMRI", "BBNI", "BBRI", "TLKM", "ASII"];

export default function AnalisisPage() {
  const [code, setCode] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const kode = code.trim().toUpperCase();
    if (kode) router.push(`/saham/${kode}`);
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
                key={stock}
                href={`/saham/${stock}`}
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
