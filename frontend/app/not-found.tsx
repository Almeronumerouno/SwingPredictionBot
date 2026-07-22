import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center py-16 px-4 sm:px-6 lg:px-8 text-center">
      <p className="font-mono text-xs tracking-[0.3em] uppercase text-[var(--color-text-muted)] mb-4">
        Halaman tidak ditemukan
      </p>

      <h1
        className="font-mono font-black text-[var(--color-text-primary)] leading-none mb-6 tabular-nums"
        style={{ fontSize: "clamp(4.5rem, 14vw, 8rem)", letterSpacing: "-0.02em" }}
      >
        404
      </h1>

      <div className="w-12 h-[3px] bg-[var(--color-primary)] mb-8"></div>

      <h2 className="text-xl sm:text-2xl font-bold text-[var(--color-text-primary)] mb-3">
        Sepertinya kamu salah jalur
      </h2>
      <p className="text-base text-[var(--color-text-secondary)] max-w-md mx-auto mb-10 leading-relaxed">
        URL yang kamu buka mungkin salah ketik, sudah dipindah, atau memang belum pernah ada.
      </p>

      <div className="flex flex-col sm:flex-row gap-3 justify-center w-full max-w-sm mx-auto">
        <Link
          href="/analisis"
          className="flex-1 px-6 py-3 bg-[var(--color-primary)] !text-white font-bold rounded-xl hover:opacity-90 active:scale-[0.98] transition-all"
        >
          Cari saham
        </Link>
        <Link
          href="/"
          className="flex-1 px-6 py-3 bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] font-bold rounded-xl hover:bg-[var(--color-muted-bg)] hover:text-[var(--color-text-primary)] active:scale-[0.98] transition-all"
        >
          Ke dashboard
        </Link>
      </div>
    </div>
  );
}