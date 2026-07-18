"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50dvh] gap-4">
      <h2 className="text-xl font-semibold">Terjadi Kesalahan</h2>
      <p className="text-zinc-400 text-sm">{error.message}</p>
      <button
        onClick={() => reset()}
        className="bg-zinc-800 hover:bg-zinc-700 px-4 py-2 rounded text-sm transition-colors"
      >
        Coba Lagi
      </button>
    </div>
  );
}
