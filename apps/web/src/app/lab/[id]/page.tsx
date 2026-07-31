"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { SignalCard } from "@/components/SignalCard";
import type { BacktestResult } from "@demo-trade/contracts";

type Horizon = "1D" | "5D" | "20D";

export default function LabPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);

  const [horizon, setHorizon] = useState<Horizon>("5D");
  const [entryThr, setEntryThr] = useState(20);
  const [exitThr, setExitThr] = useState(-5);
  const [costBps, setCostBps] = useState<string>("");   // empty = defaults
  const [slipBps, setSlipBps] = useState<string>("");

  const asset = useQuery({ queryKey: ["asset", id], queryFn: () => api.getAsset(id) });

  const backtest = useMutation({
    mutationFn: () =>
      api.runBacktest({
        asset_canonical_id: id,
        interval: "1d",
        horizon,
        entry_threshold: entryThr,
        exit_threshold: exitThr,
        cost_bps: costBps === "" ? null : Number(costBps),
        slippage_bps: slipBps === "" ? null : Number(slipBps)
      })
  });

  return (
    <div className="grid gap-4">
      <div>
        <p className="text-xs text-slate-500 mono">{id}</p>
        <h1 className="text-xl font-semibold tracking-tight">
          Signal laboratory — {asset.data?.display_symbol ?? "…"}{" "}
          <span className="text-slate-500 font-normal text-base">{asset.data?.name}</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Inspect the model's factor contributions, adjust bounded parameters,
          and run a cost-aware walk-forward backtest. All calculations are
          deterministic and audited (see{" "}
          <code className="mono">AGENTS.md</code>).
        </p>
      </div>

      <Card
        title="Current signal"
        actions={
          <div className="flex gap-1">
            {(["1D", "5D", "20D"] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`text-xs px-2 py-1 rounded border ${
                  h === horizon
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-slate-200 dark:border-slate-700 text-slate-500"
                }`}
              >
                {h}
              </button>
            ))}
          </div>
        }
      >
        <SignalCard assetId={id} horizon={horizon} />
      </Card>

      <Card title="Backtest">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm grid gap-1">
            <span className="text-xs text-slate-500">Entry threshold (score ≥)</span>
            <input
              type="number"
              value={entryThr}
              onChange={(e) => setEntryThr(Number(e.target.value))}
              min={-100}
              max={100}
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            />
          </label>
          <label className="text-sm grid gap-1">
            <span className="text-xs text-slate-500">Exit threshold (score ≤)</span>
            <input
              type="number"
              value={exitThr}
              onChange={(e) => setExitThr(Number(e.target.value))}
              min={-100}
              max={100}
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            />
          </label>
          <label className="text-sm grid gap-1">
            <span className="text-xs text-slate-500">Cost (bps/side, blank = market default)</span>
            <input
              type="number"
              value={costBps}
              onChange={(e) => setCostBps(e.target.value)}
              min={0} max={500}
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            />
          </label>
          <label className="text-sm grid gap-1">
            <span className="text-xs text-slate-500">Slippage (bps/side, blank = default)</span>
            <input
              type="number"
              value={slipBps}
              onChange={(e) => setSlipBps(e.target.value)}
              min={0} max={500}
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            />
          </label>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => backtest.mutate()}
            disabled={backtest.isPending}
            className="text-sm px-3 py-1.5 rounded border border-blue-500 text-blue-600 dark:text-blue-400 disabled:opacity-50"
          >
            {backtest.isPending ? "Running…" : "Run backtest"}
          </button>
          <p className="text-xs text-slate-500">
            Walk-forward evaluation using each bar's <code className="mono">available_at</code>{" "}
            (no lookahead). Costs applied per side on entry and exit.
          </p>
        </div>

        {backtest.error && (
          <p className="text-sm text-red-500 mt-3">
            Backtest failed: {(backtest.error as Error).message}
          </p>
        )}
        {backtest.data && <BacktestResultView result={backtest.data} />}
      </Card>

      <div>
        <Link
          href={`/assets/${encodeURIComponent(id)}`}
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          ← Back to asset detail
        </Link>
      </div>
    </div>
  );
}

function BacktestResultView({ result }: { result: BacktestResult }) {
  const m = result.metrics;
  return (
    <div className="mt-4 grid gap-4">
      {result.warnings && result.warnings.length > 0 && (
        <div className="text-xs text-amber-600 dark:text-amber-400">
          {result.warnings.map((w, i) => (
            <p key={i}>⚠️ {w}</p>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <Metric label="Total return" value={fmtPct(m.total_return)} accent={m.total_return} />
        <Metric label="CAGR" value={fmtPct(m.cagr)} accent={m.cagr} />
        <Metric label="Sharpe" value={m.sharpe.toFixed(2)} />
        <Metric label="Sortino" value={m.sortino.toFixed(2)} />
        <Metric label="Max drawdown" value={fmtPct(-m.max_drawdown)} accent={-m.max_drawdown} />
        <Metric label="Calmar" value={m.calmar.toFixed(2)} />
        <Metric label="Win rate" value={fmtPct(m.win_rate)} />
        <Metric
          label="Profit factor"
          value={typeof m.profit_factor === "number" ? m.profit_factor.toFixed(2) : "∞"}
        />
        <Metric label="Trades" value={String(m.trades)} />
        <Metric label="Avg holding (bars)" value={m.avg_holding_bars.toFixed(1)} />
        <Metric label="Exposure" value={fmtPct(m.exposure)} />
        <Metric label="Turnover / yr" value={m.turnover.toFixed(1)} />
      </div>

      <div className="grid gap-2 text-sm">
        <p className="text-xs text-slate-500">vs baselines (window return)</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Metric label="Strategy" value={fmtPct(m.total_return)} accent={m.total_return} />
          <Metric label="Buy & hold" value={fmtPct(m.buy_hold_return)} accent={m.buy_hold_return} />
          <Metric label="SMA 50/200" value={fmtPct(m.sma_baseline_return)} accent={m.sma_baseline_return} />
          <Metric
            label="Benchmark"
            value={m.benchmark_return != null ? fmtPct(m.benchmark_return) : "—"}
            accent={m.benchmark_return ?? 0}
          />
        </div>
      </div>

      <EquityChart points={result.equity} />

      <p className="text-[10px] italic text-slate-500">
        Backtest results describe past behavior of the model over the sampled window.
        Live performance will differ. Trading costs, slippage, and taxes are configurable
        (see <code className="mono">app/quant/costs.py</code>). Not investment advice.
      </p>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: number }) {
  const color =
    accent == null
      ? "text-slate-700 dark:text-slate-200"
      : accent >= 0
      ? "text-emerald-600 dark:text-emerald-400"
      : "text-red-600 dark:text-red-400";
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`font-medium mono ${color}`}>{value}</p>
    </div>
  );
}

function fmtPct(x: number): string {
  if (!Number.isFinite(x)) return "—";
  return `${(x * 100).toFixed(2)}%`;
}

function EquityChart({ points }: { points: BacktestResult["equity"] }) {
  if (points.length < 2) return null;
  const w = 800;
  const h = 200;
  const times = points.map((p) => new Date(p.t).getTime());
  const t0 = times[0];
  const tN = times[times.length - 1];
  const span = Math.max(1, tN - t0);
  const values = points.flatMap((p) => [p.strategy, p.buy_hold]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(1e-9, max - min);

  const path = (key: "strategy" | "buy_hold") =>
    points
      .map((p, i) => {
        const x = ((times[i] - t0) / span) * w;
        const y = h - ((p[key] - min) / range) * h;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48" role="img" aria-label="Equity curve">
        <path d={path("buy_hold")} fill="none" stroke="#64748b" strokeWidth="1.2" />
        <path d={path("strategy")} fill="none" stroke="#4f8cff" strokeWidth="1.6" />
      </svg>
      <div className="text-xs text-slate-500 flex gap-4 mt-1">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-3 bg-[#4f8cff]" aria-hidden /> Strategy
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-3 bg-slate-500" aria-hidden /> Buy &amp; hold
        </span>
      </div>
    </div>
  );
}
