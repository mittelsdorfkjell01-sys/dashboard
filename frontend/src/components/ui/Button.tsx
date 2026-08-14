import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const BASE =
  "inline-flex min-h-11 items-center justify-center gap-1.5 font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70 disabled:cursor-not-allowed disabled:opacity-50";

const VARIANT: Record<Variant, string> = {
  primary: "",
  secondary: "",
  ghost: "",
  danger: "",
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
