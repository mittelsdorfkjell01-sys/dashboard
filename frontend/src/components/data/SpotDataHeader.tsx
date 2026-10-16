import type { Spot } from "../../lib/types";
import { CheckCircleIcon } from "../../lib/icons";
import { sportLabel } from "../../lib/labels";
import { useSpotDataScope } from "../../state/SpotDataScope";
import Segmented from "../ui/Segmented";

export default function SpotDataHeader({ spot }: { spot: Spot }) {
  const { sportMode, setSportMode, windUnit, setWindUnit } = useSpotDataScope();
  const region = spot.region.split(",")[0]?.trim() || spot.region;

  return (
    <div className="grid gap-3 py-3 sm:grid-cols-[1fr_auto] sm:items-center">
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-baseline gap-2.5">
          <h1 className="text-title font-semibold tracking-tight text-ink">{spot.name}</h1>
          <span className="text-body font-light text-muted">{region}</span>
        </div>
        {spot.sports && spot.sports.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
            {spot.sports.map((sport) => (
              <span key={sport} className="inline-flex items-center gap-1 text-ui font-medium text-ink">
                {sportLabel(sport)}
                <CheckCircleIcon checkOnly width={16} height={16} className="text-ink" />
              </span>
            ))}
          </div>
        )}
      </div>
      {/* One grouped control instead of two equally-weighted toggles — both
          compact, so they read as a secondary setting next to the data
          rather than competing with it (audit P1). */}
      <div className="flex flex-wrap items-center gap-2 sm:justify-self-end">
        <Segmented
          value={sportMode}
          onChange={setSportMode}
          options={[{ id: "wind", label: "Wind" }, { id: "surf", label: "Surf" }]}
          label="Sportmodus"
        />
        <Segmented
          value={windUnit}
          onChange={setWindUnit}
          options={[{ id: "kn", label: "kn" }, { id: "ms", label: "m/s" }]}
          label="Windeinheit"
        />
      </div>
    </div>
  );
}
