import { RoadmapPage } from "@/components/roadmap-page";
export default function Page() {
  return <RoadmapPage title="Charts and Replay" phase="Phase 7" intro="Candles with trade and signal overlays."
    items={["TradingView Lightweight Charts (Apache-2.0): candles, markers, price lines for entry, stop and target, synced equity pane",
      "Bar-by-bar replay by feeding bars incrementally (the library has no built-in replay)", "Screenshot annotation on a separate canvas layer (the library has no drawing tools)"]}
    dependsOn="candle datasets (Phase 3)" />;
}
