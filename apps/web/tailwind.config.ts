import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0b0d10",
          soft: "#12161b",
          border: "#1f2933"
        },
        ink: {
          DEFAULT: "#e6e8ec",
          soft: "#a3adbb",
          faint: "#5c6675"
        },
        accent: {
          DEFAULT: "#4f8cff",
          up: "#22c55e",
          down: "#ef4444",
          warn: "#f59e0b"
        }
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"]
      }
    }
  },
  plugins: []
};

export default config;
