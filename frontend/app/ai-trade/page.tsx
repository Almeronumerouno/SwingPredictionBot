"use client";

export default function AITradePage() {
  return (
    <>
      <header className="flex flex-col sm:flex-row sm:items-end justify-between mb-6 sm:mb-8 gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)] mb-0.5">AI Trade</h1>
          <p className="text-[11px] sm:text-xs font-medium text-[var(--color-text-secondary)]">
            Rekomendasi trading berbasis AI &middot; Segera hadir
          </p>
        </div>
      </header>

      <section>
        <div className="border border-[var(--color-border)] rounded-lg px-4 py-12 bg-[var(--color-surface)] flex flex-col items-center justify-center text-center">
          <div className="w-10 h-10 rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center mb-4">
            <svg className="w-5 h-5 text-[var(--color-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714a2.25 2.25 0 0 0 .659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-1.47 4.41a2.25 2.25 0 0 1-2.133 1.59H8.603a2.25 2.25 0 0 1-2.134-1.59L5 14.5m14 0H5" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-[var(--color-text-primary)] mb-1">Coming Soon</p>
          <p className="text-[11px] font-medium text-[var(--color-text-muted)]">
            Fitur AI Trade sedang dalam pengembangan. Halaman ini siap untuk diisi konten.
          </p>
        </div>
      </section>
    </>
  );
}
