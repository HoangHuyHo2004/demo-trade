"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { ProviderPanel } from "@/components/ProviderPanel";

export default function DashboardPage() {
  const markets = useQuery({ queryKey: ["markets"], queryFn: api.marketStatus });
  const watchlists = useQuery({ queryKey: ["watchlists"], queryFn: api.listWatchlists });

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Markets">
          {markets.isPending && <p className="text-sm text-slate-500">Loading…</p>}
          {markets.error && <p className="text-sm text-red-500">Error loading markets.</p>}
          <ul className="grid gap-2">
            {markets.data?.map((m) => (
              <li key={m.calendar} className="flex items-center justify-between text-sm">
                <span className="font-medium">
                  {m.market} <span className="text-slate-500">({m.calendar})</span>
                </span>
                <span className={m.is_open ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500"}>
                  {m.state}
                  {m.is_open ? " · closes " : " · opens "}
                  <span className="mono">
                    {m.is_open
                      ? m.next_close_utc
                        ? new Date(m.next_close_utc).toLocaleString()
                        : "—"
                      : m.next_open_utc
                      ? new Date(m.next_open_utc).toLocaleString()
                      : "—"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Data providers">
          <ProviderPanel />
        </Card>
      </div>

      <Card
        title="Watchlist"
        actions={
          <Link
            href="/watchlist"
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
          >
            Manage →
          </Link>
        }
      >
        {watchlists.isPending && <p className="text-sm text-slate-500">Loading…</p>}
        {watchlists.data?.map((wl) => (
          <div key={wl.id} className="grid gap-1">
            <p className="text-sm font-medium">{wl.name}</p>
            <ul className="grid gap-1">
              {wl.items.length === 0 && (
                <li className="text-sm text-slate-500">No assets yet.</li>
              )}
              {wl.items.map((it) => (
                <li key={it.id} className="flex justify-between text-sm">
                  <Link
                    href={`/assets/${encodeURIComponent(it.asset.canonical_id)}`}
                    className="hover:underline mono"
                  >
                    {it.asset.display_symbol}
                    <span className="text-slate-500 ml-2">{it.asset.name}</span>
                  </Link>
                  <span className="text-slate-500">{it.asset.market}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Card>

      <p className="text-xs text-slate-500">
        Phase 2 wired. Coinbase spot data is fetched from the public exchange endpoint;
        Alpaca and SSI FastConnect are auto-selected when credentials are configured.
      </p>
    </div>
  );
}
