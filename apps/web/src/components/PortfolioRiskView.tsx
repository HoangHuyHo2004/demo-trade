import type { PortfolioRisk } from "@demo-trade/contracts";

export function PortfolioRiskView({ risk }: { risk: PortfolioRisk }) {
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <Stat label="Equity" value={num(risk.total_equity_base)} />
        <Stat label="Holdings" value={String(risk.n_holdings)} />
        <Stat
          label="Concentration (HHI)"
          value={risk.hhi_asset.toFixed(3)}
          hint={
            risk.hhi_asset > 0.5
              ? "very concentrated"
              : risk.hhi_asset > 0.25
              ? "moderately concentrated"
              : "diversified"
          }
        />
        <Stat
          label="Top holding"
          value={pct(risk.top_holding_weight)}
          hint={risk.top_holding_weight > 0.4 ? "concentrated" : ""}
        />
        <Stat label="Cash weight" value={pct(risk.cash_weight)} />
        <Stat
          label="Vol (annualized)"
          value={risk.volatility_annualized != null ? pct(risk.volatility_annualized) : "—"}
        />
        <Stat
          label="Max drawdown"
          value={risk.max_drawdown != null ? pct(risk.max_drawdown) : "—"}
          hint={risk.max_drawdown != null && risk.max_drawdown > 0.3 ? "large" : ""}
        />
        <Stat
          label="VaR 95% (1d)"
          value={risk.var_95_1d != null ? pct(risk.var_95_1d) : "—"}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
            Allocation by asset
          </p>
          <ul className="grid gap-1 text-xs">
            {Object.entries(risk.allocation_by_asset)
              .sort((a, b) => b[1] - a[1])
              .map(([cid, w]) => (
                <li key={cid} className="grid grid-cols-[1fr_60px_80px] items-center gap-2">
                  <span className="mono truncate">{cid}</span>
                  <div className="h-2 bg-slate-200/60 dark:bg-slate-800 rounded overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${Math.min(100, w * 100).toFixed(1)}%` }}
                    />
                  </div>
                  <span className="text-right mono">{pct(w)}</span>
                </li>
              ))}
          </ul>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
            Allocation by market
          </p>
          <ul className="grid gap-1 text-xs">
            {Object.entries(risk.allocation_by_market)
              .sort((a, b) => b[1] - a[1])
              .map(([m, w]) => (
                <li key={m} className="grid grid-cols-[1fr_60px_80px] items-center gap-2">
                  <span className="font-medium">{m}</span>
                  <div className="h-2 bg-slate-200/60 dark:bg-slate-800 rounded overflow-hidden">
                    <div
                      className="h-full bg-emerald-500"
                      style={{ width: `${Math.min(100, w * 100).toFixed(1)}%` }}
                    />
                  </div>
                  <span className="text-right mono">{pct(w)}</span>
                </li>
              ))}
          </ul>
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
          Stress scenarios (informational)
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          {Object.entries(risk.stress_scenarios).map(([label, pnl]) => (
            <div key={label}>
              <p className="text-xs text-slate-500">{label}</p>
              <p className={`mono font-medium ${pnl < 0 ? "text-red-600 dark:text-red-400" : ""}`}>
                {pct(pnl)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {risk.warnings.length > 0 && (
        <div className="text-xs text-amber-600 dark:text-amber-400">
          {risk.warnings.map((w, i) => (
            <p key={i}>⚠️ {w}</p>
          ))}
        </div>
      )}

      <p className="text-[10px] italic text-slate-500">
        Risk metrics are informational estimates from historical bar returns
        weighted by current allocation. VaR is historical (percentile-based),
        not a guarantee. Stress scenarios assume a uniform shock to risk
        assets with cash unchanged.
      </p>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-medium mono">{value}</p>
      {hint && <p className="text-[10px] text-slate-400">{hint}</p>}
    </div>
  );
}

function pct(x: number): string {
  if (!Number.isFinite(x)) return "—";
  return `${(x * 100).toFixed(2)}%`;
}

function num(x: number): string {
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
