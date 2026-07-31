import type { ResearchResponse } from "@demo-trade/contracts";

function List({ title, items, tone = "default" }: {
  title: string;
  items: string[];
  tone?: "bull" | "bear" | "warn" | "default";
}) {
  if (!items.length) return null;
  const color =
    tone === "bull"
      ? "text-emerald-700 dark:text-emerald-300"
      : tone === "bear"
      ? "text-red-700 dark:text-red-300"
      : tone === "warn"
      ? "text-amber-700 dark:text-amber-300"
      : "text-slate-700 dark:text-slate-200";
  return (
    <div className="grid gap-1">
      <p className={`text-xs font-semibold uppercase tracking-wide ${color}`}>{title}</p>
      <ul className="list-disc ml-4 grid gap-0.5 text-sm">
        {items.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    </div>
  );
}

export function ResearchResponseView({ response }: { response: ResearchResponse }) {
  return (
    <div className="grid gap-4">
      {response.abstained && (
        <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium text-amber-700 dark:text-amber-300">
            Agent abstained
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
            Reason: {response.abstention_reason || "unspecified"}
          </p>
        </div>
      )}

      <div>
        <p className="text-sm">{response.executive_summary}</p>
      </div>

      {response.signal_summary && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
            Signal summary (quantitative)
          </p>
          <p className="text-sm">{response.signal_summary}</p>
        </div>
      )}

      {response.current_trend && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
            Current trend
          </p>
          <p className="text-sm">{response.current_trend}</p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <List title="Bull case" items={response.bull_case} tone="bull" />
        <List title="Bear case" items={response.bear_case} tone="bear" />
      </div>

      <List title="Key risks" items={response.key_risks} tone="warn" />
      <List title="Upcoming catalysts" items={response.upcoming_catalysts} />
      <List
        title="Data-quality warnings"
        items={response.data_quality_warnings}
        tone="warn"
      />

      <div className="grid gap-4 md:grid-cols-2">
        <List title="Verified facts" items={response.verified_facts} />
        <List title="Model interpretation" items={response.interpretation} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <List title="Assumptions" items={response.assumptions} />
        <List title="Unknowns / not verified" items={response.unknowns} tone="warn" />
      </div>

      <List title="Suggested next questions" items={response.suggested_questions} />

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
          Citations
        </p>
        {response.citations.length === 0 ? (
          <p className="text-xs text-red-600 dark:text-red-400">
            No citations — treat every statement above as unverified.
          </p>
        ) : (
          <ul className="grid gap-1 text-xs">
            {response.citations.map((c, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2">
                <span
                  className={`px-1.5 py-0.5 rounded border text-[10px] uppercase ${
                    c.kind === "quantitative"
                      ? "border-blue-500/30 text-blue-700 dark:text-blue-300"
                      : c.kind === "system"
                      ? "border-slate-500/30 text-slate-500"
                      : "border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                  }`}
                >
                  {c.kind}
                </span>
                <span className="font-medium">{c.title}</span>
                <span className="text-slate-500">— {c.publisher}</span>
                {c.url && (
                  <a
                    href={c.url}
                    className="text-blue-600 dark:text-blue-400 hover:underline"
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    ↗
                  </a>
                )}
                {c.published_at && (
                  <span className="text-slate-500">
                    · {new Date(c.published_at).toLocaleString()}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-[10px] italic text-slate-500 border-t border-slate-100 dark:border-slate-800 pt-2">
        Educational / research use only. Not investment advice. Signals are
        model output, not recommendations. Past performance does not indicate
        future results.
      </p>
    </div>
  );
}
