import { useEffect, useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";

import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";
import PageBackLink from "../components/PageBackLink";
import ScrollBackButton from "../components/ScrollBackButton";
import { CONTACT_TOPICS_ANCHOR } from "../lib/infoSections";
import type { TranslationKey } from "../lib/i18n";

/**
 * "Kontakt" (/kontakt) — the operator mailbox, on its own page again.
 *
 * It was a section of "Daten & Fragen" for a while, and /kontakt redirected to
 * that anchor. That put the one thing a visitor comes to *do* at the bottom of
 * a very long page they came to *read*, behind nine sections of help text,
 * while the site navigation still offered it as a destination of its own.
 *
 * Every string stays in the catalogue under `help.contact.*` (the keys did not
 * move, so no translation was re-keyed); the heading reuses
 * `help.section.contact`. Nothing here is a literal.
 *
 * Layout: the single centred `max-w-content` column that every other
 * navigation destination uses (Impressum, Datenschutz, Nutzungsbedingungen),
 * so the pages reachable from the site menu share one measure and one axis.
 */

const LINK_CLASS = "font-semibold text-ink underline underline-offset-4 hover:opacity-70";

/**
 * Named links for `<Trans>`. The same catalogue sentences used to live on
 * /fragen, where two of these were in-page hashes; from here they are absolute
 * routes into that page, so a translator's sentence keeps working unchanged.
 */
const LINK_COMPONENTS = {
  privacy: <Link to="/datenschutz" className={LINK_CLASS} />,
  terms: <Link to="/nutzungsbedingungen" className={LINK_CLASS} />,
  settings: <Link to="/konto/einstellungen" className={LINK_CLASS} />,
  contribute: <Link to="/fragen#mitmachen" className={LINK_CLASS} />,
  spotSuggest: <Link to="/fragen#spot-vorschlagen" className={LINK_CLASS} />,
};

/** See pages/Fragen.tsx: narrowing `Trans` keeps the key checked without
 *  blowing TypeScript's union-complexity budget (TS2590). */
const RichText = Trans as unknown as (props: {
  i18nKey: TranslationKey;
  components: typeof LINK_COMPONENTS;
}) => ReactElement;

const TOPICS: { term: TranslationKey; body: TranslationKey }[] = [
  { term: "help.contact.topics.spotErrorTerm", body: "help.contact.topics.spotErrorBody" },
  { term: "help.contact.topics.accountTerm", body: "help.contact.topics.accountBody" },
  { term: "help.contact.topics.technicalTerm", body: "help.contact.topics.technicalBody" },
  { term: "help.contact.topics.newSpotTerm", body: "help.contact.topics.newSpotBody" },
  { term: "help.contact.topics.unlawfulTerm", body: "help.contact.topics.unlawfulBody" },
  { term: "help.contact.topics.privacyTerm", body: "help.contact.topics.privacyBody" },
  { term: "help.contact.topics.securityTerm", body: "help.contact.topics.securityBody" },
];

/** Same source as Impressum/Datenschutz — an unconfigured view says so rather
 *  than printing a dead placeholder address. */
const CONTACT_EMAIL = (import.meta.env.VITE_LEGAL_EMAIL || "").trim();
const EMAIL_CONFIGURED = CONTACT_EMAIL !== "" && !CONTACT_EMAIL.endsWith(".invalid");

export default function Kontakt() {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    document.title = `${t("help.section.contact")} — surfwind data`;
  }, [t, i18n.resolvedLanguage]);

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-content px-4 pb-24 pt-32 sm:px-8">
        <PageBackLink className="mb-2" />
        <ScrollBackButton />
        <h1 className="text-title font-semibold text-ink">{t("help.section.contact")}</h1>
        <p className="mt-2 text-ui text-ink-soft">{t("help.contact.intro")}</p>

        <ContactCard />

        <h2 id={CONTACT_TOPICS_ANCHOR} className="mt-10 scroll-mt-24 text-lead font-semibold text-ink">{t("help.contact.topicsTitle")}</h2>
        <p className="mt-1 text-ui text-muted">{t("help.contact.topicsHint")}</p>
        <dl className="mt-5 space-y-5">
          {TOPICS.map((topic) => (
            <div key={topic.term}>
              <dt className="text-ui font-semibold text-ink">{t(topic.term)}</dt>
              <dd className="mt-1 text-ui leading-relaxed text-ink-soft">
                <RichText i18nKey={topic.body} components={LINK_COMPONENTS} />
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-8 border-t border-line pt-5">
          <p className="text-ui text-muted">{t("help.contact.responseTime")}</p>
          <p className="mt-2 text-ui text-muted">{t("help.contact.notEmergency")}</p>
        </div>

        {/* The questions this page does not answer are one link away, so a
            visitor who landed here by mistake is not sent back via the menu. */}
        <p className="mt-10 text-ui text-ink-soft">
          <Link to="/fragen" className={LINK_CLASS}>
            {t("siteLinks.faq")}
          </Link>
        </p>
      </main>
      <Footer />
    </div>
  );
}

/** The operator mailbox: a `mailto:` plus copy-to-clipboard, with an honest
 *  message when VITE_LEGAL_EMAIL is unset in a development view. */
function ContactCard() {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  const copy = async () => {
    setCopyError(false);
    try {
      await navigator.clipboard.writeText(CONTACT_EMAIL);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopyError(true);
    }
  };

  if (!EMAIL_CONFIGURED) {
    return (
      <section className="mt-6 rounded-card border border-line bg-surface p-5 sm:p-6">
        <p role="status" className="text-ui text-muted">
          {t("help.contact.unconfigured")}
        </p>
      </section>
    );
  }

  return (
    <section className="mt-6 rounded-card border border-line bg-surface p-5 sm:p-6">
      <p className="text-caption font-semibold uppercase tracking-caps text-muted">
        {t("help.contact.emailLabel")}
      </p>
      <p className="mt-2 break-all text-lead font-semibold text-ink">
        <a href={`mailto:${CONTACT_EMAIL}`} className="underline underline-offset-4 hover:opacity-70">
          {CONTACT_EMAIL}
        </a>
      </p>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <a
          href={`mailto:${CONTACT_EMAIL}`}
          className="inline-flex min-h-11 items-center justify-center rounded-card bg-ink px-5 text-ui font-semibold text-surface transition-opacity hover:opacity-90"
        >
          {t("help.contact.write")}
        </a>
        <button
          type="button"
          onClick={() => void copy()}
          className="inline-flex min-h-11 items-center justify-center rounded-card border border-line bg-surface px-5 text-ui font-semibold text-ink transition-colors hover:bg-band"
        >
          {t("help.contact.copy")}
        </button>
      </div>
      <p role="status" aria-live="polite" className="mt-3 min-h-5 text-ui text-muted">
        {copied && t("help.contact.copied")}
        {copyError && t("help.contact.copyFailed")}
      </p>
    </section>
  );
}
