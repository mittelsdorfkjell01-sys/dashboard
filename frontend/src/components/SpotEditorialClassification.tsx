import type { Spot } from "../lib/types";
import { MapIcon, UserIcon } from "../lib/icons";

const LABELS = {
  world_class: "World Class",
  worth_trip: "Eine Reise wert",
  worth_checking_out: "Entdecken lohnt sich",
} as const;

export default function SpotEditorialClassification({ spot }: { spot: Spot }) {
  const label = spot.editorialClassification ? LABELS[spot.editorialClassification] : null;
  if (!label && spot.origin !== "community") return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-caption text-muted">
      {label && (
        <span className="inline-flex items-center gap-1.5">
          <MapIcon aria-hidden width={15} height={15} className="shrink-0 text-ink-soft" />
          {label}
        </span>
      )}
      {spot.origin === "community" && (
        <span className="inline-flex min-w-0 items-center gap-1.5">
          <UserIcon aria-hidden width={15} height={15} className="shrink-0 text-ink-soft" />
          <span className="min-w-0 break-words">
            Community{spot.contributorName ? ` · ${spot.contributorName}` : ""}
          </span>
        </span>
      )}
    </div>
  );
}
