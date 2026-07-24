import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const VARIANT: Record<Variant, string> = {
  primary: "bg-teal text-white hover:bg-teal-hover",
  secondary: "bg-white text-teal ring-1 ring-teal/30 hover:ring-teal/50",
  ghost: "border border-teal/30 bg-white text-teal hover:bg-teal/5",
  danger: "bg-red-600 text-white hover:bg-red-700",
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
