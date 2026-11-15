"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ErrorNote, errMsg } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      signIn(await api.login({ email, password }));
      router.replace("/dashboard");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={submit} className="card w-80 space-y-3 p-6">
        <h1 className="text-lg font-semibold">Sign in to AgentOS</h1>
        <ErrorNote message={error} />
        <input className="input" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input className="input" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button className="btn w-full justify-center" disabled={busy}>
          {busy ? "Signing in..." : "Sign in"}
        </button>
        <p className="text-xs text-slate-500">
          No account?{" "}
          <Link href="/register" className="text-indigo-600 hover:underline">
            Create an organization
          </Link>
        </p>
      </form>
    </div>
  );
}
