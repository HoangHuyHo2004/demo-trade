import type { ReactNode } from "react";

type Tone = "neutral" | "pos" | "neg" | "warn";

interface Props {
  icon?: ReactNode;
  label: string;
  value: string | number;
  hint?: string;
  tone?: Tone;
  hintTone?: Tone;
}

const HINT_STYLES: Record<Tone, string> = {
  neutral: "bg-canvas text-ink-soft",
  pos: "bg-pos-soft text-pos",
  neg: "bg-neg-soft text-neg",
  warn: "bg-warn-soft text-warn"
};

const ICON_BG: Record<Tone, string> = {
  neutral: "bg-canvas text-ink-soft",
  pos: "bg-pos-soft text-pos",
  neg: "bg-neg-soft text-neg",
  warn: "bg-warn-soft text-warn"
};

export function StatCard({
  icon, label, value, hint, tone = "neutral", hintTone
}: Props) {
  return (
    <section className="bg-white rounded-card shadow-card border border-canvas-border p-4">
      <div className="flex items-center gap-3">
        {icon && (
          <div className={`h-9 w-9 rounded-lg flex items-center justify-center ${ICON_BG[tone]}`}>
            {icon}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-xs text-ink-faint">{label}</p>
          <p className="text-lg font-semibold mono truncate">{value}</p>
        </div>
        {hint && (
          <span
            className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${HINT_STYLES[hintTone ?? tone]}`}
          >
            {hint}
          </span>
        )}
      </div>
    </section>
  );
}
