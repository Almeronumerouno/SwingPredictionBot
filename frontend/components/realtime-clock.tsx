"use client";

import { useEffect, useState } from "react";

export default function RealtimeClock() {
  const [timeStr, setTimeStr] = useState<string>("");
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [mounted, setMounted] = useState<boolean>(false);

  useEffect(() => {
    setMounted(true);

    const updateClock = () => {
      const now = new Date();

      // Convert to WIB (UTC+7)
      const options: Intl.DateTimeFormatOptions = {
        timeZone: "Asia/Jakarta",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      };
      const formattedTime = new Intl.DateTimeFormat("id-ID", options).format(now);
      setTimeStr(formattedTime.replace(/\./g, ":"));

      // Check if IDX Market is currently OPEN
      // IDX Hours: Mon-Fri (1-5)
      // Session 1: 09:00 - 12:00 (Fri: 09:00 - 11:30)
      // Session 2: 13:30 - 15:50 (Fri: 14:00 - 15:50)
      const jakartaDate = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Jakarta" }));
      const day = jakartaDate.getDay();
      const hour = jakartaDate.getHours();
      const min = jakartaDate.getMinutes();
      const timeInMins = hour * 60 + min;

      let marketOpen = false;
      if (day >= 1 && day <= 5) {
        if (day === 5) {
          // Friday
          const s1 = timeInMins >= 9 * 60 && timeInMins < 11 * 60 + 30;
          const s2 = timeInMins >= 14 * 60 && timeInMins < 15 * 60 + 50;
          marketOpen = s1 || s2;
        } else {
          // Mon-Thu
          const s1 = timeInMins >= 9 * 60 && timeInMins < 12 * 60;
          const s2 = timeInMins >= 13 * 60 + 30 && timeInMins < 15 * 60 + 50;
          marketOpen = s1 || s2;
        }
      }
      setIsOpen(marketOpen);
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);

    return () => clearInterval(interval);
  }, []);

  if (!mounted || !timeStr) {
    return <div className="h-9 w-24 bg-transparent" />;
  }

  const sandColor = isOpen ? "#10B981" : "#F59E0B";

  return (
    <div
      className="inline-flex items-center gap-2 select-none pr-1"
      title={isOpen ? "Bursa IDX Buka (Live)" : "Bursa IDX Tutup"}
    >
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes hg-flip {
          0%, 65% {
            transform: rotate(0deg);
          }
          80%, 100% {
            transform: rotate(180deg);
          }
        }
        @keyframes top-sand-drain {
          0% {
            clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%);
          }
          65% {
            clip-path: polygon(0 80%, 100% 80%, 100% 100%, 0 100%);
          }
          80%, 100% {
            clip-path: polygon(0 100%, 100% 100%, 100% 100%, 0 100%);
          }
        }
        @keyframes bottom-sand-fill {
          0% {
            clip-path: polygon(50% 100%, 50% 100%, 50% 100%, 50% 100%);
          }
          65% {
            clip-path: polygon(0 60%, 100% 60%, 100% 100%, 0 100%);
          }
          80%, 100% {
            clip-path: polygon(0 30%, 100% 30%, 100% 100%, 0 100%);
          }
        }
        @keyframes sand-flow {
          0%, 65% {
            opacity: 1;
            stroke-dashoffset: 0;
          }
          70%, 100% {
            opacity: 0;
            stroke-dashoffset: -10;
          }
        }
        .hg-animated-box {
          animation: hg-flip 4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
          transform-origin: center center;
        }
        .hg-top-sand {
          animation: top-sand-drain 4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
          transform-origin: bottom center;
        }
        .hg-bottom-sand {
          animation: bottom-sand-fill 4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
          transform-origin: bottom center;
        }
        .hg-sand-stream {
          animation: sand-flow 4s linear infinite;
          stroke-dasharray: 2 2;
        }
      `}} />

      {/* Animated Hourglass with Falling Sand */}
      <div className="flex items-center justify-center w-5 h-5">
        <svg
          className="w-4 h-4 hg-animated-box"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
        >
          {/* Glass Outer Shell */}
          <path
            d="M5 2h14M5 22h14"
            stroke="var(--color-text-primary)"
            strokeLinecap="round"
          />
          <path
            d="M6 2v3.5a5 5 0 0 0 2 4L12 12l4-2.5a5 5 0 0 0 2-4V2"
            stroke="var(--color-text-muted)"
            strokeLinecap="round"
          />
          <path
            d="M6 22v-3.5a5 5 0 0 1 2-4L12 12l4 2.5a5 5 0 0 1 2 4V22"
            stroke="var(--color-text-muted)"
            strokeLinecap="round"
          />

          {/* Top Sand (Draining) */}
          <path
            d="M7 4h10c0 1.5-.8 3-2.5 4.2L12 10 9.5 8.2C7.8 7 7 5.5 7 4z"
            fill={sandColor}
            stroke="none"
            className="hg-top-sand"
          />

          {/* Sand Stream Trickling Down */}
          <line
            x1="12"
            y1="10.5"
            x2="12"
            y2="19"
            stroke={sandColor}
            strokeWidth="1.5"
            className="hg-sand-stream"
          />

          {/* Bottom Sand (Filling) */}
          <path
            d="M7.5 20h9c0-1.5-.8-3-2.5-4.2L12 14.5l-2 1.3C8.3 17 7.5 18.5 7.5 20z"
            fill={sandColor}
            stroke="none"
            className="hg-bottom-sand"
          />
        </svg>
      </div>

      {/* Realtime Time Display */}
      <div className="flex items-baseline gap-1 text-sm font-medium tabular-nums text-[var(--color-text-primary)]">
        <span>{timeStr}</span>
        <span className="text-xs font-normal text-[var(--color-text-muted)] uppercase">
          WIB
        </span>
      </div>
    </div>
  );
}
