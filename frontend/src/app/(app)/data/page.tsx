import { RoadmapPage } from "@/components/roadmap-page";
export default function Page() {
  return <RoadmapPage title="Market Data" phase="Phase 3" intro="Versioned XAUUSD candle datasets with provenance."
    items={["CSV import for 1m, 5m, 15m, 30m, 1h, 4h and daily candles, normalized to UTC", "Each import becomes an immutable dataset version with checksum, provider, symbol, exchange timezone, precision, coverage and licence note",
      "Validation report: OHLC consistency, duplicates, gaps against the expected session calendar, outliers against rolling ATR. Problems are reported, never patched",
      "Provider adapters added only after their licence terms are confirmed; feeds are never merged"]} />;
}
