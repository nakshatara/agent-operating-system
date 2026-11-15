"use client";

import cytoscape from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";
import { ErrorNote, PageHeader, errMsg } from "@/components/ui";
import { api } from "@/lib/api";
import type { GraphData, GraphNode } from "@/lib/types";

const TYPES = ["Organization", "User", "Agent", "Model"] as const;
const COLORS: Record<string, string> = {
  Organization: "#475569",
  User: "#0ea5e9",
  Agent: "#4f46e5",
  Model: "#d97706",
};

export default function GraphPage() {
  const container = useRef<HTMLDivElement>(null);
  const cy = useRef<cytoscape.Core | null>(null);
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({ Organization: true, User: true, Agent: true, Model: true });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<GraphNode | null>(null);

  useEffect(() => {
    api.graph().then(setData).catch((e) => setError(errMsg(e)));
  }, []);

  const nodeIndex = useMemo(() => new Map((data?.nodes ?? []).map((n) => [n.id, n])), [data]);

  // Build the cytoscape instance when data arrives.
  useEffect(() => {
    if (!data || !container.current) return;
    const ids = new Set(data.nodes.map((n) => n.id));
    const instance = cytoscape({
      container: container.current,
      elements: [
        ...data.nodes.map((n) => ({ data: { id: n.id, label: n.label, type: n.type } })),
        ...data.edges
          .filter((e) => ids.has(e.source) && ids.has(e.target))
          .map((e, i) => ({ data: { id: `e${i}`, source: e.source, target: e.target, label: e.type.replace(/_/g, " ").toLowerCase() } })),
      ],
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 10, "background-color": "#94a3b8", width: 22, height: 22, "text-valign": "bottom", "text-margin-y": 4 } },
        ...TYPES.map((t) => ({ selector: `node[type = "${t}"]`, style: { "background-color": COLORS[t] } })),
        { selector: "edge", style: { width: 1.5, "line-color": "#cbd5e1", "target-arrow-color": "#cbd5e1", "target-arrow-shape": "triangle", "curve-style": "bezier" } },
        { selector: ".hidden", style: { display: "none" } },
        { selector: ".match", style: { "border-width": 3, "border-color": "#ef4444" } },
        { selector: ":selected", style: { "border-width": 3, "border-color": "#111827" } },
      ],
      layout: { name: "cose", animate: false },
      wheelSensitivity: 0.3,
    });
    instance.on("tap", "node", (evt) => setSelected(nodeIndex.get(evt.target.id()) ?? null));
    instance.on("tap", (evt) => {
      if (evt.target === instance) setSelected(null);
    });
    cy.current = instance;
    return () => {
      instance.destroy();
      cy.current = null;
    };
  }, [data, nodeIndex]);

  // Type filter.
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.nodes().forEach((n) => {
      n.toggleClass("hidden", !visible[n.data("type") as string]);
    });
  }, [visible, data]);

  // Search highlight.
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.nodes().removeClass("match");
    const q = search.trim().toLowerCase();
    if (!q) return;
    const hits = c.nodes().filter((n) => String(n.data("label")).toLowerCase().includes(q));
    hits.addClass("match");
    if (hits.length > 0) c.animate({ fit: { eles: hits, padding: 80 }, duration: 250 });
  }, [search, data]);

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Agent Hierarchy / Graph" />
      <ErrorNote message={error} />
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <input className="input max-w-xs" placeholder="Search nodes" value={search} onChange={(e) => setSearch(e.target.value)} />
        {TYPES.map((t) => (
          <label key={t} className="flex items-center gap-1 text-xs">
            <input type="checkbox" checked={visible[t]} onChange={(e) => setVisible({ ...visible, [t]: e.target.checked })} />
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS[t] }} /> {t}
          </label>
        ))}
        <button className="btn-ghost" onClick={() => cy.current?.fit(undefined, 40)}>Fit</button>
        <span className="text-xs text-slate-400">The graph is a projection of events; it may lag PostgreSQL by a moment.</span>
      </div>
      <div className="flex min-h-[28rem] flex-1 gap-3">
        <div ref={container} className="card flex-1" />
        <aside className="card w-64 shrink-0 overflow-y-auto p-3">
          <h2 className="mb-2 font-semibold">Inspector</h2>
          {!selected && <p className="text-slate-400">Click a node.</p>}
          {selected && (
            <dl className="space-y-1 text-xs">
              <div><dt className="font-medium text-slate-500">Type</dt><dd>{selected.type}</dd></div>
              <div><dt className="font-medium text-slate-500">Label</dt><dd>{selected.label}</dd></div>
              {Object.entries(selected.properties)
                .filter(([k]) => k !== "organization_id")
                .map(([k, v]) => (
                  <div key={k}><dt className="font-medium text-slate-500">{k}</dt><dd className="break-all">{String(v)}</dd></div>
                ))}
            </dl>
          )}
        </aside>
      </div>
    </div>
  );
}
