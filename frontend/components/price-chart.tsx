"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, CandlestickSeries } from "lightweight-charts";
import type { Candle } from "@/types/api";

export default function PriceChart({ data }: { data: Candle[] }) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || !data.length) return;

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#FFFFFF" },
        textColor: "#64748B",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#F1F5F9" },
        horzLines: { color: "#F1F5F9" },
      },
      width: chartRef.current.clientWidth,
      height: 400,
      crosshair: { mode: 0 },
      timeScale: {
        borderColor: "#E2E8F0",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "#E2E8F0",
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#059669",
      downColor: "#DC2626",
      borderDownColor: "#DC2626",
      borderUpColor: "#059669",
      wickDownColor: "#DC2626",
      wickUpColor: "#059669",
    });

    series.setData(data);
    chart.timeScale().fitContent();

    const handleResize = () => {
      chart.applyOptions({ width: chartRef.current!.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data]);

  return <div ref={chartRef} />;
}
