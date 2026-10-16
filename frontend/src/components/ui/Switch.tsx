import type { ReactNode } from "react";

/**
 * The visual on/off track — exported on its own for rows where the whole row
 * is already the `role="switch"` button (e.g. the theme row in the menu).
 * Off: band track with a hairline. On: the brand blue with the thumb slid
 * across. 56×32 track, 24px thumb.
 */
export function SwitchTrack({ checked, icon }: { checked: boolean; icon?: ReactNode }) {
  return (
    <span
      aria-hidden="true"
      className={`relative inline-flex h-8 w-14 shrink-0 items-center rounded-full px-1 transition-colors duration-base ${
        checked ? "bg-teal" : "bg-band ring-1 ring-line"
      }`}
    >
      <span
        className={`grid h-6 w-6 place-items-center rounded-full bg-surface text-ink ring-1 ring-black/5 transition-transform duration-base motion-reduce:transition-none ${
          checked ? "translate-x-6" : "translate-x-0"
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
      className={`flex min-h-11 w-full items-center justify-between gap-4 text-left text-ui text-ink disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      <span className="min-w-0">
        {children}
        {description && <span className="mt-0.5 block text-caption text-muted">{description}</span>}
      </span>
      <SwitchTrack checked={checked} />
    </button>
  );
}
