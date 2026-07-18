import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Swingbot — Analisis Saham",
  description: "Swing trading signal system for IDX stocks",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="bg-zinc-950 text-zinc-100 min-h-dvh">
        <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
