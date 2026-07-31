import "./globals.css";
import type { Metadata } from "next";
import AppProviders from "./providers";
import { TopNav } from "@/components/TopNav";
import { Disclaimer } from "@/components/Disclaimer";

export const metadata: Metadata = {
  title: "DEMO-TRADE",
  description: "Multi-market investment research and trading-signal platform (research/educational use)."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <AppProviders>
          <TopNav />
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
          <Disclaimer />
        </AppProviders>
      </body>
    </html>
  );
}
