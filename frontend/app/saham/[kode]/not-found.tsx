import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50dvh] gap-4">
      <h2 className="text-xl font-semibold">Saham Tidak Ditemukan</h2>
      <p className="text-zinc-400 text-sm">Kode saham tidak valid atau tidak tersedia.</p>
      <Link href="/" className="bg-zinc-800 hover:bg-zinc-700 px-4 py-2 rounded text-sm transition-colors">
        Kembali ke Beranda
      </Link>
    </div>
  );
}
