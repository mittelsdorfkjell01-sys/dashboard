// One result tile in the picker grid.
//
// The badge strip is the point of this component: resolution, license, prior
// use and geo confidence are exactly the things an operator would otherwise
// have to open the source page to find out.

import { aspectRatio, isUsable, tileBadges, type MediaItem, type MediaRole } from "../../../lib/mediaPicker";

const TONE: Record<string, string> = {
  neutral: "bg-black/55 text-white/85",
  warning: "bg-amber-500/85 text-black",
  info: "bg-sky-500/80 text-white",
};

export default function MediaTile({
  item,
  role,
  selected,
  onSelect,
}: {
  item: MediaItem;
  role: MediaRole;
  selected: boolean;
  onSelect: () => void;
}) {
  const usable = isUsable(item, role);
  const badges = tileBadges(item, role);

  return (
    <button
      type="button"
      // Not clickable when it cannot be adopted in this mode — the badge says
      // why, so a dimmed tile is never a mystery.
      disabled={!usable}
      aria-pressed={selected}
      onClick={onSelect}
      className={`group relative block w-full overflow-hidden rounded-lg border text-left transition-all ${
        selected
          ? "border-admin-primary ring-2 ring-admin-primary"
          : "border-admin-border hover:border-admin-border-strong"
      } ${usable ? "cursor-pointer" : "cursor-not-allowed opacity-40"}`}
    >
      {/* Reserved box from the real aspect ratio, so lazy images cause no
          layout shift as they arrive. */}
      <div style={{ aspectRatio: aspectRatio(item) }} className="w-full bg-admin-hover">
        <img
          src={item.thumb_url}
          alt=""
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover"
        />
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap gap-1 bg-gradient-to-t from-black/70 to-transparent p-1.5 pt-6">
        {badges.map((badge) => (
          <span
            key={badge.label}
            title={badge.title}
            className={`rounded px-1.5 py-0.5 text-[11px] font-medium leading-tight ${
              TONE[badge.tone] ?? TONE.neutral
            }`}
          >
            {badge.label}
          </span>
        ))}
      </div>
    </button>
  );
}
