import { Construction } from "lucide-react";
import { Panel, PageHeader } from "./ui";

/** A section that is designed but not built yet. States plainly what will exist and what it depends on. */
export function RoadmapPage({ title, phase, intro, items, dependsOn }: { title: string; phase: string; intro: string; items: string[]; dependsOn?: string }) {
  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader title={title} sub={intro} />
      <Panel title={`Planned for ${phase}`}>
        <div className="flex gap-3">
          <Construction className="mt-0.5 size-5 shrink-0 text-fg-faint" />
          <div className="grid gap-3">
            <p className="text-fg-dim">This section is not built yet. Nothing on this page is computed, so it shows no figures.</p>
            <ul className="grid list-disc gap-1 pl-5 text-fg-dim">{items.map((i) => <li key={i}>{i}</li>)}</ul>
            {dependsOn && <p className="text-[12px] text-fg-faint">Depends on: {dependsOn}</p>}
          </div>
        </div>
      </Panel>
    </div>
  );
}
