// Admin-scoped UI primitives — the monochrome, token-driven building blocks for
// the back office. These are separate from the shared src/components/ui/* set
// (used by the public site) so the admin can carry its own visual identity and
// dark mode without touching public styling. All colors come from the admin
// tokens (see admin-theme.css); never hard-code hex here.

import type { ReactNode } from "react";

/* ------------------------------------------------------------------------- */
/* Page header — one compact title plus right-aligned actions.               */
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
    <div
      className={`mb-6 flex flex-col gap-3 border-b border-admin-border pb-5 sm:flex-row sm:items-start sm:justify-between ${className}`}
    >
      <div className="min-w-0">
        <h1 className="text-[22px] font-semibold leading-tight text-admin-fg">
          {title}
        </h1>
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
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
