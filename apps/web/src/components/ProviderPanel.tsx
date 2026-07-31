"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  ok: "text-emerald-600 dark:text-emerald-400",
  degraded: "text-amber-600 dark:text-amber-400",
  down: "text-red-600 dark:text-red-400",
  missing_credentials: "text-slate-500",
  unknown: "text-slate-500"
};

export function ProviderPanel() {
  const q = useQuery({ queryKey: ["providers"], queryFn: api.providersStatus });

  return (
    <div className="grid gap-2 text-sm">
      {q.isPending && <p className="text-slate-500">Loading…</p>}
      {q.error && <p className="text-red-500">Failed to load provider status.</p>}
      {q.data?.map((p) => (
        <div
          key={p.slug}
          className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 py-1.5 last:border-none"
        >
          <div>
            <span className="font-medium mono">{p.slug}</span>
            {p.is_selected_for.length > 0 && (
              <span className="ml-2 text-xs text-slate-500">
                → serving {p.is_selected_for.join(", ")}
              </span>
            )}
          </div>
          <span className={`text-xs ${STATUS_COLOR[p.status] ?? "text-slate-500"}`}>
            {p.status}
          </span>
        </div>
      ))}
    </div>
  );
}
