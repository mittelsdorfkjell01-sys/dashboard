/**
 * Compile-time key checking.
 *
 * Binding i18next's resource types to the German catalogue means `t("footr.faq")`
 * is a type error, not a string that silently renders as "footr.faq" in
 * production. This is the main reason the catalogue uses `as const`.
 */
import type { resources } from "./index";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "translation";
    resources: (typeof resources)["de"];
  }
}
