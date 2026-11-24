import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { choiceBox, choiceFill, choiceFrame, choiceLabel, choiceMark, type ChoiceLayout } from "./choiceClass";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "children"> & {
  children: ReactNode;
  layout?: ChoiceLayout;
  className?: string;
};

/** Atom: radio option with its label. Group several under one `name` inside a
 *  <fieldset> with a <legend>. Native input, drawn circle, 20px (see choiceClass). */
const Radio = forwardRef<HTMLInputElement, Props>(({ children, layout = "row", className = "", ...props }, ref) => (
  <label className={`${choiceLabel[layout]} ${className}`}>
    <span className={`${choiceFrame} ${layout === "plain" ? "mt-px" : ""}`}>
      <input ref={ref} type="radio" className={`${choiceBox} rounded-full`} {...props} />
      <span aria-hidden="true" className={`${choiceFill} rounded-full`} />
      <span aria-hidden="true" className={`${choiceMark} h-2 w-2 rounded-full bg-white`} />
    </span>
    <span className="min-w-0">{children}</span>
  </label>
));
Radio.displayName = "Radio";
export default Radio;
