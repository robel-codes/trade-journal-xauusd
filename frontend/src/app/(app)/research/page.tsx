import { RoadmapPage } from "@/components/roadmap-page";
export default function Page() {
  return <RoadmapPage title="Research Workspace" phase="Phase 4 and 6" intro="Batch evaluation of strategies across timeframes, sessions and regimes."
    items={["Pick strategies, timeframes, date range, dataset, session, cost and sizing assumptions, and in-sample/out-of-sample windows",
      "Staged pipeline: compatibility → data coverage → baseline → costs → sensitivity → sessions/regimes → out-of-sample → walk-forward → Monte Carlo → ranking",
      "Background jobs with queued/running/completed/cancelled/failed states, progress, cancellation and resume",
      "Job-size estimate before launch and duplicate-job prevention via configuration hashes"]}
    dependsOn="candle datasets and the backtest engine (Phase 3)" />;
}
