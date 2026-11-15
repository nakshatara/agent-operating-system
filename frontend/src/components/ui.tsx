import type { ReactNode } from "react";

const TONES: Record<string, string> = {
  slate: "bg-slate-100 text-slate-700",
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-800",
  blue: "bg-sky-100 text-sky-800",
  indigo: "bg-indigo-100 text-indigo-800",
  violet: "bg-violet-100 text-violet-800",
};

export function Badge({ tone = "slate", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>
  );
}

const STATUS_TONE: Record<string, string> = {
  draft: "slate",
  active: "green",
  paused: "amber",
  disabled: "slate",
  archived: "slate",
  terminated: "red",
  queued: "slate",
  running: "blue",
  succeeded: "green",
  failed: "red",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "slate"}>{status}</Badge>;
}

/** Honest mode labelling: simulated runs never look like live model output. */
export function ModeBadge({ mode }: { mode: string }) {
  return mode === "live" ? <Badge tone="indigo">LIVE</Badge> : <Badge tone="amber">SIMULATED</Badge>;
}

export function ReadinessBadge({ readiness }: { readiness: string }) {
  const tone = readiness === "live" ? "indigo" : readiness === "configured" ? "violet" : "amber";
  const title =
    readiness === "configured"
      ? "Set to live, but the provider has no API key: cannot run"
      : readiness === "live"
        ? "Runs against a real model"
        : "Runs through the simulated adapter (no model call)";
  return (
    <span title={title}>
      <Badge tone={tone}>{readiness}</Badge>
    </span>
  );
}

export function StatCard({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="card p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{message}</div>;
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <h1 className="text-lg font-semibold">{title}</h1>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

export const fmtDate = (s: string | null): string => (s ? new Date(s).toLocaleString() : "-");
export const errMsg = (e: unknown): string => (e instanceof Error ? e.message : "Unexpected error");
