import type { ReactNode } from "react";

const DROPCAP =
  "first-letter:float-left first-letter:mr-3 first-letter:mt-1 first-letter:text-[4.5rem] " +
  "first-letter:font-semibold first-letter:leading-[0.78] first-letter:text-ink";

/**
 * The editorial lede — a wide, comfortable reading column for the spot/region
 * write-up. Capped at ~68ch, larger type, relaxed leading. Falls back to a quiet
 * placeholder when there is no copy.
 *
 * `dropcap` renders an oversized initial letter (the cheapest magazine
 * signature there is) — only applied when there's real string copy, never on
 * the placeholder or on non-text `children`. Defaults to `false` so
 * `RegionDetail` (which never passes it) is unaffected.
 */
export default function Lede({
  children,
  dropcap = false,
}: {
  children?: ReactNode;
  dropcap?: boolean;
}) {
  const applyDropcap = dropcap && typeof children === "string" && children.length > 0;
  return (
    <div
      className={`max-w-[68ch] text-lede leading-relaxed text-ink-soft text-pretty ${
        applyDropcap ? DROPCAP : ""
      }`}
    >
      {children ? (
        children
      ) : (
        <span className="text-muted">Noch keine Beschreibung hinterlegt.</span>
      )}
    </div>
  );
}
