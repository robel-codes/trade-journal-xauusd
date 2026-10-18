"use client";
import { AreaSeries, ColorType, createChart, HistogramSeries, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

export type EquityPoint = { at: string; equity: number; drawdown: number };

function css(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Equity (top pane) and drawdown (bottom pane), one point per closed trade. */
export function EquityChart({ points, height = 300 }: { points: EquityPoint[]; height?: number }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!el.current) return;
    let chart: IChartApi | null = null;
    const build = () => {
      chart?.remove();
      const fg = css("--fg-dim"), line = css("--line"), pos = css("--pos"), neg = css("--neg"), accent = css("--accent");
      chart = createChart(el.current!, {
        height, autoSize: true,
        layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: fg, fontFamily: css("--font-plex-mono") || "monospace", fontSize: 11, attributionLogo: true,
          panes: { separatorColor: line, enableResize: true } },
        grid: { vertLines: { color: line }, horzLines: { color: line } },
        rightPriceScale: { borderColor: line }, timeScale: { borderColor: line, timeVisible: true },
        crosshair: { horzLine: { labelBackgroundColor: accent }, vertLine: { labelBackgroundColor: accent } },
      });
      // Strictly increasing times are required; trades closing in the same second are nudged by 1s.
      let last = 0;
      const pts = points.map((p) => {
        let t = Math.floor(new Date(p.at).getTime() / 1000);
        if (t <= last) t = last + 1;
        last = t;
        return { ...p, time: t as UTCTimestamp };
      });
      const end = pts.at(-1)?.equity ?? 0, start = pts.length ? pts[0].equity - 0 : 0;
      const up = end >= start;
      const eq = chart.addSeries(AreaSeries, { lineColor: up ? pos : neg, topColor: (up ? pos : neg) + "33", bottomColor: "transparent", lineWidth: 2, priceLineVisible: false });
      eq.setData(pts.map((p) => ({ time: p.time, value: p.equity })));
      const dd = chart.addSeries(HistogramSeries, { color: neg, priceLineVisible: false, lastValueVisible: false }, 1);
      dd.setData(pts.map((p) => ({ time: p.time, value: p.drawdown })));
      chart.panes()[1]?.setHeight(Math.round(height * 0.28));
      chart.timeScale().fitContent();
    };
    build();
    const obs = new MutationObserver(build);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { obs.disconnect(); chart?.remove(); };
  }, [points, height]);
  return <div ref={el} style={{ height }} role="img" aria-label="Equity curve with drawdown below" />;
}
