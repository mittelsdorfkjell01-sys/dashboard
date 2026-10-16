/**
 * Design token — shared anatomy for Checkbox and Radio: a native input (so
 * keyboard, form and screen-reader behaviour are the browser's own) tinted
 * with the brand blue via `accent-color`, sized to 20px, next to a label that
 * is itself the click target. The global :focus-visible rule draws the ring.
 *
 *  row   — the label as a full-width 44px row with a hover wash (option lists
 *          in filter/sort panels)
 *  plain — label text flows at its natural height, aligned to the first line
 *          (consent statements, inline settings)
 */
export const choiceLabel = {
  plain:
    "flex cursor-pointer items-start gap-3 text-ui text-ink has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50",
  row:
    "flex min-h-11 cursor-pointer items-center gap-3 rounded-card px-2 py-1.5 text-ui text-ink transition-colors hover:bg-ink/[0.06] has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50",
} as const;

export type ChoiceLayout = keyof typeof choiceLabel;

export const choiceInput = "h-5 w-5 shrink-0 cursor-pointer accent-teal disabled:cursor-not-allowed";
