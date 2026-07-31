"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type { TxKind } from "@demo-trade/contracts";

const KINDS: { value: TxKind; label: string; needsAsset: boolean; needsPrice: boolean }[] = [
  { value: "DEPOSIT", label: "Deposit cash", needsAsset: false, needsPrice: false },
  { value: "WITHDRAW", label: "Withdraw cash", needsAsset: false, needsPrice: false },
  { value: "BUY", label: "Buy asset", needsAsset: true, needsPrice: true },
  { value: "SELL", label: "Sell asset", needsAsset: true, needsPrice: true },
  { value: "DIVIDEND", label: "Dividend received", needsAsset: true, needsPrice: false },
  { value: "FEE", label: "Fee", needsAsset: false, needsPrice: false }
];

interface Props {
  portfolioId: number;
  baseCurrency: string;
  onSuccess?: () => void;
}

export function TransactionForm({ portfolioId, baseCurrency, onSuccess }: Props) {
  const [kind, setKind] = useState<TxKind>("DEPOSIT");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState(baseCurrency);
  const [fee, setFee] = useState("0");
  const [assetQuery, setAssetQuery] = useState("");
  const [selectedAsset, setSelectedAsset] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const meta = KINDS.find((k) => k.value === kind)!;

  const search = useQuery({
    queryKey: ["assets-search", assetQuery],
    queryFn: () => api.searchAssets(assetQuery),
    enabled: meta.needsAsset && assetQuery.length >= 1
  });

  const submit = useMutation({
    mutationFn: () =>
      api.addTransaction(portfolioId, {
        kind,
        asset_canonical_id: meta.needsAsset ? selectedAsset : null,
        quantity,
        price: meta.needsPrice ? price : "0",
        currency,
        fee,
        note
      }),
    onSuccess: () => {
      setQuantity("");
      setPrice("");
      setFee("0");
      setNote("");
      onSuccess?.();
    }
  });

  const canSubmit =
    quantity !== "" &&
    Number(quantity) > 0 &&
    (!meta.needsAsset || !!selectedAsset) &&
    (!meta.needsPrice || Number(price) > 0);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) submit.mutate();
      }}
      className="grid gap-3"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm grid gap-1">
          <span className="text-xs text-slate-500">Kind</span>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as TxKind)}
            className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
          >
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>{k.label}</option>
            ))}
          </select>
        </label>
        <label className="text-sm grid gap-1">
          <span className="text-xs text-slate-500">
            {meta.needsAsset || meta.value === "BUY" || meta.value === "SELL"
              ? "Quantity"
              : "Amount"}
          </span>
          <input
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            type="number" min="0" step="any"
            className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
          />
        </label>
        {meta.needsPrice && (
          <label className="text-sm grid gap-1">
            <span className="text-xs text-slate-500">Price / unit</span>
            <input
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              type="number" min="0" step="any"
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            />
          </label>
        )}
        <label className="text-sm grid gap-1">
          <span className="text-xs text-slate-500">Currency</span>
          <input
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            maxLength={3}
            className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1 mono"
          />
        </label>
        <label className="text-sm grid gap-1">
          <span className="text-xs text-slate-500">Fee</span>
          <input
            value={fee}
            onChange={(e) => setFee(e.target.value)}
            type="number" min="0" step="any"
            className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
          />
        </label>
      </div>

      {meta.needsAsset && (
        <div className="grid gap-1">
          <label className="text-sm">
            <span className="text-xs text-slate-500">Asset</span>
            <input
              value={assetQuery}
              onChange={(e) => {
                setAssetQuery(e.target.value);
                setSelectedAsset(null);
              }}
              placeholder="Search ticker or name (e.g. AAPL, VNM, BTC)"
              className="mt-1 w-full border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            />
          </label>
          {selectedAsset ? (
            <p className="text-xs text-emerald-600 dark:text-emerald-400">
              Selected: <span className="mono">{selectedAsset}</span>{" "}
              <button
                type="button"
                onClick={() => { setSelectedAsset(null); setAssetQuery(""); }}
                className="text-red-500 hover:underline ml-1"
              >
                clear
              </button>
            </p>
          ) : (
            <ul className="grid gap-1 text-xs max-h-40 overflow-auto">
              {search.data?.slice(0, 6).map((a) => (
                <li key={a.canonical_id} className="flex justify-between">
                  <span>
                    <span className="mono font-medium">{a.display_symbol}</span>
                    <span className="text-slate-500 ml-2">{a.name}</span>
                    <span className="text-slate-400 ml-2">{a.canonical_id}</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedAsset(a.canonical_id);
                      setCurrency(a.quote_currency);
                      setAssetQuery(`${a.display_symbol} — ${a.name}`);
                    }}
                    className="text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Pick
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <label className="text-sm grid gap-1">
        <span className="text-xs text-slate-500">Note (optional)</span>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
        />
      </label>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit || submit.isPending}
          className="text-sm px-3 py-1.5 rounded border border-blue-500 text-blue-600 dark:text-blue-400 disabled:opacity-50"
        >
          {submit.isPending ? "Saving…" : "Add transaction"}
        </button>
        {submit.error && (
          <span className="text-xs text-red-500">
            {(submit.error as Error).message}
          </span>
        )}
      </div>
    </form>
  );
}
