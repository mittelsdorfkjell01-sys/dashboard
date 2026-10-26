import type { SVGProps } from "react";
import surfIconSrc from "../assets/icons/surf.png";
import kiteIconSrc from "../assets/icons/kite.png";
import windsurfIconSrc from "../assets/icons/windsurf.png";
import wingIconSrc from "../assets/icons/wing.png";

/** Thin, consistent line icons (stroke = currentColor) sized 1em by default. */
type IconProps = SVGProps<SVGSVGElement>;

const base = {
  width: "1em",
  height: "1em",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export const SearchIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

export const MenuIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

export const UserIcon = (p: IconProps) => (
  <svg {...base} {...p} viewBox="0 0 24 24" fill="currentColor" stroke="none">
    <circle cx="12" cy="8.5" r="3.6" />
    <path d="M4.5 20a7.5 7.5 0 0 1 15 0Z" />
  </svg>
);

export const HeartIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M12 20s-7-4.35-9.2-8.6C1.3 8.2 3 5 6.2 5c1.9 0 3.1 1 3.8 2 .7-1 1.9-2 3.8-2 3.2 0 4.9 3.2 3.4 6.4C19 15.65 12 20 12 20Z" />
  </svg>
);

/** Swell/wave glyph — two stacked crests, used in the wind-map point panel and
 *  its hourly forecast strip. The marine wave *value* is not yet published, so
 *  this marks the slot visually until the wave field is activated. */
export const WaveIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M2 15c2.2 0 2.2-2.4 4.4-2.4S8.6 15 10.8 15s2.2-2.4 4.4-2.4S17.4 15 19.6 15 22 12.6 22 12.6" />
    <path d="M2 19.5c2.2 0 2.2-2.4 4.4-2.4s2.2 2.4 4.4 2.4 2.2-2.4 4.4-2.4 2.2 2.4 4.4 2.4" />
  </svg>
);

/** Meteorological wind — three restrained stream lines. */
export const WindIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M3 8h10.5a2.5 2.5 0 1 0-2.2-3.7" />
    <path d="M3 12h15a2.5 2.5 0 1 1-2.2 3.7" />
    <path d="M3 16h7" />
  </svg>
);

/** Air / water temperature. */
export const TemperatureIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M10 5a2 2 0 0 1 4 0v8.2a4 4 0 1 1-4 0Z" />
    <path d="M12 8v7" />
  </svg>
);

/** House mark in miniature — the favicon's teardrop with its dot knocked out.
 *  Marks a spot we entered ourselves (see components/SpotOriginMark). Filled,
 *  not stroked, so it still reads as one shape at 12–14px. */
export const EditorialMarkIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <path
      d="M12 2.5c4 0 6.7 2.7 6.7 7.3 0 4.7-3.4 9.9-6.7 12.7-3.3-2.8-6.7-8-6.7-12.7 0-4.6 2.7-7.3 6.7-7.3Zm0 4.8a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z"
      fillRule="evenodd"
      clipRule="evenodd"
    />
  </svg>
);

export const GridIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <rect x="3.5" y="3.5" width="7" height="7" rx="1.6" />
    <rect x="13.5" y="3.5" width="7" height="7" rx="1.6" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="1.6" />
    <rect x="13.5" y="13.5" width="7" height="7" rx="1.6" />
  </svg>
);

export const MapIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4Z" />
    <path d="M9 4v14M15 6v14" />
  </svg>
);

/** Open an external/link destination. */
export const LinkIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M10 14a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1" />
    <path d="M14 10a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 19.1l1.1-1.1" />
  </svg>
);

export const SortIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M4 8h11" />
    <circle cx="17.5" cy="8" r="2" />
    <path d="M4 16h5" />
    <circle cx="11.5" cy="16" r="2" />
    <path d="M14 16h6" />
  </svg>
);

/** Sliders / adjustments — opens the filter panel (Figma Frame 78: two rails,
 * top knob left, bottom knob right). */
export const FilterIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M4 8h2" />
    <circle cx="8" cy="8" r="2" />
    <path d="M10 8h10" />
    <path d="M4 16h10" />
    <circle cx="16" cy="16" r="2" />
    <path d="M18 16h2" />
  </svg>
);

export const PinIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <path d="M12 2c3.87 0 7 3.13 7 7 0 4.87-7 13-7 13S5 13.87 5 9c0-3.87 3.13-7 7-7Z" />
    <circle cx="12" cy="9" r="2.6" fill="#fff" />
  </svg>
);

/** Overflow / more actions — horizontal three dots. */
export const MoreIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <circle cx="5" cy="12" r="1.8" />
    <circle cx="12" cy="12" r="1.8" />
    <circle cx="19" cy="12" r="1.8" />
  </svg>
);

/** Add a spot — a map/card tile with a plus. */
export const SpotAddIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <rect x="4" y="4" width="16" height="16" rx="3.6" />
    <path d="M12 9v6M9 12h6" />
  </svg>
);

export const CalendarIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
    <path d="M3.5 9.5h17M8 3.5v3M16 3.5v3" />
  </svg>
);

export const CloseIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const PlusIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const MinusIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M5 12h14" />
  </svg>
);

export const ChevronDownIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const InfoIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </svg>
);

/** Safety / hazard notice. */
export const SafetyIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M12 3 2.8 20h18.4L12 3Z" />
    <path d="M12 9v5M12 17.2h.01" />
  </svg>
);

/** Facility: parking — "P" in a rounded square. */
export const ParkingIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <rect x="3" y="3" width="18" height="18" rx="4.5" />
    <path d="M9.3 17.5V6.5h3.7a3.2 3.2 0 0 1 0 6.4H9.3" />
  </svg>
);

/** Facility: surf school / rental — an upright fish-tail surfboard: rounded
 *  nose, center stringer, swallowtail notch and a single leash-plug dot. */
export const SchoolIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M9.3 4.3C9.9 2.9 10.8 2.1 12 2.1c1.2 0 2.1.8 2.7 2.2C16.3 6.6 16.7 9.2 15.9 11.8 15.8 15 15.4 17.3 14.8 19.1L15.6 21.5 12 18.8 8.4 21.5 9.2 19.1C8.6 17.3 8.2 15 8.1 11.8 7.7 9.2 8.1 6.6 9.3 4.3Z" />
    <path d="M12 3v15.3" />
    <circle cx="12" cy="19.6" r="0.6" fill="currentColor" stroke="none" />
  </svg>
);

/** Facility: shower — curved wall arm, shower head and water drops. */
export const ShowerIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M5 21V8a4 4 0 0 1 4-4h5v2" />
    <path d="M9.5 11a4.5 4.5 0 0 1 9 0Z" />
    <path d="M11 13.8v2M14 13.8v2M17 13.8v2M12.5 16.8v1.8M15.5 16.8v1.8" />
  </svg>
);

/** Facility: gastronomy — crossed fork and knife. */
export const FoodIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M16.8 4v4.2a2.2 2.2 0 0 1-4.4 0V4" />
    <path d="M14.6 8.4v1.9L7 20" />
    <path d="M8 4.2c1.7 0 2.7 1.5 2.7 3.4 0 1.3-.8 2.3-1.9 2.6L17 20" />
  </svg>
);

/** Facility: camping — pitched tent with crossed poles and entrance. */
export const CampingIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M12 5 3.5 20.5h17L12 5Z" />
    <path d="M12 11 8.7 20.5M12 11l3.3 9.5" />
    <path d="M10.3 3.5 13.2 6.6M13.7 3.5 10.8 6.6" />
  </svg>
);

/** Facility: surf school — two upright surfboards on the beach with a sun.
 *  Dedicated to the facilities panel so it doesn't touch the shared SchoolIcon
 *  ("Mein Setup" in the account menu). */
export const SurfSchoolIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="6" cy="6" r="2.1" />
    <path d="M6 2v1.2M6 8.8V10M2 6h1.2M8.8 6H10M3.6 3.6l.9.9M8.4 3.6l-.9.9M3.6 8.4l.9-.9M8.4 8.4l-.9-.9" />
    <path d="M12.5 20c-1.9-2.2-1.9-9.5 0-13.5 1.9 4 1.9 11.3 0 13.5Z" />
    <path d="M17.5 20c-1.9-2.2-1.9-9.5 0-13.5 1.9 4 1.9 11.3 0 13.5Z" />
    <path d="M3 20.5h18" />
  </svg>
);

/** Spot ground / terrain (Untergrund) — a low sun, dunes and two waterlines. */
export const GroundIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="7.5" cy="6" r="2" />
    <path d="M7.5 2.5v1M7.5 8.5v1M4 6h1M10 6h1M5.3 3.8l.7.7M9.7 3.8l-.7.7" />
    <path d="M2 15c2-3.2 4.5-3.2 6.5 0M8 15c2-3.4 4.7-3.4 6.7 0" />
    <path d="M2 18.6c3-1.6 5 1.4 8 0s5-1.4 8 0" />
    <path d="M2 21.4c3-1.6 5 1.4 8 0s5-1.4 8 0" />
  </svg>
);

/** Community tip — an opening quotation mark. */
export const QuoteIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <path d="M7.5 6C5 6 3.5 8 3.5 10.7c0 2.4 1.6 3.8 3.5 3.8 1.3 0 2.3-.9 2.3-2.2 0-1.2-.9-2.1-2-2.1-.2 0-.5 0-.6.1.2-1 1.1-1.9 2.3-2.2L7.5 6Zm9 0c-2.5 0-4 2-4 4.7 0 2.4 1.6 3.8 3.5 3.8 1.3 0 2.3-.9 2.3-2.2 0-1.2-.9-2.1-2-2.1-.2 0-.5 0-.6.1.2-1 1.1-1.9 2.3-2.2L16.5 6Z" />
  </svg>
);

/** Filled heart — active favourite state. */
export const HeartFilledIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <path d="M12 20s-7-4.35-9.2-8.6C1.3 8.2 3 5 6.2 5c1.9 0 3.1 1 3.8 2 .7-1 1.9-2 3.8-2 3.2 0 4.9 3.2 3.4 6.4C19 15.65 12 20 12 20Z" />
  </svg>
);

/** Save/bookmark — outline (not saved) and filled (saved). */
export const BookmarkIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M6 4.5h12a1 1 0 0 1 1 1V20l-7-3.6L5 20V5.5a1 1 0 0 1 1-1Z" />
  </svg>
);

export const BookmarkFilledIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <path d="M6 4.5h12a1 1 0 0 1 1 1V20l-7-3.6L5 20V5.5a1 1 0 0 1 1-1Z" />
  </svg>
);

/** Share — node-and-links glyph (works cross-platform, no OS-specific arrow). */
export const ShareIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="6" cy="12" r="2.4" />
    <circle cx="17.5" cy="6" r="2.4" />
    <circle cx="17.5" cy="18" r="2.4" />
    <path d="m8.1 10.9 7.3-3.8M8.1 13.1l7.3 3.8" />
  </svg>
);

/** Suggest an edit — a pencil. */
export const PencilIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M4 20h4L18.5 9.5a2 2 0 0 0-2.83-2.83L5.17 17.17 4 20Z" />
    <path d="m14.5 8.5 1.83 1.83" />
  </svg>
);

/** Account settings — a gear. */
export const GearIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.3a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.3 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 7 2.7h.1A1.7 1.7 0 0 0 8.3 1V.9a2 2 0 1 1 4 0V1a1.7 1.7 0 0 0 1.2 1.7 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 21.3 8H21a1.7 1.7 0 0 0 0 4h.1a1.7 1.7 0 0 0 1.2 1z" transform="translate(1 1) scale(0.92)" />
  </svg>
);

/* ── Account navigation icons ──────────────────────────────────────────────
 * Dedicated line icons for the account/settings menu (ACCOUNT_NAV), matching
 * the supplied design. Kept separate from the shared UserIcon/PinIcon/etc. so
 * swapping them here does not change those icons elsewhere in the app. Same
 * 24-viewBox / 1em sizing as every other icon, so they render at the current
 * nav icon size. */

/** Account · Profil — outlined person (head + shoulders). */
export const AccountProfileIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="8" r="3.2" />
    <path d="M5.7 19.8c.7-3.7 3.2-5.9 6.3-5.9s5.6 2.2 6.3 5.9" />
  </svg>
);

/** Account · Saved — bookmark. */
export const AccountSavedIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M6.5 4.3h11a1 1 0 0 1 1 1V20l-6.5-4.4L5.5 20V5.3a1 1 0 0 1 1-1Z" />
  </svg>
);

/** Account · Spots besucht — map pin with a centre dot. */
export const AccountVisitedIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M12 21c4-3.9 6-7.1 6-10.5a6 6 0 1 0-12 0c0 3.4 2 6.6 6 10.5Z" />
    <circle cx="12" cy="10.4" r="2" />
  </svg>
);

/** Account · Spots hinzufügen — stacked cards with a plus. */
export const AccountAddSpotsIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <rect x="3.8" y="7.6" width="12.4" height="12.4" rx="2.2" />
    <path d="M10 11v5.6M7.2 13.8h5.6" />
    <path d="M7.8 4.5h9.2a2.2 2.2 0 0 1 2.2 2.2V16" />
  </svg>
);

/** Account · Einstellungen — cog with a solid hub. */
export const AccountSettingsIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <g transform="translate(12 12) scale(0.86) translate(-12 -12)">
      <path d="M19.58 8.86 22.22 8.84 22.22 15.16 19.58 15.14 21.46 16.99 16.99 21.46 15.14 19.58 15.16 22.22 8.84 22.22 8.86 19.58 7.01 21.46 2.54 16.99 4.42 15.14 1.78 15.16 1.78 8.84 4.42 8.86 2.54 7.01 7.01 2.54 8.86 4.42 8.84 1.78 15.16 1.78 15.14 4.42 16.99 2.54 21.46 7.01Z" />
    </g>
    <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />
  </svg>
);

/** Sign out — door + arrow. */
export const LogoutIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="M16 17l5-5-5-5M21 12H9" />
  </svg>
);

/** Light theme — sun. */
export const SunIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

/** Dark theme — moon. */
export const MoonIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z" />
  </svg>
);

/** Delete / remove — trash can. */
export const TrashIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
  </svg>
);

/** Add / propose a spot — plus in a circle. */
export const PlusCircleIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v8M8 12h8" />
  </svg>
);

/** Check badge for sport labels; `checkOnly` removes the surrounding circle. */
export const CheckCircleIcon = ({ checkOnly = false, ...p }: IconProps & { checkOnly?: boolean }) => (
  <svg {...base} {...p} fill={checkOnly ? "none" : "currentColor"} stroke="none" viewBox="0 0 24 24">
    {!checkOnly && <circle cx="12" cy="12" r="10" />}
    <path d="M6.5 12.5 10.5 16.5 18 8.5" stroke={checkOnly ? "currentColor" : "white"} strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/** Chevron pointing left/right — gallery prev/next arrows. */
export const ChevronLeftIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M15 5l-7 7 7 7" />
  </svg>
);
export const ChevronRightIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M9 5l7 7-7 7" />
  </svg>
);
export const ListIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M8 6h13M8 12h13M8 18h13" />
    <path d="M3 6h.01M3 12h.01M3 18h.01" />
  </svg>
);

/* Sport glyphs — the uploaded artwork itself (PNG, black on transparent),
   for the search "Welche Sportart?" list. `dark:invert` flips them white on
   the dark surface; sizing/color props (className only) mirror the other
   icons so they drop into the same call sites. */
function SportGlyph({ src, className }: { src: string; className?: string }) {
  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      className={`inline-block h-[1em] w-[1em] object-contain align-[-0.125em] dark:invert ${className ?? ""}`}
    />
  );
}
export const SurfIcon = (p: IconProps) => <SportGlyph src={surfIconSrc} className={p.className} />;
export const KitesurfIcon = (p: IconProps) => <SportGlyph src={kiteIconSrc} className={p.className} />;
export const WindsurfIcon = (p: IconProps) => <SportGlyph src={windsurfIconSrc} className={p.className} />;
export const WingIcon = (p: IconProps) => <SportGlyph src={wingIconSrc} className={p.className} />;
