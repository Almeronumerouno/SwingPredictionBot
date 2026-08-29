export default function Loading() {
  const candles = [
    { h: 38, up: true },
    { h: 62, up: false },
    { h: 45, up: true },
    { h: 74, up: true },
    { h: 30, up: false },
    { h: 55, up: true },
    { h: 68, up: false },
    { h: 42, up: true },
    { h: 58, up: true },
    { h: 26, up: false },
    { h: 70, up: true },
    { h: 48, up: false },
    { h: 64, up: true },
    { h: 36, up: true },
    { h: 52, up: false },
  ];

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Loading market data"
      className="ld-root flex min-h-[70vh] w-full flex-col items-center justify-center px-4 py-10 bg-[var(--color-bg)]"
    >
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes ld-candle-grow {
          0% { transform: scaleY(0.35); }
          50% { transform: scaleY(1); }
          100% { transform: scaleY(0.55); }
        }

        @keyframes ld-scan {
          0% { left: -4%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { left: 104%; opacity: 0; }
        }

        @keyframes ld-dot-pop {
          0%, 20% { transform: scale(0); opacity: 0; }
          40% { transform: scale(1.3); opacity: 1; }
          60%, 100% { transform: scale(1); opacity: 1; }
        }

        .ld-candle {
          animation-name: ld-candle-grow;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
          animation-direction: alternate;
          transform-origin: bottom center;
        }

        .ld-scanline {
          animation: ld-scan 3.2s ease-in-out infinite;
        }

        .ld-dot {
          display: inline-block;
          animation: ld-dot-pop 1.4s ease-in-out infinite;
        }

        @media (prefers-reduced-motion: reduce) {
          .ld-candle,
          .ld-scanline,
          .ld-dot {
            animation: none !important;
          }
          .ld-candle {
            transform: scaleY(0.75) !important;
          }
          .ld-dot {
            opacity: 1 !important;
          }
        }
      `}} />

      <div className="flex flex-col gap-6 p-6 sm:p-8" style={{ width: "100%", maxWidth: "480px" }}>
        {/* Candlestick visualization box seamlessly floating on background */}
        <div className="relative h-36 overflow-hidden sm:h-40 bg-transparent">
          {/* horizontal grid reference lines */}
          <div className="pointer-events-none absolute inset-0 flex flex-col justify-between px-0 py-3">
            <div className="h-px w-full bg-[var(--color-border)]/25" />
            <div className="h-px w-full bg-[var(--color-border)]/25" />
            <div className="h-px w-full bg-[var(--color-border)]/25" />
          </div>

          {/* candles */}
          <div className="absolute inset-0 flex items-end justify-between gap-[3px] px-4 pb-3 sm:gap-1.5 sm:px-6">
            {candles.map((c, i) => (
              <div
                key={i}
                className="relative flex h-full flex-1 items-end justify-center"
              >
                {/* wick */}
                <div
                  className="absolute bottom-0 w-px bg-[var(--color-border)]"
                  style={{ height: "100%" }}
                />
                {/* body */}
                <div
                  className={`ld-candle relative w-full max-w-[7px] rounded-[1.5px] sm:max-w-[9px] ${
                    c.up ? "bg-[var(--color-up)]" : "bg-[var(--color-down)]"
                  }`}
                  style={{
                    height: `${c.h}%`,
                    animationDuration: `${1.6 + (i % 5) * 0.22}s`,
                    animationDelay: `${(i % 7) * 0.12}s`,
                  }}
                />
              </div>
            ))}
          </div>

          {/* scanning laser line */}
          <div
            className="ld-scanline pointer-events-none absolute top-0 h-full w-px bg-blue-500"
            style={{
              boxShadow: "0 0 10px 2px rgba(59, 130, 246, 0.45)",
            }}
          />
        </div>

        {/* Text */}
        <div className="flex items-center justify-center gap-1 text-center">
          <h1 className="text-base font-semibold sm:text-lg text-[var(--color-text-primary)]">
            Loading
          </h1>
          <span className="ld-dot text-base font-semibold sm:text-lg text-[var(--color-text-primary)]" style={{ animationDelay: "0s" }}>
            .
          </span>
          <span className="ld-dot text-base font-semibold sm:text-lg text-[var(--color-text-primary)]" style={{ animationDelay: "0.25s" }}>
            .
          </span>
          <span className="ld-dot text-base font-semibold sm:text-lg text-[var(--color-text-primary)]" style={{ animationDelay: "0.5s" }}>
            .
          </span>
        </div>
      </div>
    </div>
  );
}