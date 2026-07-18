import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/sidebar";
import Footer from "@/components/footer";

export const metadata: Metadata = {
  title: "Swingbot — Analisis Teknikal IDX",
  description: "Swing trading signal generator untuk Bursa Efek Indonesia",
  icons: { icon: "/logo.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="flex min-h-screen bg-[var(--color-bg)]">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 overflow-x-hidden">
          <main className="flex-1 w-full max-w-[1400px] px-8 py-8">
            {children}
          </main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
