"use client";

import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/Card";
import { ResearchResponseView } from "@/components/ResearchResponseView";

interface Turn {
  role: "user" | "agent";
  prompt?: string;
  response?: Awaited<ReturnType<typeof api.agentChat>>;
}

export default function ResearchPage() {
  const params = useSearchParams();
  const assetId = params.get("asset") ?? "";
  const [input, setInput] = useState(
    assetId ? `Research ${assetId}` : ""
  );
  const [history, setHistory] = useState<Turn[]>([]);

  const send = useMutation({
    mutationFn: async (prompt: string) =>
      api.agentChat({
        prompt,
        asset_canonical_id: assetId || null
      }),
    onSuccess: (data, prompt) => {
      setHistory((h) => [
        ...h,
        { role: "user", prompt },
        { role: "agent", response: data }
      ]);
      setInput("");
    }
  });

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Research chat</h1>
      <p className="text-xs text-slate-500">
        Model output only — not investment advice. Every fact this agent
        surfaces is traced to a tool call (see the tool activity list under each
        answer). The agent cannot invent prices or override the signal engine.
      </p>

      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (input.trim()) send.mutate(input.trim());
          }}
          className="grid gap-2"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. 'Research AAPL' or 'What's the current signal for BTC-USD?'"
            rows={3}
            className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-3 py-2 text-sm"
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {assetId ? (
                <>
                  Context asset: <span className="mono">{assetId}</span>
                </>
              ) : (
                "No asset context. Include a ticker in your question."
              )}
            </span>
            <button
              type="submit"
              disabled={send.isPending || input.trim().length === 0}
              className="text-sm px-3 py-1.5 rounded border border-blue-500 text-blue-600 dark:text-blue-400 disabled:opacity-50"
            >
              {send.isPending ? "Thinking…" : "Send"}
            </button>
          </div>
        </form>
      </Card>

      {send.error && (
        <Card>
          <p className="text-sm text-red-500">
            Agent call failed: {(send.error as Error).message}
          </p>
        </Card>
      )}

      {history.map((turn, i) => (
        <div key={i}>
          {turn.role === "user" ? (
            <Card>
              <p className="text-xs text-slate-500 mb-1">You</p>
              <p className="text-sm whitespace-pre-wrap">{turn.prompt}</p>
            </Card>
          ) : (
            <Card>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-slate-500">
                  Agent · run <span className="mono">#{turn.response!.run_id}</span> ·
                  status <span className="mono">{turn.response!.status}</span>
                </p>
              </div>
              <ResearchResponseView response={turn.response!.response} />
            </Card>
          )}
        </div>
      ))}
    </div>
  );
}
