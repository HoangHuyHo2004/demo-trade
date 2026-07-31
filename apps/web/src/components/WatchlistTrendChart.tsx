"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { api } from "@/lib/api";

/**
 * Two-line "portfolio-style" trend chart, rebased to 100.
 *
 * Line A (blue): equal-weighted watchlist basket.
 * Line B (orange): the aligned market benchmark (SPY for US, or the
 * asset with the most bars if no benchmark is available).
 *
 * Uses lightweight-charts, same as the asset-detail page.
 */
export function WatchlistTrendChart() {
  const wl = useQuery({ queryKey: ["watchlists"], queryFn: api.listWatchlists });
  const ids = useMemo(
    () =>
      (wl.data ?? []).flatMap((w) => w.items.map((i) => i.asset.canonical_id)),
    [wl.data]
  );

  const bars = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["bars", id, "1d", 90],
      queryFn: () => api.getBars(id, "1d", 90)
    }))
  });

  const bench = useQuery({
    queryKey: ["bars", "ETF:US:NYSE:SPY", "1d", 90],
    queryFn: () => api.getBars("ETF:US:NYSE:SPY", "1d", 90)
  });

  const series = useMemo(() => {
    // Align by intersection of bar times → equal-weighted average of
    // (close / first_close). Very intentionally simple.
    const perAssetCloses: { time: number; c: number }[][] = [];
    for (const q of bars) {
      if (!q.data) continue;
      const rows = q.data.bars.map((b) => ({
        time: Math.floor(new Date(b.t).getTime() / 1000),
        c: Number(b.c)
      }));
      if (rows.length >= 2) perAssetCloses.push(rows);
    }
    if (perAssetCloses.length === 0) return { basket: [], benchmark: [] };

    const commonTimes = perAssetCloses
      .map((rs) => new Set(rs.map((r) => r.time)))
      .reduce((acc, s) => new Set([...acc].filter((t) => s.has(t))));
    const times = [...commonTimes].sort((a, b) => a - b);

    // Rebase each asset to its own first common close, then average.
    const baskets = times.map((t) => {
      let acc = 0;
      let n = 0;
      for (const rs of perAssetCloses) {
        const first = rs.find((r) => commonTimes.has(r.time))?.c;
        const cur = rs.find((r) => r.time === t)?.c;
        if (first && cur) {
          acc += cur / first;
          n++;
        }
      }
      return { time: t, value: n > 0 ? (acc / n) * 100 : 100 };
    });

    let benchmark: { time: number; value: number }[] = [];
    if (bench.data && bench.data.bars.length >= 2) {
      const raw = bench.data.bars.map((b) => ({
        time: Math.floor(new Date(b.t).getTime() / 1000),
        c: Number(b.c)
      }));
      const first = raw[0].c;
      benchmark = raw.map((r) => ({ time: r.time, value: (r.c / first) * 100 }));
    }

    return { basket: baskets, benchmark };
  }, [bars, bench.data]);

  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;
    let chartApi: { remove: () => void } | null = null;

    (async () => {
      const { createChart, ColorType, LineStyle } = await import("lightweight-charts");
      if (disposed || !containerRef.current) return;
      const chart = createChart(containerRef.current, {
        height: 260,
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: "#64748b",
          fontSize: 11
        },
        grid: {
          vertLines: { color: "#eef1f6", style: LineStyle.Dotted },
          horzLines: { color: "#eef1f6", style: LineStyle.Dotted }
        },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false }
      });
      chartApi = chart;

      if (series.basket.length >= 2) {
        const s1 = chart.addAreaSeries({
          lineColor: "#2563eb",
          topColor: "rgba(37, 99, 235, 0.20)",
          bottomColor: "rgba(37, 99, 235, 0)",
          lineWidth: 2,
          priceLineVisible: false
        });
        s1.setData(series.basket as never);
      }
      if (series.benchmark.length >= 2) {
        const s2 = chart.addLineSeries({
          color: "#f97316",
          lineWidth: 2,
          priceLineVisible: false
        });
        s2.setData(series.benchmark as never);
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
  }, [series]);

  const basketLast = series.basket.length > 0
    ? series.basket[series.basket.length - 1].value
    : null;
  const benchmarkLast = series.benchmark.length > 0
    ? series.benchmark[series.benchmark.length - 1].value
    : null;

  return (
    <div className="grid gap-3">
      <div className="flex items-center gap-6 text-sm">
        <Legend
          color="#2563eb"
          label="Watchlist basket"
          value={basketLast != null ? `${basketLast.toFixed(2)}` : "—"}
        />
        <Legend
          color="#f97316"
          label="Benchmark (SPY)"
          value={benchmarkLast != null ? `${benchmarkLast.toFixed(2)}` : "—"}
        />
      </div>
      <div ref={containerRef} style={{ width: "100%", height: 260 }} aria-label="Watchlist trend chart" />
      <p className="text-[11px] text-ink-faint">
        Equal-weighted, rebased to 100 at the earliest common bar. Cross-currency
        holdings inflate/deflate the basket vs the USD benchmark — this is a
        directional overview, not a currency-adjusted return.
      </p>
    </div>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden
        className="inline-block h-2.5 w-2.5 rounded-sm"
        style={{ backgroundColor: color }}
      />
      <div>
        <p className="text-[10px] text-ink-faint">{label}</p>
        <p className="font-semibold mono">{value}</p>
      </div>
    </div>
  );
}
