// Admin-scoped UI primitives — the monochrome, token-driven building blocks for
// the back office. These are separate from the shared src/components/ui/* set
// (used by the public site) so the admin can carry its own visual identity and
// dark mode without touching public styling. All colors come from the admin
// tokens (see admin-theme.css); never hard-code hex here.

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

/* ------------------------------------------------------------------------- */
/* Button — the single admin button. A fixed variant set with identical       */
/* geometry (height, padding, radius, type ramp); variants differ only in     */
/* colour/emphasis, never in size. Keyboard focus comes from the global       */
/* :focus-visible token. Use `block` for full-width; add `min-h-11` via       */
/* className for primary touch targets on mobile bars.                        */
/* ------------------------------------------------------------------------- */
export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

const BTN_BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-label font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const BTN_VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-admin-primary text-admin-primary-fg hover:bg-admin-primary-hover",
  secondary:
    "border border-admin-border bg-admin-surface text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg",
  ghost: "text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg",
  destructive:
    "border border-admin-danger-border bg-admin-danger-bg text-admin-danger hover:brightness-110",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; block?: boolean }
>(({ variant = "secondary", block = false, type = "button", className = "", ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    className={`${BTN_BASE} ${BTN_VARIANT[variant]} ${block ? "w-full" : ""} ${className}`}
    {...props}
  />
));
Button.displayName = "AdminButton";

/* ------------------------------------------------------------------------- */
/* Page header — screen-reader title plus optional right-aligned actions.    */
/* ------------------------------------------------------------------------- */
export function PageHeader({
  title,
  actions,
  className = "",
}: {
  title: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <>
      <h1 className="sr-only">{title}</h1>
      {actions && (
        <div className={`mb-4 flex flex-wrap items-center justify-end gap-2 ${className}`}>
          {actions}
        </div>
      )}
    </>
  );
}
/* ------------------------------------------------------------------------- */
/* Badge / status — small indicator dot + text. Color is never the only cue: */
/* the label always carries the meaning.                                     */
/* ------------------------------------------------------------------------- */
export type BadgeTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "primary";

const BADGE_TONE: Record<BadgeTone, { wrap: string; dot: string }> = {
  neutral: {
    wrap: "bg-admin-hover text-admin-fg2 border-admin-border",
    dot: "bg-admin-faint",
  },
  success: {
    wrap: "bg-admin-success-bg text-admin-success border-admin-success-border",
    dot: "bg-admin-success",
  },
  warning: {
    wrap: "bg-admin-warning-bg text-admin-warning border-admin-warning-bg",
    dot: "bg-admin-warning",
  },
  danger: {
    wrap: "bg-admin-danger-bg text-admin-danger border-admin-danger-border",
    dot: "bg-admin-danger",
  },
  info: {
    wrap: "bg-admin-info-bg text-admin-info border-admin-info-bg",
    dot: "bg-admin-info",
  },
  primary: {
    wrap: "bg-admin-primary-bg text-admin-primary border-admin-primary-bg",
    dot: "bg-admin-primary",
  },
};

export function Badge({
  tone = "neutral",
  dot = true,
  children,
  className = "",
}: {
  tone?: BadgeTone;
  dot?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const t = BADGE_TONE[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-caption font-medium ${t.wrap} ${className}`}
    >
      {dot && (
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${t.dot}`}
        />
      )}
      {children}
    </span>
  );
}
