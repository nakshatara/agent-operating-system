"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const ACTIVE = [
  { href: "/dashboard", label: "Overview" },
  { href: "/agents", label: "Agents" },
  { href: "/graph", label: "Hierarchy / Graph" },
  { href: "/audit", label: "Audit Logs" },
  { href: "/settings", label: "Organization" },
];

const PLANNED = [
  "Workflow Builder",
  "Command Center",
  "Collaboration Hub",
  "Memory",
  "Approvals",
  "Policies",
  "Analytics",
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="px-4 py-4 text-base font-semibold">AgentOS</div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2">
        {ACTIVE.map((i) => {
          const on = pathname === i.href || pathname.startsWith(i.href + "/");
          return (
            <Link
              key={i.href}
              href={i.href}
              className={`block rounded px-2 py-1.5 ${on ? "bg-indigo-50 font-medium text-indigo-700" : "text-slate-700 hover:bg-slate-100"}`}
            >
              {i.label}
            </Link>
          );
        })}
        <div className="px-2 pb-1 pt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">Roadmap</div>
        {PLANNED.map((p) => (
          <div key={p} aria-disabled="true" className="flex cursor-not-allowed items-center justify-between rounded px-2 py-1.5 text-slate-400">
            <span>{p}</span>
            <span className="rounded bg-slate-100 px-1.5 text-[10px] font-medium uppercase text-slate-500">Planned</span>
          </div>
        ))}
      </nav>
      <div className="border-t border-slate-200 p-3 text-xs">
        <div className="truncate font-medium">{user?.full_name}</div>
        <div className="truncate text-slate-500">
          {user?.email} - {user?.role}
        </div>
        <button className="mt-2 text-indigo-600 hover:underline" onClick={signOut}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
