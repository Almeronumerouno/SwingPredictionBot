import Link from "next/link";

export default function SahamNotFound() {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 text-center">
      <div className="relative mb-8">
        <div className="absolute inset-0 bg-[var(--color-primary)]/20 blur-2xl rounded-full"></div>
        <div className="relative flex items-center justify-center w-24 h-24 rounded-3xl bg-[var(--color-surface)] border border-[var(--color-border)] shadow-lg mx-auto text-[var(--color-text-muted)]">
          <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
      </div>
      
      <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-4">
        Saham Tidak Ditemukan
      </h1>
      <p className="text-base sm:text-lg font-medium text-[var(--color-text-secondary)] max-w-md mx-auto mb-8">
        Kode saham yang kamu cari mungkin salah ketik, belum terdaftar di BEI, atau tidak ada data historis yang cukup.
      </p>

      <div className="flex flex-col sm:flex-row gap-4 justify-center w-full max-w-sm mx-auto">
        <Link 
          href="/analisis" 
          className="flex-1 px-6 py-3 bg-[var(--color-primary)] !text-white font-bold rounded-xl shadow-sm hover:opacity-90 transition-opacity"
        >
          Cari Saham Lain
        </Link>
        <Link 
          href="/" 
          className="flex-1 px-6 py-3 bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] font-bold rounded-xl hover:bg-[var(--color-muted-bg)] hover:text-[var(--color-text-primary)] transition-all"
        >
          Ke Dashboard
        </Link>
      </div>
    </div>
  );
}
