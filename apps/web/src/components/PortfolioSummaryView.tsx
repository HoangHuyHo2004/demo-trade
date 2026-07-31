import Link from "next/link";
import type { PortfolioDetail } from "@demo-trade/contracts";

export function PortfolioSummaryView({ detail }: { detail: PortfolioDetail }) {
  const equity = Number(detail.equity_base);
  const cash = Number(detail.cash_base);
  const positions = Number(detail.positions_value_base);
  const unrealized = Number(detail.unrealized_pnl_base);
  const realized = Number(detail.realized_pnl_base);

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <Stat label="Equity" value={fmt(equity, detail.base_currency)} accent={0} />
        <Stat label="Cash" value={fmt(cash, detail.base_currency)} />
        <Stat label="Positions" value={fmt(positions, detail.base_currency)} />
        <Stat
          label="Unrealized P&L"
          value={fmt(unrealized, detail.base_currency)}
          accent={unrealized}
        />
        <Stat label="Realized P&L" value={fmt(realized, detail.base_currency)} accent={realized} />
        <div>
          <p className="text-xs text-slate-500">Cash by currency</p>
          <p className="text-xs font-medium mono">
            {Object.entries(detail.cash_by_currency)
              .map(([c, a]) => `${Number(a).toFixed(2)} ${c}`)
              .join(" · ") || "—"}
          </p>
        </div>
      </div>

      {detail.warnings.length > 0 && (
        <div className="text-xs text-amber-600 dark:text-amber-400">
          {detail.warnings.map((w, i) => (
            <p key={i}>⚠️ {w}</p>
          ))}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="py-1 pr-4">Asset</th>
              <th className="py-1 pr-4">Market</th>
              <th className="py-1 pr-4 text-right">Qty</th>
              <th className="py-1 pr-4 text-right">Avg cost</th>
              <th className="py-1 pr-4 text-right">Last</th>
              <th className="py-1 pr-4 text-right">MV (base)</th>
              <th className="py-1 pr-4 text-right">Unrealized</th>
              <th className="py-1 pr-4 text-right">Realized</th>
            </tr>
          </thead>
          <tbody>
            {detail.positions.map((p) => {
              const un = p.unrealized_pnl_base == null ? null : Number(p.unrealized_pnl_base);
              const rl = Number(p.realized_pnl_ccy);
              return (
                <tr
                  key={p.asset_canonical_id}
                  className="border-t border-slate-100 dark:border-slate-800"
                >
                  <td className="py-1 pr-4 mono">
                    <Link
                      className="hover:underline"
                      href={`/assets/${encodeURIComponent(p.asset_canonical_id)}`}
                    >
                      {p.display_symbol}
                    </Link>
                    <span className="text-slate-500 ml-2 text-xs">{p.quote_currency}</span>
                  </td>
                  <td className="py-1 pr-4 text-slate-500">{p.market}</td>
                  <td className="py-1 pr-4 text-right mono">{Number(p.quantity).toFixed(4)}</td>
                  <td className="py-1 pr-4 text-right mono">{Number(p.avg_cost).toFixed(2)}</td>
                  <td className="py-1 pr-4 text-right mono">
                    {p.last_price ? Number(p.last_price).toFixed(2) : "—"}
                  </td>
                  <td className="py-1 pr-4 text-right mono">
                    {p.market_value_base ? Number(p.market_value_base).toFixed(2) : "—"}
                  </td>
                  <td
                    className={`py-1 pr-4 text-right mono ${
                      un == null
                        ? "text-slate-400"
                        : un >= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    {un == null ? "—" : fmt(un, detail.base_currency)}
                  </td>
                  <td
                    className={`py-1 pr-4 text-right mono ${
                      rl >= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    {Number(rl).toFixed(2)} {p.quote_currency}
                  </td>
                </tr>
              );
            })}
            {detail.positions.length === 0 && (
              <tr>
                <td colSpan={8} className="text-sm text-slate-500 py-2">
                  No positions yet. Add a DEPOSIT then a BUY below.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-500">
        As of <span className="mono">{new Date(detail.as_of).toLocaleString()}</span>.
        FX rates used: {Object.entries(detail.fx_used).map(([k, v]) => `${k}=${Number(v).toFixed(4)}`).join(", ") || "—"}
      </p>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: number }) {
  const color =
    accent == null
      ? "text-slate-700 dark:text-slate-200"
      : accent >= 0
      ? "text-emerald-600 dark:text-emerald-400"
      : "text-red-600 dark:text-red-400";
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`font-medium mono ${color}`}>{value}</p>
    </div>
  );
}

function fmt(x: number, ccy: string): string {
  if (!Number.isFinite(x)) return "—";
  return `${x.toFixed(2)} ${ccy}`;
}
