"use client";

import { useState } from "react";

/**
 * Demo-login button (client component).
 *
 * Posts to the API's /api/v1/auth/demo-login endpoint (which sets the
 * shared HS256 session cookie), then reloads at the callback URL so
 * the middleware sees the cookie and lets the user through.
 */
export function DemoLoginButton({ callbackUrl }: { callbackUrl: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function go() {
    setPending(true);
    setError(null);
    try {
      const base =
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const r = await fetch(`${base}/api/v1/auth/demo-login`, {
        method: "POST",
        credentials: "include"
      });
      if (!r.ok) throw new Error(`API returned ${r.status}`);
      window.location.href = callbackUrl;
    } catch (e) {
      setError((e as Error).message);
      setPending(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={go}
        disabled={pending}
        className="w-full text-sm px-4 py-2 rounded border border-blue-500 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950 disabled:opacity-50"
      >
        {pending ? "Signing in…" : "Continue as demo user"}
      </button>
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      <p className="text-[10px] text-slate-500 mt-1">
        Demo login is only available when the API is running with
        DEMO_MODE=true.
      </p>
    </div>
  );
}
