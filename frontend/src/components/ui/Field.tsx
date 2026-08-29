import { cloneElement, isValidElement, useId } from "react";
import type { ReactElement, ReactNode } from "react";

/**
 * Molecule: a labelled form row (label + control + hint/error). The control is
 * nested inside the <label>, so clicking the label focuses the field. An
 * optional required marker and an error slot keep validation consistent.
 *
 * When a single element is passed as the control, its hint/error text is wired
 * up with `aria-describedby` (+ `aria-invalid` on error) automatically, so
 * screen readers announce the message in the field's context — no per-call-site
 * plumbing needed.
 */
export default function Field({
  label,
  children,
  hint,
  error,
  required,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  error?: string;
  required?: boolean;
}) {
  const id = useId();
  const errId = `${id}-err`;
  const hintId = `${id}-hint`;
  const describedBy = error ? errId : hint ? hintId : undefined;

  const control =
    isValidElement(children) && describedBy
      ? cloneElement(children as ReactElement<Record<string, unknown>>, {
          "aria-describedby": describedBy,
          ...(error ? { "aria-invalid": true } : {}),
        })
      : children;

  return (
    <label className="block min-w-0">
      <span className="text-label font-medium text-ink">
        {label}
        {required && (
          <span className="ml-0.5 text-danger" aria-hidden="true">
            *
          </span>
        )}
      </span>
      <div className="mt-1.5 min-h-10">{control}</div>
      {hint && !error && (
        <p id={hintId} className="mt-1 text-caption text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errId} role="alert" className="mt-1 text-caption font-medium text-danger">
          {error}
        </p>
      )}
    </label>
  );
}
