import "./globals.css";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import AppProviders from "./providers";
import { Sidebar } from "@/components/Sidebar";
import { Disclaimer } from "@/components/Disclaimer";

export const metadata: Metadata = {
  title: "DEMO-TRADE",
  description:
    "Multi-market investment research and trading-signal platform (research/educational use)."
};

export default async function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  const cookieName = process.env.AUTH_COOKIE_NAME || "demo-trade.session";
  const store = await cookies();
  const signedIn = Boolean(store.get(cookieName)?.value);

  return (
    <html lang="en">
      <body className="min-h-screen antialiased bg-canvas text-ink">
        <AppProviders>
          {signedIn ? (
            <div className="flex min-h-screen">
              <Sidebar userEmail="demo@demo-trade.local" />
              <main className="flex-1 min-w-0 p-4 md:p-6">
                {children}
                <Disclaimer />
              </main>
            </div>
          ) : (
            <main className="mx-auto max-w-6xl px-4 py-6">
              {children}
              <Disclaimer />
            </main>
          )}
        </AppProviders>
      </body>
    </html>
  );
}
