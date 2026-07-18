"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50dvh] gap-4">
      <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Terjadi Kesalahan</h2>
      <p className="text-sm text-[var(--color-text-muted)]">{error.message}</p>
      <button
        onClick={reset}
        className="px-4 py-2 text-sm font-medium text-white bg-[var(--color-primary)] rounded-md hover:opacity-90 transition-opacity duration-150 cursor-pointer"
      >
        Coba Lagi
      </button>
    </div>
  );
}
