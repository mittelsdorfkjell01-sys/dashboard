import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const BASE =
  "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50";

// One filled primary style (Ink), used for every genuine main action (form
// submits, confirm dialogs, reload). Ink/surface are tokens, so the button
// inverts correctly in dark mode (light fill, dark text) and never relies on the
// restricted teal/orange accents. `ghost` preserves the old text-link look for
// buttons that are really links; `danger` keeps orange as an accent outline
// (never a fill) per the accent rules.
const VARIANT: Record<Variant, string> = {
  primary: "bg-ink text-surface hover:bg-ink-soft",
  secondary: "border border-line bg-surface text-ink hover:bg-band",
  ghost: "text-ink hover:underline hover:underline-offset-4 hover:opacity-70",
  danger: "border border-orange text-orange hover:bg-orange/10",
};

const SIZE: Record<Size, string> = {
  sm: "px-3 py-1.5 text-label",
  md: "px-4 py-2 text-ui",
};

/** Atom: button. Keyboard focus is handled by the global :focus-visible token. */
const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }
>(({ variant = "primary", size = "md", type = "button", className = "", ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    className={`${BASE} ${VARIANT[variant]} ${SIZE[size]} ${className}`}
    {...props}
  />
));
Button.displayName = "Button";
export default Button;
