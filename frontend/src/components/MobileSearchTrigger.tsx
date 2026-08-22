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
}: {
  onClick: () => void;
  label?: string;
  /** Map header: a shorter, less tall capsule that fits a control row. */
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Suche öffnen"
      className={`flex w-full items-center justify-center gap-2.5 rounded-2xl border border-line bg-surface text-ink shadow-float transition-transform active:scale-[0.99] ${compact ? "px-4 py-2.5" : "px-6 py-4"}`}
    >
      <SearchIcon className={`shrink-0 ${compact ? "text-[16px]" : "text-[20px]"}`} />
      <span className={`font-medium ${compact ? "text-[13px]" : "text-[15px]"}`}>{label}</span>
    </button>
  );
}
