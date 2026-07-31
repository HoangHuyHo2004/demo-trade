"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { FreshnessBadge } from "@/components/FreshnessBadge";
import { PriceChart } from "@/components/PriceChart";
import { SignalCard } from "@/components/SignalCard";
import { fmtNumber, fmtTime } from "@/lib/format";
import { PERIODS, periodByKey, periodReturn, type PeriodKey } from "@/lib/periods";

export default function AssetPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);

  const [period, setPeriod] = useState<PeriodKey>("1Y");
  const p = periodByKey(period);

  const asset = useQuery({ queryKey: ["asset", id], queryFn: () => api.getAsset(id) });
  const quote = useQuery({ queryKey: ["quote", id], queryFn: () => api.getQuote(id) });
  const bars = useQuery({
    queryKey: ["bars", id, p.interval, p.lookbackDays],
    queryFn: () => api.getBars(id, p.interval, p.lookbackDays)
  });

  const returns = useMemo(() => {
    const rows = PERIODS.map((pp) => ({ p: pp, value: null as number | null }));
    if (!bars.data) return rows;
    // For each period, compute return over the corresponding tail of the
    // currently loaded series when the loaded lookback covers it. When it
    // doesn't, we leave the cell blank rather than lie.
    const closes = bars.data.bars.map((b) => Number(b.c));
    const times = bars.data.bars.map((b) => new Date(b.t).getTime());
    const nowMs = Date.now();
    return rows.map((row) => {
      if (closes.length < 2) return row;
      const cutoff = nowMs - row.p.lookbackDays * 86_400_000;
      const idx = times.findIndex((t) => t >= cutoff);
      if (idx < 0 || idx >= closes.length - 1) return row;
      const first = closes[idx];
      const last = closes[closes.length - 1];
      if (!first) return row;
      return { p: row.p, value: (last - first) / first };
    });
  }, [bars.data]);

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <p className="text-xs text-slate-500 mono">{id}</p>
          <h1 className="text-xl font-semibold tracking-tight">
            {asset.data?.display_symbol ?? "…"}{" "}
            <span className="text-slate-500 font-normal text-base">{asset.data?.name}</span>
          </h1>
        </div>
        <div className="flex gap-3 text-xs">
          <Link
            href={`/lab/${encodeURIComponent(id)}`}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Signal lab →
          </Link>
          <Link
            href={`/research?asset=${encodeURIComponent(id)}`}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Research chat →
          </Link>
          <Link
            href={`/compare?ids=${encodeURIComponent(id)}`}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Compare with… →
          </Link>
        </div>
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
              <div className="flex items-center gap-2 flex-wrap text-xs text-slate-500">
                <FreshnessBadge
                  eventTime={quote.data.event_time}
                  isStale={quote.data.is_stale}
                  source={quote.data.source}
                />
                <span>
                  Market{" "}
                  <span
                    className={
                      quote.data.market_state === "OPEN"
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-slate-500"
                    }
                  >
                    {quote.data.market_state}
                  </span>
                </span>
                <span>· {fmtTime(quote.data.event_time)}</span>
              </div>
            </div>
          )}
        </Card>

        <Card
          title="Signal"
          actions={
            <Link
              href={`/lab/${encodeURIComponent(id)}`}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
            >
              Open lab →
            </Link>
          }
        >
          <SignalCard assetId={id} horizon="5D" />
        </Card>
      </div>

      <Card
        title={`Chart · ${p.interval} · ${p.label}`}
        actions={
          <div className="flex gap-1 flex-wrap">
            {PERIODS.map((pp) => (
              <button
                key={pp.key}
                onClick={() => setPeriod(pp.key)}
                className={`text-xs px-2 py-1 rounded border ${
                  pp.key === period
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                {pp.label}
              </button>
            ))}
          </div>
        }
      >
        {bars.isPending && <p className="text-sm text-slate-500">Loading…</p>}
        {bars.data && bars.data.bars.length > 0 && (
          <>
            <PriceChart bars={bars.data.bars} type="line" />
            <div className="mt-3 flex items-center justify-between flex-wrap gap-2">
              <div className="flex flex-wrap gap-2">
                {returns.map((r) => (
                  <span
                    key={r.p.key}
                    className="text-xs px-2 py-1 rounded border border-slate-200 dark:border-slate-800"
                  >
                    <span className="text-slate-500">{r.p.label}</span>{" "}
                    <span
                      className={
                        r.value == null
                          ? "text-slate-400"
                          : r.value >= 0
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-red-600 dark:text-red-400"
                      }
                    >
                      {r.value == null ? "—" : `${(r.value * 100).toFixed(2)}%`}
                    </span>
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>{bars.data.bars.length} bars</span>
                <span>·</span>
                <span>source <span className="mono">{bars.data.source}</span></span>
                <span>·</span>
                <span>{bars.data.from_cache ? "from cache" : "fresh fetch"}</span>
                <FreshnessBadge
                  eventTime={bars.data.last_bar_time}
                  ingestTime={bars.data.last_ingest_time}
                />
              </div>
            </div>
          </>
        )}
        {bars.data && bars.data.bars.length === 0 && (
          <p className="text-sm text-slate-500">No bars available for this window.</p>
        )}
      </Card>
    </div>
  );
}
