"use client";

export default function BSJPPage() {
  return (
    <>
      <header className="flex flex-col sm:flex-row sm:items-end justify-between mb-6 sm:mb-8 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)] mb-0.5">BSJP Screener</h1>
          <p className="text-[11px] sm:text-xs font-medium text-[var(--color-text-secondary)]">
            Beli Sore, Jual Pagi &middot; Segera hadir
          </p>
        </div>
      </header>

      <section>
        <div className="border border-[var(--color-border)] rounded-lg px-4 py-12 bg-[var(--color-surface)] flex flex-col items-center justify-center text-center">
          <div className="w-10 h-10 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center mb-4">
            <svg className="w-5 h-5 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-[var(--color-text-primary)] mb-1">Coming Soon</p>
          <p className="text-[11px] font-medium text-[var(--color-text-muted)]">
            Fitur BSJP Screener sedang dalam pengembangan. Halaman ini siap untuk diisi konten.
          </p>
        </div>
      </section>
    </>
  );
}
