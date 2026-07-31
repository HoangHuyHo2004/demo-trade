"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const results = useQuery({
    queryKey: ["assets-search", q],
    queryFn: () => api.searchAssets(q),
    enabled: q.length >= 1
  });

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Search</h1>
      <Card>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search assets across US / VN / crypto"
          className="w-full border border-slate-300 dark:border-slate-700 bg-transparent rounded px-3 py-2 text-sm"
        />
        <ul className="mt-4 grid gap-1">
          {results.data?.map((a) => (
            <li key={a.canonical_id} className="flex justify-between text-sm py-1">
              <Link href={`/assets/${encodeURIComponent(a.canonical_id)}`} className="hover:underline">
                <span className="mono font-medium">{a.display_symbol}</span>
                <span className="text-slate-500 ml-2">{a.name}</span>
              </Link>
              <span className="text-slate-400 text-xs">{a.canonical_id}</span>
            </li>
          ))}
          {results.data && results.data.length === 0 && q && (
            <li className="text-sm text-slate-500">No matches. Symbols may collide across markets — try refining by market.</li>
          )}
        </ul>
      </Card>
    </div>
  );
}
