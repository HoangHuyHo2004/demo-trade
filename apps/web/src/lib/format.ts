export function fmtNumber(x: number | string, digits = 2, currency?: string): string {
  const n = typeof x === "string" ? Number(x) : x;
  if (!Number.isFinite(n)) return "—";
  const s = n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
  return currency ? `${s} ${currency}` : s;
}

export function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function ageString(iso: string, nowMs = Date.now()): string {
  const t = new Date(iso).getTime();
  const s = Math.max(0, Math.floor((nowMs - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
