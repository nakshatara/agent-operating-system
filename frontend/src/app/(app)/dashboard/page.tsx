"use client";

import { useCallback, useEffect, useState } from "react";
import { ErrorNote, PageHeader, StatCard, errMsg, fmtDate } from "@/components/ui";
import { api } from "@/lib/api";
import type { DashboardSummary, EventEnvelope } from "@/lib/types";
import { useEventStream } from "@/lib/ws";

const MAX_EVENTS = 50;

function describe(e: EventEnvelope): string {
  const p = e.payload as { agent?: { name?: string }; user?: { full_name?: string }; organization?: { name?: string }; execution?: { agent_id?: string; mode?: string; status?: string } };
  if (p.agent?.name) return p.agent.name;
  if (p.user?.full_name) return p.user.full_name;
  if (p.organization?.name) return p.organization.name;
  if (p.execution) return `execution ${p.execution.status ?? ""} (${p.execution.mode ?? ""})`;
  return "";
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<EventEnvelope[]>([]);

  const load = useCallback(() => {
    api.dashboard().then(setSummary).catch((e) => setError(errMsg(e)));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const connected = useEventStream((e) => {
    setEvents((prev) => [e, ...prev].slice(0, MAX_EVENTS));
    load();
  });

  const s = summary;
  return (
    <div>
      <PageHeader title="Overview">
        <span className={`text-xs ${connected ? "text-emerald-600" : "text-slate-400"}`}>
          {connected ? "Live stream connected" : "Live stream disconnected"}
        </span>
      </PageHeader>
      <ErrorNote message={error} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Agents" value={s?.agents.total ?? "-"} sub={s ? `${s.agents.active} active, ${s.agents.paused} paused` : undefined} />
        <StatCard
          label="Readiness"
          value={s ? s.agents.by_readiness.live : "-"}
          sub={s ? `live / ${s.agents.by_readiness.configured} configured / ${s.agents.by_readiness.simulated} simulated` : undefined}
        />
        <StatCard
          label="Executions"
          value={s?.executions.total ?? "-"}
          sub={s ? `${s.executions.running + s.executions.queued} in flight, ${s.executions.succeeded} ok, ${s.executions.failed} failed` : undefined}
        />
        <StatCard label="Tokens (live only)" value={s?.tokens.total.toLocaleString() ?? "-"} sub={s ? `${s.tokens.input.toLocaleString()} in / ${s.tokens.output.toLocaleString()} out` : undefined} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <section className="card lg:col-span-2">
          <h2 className="border-b border-slate-200 px-4 py-2 font-semibold">Live events</h2>
          <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {events.length === 0 && <li className="px-4 py-6 text-slate-400">Waiting for events. Create or run an agent.</li>}
            {events.map((e) => (
              <li key={e.event_id} className="flex items-center justify-between px-4 py-1.5">
                <span>
                  <span className="font-mono text-xs font-medium">{e.type}</span>{" "}
                  <span className="text-slate-500">{describe(e)}</span>
                </span>
                <span className="text-xs text-slate-400">{fmtDate(e.occurred_at)}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h2 className="border-b border-slate-200 px-4 py-2 font-semibold">System health</h2>
          <ul className="divide-y divide-slate-100">
            {(["postgres", "neo4j", "kafka", "redis"] as const).map((k) => {
              const h = s?.health[k];
              return (
                <li key={k} className="flex items-center justify-between px-4 py-2">
                  <span className="capitalize">{k}</span>
                  <span className={h ? (h.ok ? "text-emerald-600" : "text-red-600") : "text-slate-400"}>
                    {h ? (h.ok ? "ok" : `down${h.detail ? ` (${h.detail})` : ""}`) : "-"}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </div>
  );
}
