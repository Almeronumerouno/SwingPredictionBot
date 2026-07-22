"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 text-center">
      <div className="relative mb-8">
        <div className="absolute inset-0 bg-[var(--color-down)]/20 blur-2xl rounded-full"></div>
        <div className="relative flex items-center justify-center w-24 h-24 rounded-3xl bg-[var(--color-surface)] border border-[var(--color-border)] shadow-lg mx-auto text-[var(--color-down)]">
          <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
      </div>
      
      <h1 className="text-4xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-4">
        Terjadi Kesalahan Sistem
      </h1>
      <p className="text-base font-medium text-[var(--color-text-secondary)] max-w-md mx-auto mb-8">
        {error.message || "Maaf, ada gangguan saat mencoba memuat halaman ini."}
      </p>

      <button
        onClick={reset}
        className="px-8 py-3 bg-[var(--color-text-primary)] text-white font-bold rounded-xl hover:opacity-90 transition-opacity"
      >
        Coba Muat Ulang
      </button>
    </div>
  );
}
