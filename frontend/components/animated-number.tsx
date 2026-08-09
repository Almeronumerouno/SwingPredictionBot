"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Nomor KPI dengan animasi count-up.
 * Mati otomatis saat prefers-reduced-motion aktif (langsung tampil nilai akhir).
 * Nilai akhir tetap tersedia untuk screen reader lewat elemen sr-only.
 */
export default function AnimatedNumber({
  value,
  format = "id",
  decimals = 0,
  duration = 700,
  className,
}: {
  value: number;
  format?: "id" | "idr" | "pct";
  decimals?: number;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(0);
  const prefersReduced = useRef(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    prefersReduced.current = mq.matches;

    let raf = 0;

    // Tanpa animasi: tampilkan nilai akhir pada frame berikutnya
    if (mq.matches) {
      raf = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(raf);
    }

    const start = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      setDisplay(value * eased);
      if (progress < 1) raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  const fmt = (n: number) => {
    if (format === "idr") {
      return new Intl.NumberFormat("id-ID", {
        style: "currency",
        currency: "IDR",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(n);
    }
    if (format === "pct") {
      const v = n.toFixed(decimals);
      return `${n > 0 ? "+" : ""}${v}%`;
    }
    return new Intl.NumberFormat("id-ID", { maximumFractionDigits: decimals }).format(n);
  };

  const final = fmt(value);

  return (
    <span className={className}>
      <span className="sr-only">{final}</span>
      <span aria-hidden="true">{fmt(display)}</span>
    </span>
  );
}