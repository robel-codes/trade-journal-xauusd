"use client";
import { ArrowLeft, Copy, Download, GitCompare } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useAppSettings } from "@/components/app-shell";
import { PineSource } from "@/components/pine-source";
import { Badge, Button, CLASSIFICATION, ClassBadge, Empty, ErrorBox, Field, Input, PageHeader, Panel, Select, SeverityIcon, Skeleton, Textarea, cx } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { bytes, dateTime } from "@/lib/format";
import { useApi } from "@/lib/use-api";

type VersionRow = { id: string; number: number; created_at: string; source_filename: string; source_sha256: string; source_bytes: number; pine_version: number | null; script_kind: string; change_note: string; classification: string | null };
type Strategy = {
  id: string; name: string; tags: string[]; category: string; description: string; hypothesis: string; entry_conditions: string; exit_conditions: string;
  stop_methodology: string; target_methodology: string; session_restrictions: string; notes: string; known_limitations: string;
  supported_timeframes: string[]; versions: VersionRow[]; classification: string | null; cloned_from_strategy_id: string | null;
};
type Finding = { code: string; severity: string; impact: string; title: string; detail: string; lines: number[] };
type Version = {
  id: string; number: number; source: string; source_sha256: string; source_filename: string; pine_version: number | null; script_kind: string;
  declared_title: string; declaration: Record<string, unknown>; created_at: string;
  inputs: { position: number; variable: string; type: string; title: string; default_raw: string; default: unknown; has_literal_default: boolean; options: Record<string, unknown>; line: number }[];
  report: { analyzer_version: string; classification: string; summary: string; findings: Finding[]; function_usage: { calls: Record<string, { count: number; lines: number[]; status: string }>; user_functions: string[]; imports: string[] } } | null;
};
type Diff = { a: number; b: number; unified: string[]; classification: string[]; inputs_added: string[]; inputs_removed: string[]; inputs_changed: string[] };

const TABS = ["Compatibility", "Source", "Inputs", "Functions", "Versions", "Details"] as const;
type Tab = (typeof TABS)[number];
const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];
const IMPACT: Record<string, string> = { none: "No effect on execution", caution: "Results may differ from TradingView", manual: "Needs manual conversion", blocking: "Blocks execution" };
const SEV_ORDER: Record<string, number> = { critical: 0, warning: 1, info: 2 };
const STATUS_TONE: Record<string, "pos" | "neg" | "warn" | "neutral" | "info"> = { supported: "pos", unsupported: "neg", manual: "warn", unknown: "warn", visual: "neutral", user: "info", library: "warn", property: "pos" };

function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "na";
  if (typeof v === "object") return (v as { expression?: string }).expression ?? JSON.stringify(v);
  return String(v);
}

export default function StrategyPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { tz } = useAppSettings();
  const st = useApi<Strategy>(`/strategies/${id}`);
  const [versionId, setVersionId] = useState<string>();
  const vid = versionId ?? st.data?.versions[0]?.id;
  const ver = useApi<Version>(vid ? `/strategies/${id}/versions/${vid}` : null);
  const [tab, setTab] = useState<Tab>("Compatibility");
  const [focusLine, setFocusLine] = useState<number>();

  function jump(line: number) { setFocusLine(line); setTab("Source"); }

  async function clone() {
    const r = await api<{ id: string }>(`/strategies/${id}/clone`, { method: "POST", json: {} });
    router.push(`/strategies/${r.id}`);
  }
  async function download() {
    if (!vid || !ver.data) return;
    const blob = await api<Blob>(`/strategies/${id}/versions/${vid}/source`);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = ver.data.source_filename.split("/").pop() || `${st.data?.name}.pine`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (st.error) return <ErrorBox error={st.error} onRetry={st.reload} />;
  if (!st.data) return <div className="grid gap-3"><Skeleton className="h-10 w-80" /><Skeleton className="h-96" /></div>;
  const s = st.data;
  const v = ver.data;
  const findings = [...(v?.report?.findings ?? [])].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);

  return (
    <div className="mx-auto max-w-[1680px]">
      <Link href="/strategies" className="mb-2 inline-flex items-center gap-1 text-[12px] text-fg-dim hover:text-fg"><ArrowLeft className="size-3.5" />Strategy Library</Link>
      <PageHeader title={s.name}
        sub={<span className="flex flex-wrap items-center gap-2">
          {v && <><ClassBadge value={v.report?.classification} /><Badge className="capitalize">{v.script_kind}</Badge><Badge>{v.pine_version ? `Pine v${v.pine_version}` : "No version"}</Badge></>}
          {s.tags.map((t) => <Badge key={t} tone="accent">{t}</Badge>)}
          {s.cloned_from_strategy_id && <Link href={`/strategies/${s.cloned_from_strategy_id}`} className="text-[12px] text-fg-dim underline">cloned from original</Link>}
        </span>}
        actions={<>
          <label className="flex items-center gap-2"><span className="label">Version</span>
            <Select value={vid} onChange={(e) => setVersionId(e.target.value)} className="w-56" aria-label="Version">
              {s.versions.map((x) => <option key={x.id} value={x.id}>v{x.number} · {dateTime(x.created_at, tz, false)}</option>)}
            </Select></label>
          <Button onClick={download} title="Downloads the exact bytes that were imported"><Download className="size-3.5" />Export original</Button>
          <Button onClick={clone} title="Copy into a new strategy before modifying it"><Copy className="size-3.5" />Clone</Button>
        </>} />

      <div role="tablist" aria-label="Strategy sections" className="mb-3 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
            className={cx("-mb-px border-b-2 px-3 py-2 text-[13px] cursor-pointer", tab === t ? "border-accent text-fg" : "border-transparent text-fg-dim hover:text-fg")}>
            {t}{t === "Compatibility" && findings.length > 0 && <span className="num ml-1.5 text-fg-faint">{findings.length}</span>}
            {t === "Inputs" && v && <span className="num ml-1.5 text-fg-faint">{v.inputs.length}</span>}
            {t === "Versions" && <span className="num ml-1.5 text-fg-faint">{s.versions.length}</span>}
          </button>
        ))}
      </div>

      {ver.error && <ErrorBox error={ver.error} onRetry={ver.reload} />}
      {!v && !ver.error && <Skeleton className="h-96" />}

      {v && tab === "Compatibility" && v.report && (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <Panel title="Findings" subtitle={`Analyzer ${v.report.analyzer_version}. Static analysis only; the script was not executed.`} bodyClass="p-0">
            {findings.length ? (
              <ul>{findings.map((f, i) => (
                <li key={i} className="flex gap-3 border-b border-line px-3.5 py-3 last:border-0">
                  <SeverityIcon severity={f.severity} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-fg">{f.title}</span>
                      <Badge tone={f.impact === "blocking" ? "neg" : f.impact === "manual" ? "warn" : f.impact === "caution" ? "info" : "neutral"}>{IMPACT[f.impact]}</Badge></div>
                    <p className="mt-1 max-w-[80ch] text-fg-dim">{f.detail}</p>
                    {f.lines.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{f.lines.map((l) => (
                      <button key={l} type="button" onClick={() => jump(l)} className="num rounded border border-line px-1.5 text-[11px] text-fg-dim hover:border-accent hover:text-fg cursor-pointer">line {l}</button>))}</div>}
                  </div>
                </li>))}</ul>
            ) : <Empty title="No findings">The analyzer found nothing to flag.</Empty>}
          </Panel>
          <div className="grid content-start gap-4">
            <Panel title="Verdict">
              <ClassBadge value={v.report.classification} />
              <p className="mt-2 text-fg-dim">{v.report.summary}</p>
              <p className="mt-2 text-[11.5px] text-fg-faint">{CLASSIFICATION[v.report.classification]?.help}</p>
            </Panel>
            <Panel title="strategy() settings" subtitle="As declared in the script; these are the original settings">
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px]">
                {Object.entries(v.declaration).filter(([k]) => !k.startsWith("_")).map(([k, val]) => (
                  <div key={k} className="contents"><dt className="num text-fg-dim">{k}</dt><dd className="num truncate text-right" title={fmtValue(val)}>{fmtValue(val)}</dd></div>))}
                {Object.keys(v.declaration).filter((k) => !k.startsWith("_")).length === 0 && <dd className="col-span-2 text-fg-faint">Only defaults; nothing declared.</dd>}
              </dl>
            </Panel>
            <Panel title="Provenance">
              <dl className="grid gap-1 text-[12px]">
                <div><dt className="label">File</dt><dd className="num break-all">{v.source_filename}</dd></div>
                <div><dt className="label">SHA-256</dt><dd className="num break-all text-fg-dim">{v.source_sha256}</dd></div>
                <div><dt className="label">Imported</dt><dd className="num">{dateTime(v.created_at, tz)}</dd></div>
              </dl>
            </Panel>
          </div>
        </div>
      )}

      {v && tab === "Source" && (
        <PineSource source={v.source} focusLine={focusLine}
          marks={findings.flatMap((f) => f.lines.map((line) => ({ line, severity: f.severity, title: f.title })))} />
      )}

      {v && tab === "Inputs" && (
        <Panel bodyClass="p-0" title="Inputs" subtitle="Defaults are the script's original values. Changed values in a backtest are recorded as a modified configuration.">
          {v.inputs.length ? (
            <div className="overflow-x-auto"><table className="w-full text-[12.5px]">
              <thead><tr className="border-b border-line">{["Variable", "Title", "Type", "Default", "Constraints", "Line"].map((h) => <th key={h} className="label px-3 py-2 text-left">{h}</th>)}</tr></thead>
              <tbody>{v.inputs.map((i) => (
                <tr key={i.position} className="border-b border-line last:border-0">
                  <td className="num px-3 py-2 text-fg">{i.variable || "—"}</td><td className="px-3 py-2">{i.title || "—"}</td>
                  <td className="px-3 py-2"><Badge>{i.type}</Badge></td>
                  <td className="num px-3 py-2">{i.has_literal_default ? fmtValue(i.default) : <span className="text-warn" title="Default is an expression, not a literal">{i.default_raw}</span>}</td>
                  <td className="num px-3 py-2 text-fg-dim">{Object.entries(i.options).map(([k, o]) => `${k}=${fmtValue(o)}`).join("  ") || "—"}</td>
                  <td className="px-3 py-2"><button type="button" onClick={() => jump(i.line)} className="num text-fg-dim hover:text-accent cursor-pointer">{i.line}</button></td>
                </tr>))}</tbody>
            </table></div>
          ) : <Empty title="No inputs">This script has no user-configurable inputs.</Empty>}
        </Panel>
      )}

      {v && tab === "Functions" && v.report && <FunctionsTab usage={v.report.function_usage} onJump={jump} />}
      {tab === "Versions" && <VersionsTab strategyId={id} versions={s.versions} tz={tz} onChanged={st.reload} currentSource={v?.source} />}
      {tab === "Details" && <DetailsTab strategy={s} onSaved={st.reload} />}
    </div>
  );
}

function FunctionsTab({ usage, onJump }: { usage: NonNullable<Version["report"]>["function_usage"]; onJump: (l: number) => void }) {
  const [filter, setFilter] = useState("");
  const rows = Object.entries(usage.calls).filter(([, u]) => !filter || u.status === filter).sort((a, b) => a[0].localeCompare(b[0]));
  const counts = Object.values(usage.calls).reduce<Record<string, number>>((m, u) => ({ ...m, [u.status]: (m[u.status] ?? 0) + 1 }), {});
  return (
    <Panel bodyClass="p-0" title="Function and property usage"
      subtitle="Status is relative to the native engine's planned support set"
      actions={<Select value={filter} onChange={(e) => setFilter(e.target.value)} className="w-44" aria-label="Filter by status">
        <option value="">All ({Object.keys(usage.calls).length})</option>
        {Object.entries(counts).map(([k, n]) => <option key={k} value={k}>{k} ({n})</option>)}
      </Select>}>
      {usage.imports.length > 0 && <div className="border-b border-line px-3.5 py-2 text-warn">Imports: {usage.imports.join(", ")}</div>}
      <div className="overflow-x-auto"><table className="w-full text-[12.5px]">
        <thead><tr className="border-b border-line">{["Name", "Status", "Uses", "Lines"].map((h) => <th key={h} className="label px-3 py-2 text-left">{h}</th>)}</tr></thead>
        <tbody>{rows.map(([name, u]) => (
          <tr key={name} className="border-b border-line last:border-0">
            <td className="num px-3 py-1.5">{name}</td><td className="px-3 py-1.5"><Badge tone={STATUS_TONE[u.status]}>{u.status}</Badge></td>
            <td className="num px-3 py-1.5">{u.count}</td>
            <td className="px-3 py-1.5"><span className="flex flex-wrap gap-1">{u.lines.slice(0, 12).map((l) => <button key={l} type="button" onClick={() => onJump(l)} className="num text-fg-dim hover:text-accent cursor-pointer">{l}</button>)}</span></td>
          </tr>))}</tbody>
      </table></div>
    </Panel>
  );
}

function VersionsTab({ strategyId, versions, tz, onChanged, currentSource }: { strategyId: string; versions: VersionRow[]; tz: string; onChanged: () => void; currentSource?: string }) {
  const [a, setA] = useState(versions[1]?.id ?? versions[0]?.id);
  const [b, setB] = useState(versions[0]?.id);
  const diff = useApi<Diff>(a && b && a !== b ? `/strategies/${strategyId}/diff${qs({ a, b })}` : null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState<Error>();
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (editing && currentSource !== undefined) setDraft(currentSource); }, [editing, currentSource]);

  async function save() {
    setBusy(true); setErr(undefined);
    try {
      await api(`/strategies/${strategyId}/versions`, { method: "POST", json: { source: draft, change_note: note } });
      setEditing(false); setNote(""); onChanged();
    } catch (e) { setErr(e as Error); } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-4">
      <Panel title="Version history" bodyClass="p-0" subtitle="Versions are immutable. Editing saves a new version; the original is never changed."
        actions={<Button size="sm" onClick={() => setEditing((x) => !x)}>{editing ? "Cancel" : "New version from latest"}</Button>}>
        {editing && (
          <div className="grid gap-2 border-b border-line p-3.5">
            <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} className="num min-h-72 text-[12px]" aria-label="Pine source" spellCheck={false} />
            <div className="flex gap-2"><Input placeholder="What changed and why" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Change note" />
              <Button variant="primary" onClick={save} busy={busy} disabled={!draft.trim()}>Save as new version</Button></div>
            {err && <ErrorBox error={err} />}
          </div>
        )}
        <table className="w-full text-[12.5px]"><tbody>{versions.map((x) => (
          <tr key={x.id} className="border-b border-line last:border-0">
            <td className="num px-3 py-2 font-semibold">v{x.number}</td>
            <td className="num px-3 py-2 text-fg-dim">{dateTime(x.created_at, tz)}</td>
            <td className="px-3 py-2"><ClassBadge value={x.classification} /></td>
            <td className="px-3 py-2 text-fg-dim">{x.change_note}</td>
            <td className="num px-3 py-2 text-right text-fg-faint" title={x.source_sha256}>{bytes(x.source_bytes)} · {x.source_sha256.slice(0, 10)}</td>
          </tr>))}</tbody></table>
      </Panel>
      <Panel title="Compare versions" actions={versions.length > 1 && <div className="flex items-center gap-2">
        <Select value={a} onChange={(e) => setA(e.target.value)} className="w-24" aria-label="From version">{versions.map((x) => <option key={x.id} value={x.id}>v{x.number}</option>)}</Select>
        <GitCompare className="size-4 text-fg-faint" />
        <Select value={b} onChange={(e) => setB(e.target.value)} className="w-24" aria-label="To version">{versions.map((x) => <option key={x.id} value={x.id}>v{x.number}</option>)}</Select>
      </div>}>
        {versions.length < 2 ? <p className="text-fg-faint">Only one version exists. Import a changed script with the same title, or save a new version, to compare.</p>
          : a === b ? <p className="text-fg-faint">Pick two different versions.</p>
          : diff.error ? <ErrorBox error={diff.error} /> : !diff.data ? <Skeleton className="h-40" /> : (
            <div className="grid gap-3">
              <div className="flex flex-wrap gap-2 text-[12px]">
                <span>Compatibility: <ClassBadge value={diff.data.classification[0]} /> → <ClassBadge value={diff.data.classification[1]} /></span>
                {diff.data.inputs_changed.length > 0 && <Badge tone="warn">defaults changed: {diff.data.inputs_changed.join(", ")}</Badge>}
                {diff.data.inputs_added.length > 0 && <Badge tone="info">inputs added: {diff.data.inputs_added.join(", ")}</Badge>}
                {diff.data.inputs_removed.length > 0 && <Badge tone="neg">inputs removed: {diff.data.inputs_removed.join(", ")}</Badge>}
              </div>
              <pre className="num max-h-[60vh] overflow-auto rounded border border-line bg-bg py-2 text-[12px] leading-[1.6]">
                {diff.data.unified.length === 0 ? <div className="px-3 text-fg-faint">No differences.</div> : diff.data.unified.map((l, i) => (
                  <div key={i} className={cx("px-3", l.startsWith("+") && !l.startsWith("+++") && "bg-pos-soft text-pos", l.startsWith("-") && !l.startsWith("---") && "bg-neg-soft text-neg", l.startsWith("@@") && "text-info")}>{l || " "}</div>))}
              </pre>
            </div>)}
      </Panel>
    </div>
  );
}

function DetailsTab({ strategy, onSaved }: { strategy: Strategy; onSaved: () => void }) {
  const initial = useMemo(() => ({ ...strategy, tagsText: strategy.tags.join(", ") }), [strategy]);
  const [f, setF] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string }>();
  useEffect(() => setF(initial), [initial]);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function save() {
    setBusy(true); setMsg(undefined);
    const { tagsText, ...rest } = f;
    const body = {
      name: rest.name, category: rest.category, description: rest.description, hypothesis: rest.hypothesis, entry_conditions: rest.entry_conditions,
      exit_conditions: rest.exit_conditions, stop_methodology: rest.stop_methodology, target_methodology: rest.target_methodology,
      session_restrictions: rest.session_restrictions, notes: rest.notes, known_limitations: rest.known_limitations, supported_timeframes: rest.supported_timeframes,
      tags: tagsText.split(",").map((t) => t.trim()).filter(Boolean),
    };
    try { await api(`/strategies/${strategy.id}`, { method: "PATCH", json: body }); setMsg({ ok: true, text: "Saved." }); onSaved(); }
    catch (e) { setMsg({ ok: false, text: (e as Error).message }); } finally { setBusy(false); }
  }

  const text = (k: keyof typeof f, label: string, hint?: string) => (
    <Field label={label} hint={hint}><Textarea value={f[k] as string} onChange={set(k)} /></Field>
  );
  return (
    <Panel title="Research notes" subtitle="Your description of the strategy. This never changes the script."
      actions={<><span className={cx("text-[12px]", msg?.ok ? "text-pos" : "text-neg")} role="status">{msg?.text}</span><Button variant="primary" onClick={save} busy={busy}>Save</Button></>}>
      <div className="grid gap-4 lg:grid-cols-2">
        <Field label="Name"><Input value={f.name} onChange={set("name")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Category"><Input value={f.category} onChange={set("category")} placeholder="Trend, mean reversion…" /></Field>
          <Field label="Tags" hint="Comma separated"><Input value={f.tagsText} onChange={set("tagsText")} /></Field>
        </div>
        <div className="lg:col-span-2"><span className="label">Supported timeframes</span>
          <div className="mt-1 flex flex-wrap gap-1.5">{TIMEFRAMES.map((t) => {
            const on = f.supported_timeframes.includes(t);
            return <button key={t} type="button" aria-pressed={on} onClick={() => setF({ ...f, supported_timeframes: on ? f.supported_timeframes.filter((x) => x !== t) : [...f.supported_timeframes, t] })}
              className={cx("num h-7 rounded border px-2.5 cursor-pointer", on ? "border-accent bg-accent-soft text-fg" : "border-line-strong text-fg-dim hover:text-fg")}>{t}</button>;
          })}</div></div>
        {text("description", "Description")}
        {text("hypothesis", "Trading hypothesis", "Why should this edge exist in gold?")}
        {text("entry_conditions", "Entry conditions")}
        {text("exit_conditions", "Exit conditions")}
        {text("stop_methodology", "Stop-loss methodology")}
        {text("target_methodology", "Take-profit methodology")}
        {text("session_restrictions", "Session restrictions")}
        {text("known_limitations", "Known limitations")}
        <div className="lg:col-span-2">{text("notes", "Notes")}</div>
      </div>
    </Panel>
  );
}
