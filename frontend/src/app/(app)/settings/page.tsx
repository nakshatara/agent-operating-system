"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ErrorNote, PageHeader, errMsg, fmtDate } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Organization, User } from "@/lib/types";

export default function SettingsPage() {
  const { hasRole } = useAuth();
  const [org, setOrg] = useState<Organization | null>(null);
  const [name, setName] = useState("");
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [invite, setInvite] = useState({ email: "", full_name: "", role: "viewer" });

  const load = useCallback(() => {
    api.organization().then((o) => { setOrg(o); setName(o.name); }).catch((e) => setError(errMsg(e)));
    api.users().then(setUsers).catch((e) => setError(errMsg(e)));
  }, []);
  useEffect(load, [load]);

  const rename = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      setOrg(await api.updateOrganization(name));
      setNotice("Organization updated");
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const doInvite = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    try {
      const r = await api.inviteUser(invite);
      setNotice(r.temporary_password ? `User created. Temporary password (shown once): ${r.temporary_password}` : "User created");
      setInvite({ email: "", full_name: "", role: "viewer" });
      load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const reconcile = async () => {
    setError(null);
    try {
      const r = await api.reconcileGraph();
      setNotice(`Graph rebuilt from PostgreSQL: ${JSON.stringify(r.reconciled)}`);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Organization Settings" />
      <ErrorNote message={error} />
      {notice && <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">{notice}</div>}

      <section className="card p-4">
        <form onSubmit={rename} className="flex items-end gap-2">
          <label className="flex-1 max-w-sm">
            <span className="text-xs font-medium uppercase text-slate-500">Organization name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} disabled={!hasRole("admin")} />
          </label>
          {hasRole("admin") && <button className="btn" disabled={!name || name === org?.name}>Save</button>}
        </form>
        <div className="mt-2 text-xs text-slate-500">Slug: {org?.slug} - created {fmtDate(org?.created_at ?? null)}</div>
        {hasRole("admin") && (
          <button className="btn-ghost mt-3" onClick={reconcile}>Rebuild graph from PostgreSQL</button>
        )}
      </section>

      <section className="card">
        <h2 className="border-b border-slate-200 px-4 py-2 font-semibold">Users ({users.length})</h2>
        <table className="w-full">
          <thead className="bg-slate-50"><tr>{["Name", "Email", "Role", "Last login"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id}>
                <td className="td">{u.full_name}</td>
                <td className="td">{u.email}</td>
                <td className="td">{u.role}</td>
                <td className="td text-xs">{fmtDate(u.last_login_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {hasRole("admin") && (
        <section className="card p-4">
          <h2 className="mb-2 font-semibold">Add user</h2>
          <form onSubmit={doInvite} className="grid gap-2 md:grid-cols-4">
            <input className="input" placeholder="Full name" value={invite.full_name} onChange={(e) => setInvite({ ...invite, full_name: e.target.value })} required />
            <input className="input" type="email" placeholder="Email" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} required />
            <select className="input" value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })}>
              {["viewer", "operator", "admin", ...(hasRole("owner") ? ["owner"] : [])].map((r) => <option key={r}>{r}</option>)}
            </select>
            <button className="btn justify-center">Create user</button>
          </form>
          <p className="mt-2 text-xs text-slate-500">A temporary password is generated and shown once.</p>
        </section>
      )}
    </div>
  );
}
