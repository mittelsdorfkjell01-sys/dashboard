import { SearchIcon } from "../lib/icons";

/**
 * Collapsed mobile search entry (Figma Frame 16). Airbnb-style: a single pill
 * that sits in the hero and, on tap, opens the full-screen MobileSearchSheet.
 * Shown only below `sm`; from `sm` the inline SearchBar dropdown takes over.
 */
export default function MobileSearchTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Suche öffnen"
      className="flex w-full items-center justify-center gap-2.5 rounded-2xl border border-line bg-surface px-6 py-4 text-ink shadow-float transition-transform active:scale-[0.99]"
    >
      <SearchIcon className="shrink-0 text-[20px]" />
      <span className="text-[15px] font-medium">Jetzt suchen</span>
    </button>
  );
}
