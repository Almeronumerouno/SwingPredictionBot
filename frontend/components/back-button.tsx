"use client";

import { useRouter } from "next/navigation";

export default function BackButton() {
  const router = useRouter();

  return (
    <button 
      onClick={() => router.back()} 
      className="inline-flex items-center gap-1.5 px-3 py-1.5 -ml-3 rounded-lg text-sm font-semibold text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)] hover:text-[var(--color-text-primary)] transition-all duration-200"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
      Kembali
    </button>
  );
}
