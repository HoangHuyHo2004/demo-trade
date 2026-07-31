"use client";

import { useEffect, useRef } from "react";
import type { Bar } from "@demo-trade/contracts";

export interface CompareSeries {
  id: string;
  label: string;
  color: string;
  bars: Bar[];
}

interface Props {
  series: CompareSeries[];
  height?: number;
}

/** Rebases every series to 100 at its first bar so we compare returns, not levels. */
export function CompareChart({ series, height = 360 }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;
    let chartApi: { remove: () => void } | null = null;

    (async () => {
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
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false }
      });
      chartApi = chart;

      for (const s of series) {
        if (s.bars.length < 2) continue;
        const base = Number(s.bars[0].c);
        if (!base) continue;
        const line = chart.addLineSeries({
          color: s.color,
          lineWidth: 2,
          priceLineVisible: false,
          title: s.label
        });
        line.setData(
          s.bars.map((b) => ({
            time: (new Date(b.t).getTime() / 1000) as never,
            value: (Number(b.c) / base) * 100
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
      return () => window.removeEventListener("resize", onResize);
    })();

    return () => {
      disposed = true;
      chartApi?.remove();
    };
  }, [series, height]);

  return <div ref={containerRef} style={{ width: "100%", height }} aria-label="Comparison chart" />;
}
