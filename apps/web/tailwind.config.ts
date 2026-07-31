import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Neutral canvas — soft off-white, no cold gray.
        canvas: {
          DEFAULT: "#f4f6fa",   // page background
          card: "#ffffff",      // card background
          border: "#e6e8ee",    // hairline border
          hover: "#eef1f6"      // hover fill
        },
        // Text
        ink: {
          DEFAULT: "#0f172a",
          soft: "#64748b",
          faint: "#94a3b8",
          invert: "#ffffff"
        },
        // Brand primary + supporting
        brand: {
          DEFAULT: "#2563eb",   // main blue
          soft: "#eff4ff",      // active-nav fill
          ring: "#3b82f680"
        },
        // Signal / P&L
        pos: {
          DEFAULT: "#10b981",
          soft: "#d1fae5"
        },
        neg: {
          DEFAULT: "#ef4444",
          soft: "#fee2e2"
        },
        warn: {
          DEFAULT: "#f59e0b",
          soft: "#fef3c7"
        },
        // Chart series
        series: {
          balance: "#2563eb",
          equity: "#f97316"
        }
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif"
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"]
      },
      borderRadius: {
        card: "16px",
        pill: "9999px"
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.02)",
        hover: "0 2px 8px rgba(15, 23, 42, 0.06)"
      }
    }
  },
  plugins: []
};

export default config;
