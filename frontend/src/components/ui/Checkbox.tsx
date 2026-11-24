import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { choiceBox, choiceFill, choiceFrame, choiceLabel, choiceMark, type ChoiceLayout } from "./choiceClass";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "children"> & {
  /** Label content. May contain inline controls (e.g. a "terms" link button). */
  children: ReactNode;
  /** Optional secondary line under the label. */
  description?: ReactNode;
  layout?: ChoiceLayout;
  /** Classes for the outer label (spacing in its parent). */
  className?: string;
};

/** Atom: checkbox with its label. Native input, drawn box, 20px (see choiceClass). */
const Checkbox = forwardRef<HTMLInputElement, Props>(
  ({ children, description, layout = "plain", className = "", ...props }, ref) => (
    <label className={`${choiceLabel[layout]} ${className}`}>
      <span className={`${choiceFrame} ${layout === "plain" ? "mt-px" : ""}`}>
        <input ref={ref} type="checkbox" className={`${choiceBox} rounded-[6px]`} {...props} />
        <span aria-hidden="true" className={`${choiceFill} rounded-[6px]`} />
        <svg aria-hidden="true" viewBox="0 0 16 16" className={`${choiceMark} h-3.5 w-3.5 text-white`} fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3.5 8.5l3 3 6-7" />
        </svg>
      </span>
      <span className="min-w-0">
        {children}
        {description && <span className="mt-0.5 block text-caption text-muted">{description}</span>}
      </span>
    </label>
  )
);
Checkbox.displayName = "Checkbox";
export default Checkbox;
