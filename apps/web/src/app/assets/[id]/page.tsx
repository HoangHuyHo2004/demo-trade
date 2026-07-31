"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { fmtNumber, fmtTime, ageString } from "@/lib/format";
import { useMemo } from "react";

export default function AssetPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);

  const asset = useQuery({ queryKey: ["asset", id], queryFn: () => api.getAsset(id) });
  const quote = useQuery({ queryKey: ["quote", id], queryFn: () => api.getQuote(id) });
  const bars = useQuery({
    queryKey: ["bars", id, "1d", 365],
    queryFn: () => api.getBars(id, "1d", 365)
  });

  const sparklinePath = useMemo(() => {
    const b = bars.data?.bars ?? [];
    if (b.length < 2) return "";
    const values = b.map((x) => Number(x.c));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const w = 600;
    const h = 140;
    const step = w / (values.length - 1);
    return values
      .map((v, i) => {
        const x = i * step;
        const y = h - ((v - min) / range) * h;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [bars.data]);

  return (
    <div className="grid gap-4">
      <div>
        <p className="text-xs text-slate-500 mono">{id}</p>
        <h1 className="text-xl font-semibold tracking-tight">
          {asset.data?.display_symbol ?? "…"}{" "}
          <span className="text-slate-500 font-normal text-base">{asset.data?.name}</span>
        </h1>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Quote">
          {quote.isPending && <p className="text-sm text-slate-500">Loading…</p>}
          {quote.data && (
            <div className="grid gap-2">
              <p className="text-3xl font-semibold mono">
                {fmtNumber(quote.data.price, 2)}{" "}
                <span className="text-base text-slate-500">{quote.data.currency}</span>
              </p>
              <p className="text-xs text-slate-500">
                As of {fmtTime(quote.data.event_time)} ({ageString(quote.data.event_time)}) ·{" "}
                source <span className="mono">{quote.data.source}</span> · market{" "}
                <span
                  className={
                    quote.data.market_state === "OPEN"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-slate-500"
                  }
                >
                  {quote.data.market_state}
                </span>
                {quote.data.is_stale && (
                  <span className="ml-2 text-amber-600 dark:text-amber-400">· stale</span>
                )}
              </p>
            </div>
          )}
        </Card>

        <Card title="Signal (Phase 3)">
          <p className="text-sm text-slate-500">
            Quantitative signal, confidence, risk class, factor contributions, and
            backtest summary will appear here once the signal engine is implemented.
            The AI research agent (Phase 4) is <em>not</em> permitted to produce these
            values — see <code className="mono">AGENTS.md</code>.
          </p>
        </Card>
      </div>

      <Card title="Chart (daily close, 1Y)">
        {bars.isPending && <p className="text-sm text-slate-500">Loading…</p>}
        {bars.data && (
          <>
            <svg viewBox="0 0 600 140" className="w-full h-40" role="img" aria-label="Close price sparkline">
              <path d={sparklinePath} fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            <p className="text-xs text-slate-500 mt-2">
              {bars.data.bars.length} bars · interval {bars.data.interval} · source{" "}
              <span className="mono">{bars.data.source}</span>
            </p>
          </>
        )}
      </Card>
    </div>
  );
}
