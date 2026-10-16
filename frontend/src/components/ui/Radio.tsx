import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { choiceInput, choiceLabel, type ChoiceLayout } from "./choiceClass";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "children"> & {
  children: ReactNode;
  layout?: ChoiceLayout;
  className?: string;
};

/** Atom: radio option with its label. Group several under one `name` inside a
 *  <fieldset> with a <legend>. Native input, brand-tinted, 20px. */
const Radio = forwardRef<HTMLInputElement, Props>(({ children, layout = "row", className = "", ...props }, ref) => (
  <label className={`${choiceLabel[layout]} ${className}`}>
    <input ref={ref} type="radio" className={`${choiceInput} ${layout === "plain" ? "mt-px" : ""}`} {...props} />
    <span className="min-w-0">{children}</span>
  </label>
));
Radio.displayName = "Radio";
export default Radio;
