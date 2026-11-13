import { useEffect, useLayoutEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";

import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";
import { ChevronDownIcon, SafetyIcon } from "../lib/icons";
import { getLenis } from "../lib/lenis";
import type { TranslationKey } from "../lib/i18n";

/**
 * "Daten & Fragen" — the single public page for help, project background and
 * contact. It replaced three separate pages (/fragen, /kontakt, /ueber-uns)
 * that repeated the same statements up to three times and, for two of them,
 * could not be translated at all because their German was hard-coded.
 *
 * Every string lives in the i18n catalogue under `help.*` (see
 * lib/i18n/locales/de.ts, the source language). Nothing here is a literal, so
 * German and English cannot drift apart again — which is exactly what happened
 * while the FAQ kept two hand-maintained arrays.
 *
 * Shape: a safety block that is deliberately *open* (it is the one statement
 * with liability weight and must not hide behind a closed accordion), then the
 * project as prose, then seven question/answer accordions, and contact as its
 * own last section.
 *
 * Layout: the page runs the full `max-w-page` width with a side navigation —
 * sticky on a wide screen, a horizontally scrolling strip on a narrow one —
 * and the prose columns stay capped at `max-w-measure`, so a wide window buys
 * a visible nav and whitespace rather than 200-character lines.
 *
 * The section anchors are public URLs (RegionDetail links to
 * `#regionale-windverfuegbarkeit`, the footer to `#kontakt`), so they are
 * stable and never translated.
 *
 * The accessibility statement that used to sit in a "Rechtliches" section
 * moved to /nutzungsbedingungen: for a service, the accessibility information
 * belongs in the terms or an equivalent document, and Impressum and
 * Datenschutz keep their own pages, which is where their statutory
 * accessibility duties attach.
 */

/** Anchors are part of the URL contract — identical in every language. */
const ANCHOR = {
  safety: "sicherheit",
  project: "projekt",
  spots: "spots",
  weather: "wetter",
  season: "saison",
  map: "karte",
  account: "konto",
  contribute: "mitmachen",
  contact: "kontakt",
  /** Entry-level anchors, linked from outside this page or from other answers. */
  regionUnknown: "regionale-windverfuegbarkeit",
  spotSuggest: "spot-vorschlagen",
  community: "community-beitraege",
} as const;

const LINK_CLASS = "font-semibold text-ink underline underline-offset-4 hover:opacity-70";

/**
 * Named link components for `<Trans>`. Catalogue strings carry e.g.
 * `<privacy>Datenschutzerklärung</privacy>`, so a translator moves the link
 * inside the sentence without touching code, and a sentence never has to be
 * split into three keys around its link.
 *
 * `to={{ hash }}` keeps the current pathname, so an in-page anchor stays a
 * router navigation (ScrollManager + Lenis handle it) instead of a native jump.
 */
const LINK_COMPONENTS = {
  privacy: <Link to="/datenschutz" className={LINK_CLASS} />,
  imprint: <Link to="/impressum" className={LINK_CLASS} />,
  terms: <Link to="/nutzungsbedingungen" className={LINK_CLASS} />,
  settings: <Link to="/konto/einstellungen" className={LINK_CLASS} />,
  addSpots: <Link to="/konto/spots" className={LINK_CLASS} />,
  map: <Link to={{ hash: `#${ANCHOR.map}` }} className={LINK_CLASS} />,
  safety: <Link to={{ hash: `#${ANCHOR.safety}` }} className={LINK_CLASS} />,
  contact: <Link to={{ hash: `#${ANCHOR.contact}` }} className={LINK_CLASS} />,
  account: <Link to={{ hash: `#${ANCHOR.account}` }} className={LINK_CLASS} />,
  contribute: <Link to={{ hash: `#${ANCHOR.contribute}` }} className={LINK_CLASS} />,
  spotSuggest: <Link to={{ hash: `#${ANCHOR.spotSuggest}` }} className={LINK_CLASS} />,
  community: <Link to={{ hash: `#${ANCHOR.community}` }} className={LINK_CLASS} />,
};

/**
 * `<Trans>` bound to the shared link components.
 *
 * i18next types `i18nKey` as the union of every catalogue key. A literal there
 * is fine, but passing a *variable* of that union makes TypeScript exceed its
 * union-complexity budget (TS2590) while resolving the interpolation types.
 * Narrowing the signature to the two props this page uses keeps the key checked
 * against `TranslationKey` at the call site without that explosion.
 */
const RichText = Trans as unknown as (props: {
  i18nKey: TranslationKey;
  components: typeof LINK_COMPONENTS;
}) => ReactElement;

// --- content shape ---------------------------------------------------------

/** One rendered piece of an answer. Keys only — the text is in the catalogue. */
type Block =
  | { kind: "p"; key: TranslationKey }
  /** A paragraph that contains links; rendered through `<Trans>`. */
  | { kind: "rich"; key: TranslationKey }
  | { kind: "list"; keys: TranslationKey[] };

type Item = {
  /** Question, rendered as the `<summary>`. */
  q: TranslationKey;
  /** Set when the entry is linked from elsewhere and must open on its hash. */
  anchor?: string;
  blocks: Block[];
};

type Section = { id: string; title: TranslationKey; jump: TranslationKey; items: Item[] };

const p = (key: TranslationKey): Block => ({ kind: "p", key });
const rich = (key: TranslationKey): Block => ({ kind: "rich", key });
const list = (...keys: TranslationKey[]): Block => ({ kind: "list", keys });

/** The accordion sections, in page order. Safety, project, contact and legal
 *  are laid out by hand below because they are not question/answer lists. */
const SECTIONS: Section[] = [
  {
    id: ANCHOR.spots,
    title: "help.section.spots",
    jump: "help.jump.spots",
    items: [
      { q: "help.spots.sports.q", blocks: [p("help.spots.sports.p1"), p("help.spots.sports.p2")] },
      { q: "help.spots.noAccount.q", blocks: [p("help.spots.noAccount.p1")] },
      { q: "help.spots.find.q", blocks: [rich("help.spots.find.p1")] },
      { q: "help.spots.complete.q", blocks: [rich("help.spots.complete.p1")] },
      { q: "help.spots.missingFromList.q", blocks: [p("help.spots.missingFromList.p1")] },
      { q: "help.spots.originMark.q", blocks: [p("help.spots.originMark.p1")] },
    ],
  },
  {
    id: ANCHOR.weather,
    title: "help.section.weather",
    jump: "help.jump.weather",
    items: [
      { q: "help.weather.forecastVsClimate.q", blocks: [p("help.weather.forecastVsClimate.p1")] },
      { q: "help.weather.windDirection.q", blocks: [rich("help.weather.windDirection.p1")] },
      { q: "help.weather.sources.q", blocks: [rich("help.weather.sources.p1")] },
      { q: "help.weather.otherApps.q", blocks: [p("help.weather.otherApps.p1")] },
      {
        q: "help.weather.tides.q",
        blocks: [
          p("help.weather.tides.p1"),
          p("help.weather.tides.p2"),
          p("help.weather.tides.p3"),
          p("help.weather.tides.p4"),
        ],
      },
      {
        q: "help.weather.waves.q",
        blocks: [
          p("help.weather.waves.p1"),
          list(
            "help.weather.waves.total",
            "help.weather.waves.windSea",
            "help.weather.waves.primary",
            "help.weather.waves.secondary",
          ),
          p("help.weather.waves.p2"),
          p("help.weather.waves.p3"),
        ],
      },
    ],
  },
  {
    id: ANCHOR.season,
    title: "help.section.season",
    jump: "help.jump.season",
    items: [
      {
        q: "help.season.percentages.q",
        blocks: [
          p("help.season.percentages.p1"),
          p("help.season.percentages.p2"),
          list(
            "help.season.percentages.data",
            "help.season.percentages.period",
            "help.season.percentages.place",
            "help.season.percentages.threshold",
            "help.season.percentages.counting",
            "help.season.percentages.percentage",
          ),
          p("help.season.percentages.p3"),
        ],
      },
      {
        q: "help.season.regionUnknown.q",
        anchor: ANCHOR.regionUnknown,
        blocks: [p("help.season.regionUnknown.p1")],
      },
    ],
  },
  {
    id: ANCHOR.map,
    title: "help.section.map",
    jump: "help.jump.map",
    items: [
      {
        q: "help.map.how.q",
        blocks: [p("help.map.how.p1"), p("help.map.how.p2"), p("help.map.how.p3")],
      },
    ],
  },
  {
    id: ANCHOR.account,
    title: "help.section.account",
    jump: "help.jump.account",
    items: [
      {
        q: "help.account.units.q",
        blocks: [
          list(
            "help.account.units.wind",
            "help.account.units.waves",
            "help.account.units.temperature",
            "help.account.units.distance",
          ),
          rich("help.account.units.p1"),
          p("help.account.units.p2"),
        ],
      },
      { q: "help.account.setup.q", blocks: [p("help.account.setup.p1")] },
      { q: "help.account.home.q", blocks: [p("help.account.home.p1")] },
      { q: "help.account.profile.q", blocks: [rich("help.account.profile.p1")] },
      {
        q: "help.account.exportDelete.q",
        blocks: [
          rich("help.account.exportDelete.exportP"),
          p("help.account.exportDelete.deleteP"),
          list(
            "help.account.exportDelete.d1",
            "help.account.exportDelete.d2",
            "help.account.exportDelete.d3",
          ),
          rich("help.account.exportDelete.p3"),
        ],
      },
      { q: "help.account.mail.q", blocks: [p("help.account.mail.p1")] },
      {
        q: "help.account.planned.q",
        blocks: [
          p("help.account.planned.p1"),
          list(
            "help.account.planned.alerts",
            "help.account.planned.notifications",
            "help.account.planned.publicProfile",
          ),
          p("help.account.planned.p2"),
        ],
      },
    ],
  },
  {
    id: ANCHOR.contribute,
    title: "help.section.contribute",
    jump: "help.jump.contribute",
    items: [
      {
        q: "help.contribute.suggest.q",
        anchor: ANCHOR.spotSuggest,
        blocks: [rich("help.contribute.suggest.p1")],
      },
      { q: "help.contribute.review.q", blocks: [p("help.contribute.review.p1")] },
      { q: "help.contribute.report.q", blocks: [rich("help.contribute.report.p1")] },
      {
        q: "help.contribute.images.q",
        blocks: [
          p("help.contribute.images.p1"),
          p("help.contribute.images.p2"),
          p("help.contribute.images.p3"),
        ],
      },
      {
        q: "help.contribute.contributions.q",
        anchor: ANCHOR.community,
        blocks: [
          list(
            "help.contribute.contributions.ratings",
            "help.contribute.contributions.gallery",
            "help.contribute.contributions.suggestions",
          ),
          rich("help.contribute.contributions.p1"),
          p("help.contribute.contributions.p2"),
          rich("help.contribute.contributions.p3"),
        ],
      },
    ],
  },
];

/** Side-navigation order: every section, including the hand-laid-out ones. */
const JUMP: { id: string; key: TranslationKey }[] = [
  { id: ANCHOR.safety, key: "help.jump.safety" },
  { id: ANCHOR.project, key: "help.jump.project" },
  { id: ANCHOR.spots, key: "help.jump.spots" },
  { id: ANCHOR.weather, key: "help.jump.weather" },
  { id: ANCHOR.season, key: "help.jump.season" },
  { id: ANCHOR.map, key: "help.jump.map" },
  { id: ANCHOR.account, key: "help.jump.account" },
  { id: ANCHOR.contribute, key: "help.jump.contribute" },
  { id: ANCHOR.contact, key: "help.jump.contact" },
];

const CONTACT_TOPICS: { term: TranslationKey; body: TranslationKey }[] = [
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

// --- page ------------------------------------------------------------------

export default function Fragen() {
  const { t, i18n } = useTranslation();
  const { hash } = useLocation();
  const target = hash ? decodeURIComponent(hash.slice(1)) : "";

  useEffect(() => {
    document.title = `${t("help.title")} — surfwind data`;
  }, [t, i18n.resolvedLanguage]);

  // Deep links land here two ways: a hash typed/shared directly, and the
  // /kontakt and /ueber-uns redirects. In both cases ScrollManager's layout
  // effect can run *before* this lazily-loaded page has mounted, so the anchor
  // does not exist yet and the scroll is silently dropped. Repeat it here, once
  // the section (and any `<details>` opened for it, see Entry) is in the DOM.
  useEffect(() => {
    if (!target) return;
    const el = document.getElementById(target);
    if (!el) return;
    const lenis = getLenis();
    if (lenis) lenis.scrollTo(el, { offset: -80 });
    else el.scrollIntoView();
  }, [target]);

  // Which section the reader is in, so the side navigation says where they
  // are. An observer rather than a scroll handler: no work on frames where
  // nothing crossed. The band is the upper third of the viewport, which is
  // where a heading sits once it has been scrolled to.
  const [active, setActive] = useState<string>(JUMP[0].id);
  useEffect(() => {
    const sections = JUMP.map((entry) => document.getElementById(entry.id)).filter(
      (el): el is HTMLElement => el !== null,
    );
    if (sections.length === 0) return;
    const seen = new Map<string, boolean>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) seen.set(entry.target.id, entry.isIntersecting);
        const current = JUMP.find((entry) => seen.get(entry.id));
        if (current) setActive(current.id);
      },
      { rootMargin: "-96px 0px -66% 0px" },
    );
    for (const el of sections) observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-page px-4 pb-24 pt-32 sm:px-8">
        <h1 className="text-heading-lg font-semibold text-ink">{t("help.title")}</h1>
        <p className="mt-3 max-w-measure text-lead text-ink-soft">{t("help.lede")}</p>

        {/* One grid, one nav landmark. Narrow: a single column, the nav a
            horizontally scrolling strip above the content (the strip scrolls,
            never the page). Wide: a sticky column beside it. Same links, same
            44px targets — only the direction changes, so there is no second
            copy of the navigation to keep in step. */}
        <div className="mt-8 grid gap-8 lg:mt-12 lg:grid-cols-[13.5rem_minmax(0,1fr)] lg:gap-14">
          <nav
            aria-label={t("help.jump.label")}
            className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0 lg:self-start lg:overflow-visible lg:sticky lg:top-28"
          >
            <ul className="flex w-max gap-2 lg:w-auto lg:flex-col lg:gap-0.5">
              {JUMP.map((entry) => {
                const current = entry.id === active;
                return (
                  <li key={entry.id}>
                    <Link
                      to={{ hash: `#${entry.id}` }}
                      aria-current={current ? "true" : undefined}
                      className={`inline-flex min-h-11 items-center rounded-card border px-3 text-ui font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink lg:w-full lg:border-0 lg:border-l-2 lg:rounded-none lg:px-3 ${
                        current
                          ? "border-line bg-band text-ink lg:border-ink lg:bg-transparent lg:font-semibold"
                          : "border-line text-ink hover:bg-band lg:border-transparent lg:text-ink-soft lg:hover:text-ink"
                      }`}
                    >
                      {t(entry.key)}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="min-w-0">

        {/* 1 — Safety. Open by design: this is the only block with liability
            weight, and it used to sit ninth in a closed accordion. */}
        <Band id={ANCHOR.safety} title={t("help.section.safety")}>
          <h3 className="text-body font-semibold text-ink">{t("help.safety.approval.title")}</h3>
          <Prose>
            <p>{t("help.safety.approval.p1")}</p>
            <p>{t("help.safety.approval.checkTitle")}</p>
          </Prose>
          <Bullets
            keys={[
              "help.safety.approval.check1",
              "help.safety.approval.check2",
              "help.safety.approval.check3",
              "help.safety.approval.check4",
              "help.safety.approval.check5",
            ]}
          />
          <Prose>
            <p>{t("help.safety.approval.ask")}</p>
            <p>{t("help.safety.approval.emergency")}</p>
          </Prose>

          <h3 className="mt-8 flex items-center gap-2 text-body font-semibold text-ink">
            <SafetyIcon aria-hidden width={17} height={17} className="shrink-0 text-danger" />
            {t("help.safety.mark.q")}
          </h3>
          <Prose>
            <p>{t("help.safety.mark.p1")}</p>
            <p>{t("help.safety.mark.p2")}</p>
            <p>{t("help.safety.mark.p3")}</p>
          </Prose>
        </Band>

        {/* 2 — The project, as prose rather than questions. */}
        <Band id={ANCHOR.project} title={t("help.section.project")}>
          <Sub title={t("help.project.what.title")}>
            <p>{t("help.project.what.p1")}</p>
            <p>{t("help.project.what.p2")}</p>
            <p>
              <RichText i18nKey="help.project.what.p3" components={LINK_COMPONENTS} />
            </p>
          </Sub>
          <Sub title={t("help.project.browse.title")}>
            <p>{t("help.project.browse.p1")}</p>
          </Sub>
          <Sub title={t("help.project.limits.title")}>
            <p>{t("help.project.limits.p1")}</p>
            <p>{t("help.project.limits.p2")}</p>
            <p>{t("help.project.limits.p3")}</p>
          </Sub>
          <Sub title={t("help.project.languages.title")}>
            <p>{t("help.project.languages.p1")}</p>
          </Sub>
        </Band>

        {/* 3–8 — question/answer accordions. */}
        {SECTIONS.map((section) => (
          <Band key={section.id} id={section.id} title={t(section.title)}>
            <div className="divide-y divide-line border-y border-line">
              {section.items.map((item) => (
                <Entry key={item.q} item={item} openTarget={target} />
              ))}
            </div>
          </Band>
        ))}

        {/* 9 — Contact: its own last section, the operator mailbox first and
            "what is it about" underneath. */}
        <Band id={ANCHOR.contact} title={t("help.section.contact")}>
          <p className="max-w-measure text-body leading-relaxed text-ink-soft">
            {t("help.contact.intro")}
          </p>
          <ContactCard />

          <h3 className="mt-10 text-body font-semibold text-ink">{t("help.contact.topicsTitle")}</h3>
          <p className="mt-1 text-ui text-muted">{t("help.contact.topicsHint")}</p>
          <dl className="mt-5 space-y-5">
            {CONTACT_TOPICS.map((topic) => (
              <div key={topic.term}>
                <dt className="text-ui font-semibold text-ink">{t(topic.term)}</dt>
                <dd className="mt-1 max-w-measure text-ui leading-relaxed text-ink-soft">
                  <RichText i18nKey={topic.body} components={LINK_COMPONENTS} />
                </dd>
              </div>
            ))}
          </dl>

          <div className="mt-8 border-t border-line pt-5">
            <p className="text-ui text-muted">{t("help.contact.responseTime")}</p>
            <p className="mt-2 text-ui text-muted">{t("help.contact.notEmergency")}</p>
          </div>
        </Band>

        <div className="mt-16 border-t border-line pt-8">
          <p className="text-lead text-ink-soft">{t("help.outro.claim")}</p>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <Link
              to="/search"
              className="inline-flex min-h-11 items-center justify-center rounded-card bg-ink px-5 text-ui font-semibold text-surface transition-opacity hover:opacity-90"
            >
              {t("help.outro.discover")}
            </Link>
            <Link
              to="/konto/spots"
              className="inline-flex min-h-11 items-center justify-center rounded-card border border-line bg-surface px-5 text-ui font-semibold text-ink transition-colors hover:bg-band"
            >
              {t("help.outro.suggest")}
            </Link>
          </div>
        </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

// --- building blocks -------------------------------------------------------

function Band({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`help-${id}`} className="mt-12 scroll-mt-24">
      <h2 id={`help-${id}`} className="text-lead font-semibold text-ink">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Sub({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-6 first:mt-0">
      <h3 className="text-body font-semibold text-ink">{title}</h3>
      <Prose>{children}</Prose>
    </div>
  );
}

function Prose({ children }: { children: ReactNode }) {
  return (
    <div className="mt-2 max-w-measure space-y-3 text-ui leading-relaxed text-ink-soft">
      {children}
    </div>
  );
}

function Bullets({ keys }: { keys: TranslationKey[] }) {
  const { t } = useTranslation();
  return (
    <ul className="mt-3 max-w-measure list-disc space-y-1.5 pl-5 text-ui leading-relaxed text-ink-soft">
      {keys.map((key) => (
        <li key={key}>{t(key)}</li>
      ))}
    </ul>
  );
}

/**
 * One accordion entry. A native `<details>` keeps it keyboard-operable and
 * focusable without bespoke ARIA state.
 *
 * `openTarget` opens the entry when the page was reached by its own hash (e.g.
 * the region pages link to `#regionale-windverfuegbarkeit`). It is applied
 * imperatively rather than through the `open` prop on purpose: a controlled
 * `open` would re-close the entry on every render and make it impossible for
 * the visitor to collapse the one they were sent to.
 */
function Entry({ item, openTarget }: { item: Item; openTarget: string }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDetailsElement>(null);

  useLayoutEffect(() => {
    if (item.anchor && item.anchor === openTarget && ref.current) ref.current.open = true;
  }, [item.anchor, openTarget]);

  return (
    <details ref={ref} id={item.anchor} className="group scroll-mt-24">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 py-4 text-left text-body font-semibold text-ink [&::-webkit-details-marker]:hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
        {t(item.q)}
        <ChevronDownIcon className="shrink-0 text-lead text-muted transition-transform duration-base group-open:rotate-180 motion-reduce:transition-none" />
      </summary>
      <div className="pb-4">
        {item.blocks.map((block, index) =>
          block.kind === "list" ? (
            <Bullets key={index} keys={block.keys} />
          ) : (
            <p
              key={index}
              className="mt-3 max-w-measure text-ui leading-relaxed text-ink-soft first:mt-0"
            >
              {block.kind === "rich" ? (
                <RichText i18nKey={block.key} components={LINK_COMPONENTS} />
              ) : (
                t(block.key)
              )}
            </p>
          ),
        )}
      </div>
    </details>
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
