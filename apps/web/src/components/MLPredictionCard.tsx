"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { isMLInsufficient, type MLPrediction } from "@demo-trade/contracts";

/**
 * ML prediction panel — shadow-only in Phase 1.
 *
 * Never presented as a directive. Always shows:
 *  - the SHADOW badge (spec §Machine-learning user interface)
 *  - the model version + data version so an operator can find the run
 *  - uncertainty and opposing evidence prominently
 */
export function MLPredictionCard({
  assetId, horizon = "5D"
}: {
  assetId: string;
  horizon?: "1D" | "5D" | "20D";
}) {
  const q = useQuery({
    queryKey: ["ml-prediction", assetId, horizon],
    queryFn: () => api.getMLPrediction(assetId, horizon)
  });

  if (q.isPending) return <p className="text-sm text-ink-soft">Loading ML prediction…</p>;
  if (q.error) return <p className="text-sm text-neg">Failed to load ML prediction.</p>;
  const r = q.data!;
  if (isMLInsufficient(r)) {
    return (
      <div className="grid gap-2">
        <ShadowBadge />
        <p className="text-sm text-ink-soft">
          No ML prediction available yet.{" "}
          <span className="text-ink-faint">{r.detail}</span>
        </p>
        <p className="text-[10px] text-ink-faint italic">
          Rule-based signal remains the authoritative source. See{" "}
          <code className="mono">docs/ml-architecture.md</code>.
        </p>
      </div>
    );
  }
  return <MLPredictionBody p={r} />;
}

function MLPredictionBody({ p }: { p: MLPrediction }) {
  const probPos = p.prob_positive ?? 0;
  return (
    <div className="grid gap-3">
      <ShadowBadge />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <Stat
          label="Prob. positive"
          value={probPos != null ? `${(probPos * 100).toFixed(0)}%` : "—"}
          tone={probPos > 0.55 ? "pos" : probPos < 0.45 ? "neg" : "neutral"}
        />
        <Stat
          label="Prob. negative"
          value={p.prob_negative != null ? `${(p.prob_negative * 100).toFixed(0)}%` : "—"}
        />
        <Stat
          label="Confidence"
          value={p.confidence != null ? `${(p.confidence * 100).toFixed(0)}%` : "—"}
        />
        <Stat
          label="Horizon"
          value={p.horizon}
        />
      </div>

      {p.expected_return_median != null && (
        <div className="text-xs text-ink-soft">
          Expected {p.horizon} return (median):{" "}
          <span className="mono text-ink">
            {(p.expected_return_median * 100).toFixed(2)}%
          </span>
          {p.expected_return_lower != null && p.expected_return_upper != null && (
            <>
              {" · band "}
              <span className="mono text-ink">
                [{(p.expected_return_lower * 100).toFixed(2)}%,{" "}
                {(p.expected_return_upper * 100).toFixed(2)}%]
              </span>
            </>
          )}
        </div>
      )}

      {p.positive_contributors.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-faint mb-1">
            Positive contributors
          </p>
          <ul className="grid gap-1 text-xs">
            {p.positive_contributors.slice(0, 5).map((c) => (
              <li key={c.feature} className="flex items-baseline justify-between">
                <span className="mono">{c.feature}</span>
                <span className="text-pos mono">
                  {c.contribution >= 0 ? "+" : ""}
                  {c.contribution.toFixed(3)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {p.negative_contributors.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-faint mb-1">
            Negative contributors
          </p>
          <ul className="grid gap-1 text-xs">
            {p.negative_contributors.slice(0, 5).map((c) => (
              <li key={c.feature} className="flex items-baseline justify-between">
                <span className="mono">{c.feature}</span>
                <span className="text-neg mono">{c.contribution.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {p.warnings.length > 0 && (
        <ul className="grid gap-1 text-xs text-warn">
          {p.warnings.map((w) => <li key={w}>⚠️ {w}</li>)}
        </ul>
      )}

      <div className="text-[10px] text-ink-faint border-t border-canvas-border pt-2">
        as of <span className="mono text-ink">{new Date(p.as_of).toLocaleString()}</span>
        {" · model "}<span className="mono text-ink">{p.model_version}</span>
        {" · data "}<span className="mono text-ink">{p.data_version}</span>
      </div>
      <p className="text-[10px] italic text-ink-faint">{p.disclaimer}</p>
    </div>
  );
}

function ShadowBadge() {
  return (
    <span className="inline-block text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-full bg-warn-soft text-warn self-start">
      SHADOW · does not influence signal
    </span>
  );
}

function Stat({
  label, value, tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neutral";
}) {
  const color =
    tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-ink";
  return (
    <div>
      <p className="text-[10px] text-ink-faint">{label}</p>
      <p className={`font-semibold mono ${color}`}>{value}</p>
    </div>
  );
}
