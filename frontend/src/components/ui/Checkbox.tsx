import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { choiceInput, choiceLabel, type ChoiceLayout } from "./choiceClass";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "children"> & {
  /** Label content. May contain inline controls (e.g. a "terms" link button). */
  children: ReactNode;
  /** Optional secondary line under the label. */
  description?: ReactNode;
  layout?: ChoiceLayout;
  /** Classes for the outer label (spacing in its parent). */
  className?: string;
};

/** Atom: checkbox with its label. Native input, brand-tinted, 20px. */
const Checkbox = forwardRef<HTMLInputElement, Props>(
  ({ children, description, layout = "plain", className = "", ...props }, ref) => (
    <label className={`${choiceLabel[layout]} ${className}`}>
      <input ref={ref} type="checkbox" className={`${choiceInput} ${layout === "plain" ? "mt-px" : ""}`} {...props} />
      <span className="min-w-0">
        {children}
        {description && <span className="mt-0.5 block text-caption text-muted">{description}</span>}
      </span>
    </label>
  )
);
Checkbox.displayName = "Checkbox";
export default Checkbox;
