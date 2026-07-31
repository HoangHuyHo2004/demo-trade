/**
 * Auth.js v5 configuration.
 *
 * Sessions are HS256-signed JWTs (not the default JWE) so the FastAPI
 * backend can verify them with PyJWT using the same `AUTH_SECRET`.
 *
 * Providers:
 *  - GitHub OAuth — requires `AUTH_GITHUB_ID` / `AUTH_GITHUB_SECRET`.
 *    Silently unavailable if unset.
 *  - Demo credentials — only enabled when `DEMO_MODE=true`. Accepts any
 *    submission and signs the demo user in. Do NOT enable in production.
 */
import NextAuth, { type NextAuthConfig } from "next-auth";
import GitHub from "next-auth/providers/github";
import Credentials from "next-auth/providers/credentials";
import jwt from "jsonwebtoken";

const AUTH_SECRET = process.env.AUTH_SECRET || process.env.API_SECRET_KEY || "";
const AUTH_COOKIE_NAME = process.env.AUTH_COOKIE_NAME || "demo-trade.session";
const DEMO_MODE = (process.env.DEMO_MODE || "").toLowerCase() === "true";
const IS_PROD = (process.env.NODE_ENV || "") === "production";
const MAX_AGE_S = Number(process.env.AUTH_SESSION_MAX_AGE_S || 7 * 24 * 3600);

const providers: NextAuthConfig["providers"] = [];

if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) {
  providers.push(
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET
    })
  );
}

if (DEMO_MODE) {
  providers.push(
    Credentials({
      id: "demo",
      name: "Demo user",
      credentials: {},
      async authorize() {
        return {
          id: "demo@demo-trade.local",
          email: "demo@demo-trade.local",
          name: "Demo User"
        };
      }
    })
  );
}

if (!AUTH_SECRET) {
  // Fail loudly during boot rather than silently issuing unsigned tokens.
  // eslint-disable-next-line no-console
  console.warn("[auth] AUTH_SECRET/API_SECRET_KEY not set — sessions cannot be issued");
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: AUTH_SECRET,
  session: { strategy: "jwt", maxAge: MAX_AGE_S },
  providers,
  cookies: {
    // Give the session cookie the same name the FastAPI middleware reads.
    sessionToken: {
      name: AUTH_COOKIE_NAME,
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: IS_PROD
      }
    }
  },
  jwt: {
    // HS256 signed JWT (NOT the default JWE) so PyJWT on the API side
    // can verify it with the same secret. Keep the claim shape aligned
    // with app.core.auth.SessionClaims.
    async encode({ token, secret, maxAge }) {
      const secretStr = Array.isArray(secret) ? secret[0] : secret;
      const now = Math.floor(Date.now() / 1000);
      const ttl = maxAge ?? MAX_AGE_S;
      const payload = {
        sub: (token?.sub as string) || (token?.email as string) || "unknown",
        email: (token?.email as string) || "",
        name: (token?.name as string) || "",
        provider: (token?.provider as string) || "unknown",
        iat: now,
        exp: now + ttl
      };
      return jwt.sign(payload, secretStr as string, { algorithm: "HS256" });
    },
    async decode({ token, secret }) {
      if (!token) return null;
      const secretStr = Array.isArray(secret) ? secret[0] : secret;
      try {
        const decoded = jwt.verify(token, secretStr as string, {
          algorithms: ["HS256"]
        });
        return typeof decoded === "object" ? (decoded as never) : null;
      } catch {
        return null;
      }
    }
  },
  callbacks: {
    async jwt({ token, account, user }) {
      // Stamp the provider slug into the JWT so the API can distinguish
      // github vs demo vs credentials logins.
      if (account?.provider) token.provider = account.provider;
      if (user?.id) token.sub = user.id;
      return token;
    }
  },
  pages: {
    signIn: "/signin"
  },
  trustHost: true
});
