"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { CompareChart, type CompareSeries } from "@/components/CompareChart";
import { PERIODS, periodByKey, type PeriodKey } from "@/lib/periods";
import type { Asset } from "@demo-trade/contracts";

const MAX_ASSETS = 5;
const COLORS = ["#4f8cff", "#22c55e", "#ef4444", "#f59e0b", "#a855f7"];

export default function ComparePage() {
  const router = useRouter();
  const params = useSearchParams();
  const idsFromUrl = useMemo(() => {
    const raw = params.get("ids") ?? "";
    return raw.split(",").map((s) => s.trim()).filter(Boolean).slice(0, MAX_ASSETS);
  }, [params]);

  const [ids, setIds] = useState<string[]>(idsFromUrl);
  const [period, setPeriod] = useState<PeriodKey>("1Y");
  const p = periodByKey(period);
  const [query, setQuery] = useState("");

  const search = useQuery({
    queryKey: ["assets-search", query],
    queryFn: () => api.searchAssets(query),
    enabled: query.length >= 1
  });

  const assetQueries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["asset", id],
      queryFn: () => api.getAsset(id)
    }))
  });
  const barQueries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["bars", id, p.interval, p.lookbackDays],
      queryFn: () => api.getBars(id, p.interval, p.lookbackDays)
    }))
  });

  const assets = assetQueries
    .map((q) => q.data)
    .filter((a): a is Asset => Boolean(a));
  const currencies = new Set(assets.map((a) => a.quote_currency));
  const mixedCurrencies = currencies.size > 1;

  const series: CompareSeries[] = ids.map((id, i) => {
    const asset = assetQueries[i].data;
    const bars = barQueries[i].data;
    return {
      id,
      label: asset?.display_symbol ?? id,
      color: COLORS[i % COLORS.length],
      bars: bars?.bars ?? []
    };
  });

  function replaceIds(next: string[]) {
    setIds(next);
    const q = next.length ? `?ids=${next.map(encodeURIComponent).join(",")}` : "";
    router.replace(`/compare${q}`);
  }
  function add(id: string) {
    if (ids.includes(id) || ids.length >= MAX_ASSETS) return;
    replaceIds([...ids, id]);
    setQuery("");
  }
  function remove(id: string) {
    replaceIds(ids.filter((x) => x !== id));
  }

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Compare</h1>

      <Card
        title="Assets"
        actions={
          <div className="flex gap-1 flex-wrap">
            {PERIODS.map((pp) => (
              <button
                key={pp.key}
                onClick={() => setPeriod(pp.key)}
                className={`text-xs px-2 py-1 rounded border ${
                  pp.key === period
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-slate-200 dark:border-slate-700 text-slate-500"
                }`}
              >
                {pp.label}
              </button>
            ))}
          </div>
        }
      >
        <div className="flex flex-wrap gap-2 mb-4">
          {series.map((s, i) => (
            <span
              key={s.id}
              className="text-xs px-2 py-1 rounded border border-slate-200 dark:border-slate-800 flex items-center gap-2"
            >
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: s.color }}
              />
              <span className="mono font-medium">{s.label}</span>
              {assets[i]?.quote_currency && (
                <span className="text-slate-400">{assets[i]!.quote_currency}</span>
              )}
              <button
                onClick={() => remove(s.id)}
                className="text-red-500 hover:underline"
                aria-label={`remove ${s.label}`}
              >
                ✕
              </button>
            </span>
          ))}
          {series.length === 0 && (
            <span className="text-sm text-slate-500">Add up to {MAX_ASSETS} assets to compare.</span>
          )}
        </div>

        {mixedCurrencies && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mb-3">
            Warning: mixing currencies ({[...currencies].join(", ")}). The chart shows
            price-return series (rebased to 100) so cross-currency comparison of
            <em> percentage change</em> is meaningful, but absolute prices are not
            currency-normalized here.
          </p>
        )}

        {ids.length < MAX_ASSETS && (
          <div className="grid gap-2 mb-4">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search to add (ticker or name)"
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-3 py-2 text-sm"
            />
            <ul className="grid gap-1">
              {search.data?.slice(0, 8).map((a) => (
                <li key={a.canonical_id} className="flex justify-between text-sm">
                  <span>
                    <span className="mono font-medium">{a.display_symbol}</span>
                    <span className="text-slate-500 ml-2">{a.name}</span>
                    <span className="text-slate-400 ml-2 text-xs">{a.canonical_id}</span>
                  </span>
                  <button
                    onClick={() => add(a.canonical_id)}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    disabled={ids.includes(a.canonical_id)}
                  >
                    {ids.includes(a.canonical_id) ? "already added" : "Add"}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {series.length > 0 && <CompareChart series={series} />}

        {series.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-1 pr-4">Asset</th>
                  <th className="py-1 pr-4">Ccy</th>
                  <th className="py-1 pr-4">Bars</th>
                  <th className="py-1 pr-4">{p.label} return</th>
                </tr>
              </thead>
              <tbody>
                {series.map((s, i) => {
                  const closes = s.bars.map((b) => Number(b.c));
                  const first = closes[0];
                  const last = closes[closes.length - 1];
                  const ret = first && last ? (last - first) / first : null;
                  return (
                    <tr key={s.id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-1 pr-4 mono">
                        <span
                          aria-hidden
                          className="inline-block h-2 w-2 rounded-full mr-2"
                          style={{ backgroundColor: s.color }}
                        />
                        {s.label}
                      </td>
                      <td className="py-1 pr-4 text-slate-500">
                        {assets[i]?.quote_currency ?? "—"}
                      </td>
                      <td className="py-1 pr-4 text-slate-500">{s.bars.length}</td>
                      <td
                        className={`py-1 pr-4 mono ${
                          ret == null
                            ? "text-slate-400"
                            : ret >= 0
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "text-red-600 dark:text-red-400"
                        }`}
                      >
                        {ret == null ? "—" : `${(ret * 100).toFixed(2)}%`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
