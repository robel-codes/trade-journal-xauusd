"use client";
import type { ColumnDef } from "@tanstack/react-table";
import { BookOpen, FlaskConical, LibraryBig } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useAppSettings } from "@/components/app-shell";
import { DataTable } from "@/components/data-table";
import { EquityChart } from "@/components/equity-chart";
import { PnlCalendar } from "@/components/pnl-calendar";
import { Badge, Button, CLASSIFICATION, Empty, ErrorBox, Field, Input, PageHeader, Panel, Select, SeverityIcon, Skeleton, Stat, cx } from "@/components/ui";
import { qs } from "@/lib/api";
import { dateTime, money, pct, ratio, rmult, tone } from "@/lib/format";
import { useApi } from "@/lib/use-api";

type Summary = {
  trades: number; wins: number; losses: number; net_pnl: number; gross_profit: number; gross_loss: number; win_rate: number | null;
  profit_factor: number | null; expectancy: number | null; avg_win: number | null; avg_loss: number | null; payoff_ratio: number | null;
  avg_r: number | null; median_r: number | null; r_trades: number; starting_balance: number; ending_equity: number; total_return_pct: number | null;
  max_drawdown: number; max_drawdown_pct: number | null; current_drawdown: number; current_drawdown_pct: number | null; low_sample: boolean;
  max_consecutive_losses: number;
};
type Row = { key: string; trades: number; net_pnl: number; win_rate: number | null; profit_factor: number | null; expectancy: number | null; avg_r: number | null; low_sample: boolean };
type Overview = {
  timezone: string; summary: Summary; open_positions: number; accounts: { id: string; name: string; kind: string }[];
  equity_curve: { at: string; equity: number; drawdown: number }[]; daily: Record<string, { pnl: number; trades: number }>;
  monthly: Record<string, { pnl: number; trades: number }>; by_strategy: Row[]; by_timeframe: Row[]; by_session: Row[]; by_direction: Row[];
  recent_trades: { id: string; closed_at: string; direction: string; pnl: number; r: number | null; setup: string; strategy: string | null }[];
  library: { total: number; by_classification: Record<string, number>; by_kind: Record<string, number> };
  recent_backtests: unknown[]; warnings: { level: string; message: string }[];
};

const breakdownCols: ColumnDef<Row, unknown>[] = [
  { accessorKey: "key", header: "Group", cell: (c) => <span className="flex items-center gap-1.5">{c.row.original.key}{c.row.original.low_sample && <Badge tone="warn" title="Fewer than 30 trades: ratios are unreliable">n&lt;30</Badge>}</span> },
  { accessorKey: "trades", header: "Trades", meta: { align: "right" }, cell: (c) => <span className="num">{c.getValue() as number}</span> },
  { accessorKey: "net_pnl", header: "Net", meta: { align: "right" }, cell: (c) => <span className={cx("num", tone(c.getValue() as number))}>{money(c.getValue() as number, { sign: true })}</span> },
  { accessorKey: "win_rate", header: "Win %", meta: { align: "right" }, cell: (c) => <span className="num">{pct(c.getValue() as number)}</span> },
  { accessorKey: "profit_factor", header: "PF", meta: { align: "right" }, cell: (c) => <span className="num">{ratio(c.getValue() as number)}</span> },
  { accessorKey: "avg_r", header: "Avg R", meta: { align: "right" }, cell: (c) => <span className={cx("num", tone(c.getValue() as number))}>{rmult(c.getValue() as number)}</span> },
];

export default function OverviewPage() {
  const { tz } = useAppSettings();
  const [account, setAccount] = useState("");
  const [source, setSource] = useState<"all" | "actual" | "simulated">("all");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const path = `/dashboard/overview${qs({ account_id: account, source, start: start ? `${start}T00:00:00Z` : "", end: end ? `${end}T23:59:59Z` : "" })}`;
  const { data, error, loading, reload } = useApi<Overview>(path);
  const accounts = useApi<{ id: string; name: string; kind: string }[]>("/accounts");
  const s = data?.summary;

  const groups = useMemo(() => data ? [
    { title: "By strategy", rows: data.by_strategy }, { title: "By timeframe", rows: data.by_timeframe },
    { title: "By session", rows: data.by_session }, { title: "Long vs short", rows: data.by_direction },
  ] : [], [data]);

  return (
    <div className="mx-auto max-w-[1680px]">
      <PageHeader title="Overview" sub="Actual and simulated journal results. Backtest results are kept separate and appear once Phase 3 lands." />

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-md border border-line bg-panel px-3.5 py-2.5">
        <Field label="Account" htmlFor="f-account">
          <Select id="f-account" value={account} onChange={(e) => setAccount(e.target.value)} className="w-48">
            <option value="">All accounts</option>
            {accounts.data?.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.kind}</option>)}
          </Select>
        </Field>
        <div className="grid gap-1">
          <span className="label">Results</span>
          <div role="radiogroup" aria-label="Result source" className="flex h-8 overflow-hidden rounded-[5px] border border-line-strong">
            {(["all", "actual", "simulated"] as const).map((v) => (
              <button key={v} type="button" role="radio" aria-checked={source === v} onClick={() => setSource(v)}
                className={cx("px-3 capitalize cursor-pointer", source === v ? "bg-accent-soft text-fg" : "text-fg-dim hover:text-fg", v !== "all" && "border-l border-line-strong")}>
                {v === "actual" ? "Actual (live/demo/prop)" : v}
              </button>
            ))}
          </div>
        </div>
        <Field label="From" htmlFor="f-start"><Input id="f-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="w-38" /></Field>
        <Field label="To" htmlFor="f-end"><Input id="f-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="w-38" /></Field>
        {(account || source !== "all" || start || end) && <Button variant="ghost" onClick={() => { setAccount(""); setSource("all"); setStart(""); setEnd(""); }}>Clear filters</Button>}
        <span className="ml-auto text-[11.5px] text-fg-faint">Dates filter by close time, shown in {tz}.</span>
      </div>

      {error && <ErrorBox error={error} onRetry={reload} />}
      {!data && loading && <div className="grid gap-3"><Skeleton className="h-24" /><Skeleton className="h-80" /></div>}

      {data && s && (
        <div className="grid gap-4">
          <section aria-label="Key figures" className="grid grid-cols-2 divide-line overflow-hidden rounded-md border border-line bg-panel sm:grid-cols-4 xl:grid-cols-8 [&>*]:border-line [&>*]:border-b xl:[&>*]:border-b-0 [&>*:not(:first-child)]:border-l">
            <Stat label="Net P&L" value={money(s.net_pnl, { sign: true })} valueClass={tone(s.net_pnl)} sub={`${s.trades} closed · ${data.open_positions} open`} />
            <Stat label="Total return" value={pct(s.total_return_pct, 2, true)} valueClass={tone(s.total_return_pct)} sub={`on ${money(s.starting_balance)} start`} />
            <Stat label="Equity" value={money(s.ending_equity)} sub="balance after closed trades" />
            <Stat label="Win rate" value={pct(s.win_rate)} sub={`${s.wins}W · ${s.losses}L`} />
            <Stat label="Profit factor" value={ratio(s.profit_factor)} valueClass={s.profit_factor == null ? "" : s.profit_factor >= 1 ? "text-pos" : "text-neg"} sub="gross win ÷ gross loss" />
            <Stat label="Expectancy" value={money(s.expectancy, { sign: true })} valueClass={tone(s.expectancy)} sub="per closed trade" />
            <Stat label="Avg R" value={rmult(s.avg_r)} valueClass={tone(s.avg_r)} sub={s.r_trades ? `median ${rmult(s.median_r)} · ${s.r_trades} with stop` : "needs a stop or planned risk"} />
            <Stat label="Max drawdown" value={s.max_drawdown ? `−${money(s.max_drawdown)}` : money(0)} valueClass={s.max_drawdown ? "text-neg" : ""} sub={`${pct(s.max_drawdown_pct)} · now ${pct(s.current_drawdown_pct)}`} />
          </section>

          {s.trades > 0 && s.low_sample && (
            <div className="flex items-center gap-2 rounded-md border border-warn/40 bg-warn-soft px-3.5 py-2 text-warn">
              <SeverityIcon severity="warning" /> {s.trades} closed trades is a small sample. Win rate, profit factor and expectancy can move a lot with the next few trades.
            </div>
          )}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <Panel title="Equity and drawdown" subtitle="One point per closed trade" bodyClass="p-2">
              {data.equity_curve.length ? <EquityChart points={data.equity_curve} /> : (
                <Empty icon={<BookOpen className="size-6" />} title="No closed trades yet">
                  The curve is drawn from journal trades once they have exits. Trade entry arrives with the Journal (Phase 5).
                </Empty>
              )}
            </Panel>
            <Panel title="Daily P&L" subtitle={`Calendar days in ${data.timezone}`}>
              <PnlCalendar daily={data.daily} monthly={data.monthly} />
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {groups.map((g) => (
              <Panel key={g.title} title={g.title} bodyClass="p-0">
                <DataTable data={g.rows} columns={breakdownCols} dense initialSort={[{ id: "net_pnl", desc: true }]}
                  empty={<div className="px-3.5 py-6 text-center text-fg-faint">No closed trades in this filter.</div>} />
              </Panel>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Panel title="Recent trades" bodyClass="p-0" className="xl:col-span-1">
              {data.recent_trades.length ? (
                <ul>{data.recent_trades.map((t) => (
                  <li key={t.id} className="flex items-center gap-3 border-b border-line px-3.5 py-2 last:border-0">
                    <Badge tone={t.direction === "long" ? "pos" : "neg"}>{t.direction === "long" ? "Long" : "Short"}</Badge>
                    <div className="min-w-0 flex-1"><div className="truncate">{t.strategy ?? t.setup ?? "—"}</div><div className="num text-[11px] text-fg-faint">{dateTime(t.closed_at, data.timezone)}</div></div>
                    <div className="text-right"><div className={cx("num", tone(t.pnl))}>{money(t.pnl, { sign: true })}</div><div className="num text-[11px] text-fg-faint">{rmult(t.r)}</div></div>
                  </li>))}</ul>
              ) : <div className="px-3.5 py-6 text-center text-fg-faint">No closed trades yet.</div>}
            </Panel>
            <Panel title="Recent backtest runs" bodyClass="p-0">
              <Empty icon={<FlaskConical className="size-6" />} title="No backtests yet">
                Backtests need imported candles and a native strategy adapter. Both arrive in Phase 3.
              </Empty>
            </Panel>
            <Panel title="Strategy library" actions={<Link href="/strategies" className="text-[12px] text-accent hover:underline">Open library</Link>}>
              {data.library.total ? (
                <div className="grid gap-2.5">
                  <div className="flex items-baseline gap-2"><span className="num text-[22px]">{data.library.total}</span><span className="text-fg-dim">scripts analyzed</span></div>
                  <div className="flex h-2 overflow-hidden rounded-full bg-panel-2" aria-hidden>
                    {(["validated", "partial", "manual", "unsupported"] as const).map((k) => {
                      const n = data.library.by_classification[k] ?? 0;
                      return n ? <div key={k} style={{ width: `${(n / data.library.total) * 100}%`, background: `var(--${{ validated: "pos", partial: "info", manual: "warn", unsupported: "neg" }[k]})` }} /> : null;
                    })}
                  </div>
                  <ul className="grid gap-1">
                    {(["validated", "partial", "manual", "unsupported"] as const).map((k) => (
                      <li key={k} className="flex justify-between"><span className="text-fg-dim">{CLASSIFICATION[k].label}</span><span className="num">{data.library.by_classification[k] ?? 0}</span></li>
                    ))}
                  </ul>
                </div>
              ) : (
                <Empty icon={<LibraryBig className="size-6" />} title="No strategies imported" action={<Link href="/strategies"><Button variant="primary">Import Pine scripts</Button></Link>}>
                  Import your .pine files to see what each one needs before it can be backtested.
                </Empty>
              )}
            </Panel>
          </div>

          <Panel title="Data quality and warnings">
            <ul className="grid gap-2">
              {data.warnings.map((w, i) => <li key={i} className="flex items-start gap-2"><SeverityIcon severity={w.level} /><span className="text-fg-dim">{w.message}</span></li>)}
            </ul>
          </Panel>
        </div>
      )}
    </div>
  );
}
