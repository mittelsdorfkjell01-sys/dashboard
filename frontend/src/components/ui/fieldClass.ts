/**
 * Design token — the shared visual definition for every text-like form control
 * (input / select / textarea). One source of truth so all fields look and,
 * crucially, *focus* identically: a visible neutral ring on keyboard focus
 * (WCAG 2.4.7) instead of the old outline-none-with-no-replacement pattern.
 *
 * The control font is 16px on phones and settles to the 14px UI token from
 * `sm` up: iOS Safari auto-zooms the page whenever a focused field is under
 * 16px, so keeping phone inputs at 16px stops that jarring zoom-in on tap
 * while leaving the denser desktop sizing untouched. A touch screen wider
 * than `sm` (tablet, phone held sideways) keeps 16px through the
 * `pointer: coarse` rule in index.css.
 */
export const fieldClass =
  "min-h-11 w-full rounded-lg border border-line bg-surface px-3 py-2 text-body sm:text-ui text-ink placeholder:text-muted outline-none transition-[border-color,background-color] hover:border-muted disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-danger-border aria-[invalid=true]:ring-1 aria-[invalid=true]:ring-danger-border";
