import Link from "next/link";

export default function NotFound() {
  return (
    <>
      <header className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-1">Saham Tidak Ditemukan</h1>
        <p className="text-sm font-medium text-[var(--color-text-secondary)]">
          Kode saham tidak valid atau tidak tersedia.
        </p>
      </header>

      <div className="max-w-lg">
        <div className="border border-[var(--color-border)] rounded-xl p-8 bg-[var(--color-surface)] shadow-sm flex flex-col items-center text-center gap-5">
          <div className="w-14 h-14 rounded-full bg-red-50 border border-red-200 flex items-center justify-center">
            <svg className="w-7 h-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-[var(--color-text-primary)] mb-1">Coba periksa lagi</p>
            <p className="text-xs text-[var(--color-text-muted)]">Pastikan kode saham yang dimasukkan terdaftar di BEI.</p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-bold rounded-lg bg-[var(--color-surface)] text-[var(--color-text-primary)] border border-[var(--color-border)] hover:bg-[var(--color-muted-bg)] transition-all shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Kembali ke Dashboard
          </Link>
        </div>
      </div>
    </>
  );
}
