import type { Spot } from "../lib/types";
import { CheckCircleIcon, InfoIcon, MapIcon, UserIcon } from "../lib/icons";

const LABELS = {
  world_class: "World Class",
  worth_trip: "Eine Reise wert",
  worth_checking_out: "Lohnt sich auszuchecken",
} as const;

const CRITERIA = {
  world_class: "Überregional oder international bedeutender Spot mit eigenständiger Reiseanziehung.",
  worth_trip: "Ein Spot, der eine Reise oder einen deutlichen Umweg fachlich begründen kann.",
  worth_checking_out: "Eine lokale oder ergänzende Option, die in der passenden Region relevant sein kann.",
} as const;

const formatDate = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(date)
    : null;
};

export default function SpotEditorialClassification({ spot }: { spot: Spot }) {
  const classification = spot.editorialClassification;
  const reviewed = spot.contentStatus === "verified";
  const label = classification && reviewed ? LABELS[classification] : null;
  const reviewedAt = formatDate(spot.contentReviewedAt);
  return (
    <div className="mt-3 text-caption text-muted">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
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
        {reviewed ? (
          <span className="inline-flex items-center gap-1.5">
            <CheckCircleIcon aria-hidden width={15} height={15} className="shrink-0 text-ink-soft" />
            Redaktionell geprüft{reviewedAt ? ` · ${reviewedAt}` : ""}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5">
            <InfoIcon aria-hidden width={15} height={15} className="shrink-0 text-ink-soft" />
            {spot.contentStatus === "conflict"
              ? "Inhalt mit offenem Widerspruch"
              : spot.contentStatus === "review_due"
                ? "Redaktionelle Prüfung fällig"
                : "Inhalt noch nicht redaktionell geprüft"}
          </span>
        )}
      </div>
      {classification && reviewed && (
        <details className="mt-2 max-w-measure">
          <summary className="min-h-11 cursor-pointer content-center font-medium text-ink-soft underline underline-offset-2">
            Warum diese Einordnung?
          </summary>
          <p className="mt-1 leading-relaxed">
            {spot.classificationReason || CRITERIA[classification]}
          </p>
          {spot.classificationReason && (
            <p className="mt-1 text-muted">Kriterium: {CRITERIA[classification]}</p>
          )}
        </details>
      )}
      {classification && !reviewed && (
        <p className="mt-2 max-w-measure leading-relaxed">
          Eine frühere Relevanzeinordnung ist vorhanden, wird aber erst nach der Inhaltsprüfung angezeigt.
        </p>
      )}
    </div>
  );
}
