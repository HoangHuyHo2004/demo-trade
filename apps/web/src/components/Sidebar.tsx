"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, SVGProps } from "react";
import {
  IconAward,
  IconBell,
  IconCalc,
  IconCalendar,
  IconChevronDown,
  IconChevronRight,
  IconGrid,
  IconLine,
  IconList,
  IconLogo,
  IconNews,
  IconPercent,
  IconTrophy,
  IconWallet
} from "./Icons";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

const MENU: { href: string; label: string; icon: Icon }[] = [
  { href: "/",         label: "Dashboard",   icon: IconGrid },
  { href: "/watchlist", label: "Watchlist",  icon: IconWallet },
  { href: "/portfolio", label: "Portfolio",  icon: IconAward },
  { href: "/lab",       label: "Signal Lab", icon: IconTrophy },
  { href: "/compare",   label: "Compare",    icon: IconList }
];

const APPS: { href: string; label: string; icon: Icon }[] = [
  { href: "/research", label: "Research chat", icon: IconNews },
  { href: "/search",   label: "Asset search",  icon: IconCalendar },
  { href: "/settings", label: "Settings",      icon: IconCalc }
];

// Silence unused-import lint
export const _iconsUsed = [IconLine, IconPercent];

export function Sidebar({ userEmail }: { userEmail?: string | null }) {
  const pathname = usePathname() || "/";

  return (
    <aside className="w-64 shrink-0 h-screen sticky top-0 p-4 hidden md:flex flex-col gap-4">
      <div className="bg-white rounded-card shadow-card border border-canvas-border p-4">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <IconLogo />
            <span className="font-semibold tracking-tight text-ink">DEMO-TRADE</span>
          </div>
          <IconChevronRight className="text-ink-faint" />
        </div>

        <SectionLabel>Menu</SectionLabel>
        <NavGroup items={MENU} pathname={pathname} />

        <SectionLabel className="mt-6">Apps</SectionLabel>
        <NavGroup items={APPS} pathname={pathname} />
      </div>

      <div className="bg-white rounded-card shadow-card border border-canvas-border p-4 text-sm">
        <Row label="Account" value="demo-1" />
        <Row label="Status" value={<StatusDot label="Active" />} />
        <Row label="Program" value={<span className="text-ink-soft">Research MVP</span>} />
      </div>

      <div className="mt-auto bg-white rounded-card shadow-card border border-canvas-border p-3 flex items-center gap-3">
        <div className="h-9 w-9 rounded-full bg-brand-soft flex items-center justify-center text-brand font-semibold">
          {(userEmail ?? "D").slice(0, 1).toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">Demo User</p>
          <p className="text-xs text-ink-faint truncate">{userEmail || "demo@demo-trade.local"}</p>
        </div>
        <IconChevronDown className="ml-auto text-ink-faint shrink-0" />
      </div>
    </aside>
  );
}

function NavGroup({
  items, pathname
}: {
  items: readonly { href: string; label: string; icon: Icon }[];
  pathname: string;
}) {
  return (
    <ul className="grid gap-1">
      {items.map((it) => {
        const active =
          it.href === "/"
            ? pathname === "/"
            : pathname.startsWith(it.href);
        return (
          <li key={it.href}>
            <Link
              href={it.href}
              className={
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition " +
                (active
                  ? "bg-brand text-white font-medium"
                  : "text-ink-soft hover:bg-canvas hover:text-ink")
              }
            >
              <it.icon />
              <span>{it.label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function SectionLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`text-[10px] font-semibold uppercase tracking-widest text-ink-faint mb-2 ${className}`}>
      {children}
    </p>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1.5 first:pt-0 last:pb-0 border-b border-canvas-border last:border-none">
      <span className="text-xs text-ink-faint">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

function StatusDot({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2 w-2 rounded-full bg-pos" />
      <span>{label}</span>
    </span>
  );
}

// silence unused-import checks
export { IconBell };
