"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { IconArrowUpRight, IconPlus, IconSearch } from "./Icons";

interface Props {
  userName?: string | null;
  title?: string;   // override "Welcome back, {name}" for non-dashboard pages
  subtitle?: string;
}

export function AppHeader({ userName, title, subtitle }: Props) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const displayName = userName?.split("@")[0] || "Demo";
  const headline = title ?? `Welcome back, ${displayName}`;

  return (
    <header className="flex items-center justify-between gap-4 flex-wrap py-2">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{headline}</h1>
        {subtitle && (
          <p className="text-sm text-ink-soft mt-1">{subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
          }}
          className="relative"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search assets…"
            aria-label="Search assets"
            className="h-9 w-56 pl-9 pr-3 rounded-lg border border-canvas-border bg-white text-sm placeholder:text-ink-faint"
          />
          <IconSearch className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" width={16} height={16} />
        </form>
        <button
          onClick={() => router.push("/research")}
          className="h-9 px-3 rounded-lg bg-brand text-white text-sm font-medium flex items-center gap-1.5 hover:brightness-105"
        >
          <IconArrowUpRight width={16} height={16} />
          <span>New research</span>
        </button>
        <button
          onClick={() => router.push("/watchlist")}
          className="h-9 px-3 rounded-lg bg-white border border-canvas-border text-sm text-ink hover:bg-canvas-hover flex items-center gap-1.5"
        >
          <IconPlus width={16} height={16} />
          <span>Add asset</span>
        </button>
      </div>
    </header>
  );
}
