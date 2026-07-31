"use client";

import { useEffect, useRef } from "react";
import type { Bar } from "@demo-trade/contracts";

interface Props {
  bars: Bar[];
  /** "line" is cheaper and reads well on daily+, "candles" is better intraday. */
  type?: "line" | "candles";
  height?: number;
}

export function PriceChart({ bars, type = "line", height = 320 }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;
    let chartApi: { remove: () => void } | null = null;

    (async () => {
      // dynamic import so SSR never touches this
      const { createChart, ColorType, LineStyle } = await import("lightweight-charts");
      if (disposed || !containerRef.current) return;

      const isDark =
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;

      const chart = createChart(containerRef.current, {
        height,
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: isDark ? "#a3adbb" : "#475569",
          fontSize: 11
        },
        grid: {
          vertLines: { color: isDark ? "#1f2933" : "#e2e8f0", style: LineStyle.Dotted },
          horzLines: { color: isDark ? "#1f2933" : "#e2e8f0", style: LineStyle.Dotted }
        },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
        crosshair: { mode: 1 }
      });
      chartApi = chart;

      if (type === "candles") {
        const s = chart.addCandlestickSeries({
          upColor: "#22c55e",
          downColor: "#ef4444",
          wickUpColor: "#22c55e",
          wickDownColor: "#ef4444",
          borderVisible: false
        });
        s.setData(
          bars.map((b) => ({
            time: (new Date(b.t).getTime() / 1000) as never,
            open: Number(b.o),
            high: Number(b.h),
            low: Number(b.l),
            close: Number(b.c)
          }))
        );
      } else {
        const s = chart.addAreaSeries({
          lineColor: "#4f8cff",
          topColor: "rgba(79,140,255,0.32)",
          bottomColor: "rgba(79,140,255,0)",
          lineWidth: 2,
          priceLineVisible: false
        });
        s.setData(
          bars.map((b) => ({
            time: (new Date(b.t).getTime() / 1000) as never,
            value: Number(b.c)
          }))
        );
      }
      chart.timeScale().fitContent();

      const onResize = () => {
        if (!containerRef.current) return;
        chart.applyOptions({ width: containerRef.current.clientWidth });
      };
      window.addEventListener("resize", onResize);
      onResize();

      return () => {
        window.removeEventListener("resize", onResize);
      };
    })();

    return () => {
      disposed = true;
      chartApi?.remove();
    };
  }, [bars, type, height]);

  return <div ref={containerRef} style={{ width: "100%", height }} aria-label="Price chart" />;
}
