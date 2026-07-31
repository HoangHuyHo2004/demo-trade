import Link from "next/link";

export function TopNav() {
  return (
    <header className="border-b border-slate-200 dark:border-slate-800">
      <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
        <Link href="/" className="font-semibold tracking-tight">
          DEMO-TRADE
        </Link>
        <nav className="flex gap-4 text-sm">
          <Link href="/" className="hover:underline">Dashboard</Link>
          <Link href="/watchlist" className="hover:underline">Watchlist</Link>
          <Link href="/search" className="hover:underline">Search</Link>
        </nav>
      </div>
    </header>
  );
}
