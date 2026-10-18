// Admin-scoped UI primitives — the monochrome, token-driven building blocks for
// the back office. These are separate from the shared src/components/ui/* set
// (used by the public site) so the admin can carry its own visual identity and
// its own light/dark themes without touching public styling. All colours come
// from the admin tokens (see admin-theme.css); never hard-code hex here, or the
// primitive will be wrong in one of the two themes.

import {
  forwardRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TableHTMLAttributes,
  type TdHTMLAttributes,
  type ThHTMLAttributes,
} from "react";
import { Link, NavLink, type LinkProps, type NavLinkProps } from "react-router-dom";
import { SearchIcon } from "../../../lib/icons";
import { useAdminTheme } from "../theme";

/* ------------------------------------------------------------------------- */
/* Button — the single admin button. A fixed variant set with identical       */
/* geometry (height, padding, radius, type ramp); variants differ only in     */
/* colour/emphasis, never in size. Keyboard focus comes from the global       */
/* :focus-visible token. Use `block` for full-width; add `min-h-11` via       */
/* className for primary touch targets on mobile bars.                        */
/* ------------------------------------------------------------------------- */
export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

const BTN_BASE =
  "admin-button-control inline-flex h-9 items-center justify-center gap-1.5 rounded-md px-3 text-label font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const BTN_VARIANT: Record<ButtonVariant, string> = {
  // Monochrome primary: solid near-black on light, solid near-white on dark.
  primary: "bg-admin-primary text-admin-primary-fg hover:bg-admin-primary-hover",
  secondary:
    "border border-admin-border bg-admin-surface text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg",
  ghost: "text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg",
  destructive:
    "border border-admin-danger-border bg-admin-danger-bg text-admin-danger hover:brightness-105",
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
/* IconButton — a square, icon-only control for toolbars and card headers     */
/* (theme toggle, overflow menus, row actions). Same colour vocabulary as     */
/* Button; an accessible label is required because there is no visible text.  */
/* ------------------------------------------------------------------------- */
export const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant;
    label: string;
  }
>(({ variant = "ghost", label, type = "button", className = "", ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    aria-label={label}
    title={label}
    className={`admin-button-control inline-grid h-9 w-9 place-items-center rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${BTN_VARIANT[variant]} ${className}`}
    {...props}
  />
));
IconButton.displayName = "AdminIconButton";

/* ------------------------------------------------------------------------- */
/* Field token + text controls — one definition for every text-like admin     */
/* control (inputs, selects, textareas). Focus shows only as a border-colour   */
/* change to admin-primary; deliberately NO ring/box-shadow, so the stroke     */
/* never thickens on activation. All colours come from admin tokens.          */
/* ------------------------------------------------------------------------- */
export const adminFieldClass =
  "admin-field-control h-9 rounded-md border border-admin-border-strong bg-admin-surface px-3 text-ui text-admin-fg outline-none transition-colors placeholder:text-admin-muted focus:border-admin-primary disabled:cursor-not-allowed disabled:opacity-50";

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

/** Native <select> on the shared field token. `color-scheme` on the scope makes
 *  the dropdown itself render in the active theme, so no custom listbox is
 *  needed for the back office.
 *
 *  Unlike `Input`, the width is NOT baked in: a select is as often a compact
 *  filter in a toolbar as it is a full-width form field, and a baked `w-full`
 *  cannot be overridden from `className` (the loser is decided by stylesheet
 *  order, not by the order of the class attribute). Callers that want a full
 *  width pass `w-full` themselves. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className = "", ...props }, ref) => (
    <select ref={ref} className={`${adminFieldClass} pr-8 ${className}`} {...props} />
  )
);
Select.displayName = "AdminSelect";

/** The label above a field. One definition so forms stop drifting between
 *  text-caption/text-label and medium/semibold. */
export function FieldLabel({
  children,
  className = "",
  ...props
}: HTMLAttributes<HTMLLabelElement> & { htmlFor?: string }) {
  return (
    <label
      className={`mb-1.5 block text-label font-medium text-admin-fg2 ${className}`}
      {...props}
    >
      {children}
    </label>
  );
}

/* ------------------------------------------------------------------------- */
/* Card — the standard admin surface: hairline border, 10px corner, no        */
/* shadow (elevation in this system comes from the border + canvas contrast,  */
/* shadows are reserved for popovers and dialogs).                            */
/* ------------------------------------------------------------------------- */
export function Card({
  children,
  padded = true,
  className = "",
  ...props
}: HTMLAttributes<HTMLDivElement> & { padded?: boolean }) {
  return (
    <div
      className={`rounded-lg border border-admin-border bg-admin-surface ${padded ? "p-4" : ""} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

/** Card header: title on the left, optional actions on the right, divider
 *  below. Use inside an unpadded <Card> so the divider spans the full width. */
export function CardHeader({
  title,
  description,
  actions,
  className = "",
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 border-b border-admin-border px-4 py-3 ${className}`}
    >
      <div className="min-w-0">
        <h2 className="truncate text-label font-semibold text-admin-fg">{title}</h2>
        {description && <p className="mt-0.5 text-caption text-admin-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Page header — the page title, optional description, and right-aligned      */
/* actions. The title is visible (the back office reads as a product, not as  */
/* a set of unlabelled panels); pass `srOnly` where a page already repeats it. */
/* ------------------------------------------------------------------------- */
export function PageHeader({
  title,
  description,
  actions,
  srOnly = false,
  className = "",
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  srOnly?: boolean;
  className?: string;
}) {
  if (srOnly) {
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

  return (
    <div
      className={`mb-5 flex flex-wrap items-end justify-between gap-x-4 gap-y-3 ${className}`}
    >
      <div className="min-w-0">
        <h1 className="text-sz-24 font-semibold tracking-[-0.01em] text-admin-fg">{title}</h1>
        {description && (
          <p className="mt-1 max-w-measure text-label text-admin-muted">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Tabs — a row of route links under the page header, marking the active one  */
/* with an underline rather than a filled pill (quieter, and it survives both  */
/* themes without a tinted surface).                                          */
/* ------------------------------------------------------------------------- */
export function TabBar({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`-mt-1 mb-5 flex gap-1 border-b border-admin-border ${className}`}>
      {children}
    </div>
  );
}

const TAB_BASE =
  "relative -mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-label font-medium transition-colors";

export function Tab({ className = "", ...props }: NavLinkProps) {
  return (
    <NavLink
      className={({ isActive }) =>
        `${TAB_BASE} ${
          isActive
            ? "border-admin-primary text-admin-fg"
            : "border-transparent text-admin-muted hover:border-admin-border-strong hover:text-admin-fg"
        } ${className}`
      }
      {...props}
    />
  );
}

/** The same tab look for in-page state that is not a route. */
export function TabButton({
  active,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <button
      type="button"
      aria-current={active ? "page" : undefined}
      className={`${TAB_BASE} ${
        active
          ? "border-admin-primary text-admin-fg"
          : "border-transparent text-admin-muted hover:border-admin-border-strong hover:text-admin-fg"
      } ${className}`}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------------- */
/* Table — the admin data table. Wrap in <TableFrame> for the bordered,       */
/* rounded, horizontally scrollable card the reference dashboards use.        */
/* ------------------------------------------------------------------------- */
export function TableFrame({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-lg border border-admin-border bg-admin-surface ${className}`}
    >
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

export function Table({ className = "", ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={`w-full border-collapse text-label ${className}`} {...props} />;
}

export function Thead({ className = "", ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={`bg-admin-hover ${className}`} {...props} />;
}

export function Th({ className = "", ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={`whitespace-nowrap border-b border-admin-border px-4 py-2.5 text-left text-caption font-semibold text-admin-muted ${className}`}
      {...props}
    />
  );
}

export function Tbody({ className = "", ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={`divide-y divide-admin-border ${className}`} {...props} />;
}

export function Tr({
  className = "",
  interactive = false,
  ...props
}: HTMLAttributes<HTMLTableRowElement> & { interactive?: boolean }) {
  return (
    <tr
      className={`${interactive ? "transition-colors hover:bg-admin-hover" : ""} ${className}`}
      {...props}
    />
  );
}

export function Td({ className = "", ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`px-4 py-2.5 align-middle text-admin-fg2 ${className}`} {...props} />;
}

/* ------------------------------------------------------------------------- */
/* Stat tile — a single number with its label. The number stays quiet by      */
/* design so a prioritised task list always wins the squint test over a row   */
/* of counters.                                                               */
/* ------------------------------------------------------------------------- */
export function StatTile({
  label,
  value,
  to,
  tone = "neutral",
  hint,
}: {
  label: ReactNode;
  value: ReactNode;
  to?: string;
  tone?: "neutral" | "success" | "warning" | "danger";
  hint?: ReactNode;
}) {
  const valueTone = {
    neutral: "text-admin-fg",
    success: "text-admin-success",
    warning: "text-admin-warning",
    danger: "text-admin-danger",
  }[tone];

  const body = (
    <>
      <div className="text-caption text-admin-muted">{label}</div>
      <div className={`admin-mono mt-1.5 text-sz-22 font-semibold leading-none ${valueTone}`}>
        {value}
      </div>
      {hint && <div className="mt-1.5 text-caption text-admin-faint">{hint}</div>}
    </>
  );

  const shell = "rounded-lg border border-admin-border bg-admin-surface p-4";
  return to ? (
    <Link
      to={to}
      className={`${shell} block transition-colors hover:border-admin-border-strong hover:bg-admin-hover`}
    >
      {body}
    </Link>
  ) : (
    <div className={shell}>{body}</div>
  );
}

/* ------------------------------------------------------------------------- */
/* Empty state — one definition for "nothing here yet" across lists, tables   */
/* and panels, so they stop drifting between a bare <p> and a bordered box.   */
/* ------------------------------------------------------------------------- */
export function EmptyState({
  title,
  description,
  action,
  className = "",
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`px-4 py-10 text-center ${className}`}>
      <p className="text-label font-medium text-admin-fg2">{title}</p>
      {description && (
        <p className="mx-auto mt-1 max-w-measure text-caption text-admin-muted">{description}</p>
      )}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Theme toggle — light ⇄ dark, light being the default. Lives in the admin   */
/* top bar. The icon shows the theme you would switch TO, which is the        */
/* convention operators expect from the reference dashboards.                 */
/* ------------------------------------------------------------------------- */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useAdminTheme();
  // Spelled out rather than composed: "dunkel" elides to "dunklem", so building
  // the label from the adjective yields "dunkelem".
  const label =
    theme === "dark" ? "Zu hellem Design wechseln" : "Zu dunklem Design wechseln";

  return (
    <IconButton
      variant="ghost"
      label={label}
      aria-pressed={theme === "dark"}
      onClick={toggleTheme}
      className={className}
    >
      {theme === "dark" ? (
        /* Sun — switch to light. */
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-[18px] w-[18px]">
          <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.6" />
          <path
            d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.1 5.1l1.4 1.4M17.5 17.5l1.4 1.4M18.9 5.1l-1.4 1.4M6.5 17.5l-1.4 1.4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      ) : (
        /* Moon — switch to dark. */
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-[18px] w-[18px]">
          <path
            d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </IconButton>
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
    wrap: "bg-admin-warning-bg text-admin-warning border-admin-warning-border",
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
  // `primary` is monochrome in this system: a neutral chip with a solid
  // foreground-coloured dot, used where a count is notable but not a status.
  primary: {
    wrap: "bg-admin-primary-bg text-admin-fg border-admin-border",
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
