import type { SpotFact } from "../lib/types";

/** "Spot-Steckbrief" — a compact key/value character sheet for the sidebar. */
export default function SpotFacts({ facts }: { facts: SpotFact[] }) {
  return (
    <div className="rounded-2xl bg-[#F1F5FA] p-6">
      <h2 className="mb-4 text-[15px] font-semibold text-ink">Steckbrief</h2>
      <dl className="divide-y divide-line/70 text-[13.5px]">
        {facts.map((f) => (
          <div key={f.label} className="flex items-start justify-between gap-4 py-2.5">
            <dt className="shrink-0 text-muted">{f.label}</dt>
            <dd className="text-right font-medium text-ink">{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
