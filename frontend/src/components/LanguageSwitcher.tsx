import { useTranslation } from "react-i18next";
import { SwitchTrack } from "./ui/Switch";
import type { Locale } from "../lib/i18n";

/**
 * Language control as a switch row, built exactly like the theme row directly
 * above it: the label "Sprache" on the left, the switch on the right, and the
 * state shown *inside* the thumb — where the theme row carries its moon, this
 * one carries the active language code.
 *
 * The code sits in the thumb rather than flanking the track so the two rows
 * have the same silhouette. Flanking "DE … EN" made this row wider than the
 * theme row and read as two separate targets.
 *
 * Accessibility: one button, not two, and deliberately not `role="switch"` —
 * on/off does not describe "German or English". The accessible name states the
 * current language *and* what the press does. The code in the thumb is
 * decorative (the track is `aria-hidden`), so nothing depends on reading it.
 */
export default function LanguageSwitcher({ variant = "sheet" }: { variant?: "sheet" | "menu" }) {
  const { i18n, t } = useTranslation();
  const active: Locale = i18n.resolvedLanguage === "en" ? "en" : "de";
  const english = active === "en";
  const target: Locale = english ? "de" : "en";
  const sheet = variant === "sheet";

  const nameOf = (locale: Locale) => t(locale === "de" ? "language.german" : "language.english");

  return (
    <button
      type="button"
      onClick={() => void i18n.changeLanguage(target)}
      aria-label={`${t("language.label")}: ${nameOf(active)}. ${t("language.switchTo", { language: nameOf(target) })}`}
      className={`flex w-full items-center justify-between gap-4 px-3 font-medium text-ink transition-opacity active:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
        sheet ? "min-h-11 text-body" : "min-h-11 text-ui hover:opacity-70"
      }`}
    >
      <span>{t("language.label")}</span>
      <SwitchTrack
        checked={english}
        icon={
          <span className="text-[0.625rem] font-semibold leading-none tracking-caps">
            {active.toUpperCase()}
          </span>
        }
      />
    </button>
  );
}
