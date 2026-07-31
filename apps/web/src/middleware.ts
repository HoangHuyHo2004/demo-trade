/**
 * Route-protection middleware.
 *
 * The API (`services/api/app/deps.py::get_current_user`) is the real
 * auth enforcer for every state-changing request — it verifies the
 * HS256 session JWT with PyJWT on every call. This middleware is a UX
 * gate: it prevents anonymous users from seeing pages that would just
 * flash then redirect. It intentionally does NOT re-verify the JWT
 * (Auth.js v5's built-in verifier is stricter than our shared cookie
 * format needs). Presence of the session cookie is enough here; the
 * API will 401 if the JWT is stale or forged.
 */
import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME =
  process.env.AUTH_COOKIE_NAME || "demo-trade.session";

const PUBLIC_PREFIXES = [
  "/signin",
  "/api/auth",
  "/_next",
  "/favicon",
  "/robots"
];

export default function middleware(req: NextRequest) {
  const pathname = req.nextUrl.pathname;
  if (
    PUBLIC_PREFIXES.some(
      (p) =>
        pathname === p ||
        pathname.startsWith(p + "/") ||
        pathname.startsWith(p)
    )
  ) {
    return NextResponse.next();
  }
  const hasSession = req.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (!hasSession) {
    const url = new URL("/signin", req.nextUrl);
    url.searchParams.set("callbackUrl", req.nextUrl.pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|webp|ico|gif|css|js|map)$).*)"
  ]
};
