"use client";
import clsx from "clsx";
import { AlertTriangle, Info, Loader2, OctagonAlert } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { forwardRef } from "react";

export function cx(...a: Parameters<typeof clsx>) { return clsx(...a); }

type Variant = "primary" | "default" | "ghost" | "danger";
export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean; size?: "sm" | "md" }>(
  function Button({ variant = "default", busy, size = "md", className, children, disabled, ...rest }, ref) {
    return (
      <button ref={ref} disabled={disabled || busy} {...rest}
        className={cx(
          "inline-flex items-center justify-center gap-1.5 rounded-[5px] border font-medium whitespace-nowrap transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer",
          size === "sm" ? "h-7 px-2.5 text-[12px]" : "h-8 px-3 text-[13px]",
          variant === "primary" && "bg-accent text-accent-ink border-accent hover:brightness-110",
          variant === "default" && "bg-panel-2 border-line-strong text-fg hover:border-fg-faint",
          variant === "ghost" && "border-transparent text-fg-dim hover:text-fg hover:bg-panel-2",
          variant === "danger" && "bg-neg-soft border-neg/40 text-neg hover:border-neg",
          className)}>
        {busy && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
        {children}
      </button>
    );
  });

const field = "h-8 rounded-[5px] border border-line-strong bg-panel-2 px-2.5 text-[13px] text-fg placeholder:text-fg-faint focus:border-accent focus:outline-none";
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...p }, ref) {
  return <input ref={ref} {...p} className={cx(field, className)} />;
});
export function Select({ className, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={cx(field, "pr-7", className)} />;
}
export function Textarea({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cx(field, "h-auto min-h-20 py-2 leading-relaxed", className)} />;
}
export function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="grid gap-1 min-w-0 [&>input]:w-full [&>select]:w-full [&>textarea]:w-full">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="text-[11.5px] text-fg-faint">{hint}</span>}
    </label>
  );
}

export function Panel({ title, actions, children, className, bodyClass, subtitle }: { title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string }) {
  return (
    <section className={cx("min-w-0 rounded-md border border-line bg-panel", className)}>
      {(title || actions) && (
        <header className="flex min-h-10 items-center justify-between gap-3 border-b border-line px-3.5 py-2">
          <div className="min-w-0">
            {title && <h2 className="label !text-fg-dim">{title}</h2>}
            {subtitle && <p className="text-[11.5px] text-fg-faint truncate">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cx("p-3.5", bodyClass)}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, valueClass, title }: { label: string; value: ReactNode; sub?: ReactNode; valueClass?: string; title?: string }) {
  return (
    <div className="min-w-0 px-3.5 py-3" title={title}>
      <div className="label">{label}</div>
      <div className={cx("num mt-1 truncate text-[19px] font-medium leading-tight", valueClass)}>{value}</div>
      {sub && <div className="mt-0.5 truncate text-[11.5px] text-fg-faint">{sub}</div>}
    </div>
  );
}

type Tone = "neutral" | "pos" | "neg" | "warn" | "info" | "accent";
const tones: Record<Tone, string> = {
  neutral: "bg-panel-2 text-fg-dim border-line-strong",
  pos: "bg-pos-soft text-pos border-pos/30",
  neg: "bg-neg-soft text-neg border-neg/30",
  warn: "bg-warn-soft text-warn border-warn/30",
  info: "bg-info-soft text-info border-info/30",
  accent: "bg-accent-soft text-accent border-accent/30",
};
export function Badge({ tone = "neutral", children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return <span title={title} className={cx("inline-flex h-5 items-center gap-1 rounded-[4px] border px-1.5 text-[11px] font-semibold whitespace-nowrap", tones[tone], className)}>{children}</span>;
}

export const CLASSIFICATION: Record<string, { label: string; tone: Tone; help: string }> = {
  validated: { label: "Validated", tone: "pos", help: "Native adapter exists and matches TradingView output in parity tests." },
  partial: { label: "Partially supported", tone: "info", help: "All constructs are in the engine's supported set. Needs a reviewed translation and a parity check." },
  manual: { label: "Manual conversion", tone: "warn", help: "Uses constructs that need human decisions before translation." },
  unsupported: { label: "Not executable", tone: "neg", help: "Cannot currently be backtested reliably (indicator, library, or unreproducible data)." },
};
export function ClassBadge({ value }: { value: string | null | undefined }) {
  if (!value) return <Badge>—</Badge>;
  const c = CLASSIFICATION[value];
  return <Badge tone={c.tone} title={c.help}>{c.label}</Badge>;
}

export function SeverityIcon({ severity }: { severity: string }) {
  if (severity === "critical") return <OctagonAlert className="size-4 shrink-0 text-neg" aria-label="Critical" />;
  if (severity === "warning") return <AlertTriangle className="size-4 shrink-0 text-warn" aria-label="Warning" />;
  return <Info className="size-4 shrink-0 text-info" aria-label="Info" />;
}

export function Empty({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="grid justify-items-center gap-2 px-6 py-10 text-center">
      {icon && <div className="text-fg-faint">{icon}</div>}
      <div className="text-[14px] font-semibold text-fg">{title}</div>
      {children && <div className="max-w-md text-fg-dim">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md border border-neg/40 bg-neg-soft px-3.5 py-3 text-neg">
      <OctagonAlert className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1"><div className="font-semibold">Couldn&apos;t load this</div><div className="text-fg-dim">{error.message}</div></div>
      {onRetry && <Button size="sm" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded bg-panel-2", className)} />;
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 pb-4">
      <div className="min-w-0">
        <h1 className="text-[18px] font-semibold tracking-tight text-fg">{title}</h1>
        {sub && <p className="mt-0.5 text-fg-dim">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
