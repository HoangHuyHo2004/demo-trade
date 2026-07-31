"use client";

interface Props {
  /** ISO time of the underlying event (bar close, trade tick, …). */
  eventTime: string | null | undefined;
  /** ISO time we received it. Optional; if given, we display both. */
  ingestTime?: string | null;
  /** Whether the source considers this stale (e.g., closed session, > 24h old). */
  isStale?: boolean;
  /** Extra label, e.g. provider slug. */
  source?: string;
}

function age(iso: string, nowMs = Date.now()): { text: string; severity: "fresh" | "warn" | "stale" } {
  const t = new Date(iso).getTime();
  const s = Math.max(0, Math.floor((nowMs - t) / 1000));
  const severity: "fresh" | "warn" | "stale" =
    s < 60 * 60 ? "fresh" : s < 60 * 60 * 24 ? "warn" : "stale";
  if (s < 60) return { text: `${s}s ago`, severity };
  if (s < 3600) return { text: `${Math.floor(s / 60)}m ago`, severity };
  if (s < 86_400) return { text: `${Math.floor(s / 3600)}h ago`, severity };
  return { text: `${Math.floor(s / 86_400)}d ago`, severity };
}

const CLR = {
  fresh: "text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
  warn: "text-amber-600 dark:text-amber-400 border-amber-500/30",
  stale: "text-red-600 dark:text-red-400 border-red-500/30"
} as const;

export function FreshnessBadge({ eventTime, ingestTime, isStale, source }: Props) {
  if (!eventTime) {
    return (
      <span className="text-xs px-2 py-0.5 rounded border border-slate-300 dark:border-slate-700 text-slate-500">
        no data
      </span>
    );
  }
  const a = age(eventTime);
  const severity = isStale ? "stale" : a.severity;
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded border ${CLR[severity]}`}
      title={
        `event: ${new Date(eventTime).toLocaleString()}` +
        (ingestTime ? `\ningested: ${new Date(ingestTime).toLocaleString()}` : "") +
        (source ? `\nsource: ${source}` : "")
      }
    >
      {isStale ? "stale · " : ""}
      {a.text}
      {source ? ` · ${source}` : ""}
    </span>
  );
}
