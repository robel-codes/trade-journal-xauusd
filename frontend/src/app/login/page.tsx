"use client";
import { BarChart3 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { z } from "zod";
import { Button, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";

const schema = z.object({ email: z.string().trim().min(3, "Enter your email."), password: z.string().min(1, "Enter your password.") });

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const parsed = schema.safeParse({ email: form.get("email"), password: form.get("password") });
    if (!parsed.success) return setError(parsed.error.issues[0].message);
    setBusy(true);
    setError(undefined);
    try {
      await api("/auth/login", { method: "POST", json: parsed.data });
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid w-full max-w-[340px] gap-4 rounded-md border border-line bg-panel p-6" noValidate>
      <div className="flex items-center gap-2"><BarChart3 className="size-5 text-accent" /><span className="font-semibold tracking-wide">XAU LAB</span></div>
      <p className="text-fg-dim">Sign in to your research workspace.</p>
      <Field label="Email" htmlFor="email"><Input id="email" name="email" type="email" autoComplete="username" autoFocus /></Field>
      <Field label="Password" htmlFor="password"><Input id="password" name="password" type="password" autoComplete="current-password" /></Field>
      {error && <p role="alert" className="text-neg">{error}</p>}
      <Button variant="primary" type="submit" busy={busy}>Sign in</Button>
      <p className="text-[11.5px] text-fg-faint">First run? Create the user with <code className="num">uv run python -m app.cli bootstrap</code>.</p>
    </form>
  );
}

export default function LoginPage() {
  return <div className="grid min-h-screen place-items-center px-4"><Suspense><LoginForm /></Suspense></div>;
}
