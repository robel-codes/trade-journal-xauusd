import { RoadmapPage } from "@/components/roadmap-page";
export default function Page() {
  return <RoadmapPage title="Reports" phase="Phase 6" intro="Reproducible reports for every backtest and research run."
    items={["The 23 sections in the brief, with measured results separated from interpretation", "CSV, JSON and PDF export",
      "Each report records the strategy version hash, dataset checksum, configuration and engine version, so it can be regenerated exactly"]}
    dependsOn="backtest engine and research jobs" />;
}
