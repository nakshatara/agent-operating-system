"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ErrorNote, ModeBadge, PageHeader, ReadinessBadge, StatusBadge, errMsg, fmtDate } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Agent, Execution } from "@/lib/types";
import { useEventStream } from "@/lib/ws";

const ADMIN_ONLY = new Set(["archive", "terminate", "disable"]);

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { hasRole } = useAuth();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [supervisor, setSupervisor] = useState<Agent | null>(null);
  const [execs, setExecs] = useState<Execution[]>([]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const a = await api.agent(id);
      setAgent(a);
      setSupervisor(a.supervisor_agent_id ? await api.agent(a.supervisor_agent_id).catch(() => null) : null);
      setExecs((await api.agentExecutions(id)).items);
    } catch (e) {
      setError(errMsg(e));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEventStream((e) => {
    if (e.type.startsWith("EXECUTION_") || e.type.startsWith("AGENT_")) load();
  });

  // Poll while something is in flight in case the socket is down.
  const inFlight = execs.some((x) => x.status === "queued" || x.status === "running");
  useEffect(() => {
    if (!inFlight) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [inFlight, load]);

  const act = async (action: string) => {
    setError(null);
    try {
      setAgent(await api.lifecycle(id, action));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const run = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.execute(id, prompt);
      setPrompt("");
      await load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  if (!agent) return <div>{error ? <ErrorNote message={error} /> : "Loading..."}</div>;
  const canRun = agent.status === "active" && agent.readiness !== "configured" && hasRole("operator");

  return (
    <div className="space-y-4">
      <PageHeader title={agent.name}>
        <Link href="/agents" className="btn-ghost">
          Back
        </Link>
      </PageHeader>
      <ErrorNote message={error} />

      <section className="card grid gap-3 p-4 md:grid-cols-3">
        <Field label="Role">{agent.role}</Field>
        <Field label="Status">
          <StatusBadge status={agent.status} />
        </Field>
        <Field label="Readiness">
          <ReadinessBadge readiness={agent.readiness} />
        </Field>
        <Field label="Model">
          {agent.provider}/{agent.model}
        </Field>
        <Field label="Execution mode">
          <ModeBadge mode={agent.execution_mode} />
        </Field>
        <Field label="Autonomy level">{agent.autonomy_level} (enforcement planned)</Field>
        <Field label="Supervisor">
          {supervisor ? (
            <Link className="text-indigo-600 hover:underline" href={`/agents/${supervisor.id}`}>
              {supervisor.name}
            </Link>
          ) : (
            "-"
          )}
        </Field>
        <Field label="Version">{agent.version}</Field>
        <Field label="Updated">{fmtDate(agent.updated_at)}</Field>
        <div className="md:col-span-3">
          <div className="text-xs font-medium uppercase text-slate-500">Description</div>
          <p className="whitespace-pre-wrap">{agent.description || "-"}</p>
        </div>
        <div className="md:col-span-3">
          <div className="text-xs font-medium uppercase text-slate-500">System instructions</div>
          <p className="whitespace-pre-wrap">{agent.system_instructions || "-"}</p>
        </div>
        {agent.readiness === "configured" && (
          <div className="md:col-span-3 rounded bg-violet-50 px-3 py-2 text-violet-800">
            This agent is set to live but provider &quot;{agent.provider}&quot; has no API key on the server, so it cannot run.
          </div>
        )}
      </section>

      <section className="card flex flex-wrap items-center gap-2 p-4">
        <span className="mr-2 text-xs font-medium uppercase text-slate-500">Lifecycle</span>
        {agent.available_actions.length === 0 && <span className="text-slate-400">No transitions available</span>}
        {agent.available_actions
          .filter((a) => !ADMIN_ONLY.has(a) || hasRole("admin"))
          .filter(() => hasRole("operator"))
          .map((a) => (
            <button key={a} className="btn-ghost capitalize" onClick={() => act(a)}>
              {a}
            </button>
          ))}
      </section>

      <section className="card p-4">
        <h2 className="mb-2 font-semibold">Run a prompt</h2>
        <form onSubmit={run} className="space-y-2">
          <textarea className="input" rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={canRun ? "Enter a prompt" : "Agent must be active, runnable, and you need operator access"} disabled={!canRun} required />
          <button className="btn" disabled={!canRun || busy}>
            {busy ? "Submitting..." : `Run (${agent.execution_mode})`}
          </button>
        </form>
      </section>

      <section className="card">
        <h2 className="border-b border-slate-200 px-4 py-2 font-semibold">Execution history</h2>
        <ul className="divide-y divide-slate-100">
          {execs.length === 0 && <li className="px-4 py-4 text-slate-400">No executions yet.</li>}
          {execs.map((x) => (
            <li key={x.id} className="space-y-1 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <ModeBadge mode={x.mode} />
                <StatusBadge status={x.status} />
                <span className="text-slate-500">{fmtDate(x.created_at)}</span>
                <span>tokens: {x.input_tokens ?? "-"} in / {x.output_tokens ?? "-"} out</span>
                <span>latency: {x.latency_ms !== null ? `${x.latency_ms} ms` : "-"}</span>
                <span className="text-slate-400">
                  {x.provider}/{x.model} v{x.agent_version}
                </span>
              </div>
              <div className="text-slate-500">Prompt: {x.input_prompt}</div>
              {x.output && <pre className="whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{x.output}</pre>}
              {x.error && <div className="text-red-600">Error: {x.error}</div>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div>{children}</div>
    </div>
  );
}
