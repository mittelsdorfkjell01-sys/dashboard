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

export const PinIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none">
    <path d="M12 2c3.87 0 7 3.13 7 7 0 4.87-7 13-7 13S5 13.87 5 9c0-3.87 3.13-7 7-7Z" />
    <circle cx="12" cy="9" r="2.6" fill="#fff" />
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

/** Facility: parking — compact front view, no enclosing icon tile. */
export const ParkingIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="m6.5 10 1.3-4h8.4l1.3 4" />
    <path d="M5 10h14a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V11a1 1 0 0 1 1-1Z" />
    <path d="M7 18.5V21M17 18.5V21M7.5 14h.01M16.5 14h.01M9.5 17h5" />
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

/** Facility: shower — wall arm, head and evenly spaced water drops. */
export const ShowerIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M4 21V8a4 4 0 0 1 7.6-1.7" />
    <path d="m11 8 4.5-3 3 4.5-5 2.2L11 8Z" />
    <path d="M11.5 14.5v1M15 14v1M18.5 13.5v1M13 18v1M17 17.5v1" />
  </svg>
);

/** Facility: gastronomy — a simple café cup with steam. */
export const FoodIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M5 9h11v4.5a5.5 5.5 0 0 1-11 0V9Z" />
    <path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16M4 21h15" />
    <path d="M8 6c-1-1 .8-1.8 0-3M12 6c-1-1 .8-1.8 0-3" />
  </svg>
);

/** Facility: camping — pitched tent, entrance and ground line. */
export const CampingIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <path d="M12 3.5 3.5 19h17L12 3.5Z" />
    <path d="M12 3.5V19M8.5 19l3.5-6 3.5 6M2.5 21h19" />
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

/** Account settings — a gear. */
export const GearIcon = (p: IconProps) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.3a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.3 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 7 2.7h.1A1.7 1.7 0 0 0 8.3 1V.9a2 2 0 1 1 4 0V1a1.7 1.7 0 0 0 1.2 1.7 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 21.3 8H21a1.7 1.7 0 0 0 0 4h.1a1.7 1.7 0 0 0 1.2 1z" transform="translate(1 1) scale(0.92)" />
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

/** Filled check-in-circle badge — sport chips ("Kitesurfen ✓"). */
export const CheckCircleIcon = (p: IconProps) => (
  <svg {...base} {...p} fill="currentColor" stroke="none" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" />
    <path d="M8 12.5l2.5 2.5L16 9.5" stroke="white" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
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
