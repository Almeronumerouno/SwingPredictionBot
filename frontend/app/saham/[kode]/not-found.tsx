import Link from "next/link";

export default function SahamNotFound() {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 text-center">
      <div className="relative mb-8">
        <div className="relative flex items-center justify-center w-20 h-20 rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] shadow-sm mx-auto text-[var(--color-text-muted)]">
          <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
      </div>
      
      <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-4">
        Saham Tidak Ditemukan
      </h1>
      <p className="text-base font-medium text-[var(--color-text-secondary)] max-w-md mx-auto mb-8 leading-relaxed">
        Kode saham yang kamu cari mungkin salah ketik, belum terdaftar di BEI, atau tidak ada data historis yang cukup.
      </p>

      <div className="flex flex-col sm:flex-row gap-3 justify-center w-full max-w-sm mx-auto">
        <Link 
          href="/analisis" 
          style={{ color: "#FFFFFF" }}
          className="flex-1 px-6 py-3 bg-[#0F172A] hover:bg-[#1E293B] dark:bg-[#1E293B] dark:hover:bg-[#334155] dark:border dark:border-[#334155] font-bold rounded-xl active:scale-[0.98] transition-all shadow-xs flex items-center justify-center cursor-pointer !text-white"
        >
          <span style={{ color: "#FFFFFF" }} className="!text-white font-bold">
            Cari Saham Lain
          </span>
        </Link>
        <Link 
          href="/" 
          className="flex-1 px-6 py-3 bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-muted-bg)] font-bold rounded-xl active:scale-[0.98] transition-all shadow-xs flex items-center justify-center cursor-pointer"
        >
          Ke Dashboard
        </Link>
      </div>
    </div>
  );
}
