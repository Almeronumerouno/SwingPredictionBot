"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useState, useEffect, useCallback } from "react";

const navItems = [
  {
    label: "Dashboard",
    href: "/",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zm-10 9a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1H5a1 1 0 01-1-1v-3zm10-2a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1h-4a1 1 0 01-1-1v-5z" />
      </svg>
    ),
  },
  {
    label: "Top Gainers",
    href: "/top-gainers",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    ),
  },
  {
    label: "Gorengan",
    href: "/gorengan",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
      </svg>
    ),
  },
  {
    label: "Ready To Fly",
    href: "/ready-to-fly",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2 22h20" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6.36 17.4 4 17l-2-4 1.1-.55a2 2 0 0 1 1.8 0l.17.1a2 2 0 0 0 1.8 0L8 12 5 6l.9-.45a2 2 0 0 1 2.09.2l4.02 3a2 2 0 0 0 2.1.2l4.19-2.06a2.41 2.41 0 0 1 1.73-.17L21 7a1.4 1.4 0 0 1 .87 1.99l-.38.76c-.23.46-.6.84-1.07 1.08L7.58 17.2a2 2 0 0 1-1.22.18Z" />
      </svg>
    ),
  },
  {
    label: "AI Trade",
    href: "/ai-trade",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714a2.25 2.25 0 0 0 .659 1.591L19 14.5M14.25 3.104c.251.023.501.05.75.082M19 14.5l-1.47 4.41a2.25 2.25 0 0 1-2.133 1.59H8.603a2.25 2.25 0 0 1-2.134-1.59L5 14.5m14 0H5" />
      </svg>
    ),
  },
  {
    label: "Analisis",
    href: "/analisis",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const date = searchParams.get("date");
  const qs = date ? `?date=${date}` : "";

  return (
    <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
      {navItems.map((item) => {
        const isActive =
          item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);

        return (
          <Link
            key={item.href}
            href={`${item.href}${qs}`}
            onClick={onNavigate}
            aria-current={isActive ? "page" : undefined}
            className={`relative group flex items-center gap-2.5 px-3 py-2 text-[13px] font-medium rounded-md transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 ${
              isActive
                ? "bg-[var(--color-primary)]/[0.06] text-[var(--color-primary)] font-semibold before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:h-5 before:w-[3px] before:rounded-r-full before:bg-[var(--color-primary)]"
                : "text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            {item.icon}
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarFooterNote() {
  return (
    <div className="px-3 py-3 border-t border-[var(--color-border)]">
      <p className="px-3 text-[11px] font-medium text-[var(--color-text-muted)] leading-tight">
        Sumber data: IDX &amp; Yahoo Finance
      </p>
    </div>
  );
}

function SidebarInner() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  // Close sidebar on route change
  useEffect(() => {
    const raf = requestAnimationFrame(() => setIsOpen(false));
    return () => cancelAnimationFrame(raf);
  }, [pathname]);

  // Lock body scroll when sidebar is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  const close = useCallback(() => setIsOpen(false), []);

  return (
    <>
      {/* ===== Mobile Top Bar ===== */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 h-14 bg-[var(--color-surface)] border-b border-[var(--color-border)] flex items-center justify-between px-4 print:hidden">
        <button
          onClick={() => setIsOpen(true)}
          className="w-9 h-9 flex items-center justify-center rounded-md hover:bg-[var(--color-muted-bg)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
          aria-label="Buka menu"
        >
          <svg className="w-5 h-5 text-[var(--color-text-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 relative flex-shrink-0">
            <Image src="/logo.png" alt="Swingbot Logo" fill sizes="24px" className="object-contain" priority />
          </div>
          <span className="font-bold tracking-tight text-[var(--color-text-primary)] text-sm">Swingbot IDX</span>
        </div>
        {/* Spacer to balance the hamburger button */}
        <div className="w-9" />
      </div>

      {/* ===== Mobile Backdrop ===== */}
      {isOpen && (
        <div
          className="lg:hidden fixed inset-0 z-50 bg-black/40 backdrop-blur-sm transition-opacity print:hidden"
          onClick={close}
        />
      )}

      {/* ===== Mobile Drawer ===== */}
      <aside
        className={`lg:hidden fixed top-0 left-0 z-50 h-full w-64 bg-[var(--color-surface)] border-r border-[var(--color-border)] flex flex-col transform transition-transform duration-300 ease-out print:hidden ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="px-4 py-4 flex items-center justify-between border-b border-[var(--color-border)]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 relative flex-shrink-0">
              <Image src="/logo.png" alt="Swingbot Logo" fill sizes="28px" className="object-contain" priority />
            </div>
            <span className="font-bold tracking-tight text-[var(--color-text-primary)] text-base">Swingbot IDX</span>
          </div>
          <button
            onClick={close}
            className="w-8 h-8 flex items-center justify-center rounded-md hover:bg-[var(--color-muted-bg)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
            aria-label="Tutup menu"
          >
            <svg className="w-4 h-4 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <Suspense fallback={<div className="flex-1 p-4"></div>}>
          <SidebarContent onNavigate={close} />
        </Suspense>
        <SidebarFooterNote />
      </aside>

      {/* ===== Desktop Sidebar ===== */}
      <aside className="hidden lg:flex w-56 flex-shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex-col h-screen sticky top-0 print:hidden">
        <div className="px-4 py-4 flex items-center gap-2.5 border-b border-[var(--color-border)]">
          <div className="w-7 h-7 relative flex-shrink-0">
            <Image src="/logo.png" alt="Swingbot Logo" fill sizes="28px" className="object-contain" priority />
          </div>
          <span className="font-bold tracking-tight text-[var(--color-text-primary)] text-[15px]">Swingbot IDX</span>
        </div>
        <Suspense fallback={<div className="flex-1 p-4"></div>}>
          <SidebarContent />
        </Suspense>
        <SidebarFooterNote />
      </aside>
    </>
  );
}

export default function Sidebar() {
  return <SidebarInner />;
}
