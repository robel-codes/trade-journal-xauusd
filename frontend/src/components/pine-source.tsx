"use client";
import { useEffect, useMemo, useRef } from "react";
import { TOKEN_CLASS, tokenizeLine } from "@/lib/pine-highlight";
import { cx } from "./ui";

export type LineMark = { line: number; severity: string; title: string };

/** Read-only, line-numbered source with findings marked in the gutter. Text is shown exactly as stored. */
export function PineSource({ source, marks = [], focusLine }: { source: string; marks?: LineMark[]; focusLine?: number }) {
  const lines = useMemo(() => source.replace(/\r\n/g, "\n").split("\n"), [source]);
  const byLine = useMemo(() => {
    const m = new Map<number, LineMark[]>();
    for (const x of marks) m.set(x.line, [...(m.get(x.line) ?? []), x]);
    return m;
  }, [marks]);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!focusLine || !box.current) return;
    box.current.querySelector(`[data-line="${focusLine}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focusLine]);
  return (
    <div ref={box} className="max-h-[70vh] overflow-auto rounded border border-line bg-bg">
      <pre className="num min-w-max py-2 text-[12.5px] leading-[1.6]"><code>
        {lines.map((text, i) => {
          const n = i + 1;
          const m = byLine.get(n);
          const sev = m?.some((x) => x.severity === "critical") ? "critical" : m?.some((x) => x.severity === "warning") ? "warning" : m ? "info" : null;
          return (
            <div key={n} data-line={n} title={m?.map((x) => x.title).join("\n")}
              className={cx("flex pr-4", sev === "critical" && "bg-neg-soft", sev === "warning" && "bg-warn-soft", sev === "info" && "bg-info-soft/60", focusLine === n && "outline outline-1 outline-accent")}>
              <span className={cx("sticky left-0 w-12 shrink-0 select-none border-r border-line bg-bg pr-2 text-right text-fg-faint",
                sev === "critical" && "!text-neg", sev === "warning" && "!text-warn", sev === "info" && "!text-info")}>{n}</span>
              <span className="pl-3">{tokenizeLine(text).map((t, j) => <span key={j} className={TOKEN_CLASS[t.kind]}>{t.text}</span>)}{text === "" && " "}</span>
            </div>
          );
        })}
      </code></pre>
    </div>
  );
}
