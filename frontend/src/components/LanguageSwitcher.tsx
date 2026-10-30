import { useTranslation } from "react-i18next";
import type { Locale } from "../lib/i18n";

export default function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { i18n, t } = useTranslation();
  const active: Locale = i18n.resolvedLanguage === "en" ? "en" : "de";
  const choose = (locale: Locale) => void i18n.changeLanguage(locale);

  return (
    <div
      role="group"
      aria-label={t("language.label")}
      className={`flex items-center rounded-card border border-line bg-page p-1 ${compact ? "gap-0" : "gap-1"}`}
    >
      {(["de", "en"] as const).map((locale) => (
        <button
          key={locale}
          type="button"
          lang={locale}
          aria-pressed={active === locale}
          onClick={() => choose(locale)}
          className={`min-h-9 rounded-[calc(var(--radius-card)-0.25rem)] px-3 text-caption font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
            active === locale ? "bg-ink text-surface" : "text-ink hover:bg-band"
          }`}
        >
          {locale === "de" ? "DE" : "EN"}
          {!compact && <span className="sr-only"> — {t(locale === "de" ? "language.german" : "language.english")}</span>}
        </button>
      ))}
    </div>
  );
}
