// Admin-scoped UI primitives — the monochrome, token-driven building blocks for
// the back office. These are separate from the shared src/components/ui/* set
// (used by the public site) so the admin can carry its own visual identity and
// dark mode without touching public styling. All colors come from the admin
// tokens (see admin-theme.css); never hard-code hex here.

import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { SearchIcon } from "../../../lib/icons";

/* ------------------------------------------------------------------------- */
/* Button — the single admin button. A fixed variant set with identical       */
/* geometry (height, padding, radius, type ramp); variants differ only in     */
/* colour/emphasis, never in size. Keyboard focus comes from the global       */
/* :focus-visible token. Use `block` for full-width; add `min-h-11` via       */
/* className for primary touch targets on mobile bars.                        */
/* ------------------------------------------------------------------------- */
export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

const BTN_BASE =
  "admin-button-control inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-label font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

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

/* A router <Link> that wears the exact Button geometry + variant colours, so a
   navigating action ("Neuer Spot", "Bearbeiten") is visually identical to a
   real Button and never drifts into hand-rolled inline styling. */
export const ButtonLink = forwardRef<
  HTMLAnchorElement,
  LinkProps & { variant?: ButtonVariant; block?: boolean }
>(({ variant = "secondary", block = false, className = "", ...props }, ref) => (
  <Link
    ref={ref}
    className={`${BTN_BASE} ${BTN_VARIANT[variant]} ${block ? "w-full" : ""} ${className}`}
    {...props}
  />
));
ButtonLink.displayName = "AdminButtonLink";

/* ------------------------------------------------------------------------- */
/* Field token + search input — one definition for every text-like admin      */
/* control (inputs, selects). Focus shows only as a border-colour change to    */
/* admin-primary; deliberately NO ring/box-shadow, so the stroke never         */
/* thickens on activation. All colours come from admin tokens (dark-mode safe).*/
/* ------------------------------------------------------------------------- */
export const adminFieldClass =
  "admin-field-control h-9 rounded-md border border-admin-border-strong bg-admin-surface px-3 text-ui text-admin-fg outline-none transition-colors placeholder:text-admin-faint focus:border-admin-primary disabled:cursor-not-allowed disabled:opacity-50";

/** The single admin search field: always carries a placeholder and the shared
 *  field geometry, with a leading magnifier. Focus = border colour only. */
export const SearchInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { placeholder?: string }
>(({ placeholder = "Suchen …", className = "", ...props }, ref) => (
  <div className={`relative ${className}`}>
    <SearchIcon
      aria-hidden
      className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sz-16 text-admin-faint"
    />
    <input
      ref={ref}
      type="search"
      placeholder={placeholder}
      className={`${adminFieldClass} w-full pl-8`}
      {...props}
    />
  </div>
));
SearchInput.displayName = "AdminSearchInput";

/** Plain single-line admin text field (name/URL/credit-style inputs). Same
 *  geometry and focus behaviour as `SearchInput`, without the magnifier. */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ type = "text", className = "", ...props }, ref) => (
    <input ref={ref} type={type} className={`${adminFieldClass} w-full ${className}`} {...props} />
  )
);
Input.displayName = "AdminInput";

/** Plain multi-line admin text field. Same field token as `Input`, sized by
 *  the caller via `className` (e.g. `min-h-[120px] resize-y`). */
export const Textarea = forwardRef<
  HTMLTextAreaElement,
  import("react").TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className = "", ...props }, ref) => (
  <textarea ref={ref} className={`${adminFieldClass} h-auto w-full py-2 ${className}`} {...props} />
));
Textarea.displayName = "AdminTextarea";

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
