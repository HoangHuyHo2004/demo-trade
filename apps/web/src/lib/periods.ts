import type { BarInterval } from "@demo-trade/contracts";

export type PeriodKey = "1D" | "1W" | "1M" | "3M" | "6M" | "1Y" | "5Y" | "MAX";

export interface PeriodDef {
  key: PeriodKey;
  label: string;
  lookbackDays: number;
  interval: BarInterval;
}

export const PERIODS: PeriodDef[] = [
  { key: "1D",  label: "1D",  lookbackDays: 2,    interval: "1h" },
  { key: "1W",  label: "1W",  lookbackDays: 7,    interval: "1h" },
  { key: "1M",  label: "1M",  lookbackDays: 31,   interval: "1d" },
  { key: "3M",  label: "3M",  lookbackDays: 92,   interval: "1d" },
  { key: "6M",  label: "6M",  lookbackDays: 183,  interval: "1d" },
  { key: "1Y",  label: "1Y",  lookbackDays: 365,  interval: "1d" },
  { key: "5Y",  label: "5Y",  lookbackDays: 1825, interval: "1w" },
  { key: "MAX", label: "MAX", lookbackDays: 3650, interval: "1w" }
];

export function periodByKey(k: PeriodKey): PeriodDef {
  return PERIODS.find((p) => p.key === k) ?? PERIODS[3];
}

/** Simple point-to-point return between first and last close. */
export function periodReturn(closes: number[]): number | null {
  if (closes.length < 2) return null;
  const first = closes[0];
  const last = closes[closes.length - 1];
  if (!first) return null;
  return (last - first) / first;
}
