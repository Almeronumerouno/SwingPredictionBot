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
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      width: chartRef.current.clientWidth,
      height: 400,
      crosshair: { mode: 0 },
      timeScale: { borderColor: "#3f3f46" },
      rightPriceScale: { borderColor: "#3f3f46" },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#4ade80",
      downColor: "#f87171",
      borderDownColor: "#f87171",
      borderUpColor: "#4ade80",
      wickDownColor: "#f87171",
      wickUpColor: "#4ade80",
    });

    candlestickSeries.setData(data);

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
