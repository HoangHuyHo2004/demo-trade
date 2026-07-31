"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Signal, SignalClassification } from "@demo-trade/contracts";
import { FreshnessBadge } from "./FreshnessBadge";

interface Props {
  assetId: string;
  horizon: "1D" | "5D" | "20D";
}

const CLASS_STYLE: Record<SignalClassification, string> = {
  STRONG_BULLISH: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  BULLISH:        "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20",
  NEUTRAL:        "bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/20",
  BEARISH:        "bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/20",
  STRONG_BEARISH: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
  AVOID_HIGH_RISK: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
  INSUFFICIENT_DATA: "bg-slate-500/10 text-slate-500 border-slate-500/20"
};

const RISK_STYLE: Record<string, string> = {
  LOW: "text-emerald-600 dark:text-emerald-400",
  MODERATE: "text-amber-600 dark:text-amber-400",
  HIGH: "text-orange-600 dark:text-orange-400",
  SEVERE: "text-red-600 dark:text-red-400"
};

export function SignalCard({ assetId, horizon }: Props) {
  const q = useQuery({
    queryKey: ["signal", assetId, horizon],
    queryFn: () => api.getSignal(assetId, horizon)
  });

  if (q.isPending) return <p className="text-sm text-slate-500">Computing…</p>;
  if (q.error) return <p className="text-sm text-red-500">Failed to compute signal.</p>;
  const s = q.data as Signal;
  const isInsufficient = s.classification === "INSUFFICIENT_DATA";

  return (
    <div className="grid gap-3">
      <div className="flex items-center flex-wrap gap-3">
        <span
          className={`text-sm font-semibold px-3 py-1 rounded border ${
            CLASS_STYLE[s.classification]
          }`}
        >
          {s.classification.replaceAll("_", " ")}
        </span>
        <span className="text-2xl font-semibold mono">
          {s.score > 0 ? "+" : ""}
          {s.score.toFixed(1)}
        </span>
        <span className="text-xs text-slate-500">score (−100 … +100)</span>
      </div>

      {isInsufficient ? (
        <p className="text-sm text-slate-500">
          Not enough data yet for a reliable signal on this asset. Reason:{" "}
          {s.liquidity_warnings.join("; ") || "insufficient bars"}.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <p className="text-xs text-slate-500">Confidence</p>
              <p className="font-medium">{(s.confidence * 100).toFixed(0)}%</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Risk</p>
              <p className={`font-medium ${RISK_STYLE[s.risk] ?? ""}`}>{s.risk}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Horizon</p>
              <p className="font-medium">{s.horizon} · {s.expected_holding_days}d</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Regime</p>
              <p className="font-medium">{s.regime}</p>
            </div>
          </div>

          {s.entry_zone && (
            <div className="text-xs text-slate-500">
              Reference entry zone:{" "}
              <span className="mono text-slate-700 dark:text-slate-300">
                {Number(s.entry_zone[0]).toFixed(2)} – {Number(s.entry_zone[1]).toFixed(2)}
              </span>
              {s.invalidation && (
                <>
                  {" · invalidation "}
                  <span className="mono text-slate-700 dark:text-slate-300">
                    {Number(s.invalidation).toFixed(2)}
                  </span>
                </>
              )}
              {s.take_profit && s.take_profit.length > 0 && (
                <>
                  {" · targets "}
                  <span className="mono text-slate-700 dark:text-slate-300">
                    {s.take_profit.map((x) => Number(x).toFixed(2)).join(" / ")}
                  </span>
                </>
              )}
              <p className="text-[10px] mt-1 italic">
                Reference levels only. Not a recommendation.
              </p>
            </div>
          )}

          <div className="grid gap-2">
            <p className="text-xs text-slate-500">Factor contributions</p>
            <FactorBars factors={[...s.positive_factors, ...s.negative_factors]} />
          </div>

          {s.contradictions.length > 0 && (
            <div className="text-xs text-amber-600 dark:text-amber-400">
              Contradictions:
              <ul className="list-disc ml-4 mt-1 space-y-0.5">
                {s.contradictions.map((c) => <li key={c}>{c}</li>)}
              </ul>
            </div>
          )}
          {s.liquidity_warnings.length > 0 && (
            <div className="text-xs text-amber-600 dark:text-amber-400">
              Warnings:
              <ul className="list-disc ml-4 mt-1 space-y-0.5">
                {s.liquidity_warnings.map((w) => <li key={w}>{w}</li>)}
              </ul>
            </div>
          )}
        </>
      )}

      <div className="flex items-center gap-2 flex-wrap text-xs text-slate-500 pt-2 border-t border-slate-100 dark:border-slate-800">
        <FreshnessBadge eventTime={s.as_of} />
        <span>· data quality {(s.data_quality_score * 100).toFixed(0)}%</span>
        <span>· strategy <span className="mono">{s.strategy_version}</span></span>
        <span>· data <span className="mono">{s.data_version}</span></span>
      </div>
      <p className="text-[10px] italic text-slate-500">{s.disclaimer}</p>
    </div>
  );
}

function FactorBars({ factors }: { factors: { code: string; label: string; contribution: number; detail?: string }[] }) {
  if (!factors.length) return <p className="text-xs text-slate-500">No factors computed.</p>;
  const sorted = [...factors].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  return (
    <ul className="grid gap-1">
      {sorted.map((f) => (
        <li key={f.code} className="grid grid-cols-[minmax(150px,32%)_1fr_60px] items-center gap-2 text-xs">
          <span title={f.detail}>
            <span className="font-medium">{f.label}</span>
          </span>
          <div className="relative h-2 bg-slate-200/60 dark:bg-slate-800 rounded overflow-hidden">
            <div className="absolute inset-y-0 left-1/2 w-px bg-slate-400/60" aria-hidden />
            <div
              className={`absolute inset-y-0 ${
                f.contribution >= 0
                  ? "bg-emerald-500 left-1/2"
                  : "bg-red-500 right-1/2"
              }`}
              style={{ width: `${Math.min(50, Math.abs(f.contribution) * 50)}%` }}
            />
          </div>
          <span
            className={`mono text-right ${
              f.contribution >= 0
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-red-600 dark:text-red-400"
            }`}
          >
            {f.contribution >= 0 ? "+" : ""}
            {f.contribution.toFixed(2)}
          </span>
        </li>
      ))}
    </ul>
  );
}
