/**
 * Design token — shared anatomy for Checkbox and Radio: a native input (so
 * keyboard, form and screen-reader behaviour are the browser's own), drawn
 * in the brand blue (see the drawn variant below), sized to 20px, next to a
 * label that is itself the click target. The global :focus-visible rule draws the ring.
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

/**
 * Drawn variant (chosen 2026-11-24, "Fläche füllt sich"): the native input
 * stays the real control — focusable, in the form, announced as before — but
 * draws only its outline (`appearance-none`). The brand-blue fill grows from
 * the centre over 150ms on the layer above it, then the check (or radio dot)
 * fades in 90ms later. A native checkbox cannot animate its own tick.
 *
 * The 6px corner is deliberate: at 20px the shared 14px card radius would turn
 * the box into a circle, and a round box reads as a radio.
 */
export const choiceFrame = "relative grid h-5 w-5 shrink-0 place-items-center";
export const choiceBox =
  "peer m-0 h-5 w-5 cursor-pointer appearance-none border-[1.5px] border-muted bg-surface transition-colors duration-fast checked:border-teal disabled:cursor-not-allowed";
export const choiceFill =
  "pointer-events-none absolute inset-0 scale-0 bg-teal transition-transform duration-fast peer-checked:scale-100 motion-reduce:transition-none";
export const choiceMark =
  "pointer-events-none absolute opacity-0 transition-opacity duration-fast peer-checked:opacity-100 peer-checked:delay-[90ms] motion-reduce:transition-none";
