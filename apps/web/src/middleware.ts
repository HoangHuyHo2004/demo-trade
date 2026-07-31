/**
 * Route protection middleware.
 *
 * Unauthenticated users are redirected to /signin, except for public
 * paths (marketing pages, auth handlers, Next.js internals).
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const PUBLIC_PREFIXES = ["/signin", "/api/auth", "/_next", "/favicon", "/robots"];

export default auth((req) => {
  const { nextUrl } = req;
  const pathname = nextUrl.pathname;
  if (PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/") || pathname.startsWith(p))) {
    return NextResponse.next();
  }
  if (!req.auth) {
    const url = new URL("/signin", nextUrl);
    url.searchParams.set("callbackUrl", nextUrl.pathname + nextUrl.search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
});

export const config = {
  matcher: [
    // Match every path except explicit static assets. next-auth handlers are
    // filtered inside the callback so their POST bodies aren't consumed here.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|webp|ico|gif|css|js|map)$).*)"
  ]
};
