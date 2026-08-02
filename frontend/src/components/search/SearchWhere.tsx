// "Wohin?" panel: two compact columns of suggestions — Spots left, Regionen
// right — filtered by the bar's query. The input itself lives in the search bar
// (the "Tippleiste"); this panel is just the results.

import { useMemo } from "react";
import { useRegions, useSpots } from "../../lib/hooks";
import type { WhereSelection } from "../../lib/searchSubmit";

export interface WherePick extends WhereSelection {
  country?: string | null;
}

function Row({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-band"
    >
      <span className="truncate text-[15px] text-teal">{label}</span>
    </button>
  );
}

export default function SearchWhere({
  query,
  onPick,
}: {
  query: string;
  onPick: (pick: WherePick) => void;
}) {
  const { data: spots } = useSpots({ status: "published" });
  const { data: regions } = useRegions();

  const regionById = useMemo(
    () => new Map((regions ?? []).map((r) => [r.id, r])),
    [regions]
  );

  const q = query.trim().toLowerCase();
  const spotHits = (spots ?? [])
    .filter((s) => !q || s.name.toLowerCase().includes(q))
    .slice(0, 6);
  const regionHits = (regions ?? [])
    .filter((r) => !q || r.name.toLowerCase().includes(q))
    .slice(0, 6);

  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-2">
      {/* Spots left */}
      <div>
        <h3 className="mb-2 text-[13px] font-medium text-muted">Spots</h3>
        {spotHits.length ? (
          <div className="flex flex-col gap-0.5">
            {spotHits.map((s) => {
              const country = regionById.get(s.regionId ?? "")?.country ?? null;
              return (
                <Row
                  key={s.id}
                  label={s.name}
                  onClick={() =>
                    onPick({ label: s.name, kind: "spot", id: s.uuid ?? s.id, country })
                  }
                />
              );
            })}
          </div>
        ) : (
          <p className="text-[13px] text-muted">Keine Spots gefunden.</p>
        )}
      </div>

      {/* Regionen right */}
      <div>
        <h3 className="mb-2 text-[13px] font-medium text-muted">Regionen</h3>
        {regionHits.length ? (
          <div className="flex flex-col gap-0.5">
            {regionHits.map((r) => (
              <Row
                key={r.id}
                label={r.name}
                onClick={() =>
                  onPick({ label: r.name, kind: "region", id: r.id, country: r.country })
                }
              />
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-muted">Keine Regionen gefunden.</p>
        )}
      </div>
    </div>
  );
}
