import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { SITE_LINKS } from "../lib/siteLinks";

/**
 * Site footer carrying the public info and legally required links. On narrow
 * viewports the links wrap (flex-wrap) and the column stacks instead of being
 * cut off; min-h-11 keeps every target comfortably tappable.
 *
 * The link list is shared with the account menu (lib/siteLinks.ts) — these two
 * surfaces used to keep their own copies of it.
 */
export default function Footer() {
  const { t } = useTranslation();
  const year = new Date().getFullYear();
  return (
    <footer className="bg-page">
      <div className="mx-auto flex max-w-page flex-col items-center justify-between gap-3 px-4 py-6 text-ui text-muted sm:flex-row sm:px-8">
        <span>{t("footer.copyright", { year })}</span>
        <nav className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          {SITE_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="inline-flex min-h-11 items-center text-ink hover:underline hover:underline-offset-4"
            >
              {t(link.key)}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
