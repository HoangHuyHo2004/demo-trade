"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import type { Asset } from "@demo-trade/contracts";

export default function WatchlistPage() {
  const qc = useQueryClient();
  const watchlists = useQuery({ queryKey: ["watchlists"], queryFn: api.listWatchlists });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const active = watchlists.data?.find((w) => w.id === selectedId) ?? watchlists.data?.[0];

  const [query, setQuery] = useState("");
  const search = useQuery({
    queryKey: ["assets-search", query],
    queryFn: () => api.searchAssets(query),
    enabled: query.length >= 1
  });

  const addItem = useMutation({
    mutationFn: (asset: Asset) =>
      api.addWatchlistItem(active!.id, asset.canonical_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] })
  });

  const removeItem = useMutation({
    mutationFn: (itemId: number) => api.removeWatchlistItem(active!.id, itemId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] })
  });

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Watchlists</h1>

      <Card>
        <div className="flex gap-2 mb-4 flex-wrap">
          {watchlists.data?.map((w) => (
            <button
              key={w.id}
              onClick={() => setSelectedId(w.id)}
              className={`text-sm px-3 py-1 rounded-full border ${
                (active?.id ?? -1) === w.id
                  ? "border-blue-500 text-blue-600 dark:text-blue-400"
                  : "border-slate-300 dark:border-slate-700"
              }`}
            >
              {w.name} <span className="text-slate-500">({w.items.length})</span>
            </button>
          ))}
        </div>

        {active && (
          <>
            <ul className="grid gap-2 mb-6">
              {active.items.length === 0 && (
                <li className="text-sm text-slate-500">No assets on this watchlist yet.</li>
              )}
              {active.items.map((it) => (
                <li
                  key={it.id}
                  className="flex items-center justify-between text-sm border-b border-slate-100 dark:border-slate-800 py-2"
                >
                  <Link
                    href={`/assets/${encodeURIComponent(it.asset.canonical_id)}`}
                    className="hover:underline"
                  >
                    <span className="mono font-medium">{it.asset.display_symbol}</span>
                    <span className="text-slate-500 ml-2">{it.asset.name}</span>
                    <span className="text-slate-400 ml-2 text-xs">{it.asset.market}</span>
                  </Link>
                  <button
                    onClick={() => removeItem.mutate(it.id)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>

            <div className="grid gap-2">
              <label className="text-sm font-medium">Add asset</label>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by ticker or name (e.g. AAPL, VNM, BTC)"
                className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-3 py-2 text-sm"
              />
              <ul className="grid gap-1">
                {search.data?.map((a) => (
                  <li key={a.canonical_id} className="flex justify-between text-sm">
                    <span>
                      <span className="mono font-medium">{a.display_symbol}</span>
                      <span className="text-slate-500 ml-2">{a.name}</span>
                      <span className="text-slate-400 ml-2 text-xs">{a.canonical_id}</span>
                    </span>
                    <button
                      onClick={() => addItem.mutate(a)}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                      disabled={addItem.isPending}
                    >
                      Add
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
