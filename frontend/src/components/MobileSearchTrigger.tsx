import { SearchIcon } from "../lib/icons";

/**
 * Collapsed mobile search entry (Figma Frame 16). Airbnb-style: a single pill
 * that sits in the hero and, on tap, opens the full-screen MobileSearchSheet.
 * Shown only below `sm`; from `sm` the inline SearchBar dropdown takes over.
 */
export default function MobileSearchTrigger({
  onClick,
  label = "Jetzt suchen",
  compact = false,
  iconOnly = false,
}: {
  onClick: (trigger: HTMLButtonElement) => void;
  label?: string;
  /** Map header: a shorter, less tall capsule that fits a control row. */
  compact?: boolean;
  /** Wind map: the glyph alone, so the whole control row stays one slim line.
   *  `label` then becomes the accessible name instead of visible text. */
  iconOnly?: boolean;
}) {
  if (iconOnly) {
    return (
      <button
        type="button"
        aria-label={label}
        onClick={(event) => onClick(event.currentTarget)}
        className="grid h-8 w-8 shrink-0 place-items-center rounded-card border border-line bg-surface text-ink shadow-card transition-transform active:scale-[0.97] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        <SearchIcon className="text-ui" />
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={(event) => onClick(event.currentTarget)}
      className={`flex min-h-11 w-full items-center justify-center gap-2.5 rounded-card border border-line bg-surface text-ink shadow-float transition-transform active:scale-[0.99] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${compact ? "px-4 py-2.5" : "px-6 py-4"}`}
    >
      <SearchIcon className={`shrink-0 ${compact ? "text-body" : "text-lead"}`} />
      <span className={`font-medium ${compact ? "text-ui" : "text-body"}`}>{label}</span>
    </button>
  );
}
