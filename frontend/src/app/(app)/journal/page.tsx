import { RoadmapPage } from "@/components/roadmap-page";
export default function Page() {
  return <RoadmapPage title="Trading Journal" phase="Phase 5" intro="Actual and simulated trades with reasoning, reviews and screenshots."
    items={["Trades built from fills: scale-ins, partial exits and stop moves without special cases (the schema and P&L engine already support this)",
      "Manual entry and editing, broker CSV import with duplicate detection by ticket and fill fingerprint",
      "Entry/exit screenshots with annotation, pre-trade reasoning, post-trade review, emotion, discipline and rule-following scores",
      "Calendar view, chronological feed, search by date, strategy, setup and tag", "Planned versus actual R, and actual results compared with backtest expectations"]}
    dependsOn="object storage for screenshots; backtest results (Phase 3) for plan-versus-backtest comparison" />;
}
