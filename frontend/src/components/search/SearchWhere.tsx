// "Wohin?" panel (Frame_4): suggestion lists only — the search input itself now
// lives in the search bar (the "Tippleiste"), so this panel is just the results:
// the "unentschlossen" shortcut, then Spots + Regionen filtered by the bar's
// query, and a "Zuletzt gesucht" list from localStorage.

import { useMemo } from "react";
import { useRegions, useSpots } from "../../lib/hooks";
import { getRecent, type RecentItem } from "../../lib/recentSearches";
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
  onOpen,
}: {
  query: string;
  onPick: (pick: WherePick) => void;
  onOpen: () => void;
}) {
  const { data: spots } = useSpots({ status: "published" });
  const { data: regions } = useRegions();
  // Snapshot recents once per mount so the list doesn't reshuffle mid-interaction.
  const recent = useMemo<RecentItem[]>(() => getRecent(), []);

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
    .slice(0, 5);

  return (
    <div className="flex flex-col gap-4">
      {/* "unentschlossen" opens the place axis → ranks the best regions. */}
      <button
        type="button"
        onClick={onOpen}
        className="self-start whitespace-nowrap rounded-2xl border border-teal/50 px-3 py-2 text-[12px] font-medium text-teal transition-colors hover:bg-teal/5"
      >
        unentschlossen — beste Regionen zeigen
      </button>

      {/* Two columns: Regionen left, Spots right. */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
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
      </div>

      <div className="border-t border-line pt-3">
        <h3 className="mb-2 text-[13px] font-medium text-muted">Zuletzt gesucht</h3>
        {recent.length ? (
          <div className="flex flex-col gap-0.5">
            {recent.map((r, i) => (
              <Row
                key={`${r.label}-${i}`}
                label={r.label}
                onClick={() =>
                  onPick({
                    label: r.label,
                    kind: r.kind === "region" ? "region" : "spot",
                    id: r.id,
                    country: r.country,
                  })
                }
              />
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-muted">Noch nichts gesucht.</p>
        )}
      </div>
    </div>
  );
}
