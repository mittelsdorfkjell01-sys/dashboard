import type { ReactNode } from "react";

/**
 * The visual on/off track — exported on its own for rows where the whole row
 * is already the `role="switch"` button (e.g. the theme row in the menu).
 * Off: band track with a hairline. On: the brand blue with the thumb slid
 * across. 56×28 track, 24px thumb — 44px rows carry the touch target, so the
 * track itself can sit lower than the row without shrinking what you can hit.
 *
 * Motion — three parts, all within 240ms (chosen 2026-11-24):
 *  - the thumb travels on a curve that overshoots a little and settles
 *    (`ease-switch`), like a physical toggle snapping in;
 *  - the brand blue fills the track from the left behind it, on the house
 *    curve, so the colour is "pulled along" by the thumb;
 *  - the symbol inside the thumb hands over: the outgoing one turns (icons)
 *    or slides (text such as DE/EN) out while the next one comes in.
 * Held down, the thumb stretches toward the side it would travel to; that
 * stretch needs `group` on the button around it (all three callers set it).
 * Reduced motion: no travel animation, no fill sweep, symbols just swap.
 */
export function SwitchTrack({
  checked,
  icon,
  icons,
}: {
  checked: boolean;
  /** One symbol that stays the same in both states. */
  icon?: ReactNode;
  /** A symbol per state; the handover animates. `motion: "turn"` for
   *  icons, `"slide"` for short text. Takes precedence over `icon`. */
  icons?: { off: ReactNode; on: ReactNode; motion?: "turn" | "slide" };
}) {
  const turn = (icons?.motion ?? "turn") === "turn";
  const hidden = (forward: boolean) =>
    turn
      ? `opacity-0 scale-50 ${forward ? "rotate-90" : "-rotate-90"}`
      : `opacity-0 ${forward ? "-translate-y-3" : "translate-y-3"}`;
  const shown = turn ? "opacity-100 scale-100 rotate-0" : "opacity-100 translate-y-0";
  const symbolClass =
    "absolute inset-0 grid place-items-center transition-[opacity,transform] duration-base motion-reduce:transition-none";

  return (
    <span
      aria-hidden="true"
      className={`relative inline-flex h-7 w-14 shrink-0 items-center overflow-hidden rounded-full bg-band px-1 ring-1 transition-shadow duration-fast ${
        checked ? "ring-transparent" : "ring-line"
      }`}
    >
      <span
        data-part="switch-fill"
        className={`absolute inset-0 origin-left rounded-full bg-teal transition-transform duration-base motion-reduce:transition-none ${
          checked ? "scale-x-100" : "scale-x-0"
        }`}
      />
      <span
        data-part="switch-thumb"
        className={`relative grid h-6 w-6 place-items-center overflow-hidden rounded-full bg-surface text-ink ring-1 ring-black/5 transition-[transform,width] duration-[240ms] ease-switch group-active:w-7 motion-reduce:transition-none ${
          checked ? "translate-x-6 group-active:translate-x-5" : "translate-x-0"
        }`}
      >
        {icons ? (
          <>
            <span className={`${symbolClass} ${checked ? hidden(true) : shown}`}>{icons.off}</span>
            <span className={`${symbolClass} ${checked ? shown : hidden(false)}`}>{icons.on}</span>
          </>
        ) : (
          icon
        )}
      </span>
    </span>
  );
}

/**
 * Atom: a setting that takes effect immediately (no "save"). Use a Checkbox
 * instead when the choice is submitted with a form. The full row — label and
 * track — is one 44px+ button with `role="switch"`.
 */
export default function Switch({
  checked,
  onChange,
  children,
  description,
  disabled,
  className = "",
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  children: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`group flex min-h-11 w-full items-center justify-between gap-4 text-left text-ui text-ink disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      <span className="min-w-0">
        {children}
        {description && <span className="mt-0.5 block text-caption text-muted">{description}</span>}
      </span>
      <SwitchTrack checked={checked} />
    </button>
  );
}
