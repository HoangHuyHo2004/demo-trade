import en from "@/messages/en.json";
import vi from "@/messages/vi.json";

export type Locale = "en" | "vi";
export type Messages = typeof en;

const catalogs: Record<Locale, Messages> = { en, vi };

export function t(locale: Locale, key: keyof Messages): string {
  return catalogs[locale]?.[key] ?? catalogs.en[key] ?? key;
}
