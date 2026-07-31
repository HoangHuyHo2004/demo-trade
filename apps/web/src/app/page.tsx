"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo } from "react";
import { api } from "@/lib/api";
import { AppHeader } from "@/components/AppHeader";
import { Card } from "@/components/Card";
import { StatCard } from "@/components/StatCard";
import { WatchlistTrendChart } from "@/components/WatchlistTrendChart";
import {
  IconAward,
  IconBell,
  IconChevronRight,
  IconLine,
  IconList,
  IconPercent,
  IconTrophy,
  IconWallet
} from "@/components/Icons";

export default function DashboardPage() {
  const markets = useQuery({ queryKey: ["markets"], queryFn: api.marketStatus });
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.providersStatus });
  const watchlists = useQuery({ queryKey: ["watchlists"], queryFn: api.listWatchlists });

  // Load signals for every watchlist item so we can populate the "Top
  // watchlist assets" panel + recent-signals table without an N+1 UI mess.
  const wlAssets = useMemo(
    () =>
      (watchlists.data ?? []).flatMap((w) =>
        w.items.map((i) => i.asset.canonical_id)
      ),
    [watchlists.data]
  );
  const signalQueries = useQueries({
    queries: wlAssets.map((id) => ({
      queryKey: ["signal", id, "5D"],
      queryFn: () => api.getSignal(id, "5D"),
      staleTime: 60_000
    }))
  });

  const providerCount = providers.data?.length ?? 0;
  const activeProviders = providers.data?.filter((p) => p.status === "ok").length ?? 0;
  const openMarkets = markets.data?.filter((m) => m.is_open).length ?? 0;
  const closedMarkets = (markets.data?.length ?? 0) - openMarkets;

  const signals = signalQueries
    .map((q, i) => (q.data ? { ...q.data, canonical_id: wlAssets[i] } : null))
    .filter((s): s is NonNullable<typeof s> => s !== null);
  const bullishCount = signals.filter((s) => s.score > 20).length;
  const bearishCount = signals.filter((s) => s.score < -20).length;
  const avgConfidence =
    signals.length > 0
      ? signals.reduce((a, s) => a + (s.confidence ?? 0), 0) / signals.length
      : 0;
  const staleSignals = signals.filter((s) => s.data_freshness === "STALE").length;

  return (
    <div className="grid gap-4 max-w-[1400px]">
      <AppHeader userName="demo@demo-trade.local" />

      {/* Top row: Watchlist trend chart (left) + Market cards (right) */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card
          title="Watchlist trend"
          subtitle="Rebased to 100 over the last 60 days"
        >
          <WatchlistTrendChart />
        </Card>

        <div className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <MarketPill market="US" markets={markets.data} />
            <MarketPill market="VN" markets={markets.data} />
          </div>

          <Card title="Providers" actions={
            <span className="text-xs text-ink-faint">
              {activeProviders}/{providerCount} active
            </span>
          }>
            {providers.isPending && (
              <p className="text-sm text-ink-soft">Loading…</p>
            )}
            <ul className="grid gap-2 text-sm">
              {providers.data?.map((p) => (
                <li key={p.slug} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusDot status={p.status} />
                    <span className="mono font-medium">{p.slug}</span>
                  </div>
                  <span className="text-xs text-ink-faint">
                    {p.is_selected_for.length > 0
                      ? `→ ${p.is_selected_for.join(", ")}`
                      : p.status}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      {/* Middle row: six stat tiles */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard
          icon={<IconAward width={18} height={18} />}
          label="Bullish signals"
          value={bullishCount}
          hint={`of ${signals.length}`}
          tone="pos"
        />
        <StatCard
          icon={<IconTrophy width={18} height={18} />}
          label="Bearish signals"
          value={bearishCount}
          hint={`of ${signals.length}`}
          tone="neg"
        />
        <StatCard
          icon={<IconLine width={18} height={18} />}
          label="Avg confidence"
          value={`${(avgConfidence * 100).toFixed(0)}%`}
          tone="neutral"
        />
        <StatCard
          icon={<IconPercent width={18} height={18} />}
          label="Markets open"
          value={openMarkets}
          hint={`${closedMarkets} closed`}
          tone="neutral"
        />
        <StatCard
          icon={<IconWallet width={18} height={18} />}
          label="Watched assets"
          value={wlAssets.length}
          tone="neutral"
        />
        <StatCard
          icon={<IconBell width={18} height={18} />}
          label="Stale signals"
          value={staleSignals}
          tone={staleSignals > 0 ? "warn" : "neutral"}
        />
      </div>

      {/* Bottom row: Recent signals table (left) + Notifications (right) */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card
          title="Recent signals"
          actions={
            <Link
              href="/watchlist"
              className="text-xs text-brand font-medium inline-flex items-center gap-1"
            >
              Manage watchlist <IconChevronRight width={14} height={14} />
            </Link>
          }
          padded={false}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-ink-faint">
                <tr className="border-b border-canvas-border">
                  <th className="text-left font-medium px-5 py-3">Asset</th>
                  <th className="text-left font-medium px-5 py-3">Market</th>
                  <th className="text-left font-medium px-5 py-3">Class</th>
                  <th className="text-right font-medium px-5 py-3">Score</th>
                  <th className="text-right font-medium px-5 py-3">Conf.</th>
                  <th className="text-right font-medium px-5 py-3">Risk</th>
                  <th className="text-right font-medium px-5 py-3">Data</th>
                </tr>
              </thead>
              <tbody>
                {signals.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center text-ink-soft py-6">
                      No signals yet — add assets to a watchlist.
                    </td>
                  </tr>
                )}
                {signals.map((s) => (
                  <tr
                    key={s.canonical_id}
                    className="border-b border-canvas-border last:border-none hover:bg-canvas"
                  >
                    <td className="px-5 py-3">
                      <Link
                        href={`/assets/${encodeURIComponent(s.canonical_id)}`}
                        className="mono font-medium hover:underline"
                      >
                        {s.canonical_id.split(":").pop()}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-ink-soft">
                      {s.canonical_id.split(":")[1]}
                    </td>
                    <td className="px-5 py-3">
                      <ClassPill classification={s.classification} />
                    </td>
                    <td
                      className={`px-5 py-3 text-right mono ${
                        s.score > 0 ? "text-pos" : s.score < 0 ? "text-neg" : "text-ink-soft"
                      }`}
                    >
                      {s.score > 0 ? "+" : ""}
                      {s.score.toFixed(1)}
                    </td>
                    <td className="px-5 py-3 text-right mono">
                      {(s.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-5 py-3 text-right">
                      <RiskPill risk={s.risk} />
                    </td>
                    <td className="px-5 py-3 text-right text-xs">
                      <FreshnessPill f={s.data_freshness} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Notifications" actions={
          <span className="text-xs text-ink-faint">Last 24h</span>
        }>
          <ul className="grid gap-3 text-sm">
            {(providers.data ?? []).filter((p) => p.status !== "ok").map((p) => (
              <li key={p.slug} className="flex items-start gap-3">
                <span className={`inline-block h-2 w-2 rounded-full mt-1.5 ${
                  p.status === "missing_credentials" ? "bg-warn" : "bg-neg"
                }`} />
                <div>
                  <p className="font-medium">Provider {p.slug} — {p.status.replaceAll("_", " ")}</p>
                  <p className="text-xs text-ink-faint">{p.message}</p>
                </div>
              </li>
            ))}
            {staleSignals > 0 && (
              <li className="flex items-start gap-3">
                <span className="inline-block h-2 w-2 rounded-full mt-1.5 bg-warn" />
                <div>
                  <p className="font-medium">{staleSignals} stale signal(s)</p>
                  <p className="text-xs text-ink-faint">Some watched assets have data more than a session old.</p>
                </div>
              </li>
            )}
            {(providers.data?.every((p) => p.status === "ok") ?? false) && staleSignals === 0 && (
              <li className="text-sm text-ink-soft">All systems normal.</li>
            )}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function MarketPill({
  market, markets
}: {
  market: "US" | "VN";
  markets: import("@demo-trade/contracts").MarketStatus[] | undefined;
}) {
  const rows = (markets ?? []).filter((m) => m.market === market);
  const open = rows.some((m) => m.is_open);
  const nextTransition = open
    ? rows[0]?.next_close_utc
    : rows[0]?.next_open_utc;
  return (
    <div className="bg-white rounded-card shadow-card border border-canvas-border p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-ink-faint">{market} markets</p>
        <span
          className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
            open ? "bg-pos-soft text-pos" : "bg-canvas text-ink-soft"
          }`}
        >
          {open ? "OPEN" : "CLOSED"}
        </span>
      </div>
      <p className="text-lg font-semibold">
        {rows.map((r) => r.calendar).join(" · ")}
      </p>
      <p className="text-xs text-ink-faint mt-2">
        {open ? "Closes " : "Opens "}
        <span className="mono">
          {nextTransition
            ? new Date(nextTransition).toLocaleString(undefined, {
                dateStyle: "short",
                timeStyle: "short"
              })
            : "—"}
        </span>
      </p>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "ok"
      ? "bg-pos"
      : status === "missing_credentials"
      ? "bg-warn"
      : "bg-neg";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} />;
}

const CLASS_STYLES: Record<string, string> = {
  STRONG_BULLISH: "bg-pos-soft text-pos",
  BULLISH: "bg-pos-soft text-pos",
  NEUTRAL: "bg-canvas text-ink-soft",
  BEARISH: "bg-neg-soft text-neg",
  STRONG_BEARISH: "bg-neg-soft text-neg",
  AVOID_HIGH_RISK: "bg-warn-soft text-warn",
  INSUFFICIENT_DATA: "bg-canvas text-ink-soft"
};

function ClassPill({ classification }: { classification: string }) {
  return (
    <span
      className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
        CLASS_STYLES[classification] ?? "bg-canvas text-ink-soft"
      }`}
    >
      {classification.replaceAll("_", " ")}
    </span>
  );
}

function RiskPill({ risk }: { risk: string }) {
  const tone =
    risk === "LOW"
      ? "bg-pos-soft text-pos"
      : risk === "MODERATE"
      ? "bg-canvas text-ink-soft"
      : risk === "HIGH"
      ? "bg-warn-soft text-warn"
      : "bg-neg-soft text-neg";
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${tone}`}>
      {risk}
    </span>
  );
}

function FreshnessPill({ f }: { f: string }) {
  const tone =
    f === "CURRENT"
      ? "text-pos"
      : f === "STALE"
      ? "text-warn"
      : "text-ink-faint";
  return <span className={`mono ${tone}`}>{f}</span>;
}

// Reference the (imported-but-not-used) icon to silence the linter without
// re-exporting it from a Next.js route module (which is illegal).
void IconList;
