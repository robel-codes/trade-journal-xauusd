"use client";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { money } from "@/lib/format";
import { cx } from "./ui";

type Day = { pnl: number; trades: number };

/** Month grid of daily P&L. Keys are local dates (YYYY-MM-DD) in the user's timezone, computed server-side. */
export function PnlCalendar({ daily, monthly }: { daily: Record<string, Day>; monthly: Record<string, Day> }) {
  const months = Object.keys(monthly).sort();
  const latest = months.at(-1) ?? new Date().toISOString().slice(0, 7);
  const [month, setMonth] = useState(latest);
  const [y, m] = month.split("-").map(Number);
  const cells = useMemo(() => {
    const first = new Date(Date.UTC(y, m - 1, 1));
    const lead = (first.getUTCDay() + 6) % 7; // Monday-first
    const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
    return [...Array(lead).fill(null), ...Array.from({ length: days }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  }, [y, m, month]);
  const max = Math.max(1, ...cells.filter(Boolean).map((d) => Math.abs(daily[d!]?.pnl ?? 0)));
  const shift = (n: number) => { const d = new Date(Date.UTC(y, m - 1 + n, 1)); setMonth(d.toISOString().slice(0, 7)); };
  const mTotal = monthly[month];

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <button type="button" onClick={() => shift(-1)} aria-label="Previous month" className="rounded p-1 text-fg-dim hover:bg-panel-2 cursor-pointer"><ChevronLeft className="size-4" /></button>
        <div className="num min-w-24 text-center font-medium">{new Date(Date.UTC(y, m - 1, 1)).toLocaleString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" })}</div>
        <button type="button" onClick={() => shift(1)} aria-label="Next month" className="rounded p-1 text-fg-dim hover:bg-panel-2 cursor-pointer"><ChevronRight className="size-4" /></button>
        <div className={cx("num ml-auto", mTotal && (mTotal.pnl > 0 ? "text-pos" : mTotal.pnl < 0 ? "text-neg" : ""))}>{mTotal ? `${money(mTotal.pnl, { sign: true })} · ${mTotal.trades} trades` : "No trades"}</div>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="label text-center !text-[9.5px]">{d}</div>)}
        {cells.map((d, i) => {
          const v = d ? daily[d] : undefined;
          const a = v ? 0.15 + 0.6 * Math.min(1, Math.abs(v.pnl) / max) : 0;
          return (
            <div key={d ?? `x${i}`} title={v ? `${d}: ${money(v.pnl, { sign: true })}, ${v.trades} trades` : d ?? undefined}
              className={cx("relative h-11 rounded-[4px] border border-line px-1 py-0.5", !d && "border-transparent")}
              style={v ? { background: `color-mix(in srgb, var(${v.pnl >= 0 ? "--pos" : "--neg"}) ${Math.round(a * 100)}%, transparent)` } : undefined}>
              {d && <div className="num text-[10px] text-fg-faint">{Number(d.slice(8))}</div>}
              {v && <div className="num truncate text-[10.5px] font-medium text-fg">{money(v.pnl).replace(".00", "")}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
