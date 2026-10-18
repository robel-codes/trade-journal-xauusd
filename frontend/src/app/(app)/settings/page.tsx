"use client";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { z } from "zod";
import { useAppSettings } from "@/components/app-shell";
import { Badge, Button, Empty, ErrorBox, Field, Input, PageHeader, Panel, Select, Skeleton, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useApi } from "@/lib/use-api";

type Session = { key: string; label: string; timezone: string; start: string; end: string };
type Account = { id: string; name: string; kind: string; currency: string; starting_balance: string; risk_per_trade_pct: string; daily_loss_limit_pct: string | null; max_drawdown_limit_pct: string | null; max_open_positions: number | null; archived: boolean };

const ZONES: string[] = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["UTC", "Europe/London", "America/New_York", "Asia/Tokyo"];
const KIND_LABEL: Record<string, string> = { demo: "Demo", live: "Live", simulation: "Simulation", prop_eval: "Prop evaluation" };

const accountSchema = z.object({
  name: z.string().trim().min(1, "Name the account."),
  kind: z.enum(["demo", "live", "simulation", "prop_eval"]),
  currency: z.string().regex(/^[A-Z]{3}$/, "Use a 3-letter currency code."),
  starting_balance: z.coerce.number().positive("Starting balance must be above zero."),
  risk_per_trade_pct: z.coerce.number().positive().max(100),
  daily_loss_limit_pct: z.union([z.literal(""), z.coerce.number().positive().max(100)]).transform((v) => (v === "" ? null : v)),
  max_drawdown_limit_pct: z.union([z.literal(""), z.coerce.number().positive().max(100)]).transform((v) => (v === "" ? null : v)),
});

function utcWindow(s: Session): string {
  // Show today's UTC equivalent so DST shifts are visible.
  try {
    const now = new Date();
    const [h, m] = s.start.split(":").map(Number);
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: s.timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
    const guess = new Date(`${parts}T${s.start}:00Z`);
    const local = new Intl.DateTimeFormat("en-GB", { timeZone: s.timezone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(guess);
    const [lh, lm] = local.split(":").map(Number);
    const offsetMin = (lh * 60 + lm) - (h * 60 + m);
    const toUtc = (t: string) => { const [a, b] = t.split(":").map(Number); const x = ((a * 60 + b - offsetMin) % 1440 + 1440) % 1440; return `${String(Math.floor(x / 60)).padStart(2, "0")}:${String(x % 60).padStart(2, "0")}`; };
    return `${toUtc(s.start)}–${toUtc(s.end)} UTC today`;
  } catch { return ""; }
}

export default function SettingsPage() {
  const { settings, reloadSettings } = useAppSettings();
  const [tz, setTz] = useState("UTC");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string }>();
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (settings) { setTz(settings.timezone); setSessions(settings.sessions); } }, [settings]);

  async function save() {
    setBusy(true); setMsg(undefined);
    try { await api("/settings", { method: "PUT", json: { timezone: tz, sessions } }); setMsg({ ok: true, text: "Saved." }); reloadSettings(); }
    catch (e) { setMsg({ ok: false, text: (e as Error).message }); } finally { setBusy(false); }
  }
  const upd = (i: number, k: keyof Session, v: string) => setSessions(sessions.map((s, j) => (j === i ? { ...s, [k]: v } : s)));

  return (
    <div className="mx-auto grid max-w-[1200px] gap-4">
      <PageHeader title="Settings" />
      {!settings ? <Skeleton className="h-64" /> : (
        <Panel title="Display and sessions" actions={<><span role="status" className={cx("text-[12px]", msg?.ok ? "text-pos" : "text-neg")}>{msg?.text}</span><Button variant="primary" onClick={save} busy={busy}>Save</Button></>}>
          <div className="grid gap-5">
            <Field label="Display timezone" hint="All times are stored in UTC and shown in this zone." htmlFor="tz">
              <Select id="tz" value={tz} onChange={(e) => setTz(e.target.value)} className="max-w-sm">{ZONES.map((z) => <option key={z}>{z}</option>)}</Select>
            </Field>
            <div>
              <div className="label mb-1">Trading sessions</div>
              <p className="mb-2 text-[12px] text-fg-faint">Each session is defined in its own market timezone, so London and New York hours follow their own daylight-saving dates.</p>
              <div className="overflow-x-auto"><table className="w-full text-[12.5px]">
                <thead><tr className="border-b border-line">{["Key", "Label", "Timezone", "Start", "End", "Today in UTC", ""].map((h) => <th key={h} className="label px-2 py-1.5 text-left">{h}</th>)}</tr></thead>
                <tbody>{sessions.map((s, i) => (
                  <tr key={i} className="border-b border-line">
                    <td className="px-2 py-1.5"><Input value={s.key} onChange={(e) => upd(i, "key", e.target.value)} className="num w-32" aria-label="Session key" /></td>
                    <td className="px-2 py-1.5"><Input value={s.label} onChange={(e) => upd(i, "label", e.target.value)} className="w-40" aria-label="Session label" /></td>
                    <td className="px-2 py-1.5"><Select value={s.timezone} onChange={(e) => upd(i, "timezone", e.target.value)} className="w-48" aria-label="Session timezone">{ZONES.map((z) => <option key={z}>{z}</option>)}</Select></td>
                    <td className="px-2 py-1.5"><Input type="time" value={s.start} onChange={(e) => upd(i, "start", e.target.value)} className="num w-28" aria-label="Start" /></td>
                    <td className="px-2 py-1.5"><Input type="time" value={s.end} onChange={(e) => upd(i, "end", e.target.value)} className="num w-28" aria-label="End" /></td>
                    <td className="num px-2 py-1.5 text-fg-dim">{utcWindow(s)}</td>
                    <td className="px-2 py-1.5"><Button variant="ghost" size="sm" aria-label={`Remove ${s.label}`} onClick={() => setSessions(sessions.filter((_, j) => j !== i))}><Trash2 className="size-3.5" /></Button></td>
                  </tr>))}</tbody>
              </table></div>
              <Button size="sm" className="mt-2" onClick={() => setSessions([...sessions, { key: `custom_${sessions.length + 1}`, label: "Custom", timezone: "UTC", start: "00:00", end: "06:00" }])}><Plus className="size-3.5" />Add session</Button>
            </div>
          </div>
        </Panel>
      )}
      <Accounts />
    </div>
  );
}

function Accounts() {
  const list = useApi<Account[]>("/accounts");
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.currentTarget));
    const parsed = accountSchema.safeParse(fd);
    if (!parsed.success) return setErr(parsed.error.issues[0].message);
    setBusy(true); setErr(undefined);
    try { await api("/accounts", { method: "POST", json: { ...parsed.data, starting_balance: parsed.data.starting_balance.toFixed(2) } }); setOpen(false); list.reload(); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }

  return (
    <Panel title="Trading accounts" subtitle="Live, demo and prop accounts count as actual results; simulation accounts are reported separately."
      actions={<Button size="sm" onClick={() => setOpen((o) => !o)}>{open ? "Cancel" : <><Plus className="size-3.5" />Add account</>}</Button>} bodyClass="p-0">
      {open && (
        <form onSubmit={create} className="grid gap-3 border-b border-line p-3.5 sm:grid-cols-4" noValidate>
          <Field label="Name"><Input name="name" required /></Field>
          <Field label="Type"><Select name="kind" defaultValue="demo">{Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          <Field label="Currency"><Input name="currency" defaultValue="USD" maxLength={3} className="uppercase" /></Field>
          <Field label="Starting balance"><Input name="starting_balance" inputMode="decimal" placeholder="10000" /></Field>
          <Field label="Risk per trade %"><Input name="risk_per_trade_pct" defaultValue="1" inputMode="decimal" /></Field>
          <Field label="Daily loss limit %" hint="Optional"><Input name="daily_loss_limit_pct" inputMode="decimal" /></Field>
          <Field label="Max drawdown limit %" hint="Optional"><Input name="max_drawdown_limit_pct" inputMode="decimal" /></Field>
          <div className="flex items-end"><Button variant="primary" type="submit" busy={busy}>Create account</Button></div>
          {err && <p role="alert" className="text-neg sm:col-span-4">{err}</p>}
        </form>
      )}
      {list.error && <div className="p-3.5"><ErrorBox error={list.error} onRetry={list.reload} /></div>}
      {list.data && list.data.length === 0 && !open && <Empty title="No accounts yet">Add the account you trade so journal entries and risk limits have a balance to work from.</Empty>}
      {list.data && list.data.length > 0 && (
        <table className="w-full text-[12.5px]"><tbody>{list.data.map((a) => (
          <tr key={a.id} className="border-b border-line last:border-0">
            <td className="px-3.5 py-2 font-medium">{a.name}</td>
            <td className="px-3.5 py-2"><Badge tone={a.kind === "simulation" ? "info" : a.kind === "live" ? "accent" : "neutral"}>{KIND_LABEL[a.kind]}</Badge></td>
            <td className="num px-3.5 py-2 text-right">{money(Number(a.starting_balance), { currency: a.currency })}</td>
            <td className="num px-3.5 py-2 text-right text-fg-dim">{Number(a.risk_per_trade_pct)}% risk</td>
            <td className="num px-3.5 py-2 text-right text-fg-dim">{a.daily_loss_limit_pct ? `${Number(a.daily_loss_limit_pct)}% daily` : "no daily limit"}</td>
            <td className="num px-3.5 py-2 text-right text-fg-dim">{a.max_drawdown_limit_pct ? `${Number(a.max_drawdown_limit_pct)}% max DD` : "no DD limit"}</td>
          </tr>))}</tbody></table>
      )}
    </Panel>
  );
}
