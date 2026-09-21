"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { fetchScrapedDates } from "@/lib/api/dates";
import type { ScrapedDatesResponse } from "@/types/api";

const MONTH_NAMES = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember"
];

const DAY_NAMES = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

function getWibTodayString(): string {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Jakarta",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(now);
}

function formatDisplayDate(dateStr?: string): string {
  if (!dateStr) return "Pilih Tanggal";
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function DateSelector({
  selected,
  basePath,
}: {
  selected?: string;
  basePath?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [isOpen, setIsOpen] = useState(false);
  const [scrapedData, setScrapedData] = useState<ScrapedDatesResponse | null>(null);
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const todayStr = useMemo(() => getWibTodayString(), []);

  // Inisialisasi tampilan bulan & tahun berdasarkan tanggal terpilih atau hari ini
  const initialYear = selected ? parseInt(selected.slice(0, 4), 10) : parseInt(todayStr.slice(0, 4), 10);
  const initialMonth = selected ? parseInt(selected.slice(5, 7), 10) - 1 : parseInt(todayStr.slice(5, 7), 10) - 1;

  const [viewYear, setViewYear] = useState<number>(initialYear || new Date().getFullYear());
  const [viewMonth, setViewMonth] = useState<number>(!isNaN(initialMonth) ? initialMonth : new Date().getMonth());

  // Sinkronisasi view jika selected berubah
  useEffect(() => {
    if (selected) {
      const y = parseInt(selected.slice(0, 4), 10);
      const m = parseInt(selected.slice(5, 7), 10) - 1;
      if (!isNaN(y) && !isNaN(m)) {
        setViewYear(y);
        setViewMonth(m);
      }
    }
  }, [selected]);

  // Fetch daftar tanggal yang sudah discrape
  useEffect(() => {
    let mounted = true;
    fetchScrapedDates()
      .then((res) => {
        if (mounted) setScrapedData(res);
      })
      .catch((err) => {
        console.warn("Gagal memuat daftar tanggal scrape:", err);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Tutup dropdown jika klik di luar atau tekan Escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  function handlePrevMonth() {
    setViewMonth((prev) => {
      if (prev === 0) {
        setViewYear((y) => y - 1);
        return 11;
      }
      return prev - 1;
    });
  }

  function handleNextMonth() {
    setViewMonth((prev) => {
      if (prev === 11) {
        setViewYear((y) => y + 1);
        return 0;
      }
      return prev + 1;
    });
  }

  function handleSelectDate(dateStr: string) {
    const target = basePath || pathname;
    const params = new URLSearchParams(searchParams.toString());
    params.set("date", dateStr);
    router.push(`${target}?${params.toString()}`);
    setIsOpen(false);
  }

  function handleClearDate(e?: React.MouseEvent) {
    if (e) e.stopPropagation();
    const target = basePath || pathname;
    const params = new URLSearchParams(searchParams.toString());
    params.delete("date");
    const qs = params.toString();
    router.push(qs ? `${target}?${qs}` : target);
    setIsOpen(false);
  }

  // Cek apakah tanggal sudah discrape sesuai halaman aktif
  function isDateScraped(dateStr: string): boolean {
    if (!scrapedData) return false;
    if (basePath === "/top-gainers") {
      return scrapedData.by_category?.gainers?.includes(dateStr) ?? false;
    }
    if (basePath === "/gorengan") {
      return scrapedData.by_category?.gorengan?.includes(dateStr) ?? false;
    }
    if (basePath === "/ready-to-fly") {
      return scrapedData.by_category?.readytofly?.includes(dateStr) ?? false;
    }
    return scrapedData.dates?.includes(dateStr) ?? false;
  }

  // Ambil rincian modul yang tersedia untuk tanggal tertentu
  function getDateDetailText(dateStr: string): { status: string; isScraped: boolean } {
    if (!scrapedData) return { status: "Memeriksa data...", isScraped: false };
    const detail = scrapedData.details?.[dateStr];
    if (!detail) return { status: "Belum discan", isScraped: false };

    const parts: string[] = [];
    if (detail.gainers) parts.push("Gainers");
    if (detail.gorengan) parts.push("Gorengan");
    if (detail.readytofly) parts.push("RTF");

    if (parts.length === 3) return { status: "Data lengkap (Gainers, Gorengan, RTF)", isScraped: true };
    if (parts.length > 0) return { status: `Tersedia: ${parts.join(", ")}`, isScraped: true };
    return { status: "Belum discan", isScraped: false };
  }

  // Grid 42 sel kalender (6 minggu)
  const calendarDays = useMemo(() => {
    const firstDayOfMonth = new Date(viewYear, viewMonth, 1);
    const startWeekday = (firstDayOfMonth.getDay() + 6) % 7; // Senin = 0
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    const daysInPrevMonth = new Date(viewYear, viewMonth, 0).getDate();

    const cells: {
      dateStr: string;
      dayNumber: number;
      isCurrentMonth: boolean;
      isToday: boolean;
      isSelected: boolean;
      isFuture: boolean;
      isScraped: boolean;
      isWeekend: boolean;
    }[] = [];

    // Hari padding dari bulan sebelumnya
    for (let i = startWeekday - 1; i >= 0; i--) {
      const day = daysInPrevMonth - i;
      const prevDate = new Date(viewYear, viewMonth - 1, day);
      const y = prevDate.getFullYear();
      const m = String(prevDate.getMonth() + 1).padStart(2, "0");
      const d = String(day).padStart(2, "0");
      const dateStr = `${y}-${m}-${d}`;
      const weekday = (prevDate.getDay() + 6) % 7;
      cells.push({
        dateStr,
        dayNumber: day,
        isCurrentMonth: false,
        isToday: dateStr === todayStr,
        isSelected: dateStr === selected,
        isFuture: dateStr > todayStr,
        isScraped: isDateScraped(dateStr),
        isWeekend: weekday >= 5,
      });
    }

    // Hari bulan saat ini
    for (let day = 1; day <= daysInMonth; day++) {
      const m = String(viewMonth + 1).padStart(2, "0");
      const d = String(day).padStart(2, "0");
      const dateStr = `${viewYear}-${m}-${d}`;
      const curDate = new Date(viewYear, viewMonth, day);
      const weekday = (curDate.getDay() + 6) % 7;
      cells.push({
        dateStr,
        dayNumber: day,
        isCurrentMonth: true,
        isToday: dateStr === todayStr,
        isSelected: dateStr === selected,
        isFuture: dateStr > todayStr,
        isScraped: isDateScraped(dateStr),
        isWeekend: weekday >= 5,
      });
    }

    // Hari padding bulan berikutnya
    const remaining = 42 - cells.length;
    for (let day = 1; day <= remaining; day++) {
      const nextDate = new Date(viewYear, viewMonth + 1, day);
      const y = nextDate.getFullYear();
      const m = String(nextDate.getMonth() + 1).padStart(2, "0");
      const d = String(day).padStart(2, "0");
      const dateStr = `${y}-${m}-${d}`;
      const weekday = (nextDate.getDay() + 6) % 7;
      cells.push({
        dateStr,
        dayNumber: day,
        isCurrentMonth: false,
        isToday: dateStr === todayStr,
        isSelected: dateStr === selected,
        isFuture: dateStr > todayStr,
        isScraped: isDateScraped(dateStr),
        isWeekend: weekday >= 5,
      });
    }

    return cells;
  }, [viewYear, viewMonth, todayStr, selected, scrapedData, basePath]);

  const activeHoverOrSelected = hoveredDate || selected;
  const hoverDetail = activeHoverOrSelected ? getDateDetailText(activeHoverOrSelected) : null;
  const isSelectedScraped = selected ? isDateScraped(selected) : false;

  return (
    <div
      ref={containerRef}
      className={`relative inline-block text-left ${isOpen ? "z-50" : "z-10"}`}
    >
      {/* Trigger Button */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setIsOpen(!isOpen);
          }
        }}
        className={`h-9 px-3 text-xs font-medium border rounded-lg bg-[var(--color-surface)] text-[var(--color-text-primary)] hover:border-[var(--color-border-strong)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 shadow-xs transition-all duration-200 cursor-pointer inline-flex items-center gap-2 select-none ${
          isOpen
            ? "border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/20"
            : "border-[var(--color-border)]"
        }`}
      >
        <svg
          className="w-4 h-4 text-[var(--color-text-muted)] flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>

        <span className="font-semibold tracking-tight">
          {selected ? formatDisplayDate(selected) : "Pilih Tanggal"}
        </span>

        {/* Indikator status pada trigger jika ada selected */}
        {selected && (
          <span
            className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${
              isSelectedScraped ? "bg-emerald-500 shadow-xs" : "bg-gray-300 dark:bg-gray-600"
            }`}
            title={isSelectedScraped ? "Sudah discan" : "Belum discan"}
          />
        )}

        {/* Tombol Clear (✕) jika selected aktif */}
        {selected ? (
          <button
            type="button"
            onClick={handleClearDate}
            title="Reset ke hari ini"
            className="w-4 h-4 -mr-0.5 rounded-full flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-muted-bg)] transition-colors"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        ) : (
          <svg
            className={`w-3.5 h-3.5 text-[var(--color-text-muted)] -mr-0.5 transition-transform duration-200 ${
              isOpen ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </div>

      {/* Dropdown Calendar Popover */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 z-50 w-[320px] sm:w-[340px] rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-2xl animate-scale-in">
          {/* Calendar Header */}
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold text-[var(--color-text-primary)] tracking-tight">
                {MONTH_NAMES[viewMonth]} {viewYear}
              </span>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handlePrevMonth}
                className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
                title="Bulan sebelumnya"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button
                type="button"
                onClick={handleNextMonth}
                className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--color-text-secondary)] hover:bg-[var(--color-muted-bg)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
                title="Bulan berikutnya"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>

          {/* Weekday Labels */}
          <div className="grid grid-cols-7 gap-1 text-center mb-1">
            {DAY_NAMES.map((name, i) => (
              <div
                key={name}
                className={`text-[10px] font-bold uppercase tracking-wider py-1 ${
                  i >= 5 ? "text-amber-600/80 dark:text-amber-500/80" : "text-[var(--color-text-muted)]"
                }`}
              >
                {name}
              </div>
            ))}
          </div>

          {/* Days Grid (42 cells) */}
          <div className="grid grid-cols-7 gap-1 text-center mb-3">
            {calendarDays.map((cell) => {
              const isDisabled = cell.isFuture || !cell.isCurrentMonth;

              let cellStyle = "relative h-9 rounded-lg flex flex-col items-center justify-center transition-all duration-150 cursor-pointer ";

              if (!cell.isCurrentMonth) {
                cellStyle += "opacity-20 pointer-events-none text-[var(--color-text-muted)] ";
              } else if (cell.isFuture) {
                cellStyle += "opacity-25 cursor-not-allowed text-[var(--color-text-muted)] ";
              } else if (cell.isSelected) {
                cellStyle += "bg-[var(--color-btn-primary-bg)] text-[var(--color-btn-primary-text)] font-bold shadow-xs ";
              } else if (cell.isScraped) {
                // Background soft emerald dengan border halus, warna angka tetap hitam tegas/kontras tinggi
                cellStyle += "bg-emerald-500/[0.10] hover:bg-emerald-500/[0.20] dark:bg-emerald-500/[0.18] dark:hover:bg-emerald-500/[0.28] text-[var(--color-text-primary)] border border-emerald-500/35 font-bold ";
              } else {
                cellStyle += "text-[var(--color-text-primary)] hover:bg-[var(--color-muted-bg)] ";
              }

              if (cell.isCurrentMonth && cell.isToday && !cell.isSelected) {
                cellStyle += "ring-1.5 ring-[var(--color-text-primary)]/40 font-bold ";
              }

              return (
                <button
                  key={cell.dateStr}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => cell.isCurrentMonth && handleSelectDate(cell.dateStr)}
                  onMouseEnter={() => cell.isCurrentMonth && setHoveredDate(cell.dateStr)}
                  onMouseLeave={() => setHoveredDate(null)}
                  className={cellStyle}
                  title={
                    cell.isCurrentMonth
                      ? `${cell.dateStr}: ${cell.isScraped ? "Sudah discan" : "Belum discan"}`
                      : ""
                  }
                >
                  {/* Angka tanggal - kontras tinggi, selalu tajam & hitam terbaca jelas */}
                  <span
                    className={`text-[12px] leading-none select-none ${
                      cell.isSelected
                        ? "text-[var(--color-btn-primary-text)] font-bold"
                        : cell.isCurrentMonth && cell.isScraped
                        ? "text-[var(--color-text-primary)] font-extrabold"
                        : cell.isCurrentMonth
                        ? "text-[var(--color-text-primary)] font-medium"
                        : "text-[var(--color-text-muted)]"
                    }`}
                  >
                    {cell.dayNumber}
                  </span>

                  {/* Wadah indikator dot terpisah di bawah angka dengan jarak aman */}
                  <span className="h-1.5 flex items-center justify-center mt-1">
                    {cell.isCurrentMonth && cell.isScraped ? (
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          cell.isSelected ? "bg-white" : "bg-emerald-600 dark:bg-emerald-400"
                        }`}
                      />
                    ) : (
                      <span className="w-1.5 h-1.5" />
                    )}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Dynamic Status / Tooltip Bar */}
          <div className="min-h-[28px] px-2.5 py-1.5 mb-2.5 rounded-md bg-[var(--color-muted-bg)] border border-[var(--color-border)]/60 text-[11px] flex items-center justify-between gap-2">
            {hoverDetail && activeHoverOrSelected ? (
              <>
                <span className="font-semibold text-[var(--color-text-primary)] truncate">
                  {formatDisplayDate(activeHoverOrSelected)}
                </span>
                <span
                  className={`text-[10px] font-semibold truncate flex items-center gap-1 ${
                    hoverDetail.isScraped
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-[var(--color-text-muted)]"
                  }`}
                >
                  {hoverDetail.isScraped ? "✓" : "○"} {hoverDetail.status}
                </span>
              </>
            ) : (
              /* Petunjuk / Legenda */
              <div className="w-full flex items-center justify-between text-[10px] text-[var(--color-text-muted)] font-medium">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                  Sudah discan
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600 inline-block" />
                  Belum discan
                </span>
              </div>
            )}
          </div>

          {/* Footer Quick Actions */}
          <div className="flex items-center justify-between pt-2 border-t border-[var(--color-border)] text-xs">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => handleSelectDate(todayStr)}
                className="px-2.5 py-1 font-semibold text-[var(--color-primary)] hover:bg-[var(--color-muted-bg)] rounded-md transition-colors cursor-pointer text-[11px]"
              >
                Hari Ini
              </button>
              {selected && (
                <button
                  type="button"
                  onClick={handleClearDate}
                  className="px-2.5 py-1 font-semibold text-[var(--color-text-muted)] hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-md transition-colors cursor-pointer text-[11px]"
                >
                  Reset
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="px-2.5 py-1 text-[11px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-muted-bg)] rounded-md transition-colors cursor-pointer"
            >
              Tutup
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
