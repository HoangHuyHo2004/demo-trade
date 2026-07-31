import type { ReactNode } from "react";

export function Card({ title, children, actions }: { title?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/40 p-4">
      {(title || actions) && (
        <header className="mb-3 flex items-center justify-between">
          {title && <h2 className="text-sm font-semibold tracking-tight text-slate-700 dark:text-slate-200">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
