"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type UserSettingsShape } from "@/lib/api";
import { Card } from "@/components/Card";

export default function SettingsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const [draft, setDraft] = useState<Partial<UserSettingsShape>>({});

  useEffect(() => {
    if (q.data) setDraft({});
  }, [q.data]);

  const save = useMutation({
    mutationFn: () => api.patchSettings(draft),
    onSuccess: () => {
      setDraft({});
      qc.invalidateQueries({ queryKey: ["settings"] });
    }
  });

  if (q.isPending) return <p className="text-sm text-slate-500">Loading…</p>;
  if (q.error) return <p className="text-sm text-red-500">Failed to load settings.</p>;
  const s = { ...(q.data as UserSettingsShape), ...draft };

  function bind<K extends keyof UserSettingsShape>(k: K) {
    return {
      value: s[k] as string | boolean,
      onChange: (v: UserSettingsShape[K]) =>
        setDraft((d) => ({ ...d, [k]: v }))
    };
  }

  return (
    <div className="grid gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>

      <Card title="Account">
        <div className="grid gap-2 text-sm">
          <Row label="Email"><span className="mono">{s.email}</span></Row>
          <Row label="Display name"><span>{s.display_name || "—"}</span></Row>
        </div>
      </Card>

      <Card title="Preferences">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Language">
            <select
              value={s.locale}
              onChange={(e) => bind("locale").onChange(e.target.value as "en" | "vi")}
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            >
              <option value="en">English</option>
              <option value="vi">Tiếng Việt</option>
            </select>
          </Field>
          <Field label="Base currency">
            <input
              value={s.base_currency}
              onChange={(e) => bind("base_currency").onChange(e.target.value.toUpperCase())}
              maxLength={3}
              className="mono border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1 w-24"
            />
          </Field>
          <Field label="Timezone">
            <input
              value={s.timezone}
              onChange={(e) => bind("timezone").onChange(e.target.value)}
              className="mono border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
              placeholder="Area/City"
            />
          </Field>
          <Field label="Default signal horizon">
            <select
              value={s.signal_horizon_default}
              onChange={(e) =>
                bind("signal_horizon_default").onChange(
                  e.target.value as "1D" | "5D" | "20D"
                )
              }
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            >
              <option value="1D">1 trading day</option>
              <option value="5D">3–7 trading days</option>
              <option value="20D">10–30 trading days</option>
            </select>
          </Field>
          <Field label="Risk display">
            <select
              value={s.risk_display}
              onChange={(e) =>
                bind("risk_display").onChange(
                  e.target.value as UserSettingsShape["risk_display"]
                )
              }
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            >
              <option value="BOTH">Level + score</option>
              <option value="LEVEL_ONLY">Level only</option>
              <option value="SCORE_ONLY">Score only</option>
            </select>
          </Field>
          <Field label="Theme">
            <select
              value={s.theme}
              onChange={(e) => bind("theme").onChange(e.target.value as UserSettingsShape["theme"])}
              className="border border-slate-300 dark:border-slate-700 bg-transparent rounded px-2 py-1"
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </Field>
          <Field label="Email notifications">
            <label className="text-sm flex items-center gap-2">
              <input
                type="checkbox"
                checked={s.notifications_email}
                onChange={(e) => bind("notifications_email").onChange(e.target.checked)}
              />
              <span>Receive email alerts</span>
            </label>
          </Field>
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending || Object.keys(draft).length === 0}
            className="text-sm px-3 py-1.5 rounded border border-blue-500 text-blue-600 dark:text-blue-400 disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : "Save changes"}
          </button>
          {save.error && (
            <span className="text-xs text-red-500">
              {(save.error as Error).message}
            </span>
          )}
          {Object.keys(draft).length === 0 && (
            <span className="text-xs text-slate-500">No unsaved changes.</span>
          )}
        </div>
      </Card>

      <Card title="Disclosures">
        <p className="text-sm text-slate-500">
          Educational / research use only. Not investment advice. Signals are
          model output, not recommendations. Past performance does not
          indicate future results. See{" "}
          <a href="/api/docs" className="underline">API docs</a> for the
          data model, and{" "}
          <a
            href="https://github.com/HoangHuyHo2004/demo-trade/blob/main/docs/model-risk-management.md"
            className="underline"
            target="_blank"
            rel="noreferrer"
          >
            model risk management
          </a>{" "}
          for the versioning and change process.
        </p>
      </Card>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-slate-500">{label}</span>
      <span>{children}</span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="text-sm grid gap-1">
      <span className="text-xs text-slate-500">{label}</span>
      {children}
    </label>
  );
}
