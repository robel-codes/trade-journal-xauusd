"use client";
import type { ColumnDef } from "@tanstack/react-table";
import { Download, FileUp, LibraryBig, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { useAppSettings } from "@/components/app-shell";
import { DataTable } from "@/components/data-table";
import { Badge, Button, CLASSIFICATION, ClassBadge, Empty, ErrorBox, Input, PageHeader, Panel, Select, Skeleton, cx } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { bytes, dateTime } from "@/lib/format";
import { useApi } from "@/lib/use-api";

type Row = {
  id: string; name: string; tags: string[]; category: string; version_count: number; classification: string | null;
  finding_counts: Record<string, number>; updated_at: string;
  latest_version: { number: number; pine_version: number | null; script_kind: string; source_filename: string; input_count: number } | null;
};
type ImportItem = { filename: string; status: string; message: string; strategy_id: string | null; strategy_name: string; classification: string | null; script_kind: string | null };
type ImportResult = { counts: Record<string, number>; items: ImportItem[] };

const STATUS_TONE: Record<string, "pos" | "info" | "neutral" | "warn" | "neg"> = { imported: "pos", new_version: "info", duplicate: "neutral", near_duplicate: "warn", error: "neg" };
const STATUS_LABEL: Record<string, string> = { imported: "Imported", new_version: "New version", duplicate: "Duplicate", near_duplicate: "Near duplicate", error: "Error" };
const ACCEPT = ".pine,.txt,.zip";

function ImportPanel({ onDone }: { onDone: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<"new_version" | "new_strategy">("new_version");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error>();
  const [result, setResult] = useState<ImportResult>();
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();

  function add(list: FileList | null) {
    if (!list) return;
    const ok = [...list].filter((f) => /\.(pine|txt|zip)$/i.test(f.name));
    setFiles((prev) => [...prev, ...ok.filter((f) => !prev.some((p) => p.name === f.name && p.size === f.size))]);
    setResult(undefined);
  }
  async function submit() {
    setBusy(true); setError(undefined);
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    fd.append("on_title_match", mode);
    try {
      const r = await api<ImportResult>("/strategies/import", { method: "POST", body: fd });
      setResult(r); setFiles([]); onDone();
    } catch (e) { setError(e as Error); } finally { setBusy(false); }
  }

  return (
    <Panel title="Import Pine Script" subtitle="Files are stored exactly as uploaded and analyzed as text. Nothing is executed or rewritten.">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
          className={cx("grid min-h-28 place-items-center rounded-md border border-dashed px-4 py-5 text-center", drag ? "border-accent bg-accent-soft" : "border-line-strong")}>
          <div className="grid justify-items-center gap-2">
            <FileUp className="size-5 text-fg-faint" />
            <div className="text-fg-dim">Drop .pine, .txt or .zip files here, or</div>
            <Button size="sm" onClick={() => input.current?.click()}>Choose files</Button>
            <input ref={input} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
          </div>
        </div>
        <div className="grid content-start gap-3">
          <label className="grid gap-1">
            <span className="label">When a title already exists</span>
            <Select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
              <option value="new_version">Add as a new version</option>
              <option value="new_strategy">Create a separate strategy</option>
            </Select>
            <span className="text-[11.5px] text-fg-faint">Identical files and files that differ only in comments or whitespace are always skipped and reported.</span>
          </label>
          <Button variant="primary" disabled={!files.length} busy={busy} onClick={submit}>Import {files.length ? `${files.length} file${files.length > 1 ? "s" : ""}` : ""}</Button>
        </div>
      </div>
      {files.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {files.map((f) => (
            <li key={f.name + f.size} className="flex items-center gap-1.5 rounded border border-line bg-panel-2 py-0.5 pl-2 pr-1 text-[12px]">
              <span className="num">{f.name}</span><span className="text-fg-faint">{bytes(f.size)}</span>
              <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((x) => x !== f))} className="rounded p-0.5 text-fg-faint hover:text-fg cursor-pointer"><X className="size-3" /></button>
            </li>))}
        </ul>
      )}
      {error && <div className="mt-3"><ErrorBox error={error} /></div>}
      {result && (
        <div className="mt-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="font-semibold">Import report</span>
            {Object.entries(result.counts).map(([k, n]) => <Badge key={k} tone={STATUS_TONE[k]}>{n} {STATUS_LABEL[k]?.toLowerCase()}</Badge>)}
          </div>
          <div className="max-h-72 overflow-auto rounded border border-line">
            <table className="w-full text-[12.5px]">
              <tbody>{result.items.map((i, n) => (
                <tr key={n} className={cx("border-b border-line last:border-0", i.strategy_id && "cursor-pointer hover:bg-panel-2")} onClick={() => i.strategy_id && router.push(`/strategies/${i.strategy_id}`)}>
                  <td className="w-28 px-3 py-1.5"><Badge tone={STATUS_TONE[i.status]}>{STATUS_LABEL[i.status]}</Badge></td>
                  <td className="num px-3 py-1.5">{i.filename}</td>
                  <td className="px-3 py-1.5 text-fg-dim">{i.message}</td>
                  <td className="px-3 py-1.5 text-right">{i.classification && <ClassBadge value={i.classification} />}</td>
                </tr>))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Panel>
  );
}

export default function StrategiesPage() {
  const router = useRouter();
  const { tz } = useAppSettings();
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("");
  const [kind, setKind] = useState("");
  const [showImport, setShowImport] = useState(false);
  const list = useApi<Row[]>(`/strategies${qs({ q, classification: cls, kind })}`);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  const columns = useMemo<ColumnDef<Row, unknown>[]>(() => [
    { id: "sel", enableSorting: false, header: () => <span className="sr-only">Select</span>, cell: (c) => (
      <input type="checkbox" aria-label={`Select ${c.row.original.name}`} checked={selected.has(c.row.original.id)} onClick={(e) => e.stopPropagation()}
        onChange={(e) => { const s = new Set(selected); if (e.target.checked) s.add(c.row.original.id); else s.delete(c.row.original.id); setSelected(s); }} className="accent-[var(--accent)]" />) },
    { accessorKey: "name", header: "Strategy", cell: (c) => (
      <div className="min-w-0 max-w-[340px]"><div className="truncate font-medium text-fg">{c.row.original.name}</div>
        <div className="num truncate text-[11px] text-fg-faint">{c.row.original.latest_version?.source_filename}</div></div>) },
    { id: "kind", accessorFn: (r) => r.latest_version?.script_kind, header: "Type", cell: (c) => <span className="capitalize text-fg-dim">{c.getValue() as string}</span> },
    { id: "pine", accessorFn: (r) => r.latest_version?.pine_version ?? 0, header: "Pine", meta: { align: "right" }, cell: (c) => <span className="num">{(c.getValue() as number) ? `v${c.getValue()}` : "—"}</span> },
    { accessorKey: "classification", header: "Compatibility", cell: (c) => <ClassBadge value={c.getValue() as string} /> },
    { id: "findings", accessorFn: (r) => (r.finding_counts.critical ?? 0) * 100 + (r.finding_counts.warning ?? 0), header: "Findings", cell: (c) => {
      const f = c.row.original.finding_counts;
      return <span className="num flex gap-2"><span className={f.critical ? "text-neg" : "text-fg-faint"}>{f.critical ?? 0} crit</span><span className={f.warning ? "text-warn" : "text-fg-faint"}>{f.warning ?? 0} warn</span></span>;
    } },
    { id: "inputs", accessorFn: (r) => r.latest_version?.input_count ?? 0, header: "Inputs", meta: { align: "right" }, cell: (c) => <span className="num">{c.getValue() as number}</span> },
    { accessorKey: "version_count", header: "Versions", meta: { align: "right" }, cell: (c) => <span className="num">{c.getValue() as number}</span> },
    { id: "tags", accessorFn: (r) => r.tags.join(","), header: "Tags", enableSorting: false, cell: (c) => <span className="flex gap-1">{c.row.original.tags.slice(0, 3).map((t) => <Badge key={t}>{t}</Badge>)}</span> },
    { accessorKey: "updated_at", header: "Updated", cell: (c) => <span className="num text-fg-dim">{dateTime(c.getValue() as string, tz, false)}</span> },
  ], [selected, tz]);

  async function exportSelected() {
    setExporting(true);
    try {
      const blob = await api<Blob>("/strategies/export", { method: "POST", json: [...selected] });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "strategies.zip"; a.click();
      URL.revokeObjectURL(url);
    } finally { setExporting(false); }
  }

  const rows = list.data ?? [];
  const filtered = q || cls || kind;
  return (
    <div className="mx-auto max-w-[1680px]">
      <PageHeader title="Strategy Library" sub="Every script with its compatibility report. Classification comes from static analysis; only parity-tested adapters are ever marked validated."
        actions={<>
          {selected.size > 0 && <Button onClick={exportSelected} busy={exporting}><Download className="size-3.5" />Export {selected.size} original{selected.size > 1 ? "s" : ""}</Button>}
          <Button variant="primary" onClick={() => setShowImport((v) => !v)}><FileUp className="size-3.5" />{showImport ? "Hide import" : "Import scripts"}</Button>
        </>} />
      {(showImport || (list.data && rows.length === 0 && !filtered)) && <div className="mb-4"><ImportPanel onDone={() => { setShowImport(true); list.reload(); }} /></div>}

      <Panel bodyClass="p-0" title={list.data ? `${rows.length} ${rows.length === 1 ? "script" : "scripts"}` : "Scripts"}
        actions={<div className="flex flex-wrap gap-2">
          <Input placeholder="Search name, tag or file" value={q} onChange={(e) => setQ(e.target.value)} className="w-60" aria-label="Search strategies" />
          <Select value={cls} onChange={(e) => setCls(e.target.value)} className="w-48" aria-label="Filter by compatibility">
            <option value="">All compatibility</option>
            {Object.entries(CLASSIFICATION).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </Select>
          <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-36" aria-label="Filter by script type">
            <option value="">All types</option><option value="strategy">Strategies</option><option value="indicator">Indicators</option><option value="library">Libraries</option>
          </Select>
        </div>}>
        {list.error && <div className="p-3.5"><ErrorBox error={list.error} onRetry={list.reload} /></div>}
        {!list.data && list.loading && <div className="grid gap-2 p-3.5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-9" />)}</div>}
        {list.data && (
          <DataTable data={rows} columns={columns} onRowClick={(r) => router.push(`/strategies/${r.id}`)} initialSort={[{ id: "name", desc: false }]}
            empty={filtered
              ? <Empty title="No scripts match these filters">Clear the search or filters to see the whole library.</Empty>
              : <Empty icon={<LibraryBig className="size-6" />} title="No scripts yet">Import one file, several files, or a ZIP of your TradingView strategies above.</Empty>} />
        )}
      </Panel>
    </div>
  );
}
