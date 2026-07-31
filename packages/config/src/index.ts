export interface RuntimeConfig {
  apiBaseUrl: string;
  appName: string;
  defaultLocale: "en" | "vi";
}

export function readRuntimeConfig(env: Record<string, string | undefined>): RuntimeConfig {
  return {
    apiBaseUrl: env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
    appName: env.NEXT_PUBLIC_APP_NAME ?? "DEMO-TRADE",
    defaultLocale: (env.NEXT_PUBLIC_DEFAULT_LOCALE as "en" | "vi") ?? "en",
  };
}
