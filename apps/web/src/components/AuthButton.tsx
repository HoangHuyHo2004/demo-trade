import Link from "next/link";
import { cookies } from "next/headers";

/**
 * Presence-of-session UI toggle.
 *
 * We don't decode the JWT here — Auth.js v5's built-in decoder is
 * stricter than our shared HS256 format needs. The API verifies the
 * JWT on every call (see services/api/app/deps.py::get_current_user).
 * All this needs to do is show 'Sign in' vs 'Sign out' correctly.
 */
export async function AuthButton() {
  const cookieName = process.env.AUTH_COOKIE_NAME || "demo-trade.session";
  const store = await cookies();
  const session = store.get(cookieName)?.value;

  if (!session) {
    return (
      <Link
        href="/signin"
        className="text-sm px-3 py-1 rounded border border-blue-500 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950"
      >
        Sign in
      </Link>
    );
  }

  return (
    <form action="/api/auth/signout" method="POST" className="flex items-center gap-2">
      <span className="text-xs text-slate-500 hidden sm:inline">Signed in</span>
      <button
        type="submit"
        className="text-xs px-2 py-1 rounded border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
      >
        Sign out
      </button>
    </form>
  );
}
