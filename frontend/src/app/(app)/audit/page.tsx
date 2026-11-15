"use client";

import { useCallback, useEffect, useState } from "react";
import { ErrorNote, PageHeader, errMsg, fmtDate } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuditLog } from "@/lib/types";

const PAGE = 25;

export default function AuditPage() {
  const { hasRole } = useAuth();
  const [rows, setRows] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!hasRole("admin")) return;
    api
      .audit({ action, resource_type: resourceType, limit: PAGE, offset })
      .then((p) => {
        setRows(p.items);
        setTotal(p.total);
      })
      .catch((e) => setError(errMsg(e)));
  }, [action, resourceType, offset, hasRole]);

  useEffect(load, [load]);

  if (!hasRole("admin")) return <div className="text-slate-500">Audit logs require the admin role.</div>;

  return (
    <div>
      <PageHeader title={`Audit Logs (${total})`} />
      <ErrorNote message={error} />
      <div className="mb-3 flex gap-2">
        <input className="input max-w-xs" placeholder="Action (e.g. agent.create)" value={action} onChange={(e) => { setOffset(0); setAction(e.target.value); }} />
        <input className="input max-w-xs" placeholder="Resource type" value={resourceType} onChange={(e) => { setOffset(0); setResourceType(e.target.value); }} />
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              {["Time", "Action", "Resource", "Actor", "Change", "IP"].map((h) => (
                <th key={h} className="th">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="td whitespace-nowrap text-xs">{fmtDate(r.created_at)}</td>
                <td className="td font-mono text-xs">{r.action}</td>
                <td className="td text-xs">{r.resource_type} {r.resource_id?.slice(0, 8)}</td>
                <td className="td text-xs">{r.actor_user_id?.slice(0, 8) ?? "-"}</td>
                <td className="td max-w-md break-words font-mono text-[11px] text-slate-600">
                  {r.before ? `${JSON.stringify(r.before)} -> ` : ""}
                  {r.after ? JSON.stringify(r.after) : ""}
                </td>
                <td className="td text-xs">{r.ip ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <button className="btn-ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
        <button className="btn-ghost" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>Next</button>
        <span className="text-xs text-slate-500">{total === 0 ? 0 : offset + 1}-{Math.min(offset + PAGE, total)} of {total}</span>
      </div>
    </div>
  );
}
