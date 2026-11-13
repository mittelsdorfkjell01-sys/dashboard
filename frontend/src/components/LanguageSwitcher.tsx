import { useTranslation } from "react-i18next";
import { SwitchTrack } from "./ui/Switch";
import type { Locale } from "../lib/i18n";

/**
 * Language control as a two-sided switch row, matching the theme row directly
 * above it in the account menu: the label "Sprache" on the left, then "DE",
 * the switch and "EN" on the right, with the active code carrying the weight
 * and the inactive one receding.
 *
 * It replaces the old DE/EN segmented pill. Two controls that both change a
 * global display preference read better as the same control; the segmented
 * pill also sat visually next to the theme row without matching it.
 *
 * Accessibility: one button, not two. A switch's on/off semantics do not
 * describe "German or English", so this is a plain button whose accessible
 * name states the current language *and* what the press does; the visible
 * codes carry `lang` so a screen reader pronounces them correctly.
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
        sheet ? "min-h-[52px] text-body" : "min-h-11 text-ui hover:opacity-70"
      }`}
    >
      <span>{t("language.label")}</span>
      <span className="flex items-center gap-2" aria-hidden>
        <span
          lang="de"
          className={`text-caption font-semibold tracking-caps ${english ? "text-muted" : "text-ink"}`}
        >
          DE
        </span>
        <SwitchTrack checked={english} />
        <span
          lang="en"
          className={`text-caption font-semibold tracking-caps ${english ? "text-ink" : "text-muted"}`}
        >
          EN
        </span>
      </span>
    </button>
  );
}
