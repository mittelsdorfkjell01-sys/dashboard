import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "icon";

// Every state is designed: rest, hover, pressed (a 2% press-in, switched off
// for reduced motion), keyboard focus (the global :focus-visible ring),
// disabled and loading. `rounded-lg` resolves to the one public 14px radius
// (the admin scope maps it back to its own 8px).
const BASE =
  "relative inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg font-semibold transition-[background-color,border-color,color,opacity,transform] active:scale-[0.98] motion-reduce:active:scale-100 disabled:cursor-not-allowed disabled:opacity-50 aria-busy:disabled:cursor-progress aria-busy:disabled:opacity-100";

// One filled primary style (Ink), used for every genuine main action (form
// submits, confirm dialogs, reload). Ink/surface are tokens, so the button
// inverts correctly in dark mode (light fill, dark text) and never relies on the
// restricted teal/orange accents. `ghost` preserves the old text-link look for
// buttons that are really links; `danger` is a destructive-action outline
// drawn from the status (danger) tokens — never orange, which is reserved for
// attention/brand use (wordmark, markers, best-season), not controls.
const VARIANT: Record<Variant, string> = {
  primary: "bg-ink text-surface hover:bg-ink-soft active:bg-ink-soft",
  secondary: "border border-line bg-surface text-ink hover:bg-band active:bg-band",
  ghost: "text-ink hover:underline hover:underline-offset-4 hover:opacity-70 active:opacity-60",
  danger: "border border-danger-border text-danger hover:bg-danger-bg active:bg-danger-bg",
};

const SIZE: Record<Size, string> = {
  sm: "px-3 py-1.5 text-ui",
  md: "px-4 py-2 text-ui",
  // Square 44px target for a lone icon. Always pass an `aria-label`.
  icon: "w-11 p-0 text-ui",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  /** Shows a spinner, sets aria-busy and blocks further clicks. The label
   *  stays in the layout (invisible) under the spinner, so the button keeps
   *  its width, and a busy button is not greyed out like a disabled one. */
  loading?: boolean;
};

/** Atom: button. Keyboard focus is handled by the global :focus-visible token. */
const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = "primary", size = "md", type = "button", loading = false, disabled, className = "", children, ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${BASE} ${VARIANT[variant]} ${SIZE[size]} ${className}`}
      {...props}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="absolute h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none"
        />
      )}
      <span className={`inline-flex items-center gap-1.5 ${loading ? "opacity-0" : ""}`}>{children}</span>
    </button>
  )
);
Button.displayName = "Button";
export default Button;
