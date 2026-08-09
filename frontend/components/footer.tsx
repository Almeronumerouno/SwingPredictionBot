export default function Footer() {
  return (
    <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)] py-5 mt-auto print:hidden">
      <div className="max-w-[1400px] px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-[var(--color-text-muted)]">
        <p>&copy; {new Date().getFullYear()} Swingbot IDX. All rights reserved.</p>
        <p className="flex items-center gap-1.5">
          Data disediakan untuk tujuan informasi, bukan rekomendasi investasi.
        </p>
      </div>
    </footer>
  );
}