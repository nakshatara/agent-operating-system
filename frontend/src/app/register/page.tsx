"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ErrorNote, errMsg } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [form, setForm] = useState({ organization_name: "", full_name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      signIn(await api.register(form));
      router.replace("/dashboard");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={submit} className="card w-96 space-y-3 p-6">
        <h1 className="text-lg font-semibold">Create your organization</h1>
        <ErrorNote message={error} />
        <input className="input" placeholder="Organization name" value={form.organization_name} onChange={set("organization_name")} required />
        <input className="input" placeholder="Your full name" value={form.full_name} onChange={set("full_name")} required />
        <input className="input" type="email" placeholder="Email" value={form.email} onChange={set("email")} required />
        <input className="input" type="password" placeholder="Password (min 10 characters)" minLength={10} value={form.password} onChange={set("password")} required />
        <button className="btn w-full justify-center" disabled={busy}>
          {busy ? "Creating..." : "Create account"}
        </button>
        <p className="text-xs text-slate-500">
          Already registered?{" "}
          <Link href="/login" className="text-indigo-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
