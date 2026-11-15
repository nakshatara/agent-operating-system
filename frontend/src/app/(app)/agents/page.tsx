"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ErrorNote, PageHeader, ReadinessBadge, StatusBadge, errMsg } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Agent, ExecutionMode, ModelList } from "@/lib/types";

const EMPTY = {
  name: "",
  role: "",
  description: "",
  system_instructions: "",
  objectives: "",
  provider: "anthropic",
  model: "claude-sonnet-5-5",
  autonomy_level: 1,
  supervisor_agent_id: "",
  execution_mode: "simulated" as ExecutionMode,
};

export default function AgentsPage() {
  const { hasRole } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [total, setTotal] = useState(0);
  const [models, setModels] = useState<ModelList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({ q: "", status: "", readiness: "" });
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api
      .agents({ q: filters.q, status: filters.status, readiness: filters.readiness, limit: 200 })
      .then((p) => {
        setAgents(p.items);
        setTotal(p.total);
      })
      .catch((e) => setError(errMsg(e)));
  }, [filters]);

  useEffect(load, [load]);
  useEffect(() => {
    api.models().then(setModels).catch(() => undefined);
  }, []);

  const providers = Array.from(new Set(models?.models.map((m) => m.provider) ?? []));
  const modelOptions = (models?.models ?? []).filter((m) => m.provider === form.provider);
  const nameOf = (id: string | null) => agents.find((a) => a.id === id)?.name ?? (id ? id.slice(0, 8) : "-");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createAgent({
        ...form,
        objectives: form.objectives.split("\n").map((s) => s.trim()).filter(Boolean),
        supervisor_agent_id: form.supervisor_agent_id || null,
      });
      setForm(EMPTY);
      setShowForm(false);
      load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title={`Agent Directory (${total})`}>
        {hasRole("operator") && (
          <button className="btn" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "Create agent"}
          </button>
        )}
      </PageHeader>
      <ErrorNote message={error} />

      {showForm && (
        <form onSubmit={submit} className="card mb-4 grid gap-3 p-4 md:grid-cols-2">
          <input className="input" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input className="input" placeholder="Role (e.g. Research Analyst)" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} required />
          <textarea className="input md:col-span-2" rows={2} placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <textarea className="input md:col-span-2" rows={3} placeholder="System instructions" value={form.system_instructions} onChange={(e) => setForm({ ...form, system_instructions: e.target.value })} />
          <textarea className="input md:col-span-2" rows={2} placeholder="Objectives (one per line)" value={form.objectives} onChange={(e) => setForm({ ...form, objectives: e.target.value })} />
          <select
            className="input"
            value={form.provider}
            onChange={(e) => {
              const provider = e.target.value;
              const first = models?.models.find((m) => m.provider === provider);
              setForm({ ...form, provider, model: first?.id ?? "" });
            }}
          >
            {providers.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <select className="input" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })}>
            {modelOptions.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}
                {m.live_available ? "" : " (no API key)"}
              </option>
            ))}
          </select>
          <select className="input" value={form.execution_mode} onChange={(e) => setForm({ ...form, execution_mode: e.target.value as ExecutionMode })}>
            <option value="simulated">simulated (no model call)</option>
            <option value="live">live (needs provider API key)</option>
          </select>
          <select className="input" value={form.autonomy_level} onChange={(e) => setForm({ ...form, autonomy_level: Number(e.target.value) })}>
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                Autonomy level {n} (stored; enforcement planned)
              </option>
            ))}
          </select>
          <select className="input md:col-span-2" value={form.supervisor_agent_id} onChange={(e) => setForm({ ...form, supervisor_agent_id: e.target.value })}>
            <option value="">No supervisor</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <div className="md:col-span-2">
            <button className="btn" disabled={busy}>
              {busy ? "Creating..." : "Create (as draft)"}
            </button>
          </div>
        </form>
      )}

      <div className="mb-3 flex gap-2">
        <input className="input max-w-xs" placeholder="Search name" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        <select className="input max-w-[10rem]" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          <option value="">All statuses</option>
          {["draft", "active", "paused", "disabled", "archived", "terminated"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select className="input max-w-[10rem]" value={filters.readiness} onChange={(e) => setFilters({ ...filters, readiness: e.target.value })}>
          <option value="">All readiness</option>
          {["simulated", "configured", "live"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              {["Name", "Role", "Model", "Status", "Readiness", "Autonomy", "Supervisor"].map((h) => (
                <th key={h} className="th">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {agents.length === 0 && (
              <tr>
                <td className="td text-slate-400" colSpan={7}>
                  No agents yet.
                </td>
              </tr>
            )}
            {agents.map((a) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="td font-medium">
                  <Link href={`/agents/${a.id}`} className="text-indigo-600 hover:underline">
                    {a.name}
                  </Link>
                </td>
                <td className="td">{a.role}</td>
                <td className="td text-xs">
                  {a.provider}/{a.model}
                </td>
                <td className="td">
                  <StatusBadge status={a.status} />
                </td>
                <td className="td">
                  <ReadinessBadge readiness={a.readiness} />
                </td>
                <td className="td">{a.autonomy_level}</td>
                <td className="td">{nameOf(a.supervisor_agent_id)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
