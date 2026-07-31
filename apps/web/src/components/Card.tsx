import type { ReactNode } from "react";

interface Props {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}

export function Card({
  title, subtitle, actions, children, className = "", padded = true
}: Props) {
  return (
    <section
      className={
        "bg-white rounded-card shadow-card border border-canvas-border " +
        (padded ? "p-5 " : "") + className
      }
    >
      {(title || actions) && (
        <header className="flex items-start justify-between mb-3">
          <div>
            {title && (
              <h2 className="text-sm font-semibold text-ink tracking-tight">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-xs text-ink-faint mt-0.5">{subtitle}</p>
            )}
          </div>
          {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
