"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { PortfolioSummaryView } from "@/components/PortfolioSummaryView";
import { PortfolioRiskView } from "@/components/PortfolioRiskView";
import { TransactionForm } from "@/components/TransactionForm";

export default function PortfolioPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["portfolios"], queryFn: api.listPortfolios });
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    if (selectedId == null && list.data && list.data.length > 0) {
      setSelectedId(list.data[0].id);
    }
  }, [list.data, selectedId]);

  const detail = useQuery({
    queryKey: ["portfolio", selectedId],
    queryFn: () => api.getPortfolio(selectedId!),
    enabled: selectedId != null
  });
  const risk = useQuery({
    queryKey: ["portfolio-risk", selectedId],
    queryFn: () => api.getPortfolioRisk(selectedId!, 180),
    enabled: selectedId != null
  });

  const [newName, setNewName] = useState("");
  const create = useMutation({
    mutationFn: () => api.createPortfolio(newName || "Main", "USD"),
    onSuccess: (p) => {
      setNewName("");
      qc.invalidateQueries({ queryKey: ["portfolios"] });
      setSelectedId(p.id);
    }
  });

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Paper portfolio</h1>
      <p className="text-xs text-slate-500">
        Manual transaction entry only — no broker connection, no real orders.
        Positions and P&L are computed from the transaction log using
        weighted-average cost.
      </p>

      <Card>
        {list.isPending && <p className="text-sm text-slate-500">Loading…</p>}
        <div className="flex items-center gap-2 flex-wrap">
          {list.data?.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelectedId(p.id)}
              className={`text-sm px-3 py-1 rounded-full border ${
                p.id === selectedId
                  ? "border-blue-500 text-blue-600 dark:text-blue-400"
                  : "border-slate-300 dark:border-slate-700"
              }`}
            >
              {p.name}
              <span className="text-slate-500 ml-1">({p.base_currency})</span>
            </button>
          ))}
          <span className="ml-4 flex items-center gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="new portfolio name"
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1 text-sm"
            />
            <button
              onClick={() => create.mutate()}
              disabled={create.isPending}
              className="text-xs px-3 py-1 rounded border border-blue-500 text-blue-600 dark:text-blue-400"
            >
              Create
            </button>
          </span>
        </div>
      </Card>

      {selectedId != null && detail.data && (
        <>
          <Card title="Overview">
            <PortfolioSummaryView detail={detail.data} />
          </Card>

          <Card title="Add transaction">
            <TransactionForm
              portfolioId={selectedId}
              baseCurrency={detail.data.base_currency}
              onSuccess={() => {
                qc.invalidateQueries({ queryKey: ["portfolio", selectedId] });
                qc.invalidateQueries({ queryKey: ["portfolio-risk", selectedId] });
              }}
            />
          </Card>

          <Card title="Risk">
            {risk.isPending && <p className="text-sm text-slate-500">Computing…</p>}
            {risk.error && (
              <p className="text-sm text-red-500">
                Risk computation failed: {(risk.error as Error).message}
              </p>
            )}
            {risk.data && <PortfolioRiskView risk={risk.data} />}
          </Card>
        </>
      )}
    </div>
  );
}
