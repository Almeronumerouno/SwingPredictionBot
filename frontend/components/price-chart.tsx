"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  LineStyle,
  type IChartApi,
} from "lightweight-charts";
import type { Candle } from "@/types/api";
import { calculateRSI, calculateMACD } from "@/lib/indicators";

interface PriceChartProps {
  data: Candle[];
}

type ChartViewMode = "all" | "candle" | "macd" | "rsi";

export default function PriceChart({ data }: PriceChartProps) {
  const [viewMode, setViewMode] = useState<ChartViewMode>("all");

  const priceContainerRef = useRef<HTMLDivElement>(null);
  const macdContainerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);

  // Compute indicators data
  const rsiData = useMemo(() => calculateRSI(data, 14), [data]);
  const macdData = useMemo(() => calculateMACD(data, 12, 26, 9), [data]);

  // Latest indicator stats for legend
  const latestRsi = rsiData.length > 0 ? rsiData[rsiData.length - 1].value : null;
  const latestMacd = macdData.macdLine.length > 0 ? macdData.macdLine[macdData.macdLine.length - 1].value : null;
  const latestSignal = macdData.signalLine.length > 0 ? macdData.signalLine[macdData.signalLine.length - 1].value : null;
  const latestHist = macdData.histogram.length > 0 ? macdData.histogram[macdData.histogram.length - 1].value : null;

  useEffect(() => {
    if (!data.length) return;

    const isDark = document.documentElement.classList.contains("dark");
    const textColor = isDark ? "#94A3B8" : "#64748B";
    const gridColor = isDark ? "rgba(255, 255, 255, 0.04)" : "#F1F5F9";
    const borderColor = isDark ? "#334155" : "#E2E8F0";

    const charts: IChartApi[] = [];
    const isSyncing = { current: false };

    // Standard scale options for 100% horizontal alignment
    const commonPriceScale = {
      borderColor,
      minimumWidth: 60,
      scaleMargins: { top: 0.1, bottom: 0.1 },
    };

    // 1. Master: Price Candlestick Chart (Top)
    let priceChart: IChartApi | null = null;
    if (priceContainerRef.current && (viewMode === "all" || viewMode === "candle")) {
      const pHeight = viewMode === "all" ? 300 : 400;
      priceChart = createChart(priceContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor,
          fontSize: 11,
        },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        width: priceContainerRef.current.clientWidth || 600,
        height: pHeight,
        crosshair: { mode: 0 },
        timeScale: {
          borderColor,
          timeVisible: false,
          visible: viewMode === "candle", // hide when stacked above MACD/RSI
        },
        rightPriceScale: {
          ...commonPriceScale,
          scaleMargins: { top: 0.08, bottom: 0.08 },
        },
      });

      const candleSeries = priceChart.addSeries(CandlestickSeries, {
        upColor: "#10B981",
        downColor: "#EF4444",
        borderDownColor: "#EF4444",
        borderUpColor: "#10B981",
        wickDownColor: "#EF4444",
        wickUpColor: "#10B981",
      });
      candleSeries.setData(data as any);
      charts.push(priceChart);
    }

    // 2. MACD Chart (Middle in "all" mode, or single)
    let macdChart: IChartApi | null = null;
    if (
      macdContainerRef.current &&
      (viewMode === "all" || viewMode === "macd") &&
      macdData.macdLine.length > 0
    ) {
      const mHeight = viewMode === "all" ? 170 : 360;
      macdChart = createChart(macdContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor,
          fontSize: 10,
        },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        width: macdContainerRef.current.clientWidth || 600,
        height: mHeight,
        crosshair: { mode: 0 },
        timeScale: {
          borderColor,
          timeVisible: false,
          visible: viewMode === "macd", // hide when stacked above RSI
        },
        rightPriceScale: commonPriceScale,
      });

      // Zero baseline
      const zeroLine = macdChart.addSeries(LineSeries, {
        color: isDark ? "rgba(255, 255, 255, 0.15)" : "rgba(0, 0, 0, 0.15)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      zeroLine.setData(data.map((d) => ({ time: d.time as any, value: 0 })));

      // MACD Histogram
      const histSeries = macdChart.addSeries(HistogramSeries, {
        color: "#10B981",
        priceLineVisible: false,
        lastValueVisible: false,
      });
      histSeries.setData(macdData.histogram as any);

      // MACD Fast Line (Blue)
      const macdSeries = macdChart.addSeries(LineSeries, {
        color: "#3B82F6",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      macdSeries.setData(macdData.macdLine as any);

      // Signal Line (Amber)
      const signalSeries = macdChart.addSeries(LineSeries, {
        color: "#F59E0B",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      signalSeries.setData(macdData.signalLine as any);

      charts.push(macdChart);
    }

    // 3. RSI Chart (Bottom in "all" mode, or single)
    let rsiChart: IChartApi | null = null;
    if (rsiContainerRef.current && (viewMode === "all" || viewMode === "rsi") && rsiData.length > 0) {
      const rHeight = viewMode === "all" ? 150 : 360;
      rsiChart = createChart(rsiContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor,
          fontSize: 10,
        },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        width: rsiContainerRef.current.clientWidth || 600,
        height: rHeight,
        crosshair: { mode: 0 },
        timeScale: {
          borderColor,
          timeVisible: false,
          visible: true, // Bottom-most chart anchors the date axis in "all" mode
        },
        rightPriceScale: commonPriceScale,
      });

      // Guide line 70 (Overbought - Amber/Red)
      const line70 = rsiChart.addSeries(LineSeries, {
        color: isDark ? "rgba(239, 68, 68, 0.5)" : "rgba(239, 68, 68, 0.6)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      line70.setData(data.map((d) => ({ time: d.time as any, value: 70 })));

      // Guide line 50 (Middle)
      const line50 = rsiChart.addSeries(LineSeries, {
        color: isDark ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.1)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      line50.setData(data.map((d) => ({ time: d.time as any, value: 50 })));

      // Guide line 30 (Oversold - Emerald/Green)
      const line30 = rsiChart.addSeries(LineSeries, {
        color: isDark ? "rgba(16, 185, 129, 0.5)" : "rgba(16, 185, 129, 0.6)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      line30.setData(data.map((d) => ({ time: d.time as any, value: 30 })));

      // RSI Main Line (Purple/Indigo)
      const rsiSeries = rsiChart.addSeries(LineSeries, {
        color: "#818CF8",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      });
      rsiSeries.setData(rsiData as any);

      charts.push(rsiChart);
    }

    // Align and Fit visible ranges across all charts from master
    if (priceChart) {
      priceChart.timeScale().fitContent();
      const masterRange = priceChart.timeScale().getVisibleLogicalRange();
      if (masterRange) {
        if (macdChart) macdChart.timeScale().setVisibleLogicalRange(masterRange);
        if (rsiChart) rsiChart.timeScale().setVisibleLogicalRange(masterRange);
      }
    } else if (charts.length > 0) {
      charts[0].timeScale().fitContent();
    }

    // Synchronize time scales across all rendered charts
    if (charts.length > 1) {
      charts.forEach((sourceChart) => {
        sourceChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
          if (isSyncing.current || !range) return;
          isSyncing.current = true;
          charts.forEach((targetChart) => {
            if (targetChart !== sourceChart) {
              targetChart.timeScale().setVisibleLogicalRange(range);
            }
          });
          isSyncing.current = false;
        });
      });
    }

    // Window Resize Handler
    const handleResize = () => {
      if (priceChart && priceContainerRef.current) {
        priceChart.applyOptions({
          width: priceContainerRef.current.clientWidth,
          height: viewMode === "all" ? 300 : 400,
        });
      }
      if (macdChart && macdContainerRef.current) {
        macdChart.applyOptions({
          width: macdContainerRef.current.clientWidth,
          height: viewMode === "all" ? 170 : 360,
        });
      }
      if (rsiChart && rsiContainerRef.current) {
        rsiChart.applyOptions({
          width: rsiContainerRef.current.clientWidth,
          height: viewMode === "all" ? 150 : 360,
        });
      }
    };

    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });

    if (priceContainerRef.current) resizeObserver.observe(priceContainerRef.current);
    if (macdContainerRef.current) resizeObserver.observe(macdContainerRef.current);
    if (rsiContainerRef.current) resizeObserver.observe(rsiContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      charts.forEach((c) => c.remove());
    };
  }, [data, rsiData, macdData, viewMode]);

  return (
    <div className="w-full">
      {/* Chart Top Navigation Bar & Indicator Legend */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        {/* Indicators Live Stats Legend */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="font-bold text-[var(--color-text-primary)] flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            Candlestick
          </span>

          {latestMacd !== null && latestSignal !== null && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[var(--color-muted-bg)] border border-[var(--color-border)] text-[11px] font-semibold tabular-nums text-[var(--color-text-secondary)]">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
              MACD: <span className="text-blue-500 font-bold">{latestMacd.toFixed(2)}</span>
              <span className="text-[var(--color-text-muted)]">|</span>
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
              Sig: <span className="text-amber-500 font-bold">{latestSignal.toFixed(2)}</span>
              {latestHist !== null && (
                <>
                  <span className="text-[var(--color-text-muted)]">|</span>
                  Hist:{" "}
                  <span
                    className={
                      latestHist >= 0 ? "text-emerald-500 font-bold" : "text-red-500 font-bold"
                    }
                  >
                    {latestHist >= 0 ? `+${latestHist.toFixed(2)}` : latestHist.toFixed(2)}
                  </span>
                </>
              )}
            </span>
          )}

          {latestRsi !== null && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[var(--color-muted-bg)] border border-[var(--color-border)] text-[11px] font-semibold tabular-nums text-[var(--color-text-secondary)]">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
              RSI(14):{" "}
              <strong
                className={
                  latestRsi >= 70
                    ? "text-red-500"
                    : latestRsi <= 30
                    ? "text-emerald-500"
                    : "text-[var(--color-text-primary)]"
                }
              >
                {latestRsi.toFixed(1)}
              </strong>
            </span>
          )}
        </div>

        {/* View Mode Toggle Switcher */}
        <div className="flex items-center rounded-lg border border-[var(--color-border)] bg-[var(--color-muted-bg)] p-0.5 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setViewMode("all")}
            className={`px-2.5 py-1 rounded-md transition-colors duration-100 cursor-pointer ${
              viewMode === "all"
                ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-xs border border-[var(--color-border)] font-bold"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
            }`}
          >
            3 Chart (All)
          </button>
          <button
            type="button"
            onClick={() => setViewMode("candle")}
            className={`px-2.5 py-1 rounded-md transition-colors duration-100 cursor-pointer ${
              viewMode === "candle"
                ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-xs border border-[var(--color-border)] font-bold"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
            }`}
          >
            Candle
          </button>
          <button
            type="button"
            onClick={() => setViewMode("macd")}
            className={`px-2.5 py-1 rounded-md transition-colors duration-100 cursor-pointer ${
              viewMode === "macd"
                ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-xs border border-[var(--color-border)] font-bold"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
            }`}
          >
            MACD
          </button>
          <button
            type="button"
            onClick={() => setViewMode("rsi")}
            className={`px-2.5 py-1 rounded-md transition-colors duration-100 cursor-pointer ${
              viewMode === "rsi"
                ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-xs border border-[var(--color-border)] font-bold"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] border border-transparent"
            }`}
          >
            RSI
          </button>
        </div>
      </div>

      {/* Pane 1: Candlestick Price Chart (Top) */}
      {(viewMode === "all" || viewMode === "candle") && (
        <div className="relative w-full">
          <div ref={priceContainerRef} className="w-full" />
        </div>
      )}

      {/* Pane 2: MACD Chart (Middle) */}
      {(viewMode === "all" || viewMode === "macd") && (
        <div className="relative w-full border-t border-[var(--color-border)]">
          <div className="absolute top-2.5 left-3.5 z-10 pointer-events-none flex items-center gap-2 text-[10px] font-bold text-blue-400 bg-[var(--color-surface)]/85 px-2 py-0.5 rounded border border-[var(--color-border)] shadow-xs">
            <span>MACD (12, 26, 9)</span>
            <span className="text-amber-400">Signal (9)</span>
          </div>
          <div ref={macdContainerRef} className="w-full" />
        </div>
      )}

      {/* Pane 3: RSI Chart (Bottom) */}
      {(viewMode === "all" || viewMode === "rsi") && (
        <div className="relative w-full border-t border-[var(--color-border)]">
          <div className="absolute top-2.5 left-3.5 z-10 pointer-events-none flex items-center gap-1.5 text-[10px] font-bold text-indigo-400 bg-[var(--color-surface)]/85 px-2 py-0.5 rounded border border-[var(--color-border)] shadow-xs">
            <span>RSI (14)</span>
            <span className="text-[var(--color-text-muted)] font-normal">| 70 Overbought / 30 Oversold</span>
          </div>
          <div ref={rsiContainerRef} className="w-full" />
        </div>
      )}
    </div>
  );
}
