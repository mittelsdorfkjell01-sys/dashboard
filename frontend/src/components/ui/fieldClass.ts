/**
 * Design token — the shared visual definition for every text-like form control
 * (input / select / textarea). One source of truth so all fields look and,
 * crucially, *focus* identically: a visible teal ring on keyboard focus
 * (WCAG 2.4.7) instead of the old outline-none-with-no-replacement pattern.
 */
export const fieldClass =
  "min-h-11 w-full rounded-lg border border-line bg-white px-3 py-2 text-ui text-ink placeholder:text-muted outline-none transition-[border-color,box-shadow,background-color] hover:border-teal/30 focus-visible:border-teal/50 focus-visible:ring-2 focus-visible:ring-teal/30 disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-red-400 aria-[invalid=true]:ring-1 aria-[invalid=true]:ring-red-300";
