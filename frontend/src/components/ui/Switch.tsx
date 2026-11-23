import type { ReactNode } from "react";

/**
 * The visual on/off track — exported on its own for rows where the whole row
 * is already the `role="switch"` button (e.g. the theme row in the menu).
 * Off: band track with a hairline. On: the brand blue with the thumb slid
 * across. 56×28 track, 24px thumb — 44px rows carry the touch target, so the
 * track itself can sit lower than the row without shrinking what you can hit.
 *
 * Motion, after the physical switch iOS models: the thumb travels on a curve
 * that overshoots a little and settles (`ease-switch`), while the track colour
 * crossfades on the shorter house duration — the colour has arrived before the
 * thumb does, so the state reads early and the movement finishes the sentence.
 * Held down, the thumb stretches toward the side it would travel to; it is the
 * one piece of this system that reacts to the press itself. That stretch needs
 * `group` on the button around it (all three callers set it).
 */
export function SwitchTrack({ checked, icon }: { checked: boolean; icon?: ReactNode }) {
  return (
    <span
      aria-hidden="true"
      className={`relative inline-flex h-7 w-14 shrink-0 items-center rounded-full px-1 transition-colors duration-base ${
        checked ? "bg-teal" : "bg-band ring-1 ring-line"
      }`}
    >
      <span
        className={`grid h-6 w-6 place-items-center rounded-full bg-surface text-ink ring-1 ring-black/5 transition-[transform,width] duration-slow ease-switch group-active:w-7 motion-reduce:transition-none ${
          checked ? "translate-x-6 group-active:translate-x-5" : "translate-x-0"
        }`}
      >
        {icon}
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
