import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";

import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";
import { ChevronDownIcon, MenuIcon, SafetyIcon } from "../lib/icons";
import { getLenis } from "../lib/lenis";
import PageBackLink from "../components/PageBackLink";
import ScrollBackButton from "../components/ScrollBackButton";
import type { TranslationKey } from "../lib/i18n";
import { HELP_ANCHOR, HELP_JUMP } from "../lib/infoSections";

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
 * project as prose, then seven question/answer accordions.
 *
 * Contact is NOT a section here any more: it is /kontakt (pages/Kontakt.tsx),
 * its own page again. It is the one thing a visitor comes to *do* rather than
 * read, it is its own entry in the site navigation, and as a section it sat at
 * the bottom of a very long page behind everything else.
 *
 * Layout: the navigation column and the body are one centred unit — the grid
 * carries `lg:max-w-measure-nav` (13.5rem nav + 3.5rem gap + the body measure)
 * and `mx-auto`. Centring only the body *inside* the column left over beside
 * the nav is what pushed the text ~130px right of the window centre. The body
 * is one `max-w-measure-wide` column (92ch) and everything inside shares that
 * width, headings and accordion rows included.
 *
 * Below `lg` the nav column is not rendered at all. Its links live in the
 * bottom jump menu (`JumpMenu`), which replaced a horizontally scrolling strip
 * above the text: there the later entries sat off-screen, and the strip had no
 * room to say which section the reader was in.
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

const ANCHOR = HELP_ANCHOR;

/** Contact was this page's last section until it became /kontakt again. Old
 *  links and bookmarks still carry the former hash, so they are forwarded
 *  instead of landing on a page that no longer has that section. */
const LEGACY_CONTACT_ANCHOR = "kontakt";

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
  contact: <Link to="/kontakt" className={LINK_CLASS} />,
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

const JUMP = HELP_JUMP;

/** Id of the bottom jump menu's panel, for `aria-controls` on its trigger. */
const JUMP_MENU_ID = "help-jump-menu";

// --- page ------------------------------------------------------------------

export default function Fragen() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const { hash } = location;
  const navigate = useNavigate();
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
    // `lenis.resize()` for the same reason as in ScrollManager: this page was
    // not in the DOM when Lenis last measured, so without it the jump clamps
    // against a stale limit and does nothing.
    if (lenis) {
      lenis.resize();
      lenis.scrollTo(el, { offset: -80 });
    } else {
      el.scrollIntoView();
    }
  }, [target]);

  // Contact left this page; the hash it used to answer to still travels in
  // bookmarks, old mails and the former /kontakt redirect.
  useEffect(() => {
    if (target === LEGACY_CONTACT_ANCHOR) navigate("/kontakt", { replace: true });
  }, [target, navigate]);

  // Which section the reader is in, so the navigation says where they
  // are. An observer rather than a scroll handler: no work on frames where
  // nothing crossed. The band is the upper third of the viewport, which is
  // where a heading sits once it has been scrolled to.
  const [active, setActive] = useState<string>(JUMP[0].id);

  // A jump is a ~1.2s Lenis animation (ScrollManager owns it). The observer
  // only ever reports where the reader *is*, so while that animation ran the
  // marker stayed on the entry the reader came from — clicking down the list
  // left the white rule one entry behind the whole way. Scrolling by hand was
  // never affected, because then "where the reader is" is the answer.
  //
  // So the clicked entry becomes current on the click, and the observer is
  // held back until the travel actually arrives there. The timeout is the
  // release valve for a target the page cannot scroll far enough to reach
  // (the last section on a tall window): the observer takes over again
  // instead of the marker staying stuck on a section nobody is in.
  const travellingTo = useRef<string | null>(null);
  const travelTimer = useRef<number | null>(null);
  const endTravel = useCallback(() => {
    travellingTo.current = null;
    if (travelTimer.current !== null) window.clearTimeout(travelTimer.current);
    travelTimer.current = null;
  }, []);
  const jumpTo = useCallback(
    (id: string) => {
      setActive(id);
      travellingTo.current = id;
      if (travelTimer.current !== null) window.clearTimeout(travelTimer.current);
      travelTimer.current = window.setTimeout(endTravel, 2000);
    },
    [endTravel],
  );
  useEffect(() => endTravel, [endTravel]);

  // A deep link arrives mid-travel too: mark its section at once rather than
  // letting the marker sit on the first entry until the scroll lands.
  useEffect(() => {
    if (target && JUMP.some((entry) => entry.id === target)) jumpTo(target);
  }, [target, jumpTo]);

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
        if (!current) return;
        const travelling = travellingTo.current;
        if (travelling && travelling !== current.id) return;
        if (travelling) endTravel();
        setActive(current.id);
      },
      { rootMargin: "-96px 0px -66% 0px" },
    );
    for (const el of sections) observer.observe(el);
    return () => observer.disconnect();
  }, [endTravel]);

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-page px-4 pb-24 pt-32 sm:px-8">
        {/* One grid, centred as a whole: nav column + gap + body measure. The
            body alone used to be `mx-auto` inside the column *beside* the nav,
            which reads as off-centre on a wide window — the text has to be
            centred against the window, not against the leftover space.

            The nav column exists from `lg` up only; below that the same links
            are in the bottom jump menu, so there is one copy of the list
            (JUMP) and never two live navigations at once.

            On a wide screen the nav never moves. It used to drift: `sticky`
            with a `top` *above* its own starting point scrolls along until it
            reaches that offset. Here the offset equals the layout position —
            `main` has `pt-32`, so the nav starts at exactly 128px — which
            makes the travel zero and pins it from the first pixel.

            Deliberately not `fixed`: that takes the nav out of flow, the grid
            then auto-places the body in the first column, and the text ends up
            216px wide. Sticky keeps it a grid item. It scrolls inside itself
            on a short window so the last entry stays reachable. */}
        <div className="mx-auto grid w-full gap-8 lg:max-w-measure-nav lg:grid-cols-[13.5rem_minmax(0,1fr)] lg:gap-14">
          <nav
            aria-label={t("help.jump.label")}
            className="hidden lg:sticky lg:top-32 lg:block lg:max-h-[calc(100vh-11rem)] lg:self-start lg:overflow-y-auto lg:px-0"
          >
            <ul className="flex flex-col gap-0.5">
              {JUMP.map((entry) => {
                const current = entry.id === active;
                return (
                  <li key={entry.id}>
                    <Link
                      to={{ hash: `#${entry.id}` }}
                      onClick={() => jumpTo(entry.id)}
                      aria-current={current ? "true" : undefined}
                      className={`flex min-h-11 w-full items-center border-l-2 px-3 text-ui font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
                        current
                          ? "border-ink font-semibold text-ink"
                          : "border-transparent text-ink-soft hover:text-ink"
                      }`}
                    >
                      {t(entry.key)}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="mx-auto min-w-0 w-full max-w-measure-wide">
            {/* The title sits above the body column and shares its width, so
                it reads as that column's heading instead of floating at the
                far left edge of a 1570px page. */}
            <PageBackLink className="mb-2" />
            <ScrollBackButton />
            <h1 className="text-title font-semibold text-ink">{t("help.title")}</h1>
            <p className="mt-2 text-ui text-ink-soft">{t("help.lede")}</p>

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
      <JumpMenu active={active} onJump={jumpTo} />
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
    <div className="mt-2 space-y-3 text-ui leading-relaxed text-ink-soft">
      {children}
    </div>
  );
}

function Bullets({ keys }: { keys: TranslationKey[] }) {
  const { t } = useTranslation();
  return (
    <ul className="mt-3 list-disc space-y-1.5 pl-5 text-ui leading-relaxed text-ink-soft">
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
              className="mt-3 text-ui leading-relaxed text-ink-soft first:mt-0"
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

/**
 * The jump navigation below `lg`: a small pill at the bottom edge that opens a
 * panel with the same JUMP entries.
 *
 * It replaced a horizontally scrolling strip of keywords above the text. That
 * strip put four of its nine entries off-screen, gave no sense of where the
 * reader was, and competed with the page's own vertical scroll. The pattern
 * here is the one the admin spot form uses (components/admin/FormNavBar) —
 * reachable at any scroll position without travelling back to the top —
 * rendered in the public tokens instead of the admin ones.
 *
 * Deliberately bare: eight section names, nothing else. The panel used to
 * carry a title row, a close button and a filter field — three pieces of
 * chrome around a list that is shorter than the chrome, on the one viewport
 * where space is scarce. Dismissal is where a phone already expects it: the
 * pill itself, a tap beside the panel, a swipe down over it, Esc.
 *
 * It grows out of the pill on a native CSS transition (house easing, a longer
 * duration than the house panel step — see the panel below), and the swipe is
 * hand-rolled on pointer events — the same reasoning as the mobile search
 * sheet: a compositor transform stays smooth on a busy main thread, where a
 * JS-driven animation stutters.
 *
 * Mounted only below `lg` (the wrapper is `lg:hidden`), so no handler of this
 * menu is alive on a desktop viewport, where the sticky column is the
 * navigation — a hidden-but-mounted second menu is how an invisible overlay
 * starts eating taps.
 */
const JUMP_MENU_MS = 440; // longer than --sw-dur-slow on purpose: see the panel's note

function JumpMenu({ active, onJump }: { active: string; onJump: (id: string) => void }) {
  const { t } = useTranslation();
  // `mounted` = in the DOM, `shown` = at rest. The two are separate so the
  // panel can animate in from its closed state and animate out before it goes.
  const [mounted, setMounted] = useState(false);
  const [shown, setShown] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const unmountTimer = useRef<number | null>(null);

  const reduce = () =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const close = useCallback(() => {
    setShown(false);
    triggerRef.current?.focus();
    if (unmountTimer.current !== null) window.clearTimeout(unmountTimer.current);
    unmountTimer.current = window.setTimeout(() => setMounted(false), reduce() ? 0 : JUMP_MENU_MS);
  }, []);

  const open = useCallback(() => {
    if (unmountTimer.current !== null) {
      window.clearTimeout(unmountTimer.current);
      unmountTimer.current = null;
    }
    setMounted(true);
  }, []);

  useEffect(
    () => () => {
      if (unmountTimer.current !== null) window.clearTimeout(unmountTimer.current);
    },
    [],
  );

  // Raise it one frame after it lands in the DOM, so the browser has a closed
  // state to animate *from* instead of painting the open one straight away.
  useEffect(() => {
    if (!mounted) return;
    const frame = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(frame);
  }, [mounted]);

  // Esc closes, like every other overlay on the site.
  useEffect(() => {
    if (!mounted) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mounted, close]);

  // Focus moves into the panel so a keyboard lands on the list.
  useEffect(() => {
    if (shown) panelRef.current?.focus();
  }, [shown]);

  // Eight entries fit, so the list does not scroll and the panel can claim the
  // vertical gesture for the swipe-down (without `touch-action: none` the
  // browser takes the pan for itself and cancels the pointer stream mid-drag).
  // If a large text setting ever makes the list overflow, scrolling it wins
  // over the swipe — the pill, a tap beside it and Esc still close the menu.
  const [scrollable, setScrollable] = useState(false);
  useEffect(() => {
    if (!shown) return;
    const list = listRef.current;
    setScrollable(Boolean(list && list.scrollHeight > list.clientHeight + 1));
  }, [shown]);

  // Swipe-down-to-dismiss, imperative: no React state changes while a finger
  // is on the panel, so nothing re-renders mid-gesture. The list hands the
  // gesture over only when it is scrolled to the top and the thumb travels
  // clearly downward, so an upward swipe still scrolls a long list.
  const dragRef = useRef({ startY: 0, lastY: 0, lastT: 0, vy: 0, active: false });
  const pressRef = useRef<{ y: number; id: number } | null>(null);
  const moveRaf = useRef(0);
  const pendingY = useRef(0);

  const settle = (el: HTMLElement, closing: boolean) => {
    el.style.transition = `transform ${JUMP_MENU_MS}ms var(--sw-ease), opacity var(--sw-dur-slow) var(--sw-ease)`;
    el.style.transform = closing ? "translateY(120%)" : "translateY(0) scale(1)";
    if (closing) el.style.opacity = "0";
  };

  const beginDrag = (clientY: number, pointerId: number) => {
    const el = panelRef.current;
    if (!el) return;
    dragRef.current = { startY: clientY, lastY: clientY, lastT: performance.now(), vy: 0, active: true };
    el.style.transition = "none"; // follow the finger 1:1
    try {
      // Capturing here also keeps the release from landing as a click on the
      // section link the gesture happened to start on.
      el.setPointerCapture(pointerId);
    } catch {
      /* Safari < 16 without capture still works via the element's own events. */
    }
  };

  const moveDrag = (clientY: number) => {
    const d = dragRef.current;
    if (!d.active) return;
    const now = performance.now();
    const dt = now - d.lastT;
    if (dt > 0) d.vy = (clientY - d.lastY) / dt; // px/ms, for the flick check
    d.lastY = clientY;
    d.lastT = now;
    pendingY.current = clientY;
    if (!moveRaf.current) {
      moveRaf.current = requestAnimationFrame(() => {
        moveRaf.current = 0;
        const el = panelRef.current;
        if (el && dragRef.current.active) {
          el.style.transform = `translateY(${Math.max(0, pendingY.current - dragRef.current.startY)}px)`;
        }
      });
    }
  };

  const endDrag = () => {
    pressRef.current = null;
    const d = dragRef.current;
    if (!d.active) return;
    d.active = false;
    if (moveRaf.current) {
      cancelAnimationFrame(moveRaf.current);
      moveRaf.current = 0;
    }
    const dy = d.lastY - d.startY;
    const closing = dy > 56 || (dy > 24 && d.vy > 0.4);
    const el = panelRef.current;
    if (el) settle(el, closing && !reduce());
    if (closing) close();
  };

  const onPanelPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    pressRef.current = { y: event.clientY, id: event.pointerId };
  };
  const onPanelPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.active) {
      moveDrag(event.clientY);
      return;
    }
    const press = pressRef.current;
    if (!press) return;
    if ((listRef.current?.scrollTop ?? 0) <= 0 && event.clientY - press.y > 14) {
      beginDrag(press.y, press.id);
      moveDrag(event.clientY);
    }
  };

  return (
    <div className="lg:hidden">
      {mounted && (
        <>
          {/* Tap anywhere beside the panel closes. A real element rather than a
              document listener, so nothing of this menu is listening once it is
              shut. */}
          <button
            type="button"
            aria-label={t("help.jump.close")}
            onClick={close}
            style={{ transition: "opacity var(--sw-dur-slow) var(--sw-ease)", opacity: shown ? 1 : 0 }}
            className="fixed inset-0 z-scrim bg-ink/25 backdrop-blur-[3px]"
          />
          {/* The outer box owns the position, the inner panel the motion: a
              Tailwind `-translate-x-1/2` on the moving element would be
              overwritten by every frame of the drag. */}
          <div className="fixed bottom-24 left-1/2 z-overlay -translate-x-1/2">
            <div
              ref={panelRef}
              tabIndex={-1}
              data-lenis-prevent
              role="dialog"
              aria-label={t("help.jump.label")}
              id={JUMP_MENU_ID}
              onPointerDown={onPanelPointerDown}
              onPointerMove={onPanelPointerMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
              style={{
                willChange: "transform",
                transition: `transform ${JUMP_MENU_MS}ms var(--sw-ease), opacity var(--sw-dur-slow) var(--sw-ease)`,
                // It grows out of the pill that opened it, so the origin is the
                // pill's edge and the closed state is small and low. Longer
                // than the house panel duration (300ms) because the travel is
                // longer too — a rise this large reads as a jump at 300ms.
                transformOrigin: "bottom center",
                transform: shown ? "translateY(0) scale(1)" : "translateY(28px) scale(0.86)",
                opacity: shown ? 1 : 0,
              }}
              className="flex max-h-[min(70vh,30rem)] w-[min(86vw,20rem)] flex-col rounded-card border border-line bg-page shadow-float focus:outline-none"
            >
              <ul
                ref={listRef}
                data-lenis-prevent
                // The list is the scroll container, so the browser reads the
                // gesture rules here — not on the panel around it.
                style={{ touchAction: scrollable ? "pan-y" : "none" }}
                className="no-scrollbar min-h-0 flex-1 overflow-y-auto p-2"
              >
                {JUMP.map((entry) => {
                  const current = entry.id === active;
                  return (
                    <li key={entry.id}>
                      <Link
                        to={{ hash: `#${entry.id}` }}
                        aria-current={current ? "true" : undefined}
                        // A swipe over the panel starts on one of these links,
                        // and the browser answers a drag off a link with its
                        // own native link-drag: that fires `dragstart` and
                        // cancels the pointer stream mid-gesture, so the swipe
                        // never reached its threshold and the menu stayed open.
                        draggable={false}
                        onClick={() => {
                          onJump(entry.id);
                          close();
                        }}
                        className={`flex min-h-11 items-center rounded-card px-3 py-2 text-ui transition-colors hover:bg-band ${
                          current ? "bg-band font-semibold text-ink" : "text-ink-soft"
                        }`}
                      >
                        {t(entry.title)}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </>
      )}

      {/* Same floating pill as the "Karte" control on the landing, results and
          spot-data pages: filled page colour, no stroke, travels with the
          scroll. One control per page, so they never meet.

          It sits on the panel's layer, not the page's: at `z-sticky` the open
          menu's scrim covered it, so the control that opened the menu could
          not close it again — the tap landed on the scrim instead. */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (mounted ? close() : open())}
        aria-label={t("help.jump.menuOpen")}
        aria-expanded={mounted}
        aria-controls={JUMP_MENU_ID}
        className="fixed bottom-6 left-1/2 z-overlay flex min-h-11 -translate-x-1/2 items-center gap-1.5 rounded-card bg-page px-4 py-2 text-ui font-normal text-ink shadow-float"
      >
        {t("help.jump.menu")} <MenuIcon className="text-body" />
      </button>
    </div>
  );
}
