import { RoadmapPage } from "@/components/roadmap-page";
export default function Page() {
  return <RoadmapPage title="Strategy Leaderboard" phase="Phase 4" intro="Ranked comparison of backtested strategy configurations."
    items={["Default ranking by a documented robustness score, not raw return", "Views for net return, risk-adjusted, lowest drawdown, out-of-sample, consistency and after-cost performance",
      "Filters by timeframe, session, trade count, profit factor, drawdown, expectancy, direction, regime, dataset and cost scenario",
      "A visible warning on every row with too few trades for a reliable conclusion"]}
    dependsOn="completed backtest results" />;
}
