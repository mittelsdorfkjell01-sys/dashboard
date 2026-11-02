import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";
import { ChevronDownIcon } from "../lib/icons";

/**
 * "Fragen und Antworten" — a small, public, sign-in-free help page. A native
 * <details>/<summary> accordion keeps it fully keyboard-accessible without
 * bespoke ARIA state, and there is deliberately no search box for a page this
 * size. Answers describe the product as it actually behaves today; none promise
 * internal score numbers, match categories or per-user recommendation reasons.
 */
type QA = { q: string; a: ReactNode };
type Group = { id: string; title: string; items: QA[] };

const GROUPS: Group[] = [
  {
    id: "spots",
    title: "Spots entdecken",
    items: [
      {
        q: "Was ist Surfwinddata?",
        a: "Surfwinddata hilft dir, Wassersport-Spots zu entdecken und Bedingungen für deine Planung einzuordnen. Du findest Informationen zu Spots und Regionen, Wettervorhersagen und saisonalen Windverhältnissen.",
      },
      {
        q: "Ist Surfwinddata ein kommerzielles Angebot?",
        a: "Surfwinddata ist derzeit ein nicht monetarisiertes Webtool. Es wird von einer Einzelperson in Deutschland entwickelt und betreut.",
      },
      {
        q: "Für welche Sportarten ist das Tool gedacht?",
        a: "Die Plattform unterscheidet Surfen, Windsurfen, Kitesurfen und Wingfoilen. Welche Sportarten an einem Spot geeignet sind, steht auf seiner Detailseite. Kitefoil, Windfoil und Wingfoil können unterschiedliche Anforderungen haben.",
      },
      {
        q: "Kann ich ohne Konto nach Spots suchen?",
        a: "Ja. Den öffentlichen Katalog, die Karte und Spotinformationen kannst du ohne Anmeldung nutzen. Für persönliche Favoriten, Besuche, dein Setup und kontobezogene Vorschläge brauchst du ein Konto.",
      },
      {
        q: "Wie finde ich einen bestimmten Spot oder eine Region?",
        a: "Nutze die Suche oder erkunde Spots auf der Karte. Auf der Detailseite findest du Informationen zum Ort und die verfügbaren Wetterdaten.",
      },
      {
        q: "Ist die Spotliste vollständig?",
        a: "Nein. Der Katalog wird erweitert und kann Lücken enthalten. Fehlende Spots kannst du über dein Konto vorschlagen.",
      },
      {
        q: "Warum fehlt ein Spot in einer Empfehlungsliste?",
        a: "Empfehlungslisten sind eine Auswahl und kein vollständiger Spotkatalog. Nutze die Suche oder Karte, wenn du einen bestimmten Spot suchst. Sein Fehlen in einer Liste bedeutet nicht, dass er ungeeignet ist.",
      },
      {
        q: "Was bedeutet das Zeichen am Spotnamen?",
        a: "Es kennzeichnet einen Spot, den wir selbst erfasst haben. Spots ohne dieses Zeichen hat jemand aus der Community eingetragen; am Fuß der Spotseite steht, wer. Das Zeichen ist keine Qualitäts- oder Sicherheitsbewertung: jeder Spot geht durch dieselbe Freigabe, und es sagt nur, wer die Angaben eingetragen hat.",
      },
      {
        q: "Ist ein Spoteintrag eine Sicherheitsfreigabe?",
        a: "Nein. Prüfe Wetter, Strömung, Wasserstand, lokale Regeln, Sperrungen und deine eigenen Fähigkeiten vor Ort. Nutze lokale Informationen und fahre im Zweifel nicht hinaus.",
      },
    ],
  },
  {
    id: "forecast-climate",
    title: "Wetter und Saison",
    items: [
      {
        q: "Wie zuverlässig sind Wettervorhersagen?",
        a: "Vorhersagen sind Modellberechnungen. Lokale Effekte und wechselnde Bedingungen können davon abweichen. Mit größerem zeitlichem Abstand nimmt die Unsicherheit in der Regel zu. Prüfe vor deiner Session aktuelle Bedingungen und lokale Hinweise.",
      },
      {
        q: "Was unterscheidet Vorhersage und Windklimatologie?",
        a: "Die Vorhersage beschreibt erwartete Bedingungen der kommenden Tage. Die Windklimatologie beschreibt typische Verhältnisse aus vergangenen Zeiträumen. Sie hilft bei saisonaler Planung, sagt aber nicht das Wetter an einem bestimmten zukünftigen Tag voraus.",
      },
      {
        q: "Sind saisonale Prozentwerte eine Wettergarantie?",
        a: "Nein. Sie beschreiben Häufigkeiten für das angegebene Zeitfenster und die dargestellten Bedingungen. Beachte die Beschriftung und die Methodik des jeweiligen Diagramms.",
      },
      {
        q: "Was bedeutet eine fehlende Wetterangabe?",
        a: "Für diesen Wert stehen zurzeit keine verwendbaren Daten zur Verfügung. Das bedeutet nicht Windstille, keine Wellen oder gefahrlose Bedingungen.",
      },
      {
        q: "Wie lese ich die Windrichtung?",
        a: "Sie beschreibt, aus welcher Richtung der Wind kommt. Ob sie auflandig, seitlich oder ablandig ist, hängt vom Küstenverlauf und deinem konkreten Einstieg ab.",
      },
      {
        q: "Woher stammen die Daten?",
        a: (
          <>
            Redaktionelle Spot- und Regionsinformationen stammen vom Betreiber
            und aus Community-Beiträgen. Wetterdaten basieren auf
            Wettermodellen; die Kartendarstellung nutzt OpenStreetMap-Daten und
            externe Kartenanbieter. Die aktuell eingesetzten Dienste sind in der{" "}
            <Link to="/datenschutz" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
              Datenschutzerklärung
            </Link>{" "}
            genannt.
          </>
        ),
      },
      {
        q: "Warum weichen Werte von anderen Wetter-Apps ab?",
        a: "Anwendungen können unterschiedliche Modelle, Aktualisierungszeiten, Höhen, Zeitpunkte und Darstellungsintervalle verwenden. Vergleiche deshalb auch Quelle und Bezugszeit.",
      },
    ],
  },
  {
    id: "konto",
    title: "Konto und Setup",
    items: [
      {
        q: "Wozu dient Mein Setup?",
        a: "Hier kannst du deine Kite-Ausrüstung und Fahrvorlieben hinterlegen. Angaben wie Gewicht, Level, Kites und Board-Typ unterstützen die persönliche Spot-Auswahl. Die detaillierte Setup-Funktion ist derzeit auf Kitesurfen ausgerichtet.",
      },
      {
        q: "Muss ich meinen Heimatort angeben?",
        a: "Nein. Er ist optional und lässt sich ändern oder entfernen. Ein ungefährer Ausgangspunkt für deine Planung reicht aus.",
      },
      {
        q: "Wer kann mein Profil sehen?",
        a: "Die Profilübersicht ist Teil deines Kontos. Eine öffentliche Profilseite gibt es derzeit nicht. Für veröffentlichte Community-Beiträge gelten eigene Sichtbarkeitsregeln.",
      },
      {
        q: "Wie ändere ich Einheiten und Kontodaten?",
        a: (
          <>
            Die verfügbaren Kontodaten, Anzeigeeinheiten und persönlichen
            Bedingungen findest du unter{" "}
            <Link to="/konto/einstellungen" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
              Einstellungen
            </Link>
            .
          </>
        ),
      },
      {
        q: "Wie exportiere oder lösche ich meine Daten?",
        a: (
          <>
            Nutze die entsprechenden Aktionen in den{" "}
            <Link to="/konto/einstellungen" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
              Kontoeinstellungen
            </Link>
            . Beachte vor der Löschung die Hinweise zu veröffentlichten
            Beiträgen. Wenn du dich nicht mehr anmelden kannst, nutze die{" "}
            <Link to="/kontakt" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
              Kontaktseite
            </Link>
            .
          </>
        ),
      },
      {
        q: "Warum kommt keine Bestätigungs- oder Passwort-Mail an?",
        a: "Prüfe die eingegebene E-Mail-Adresse und den Spamordner. Nutze die erneute Anforderung, sofern angeboten. Wenn das nicht hilft, kontaktiere den Betreiber. Sende keine Passwörter oder Bestätigungslinks.",
      },
      {
        q: "Was bedeutet Geplant?",
        a: "Die Funktion ist vorgesehen, aber noch nicht nutzbar. Die Kennzeichnung nennt keinen Veröffentlichungstermin.",
      },
      {
        q: "Gibt es Wetteralarme?",
        a: "Wetteralarme sind derzeit noch nicht verfügbar. Benachrichtigungen über Spot-Vorschläge sind davon getrennt und hängen vom verfügbaren E-Mail-Versand ab.",
      },
    ],
  },
  {
    id: "mitmachen",
    title: "Mitmachen",
    items: [
      {
        q: "Wie schlage ich einen Spot vor?",
        a: (
          <>
            Öffne{" "}
            <Link to="/konto/spots" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
              Spots hinzufügen
            </Link>{" "}
            in deinem Konto. Trage Name, Region und Position ein; Sportarten
            kannst du ergänzen. Prüfe vorher, ob der Spot bereits vorhanden ist.
          </>
        ),
      },
      {
        q: "Ist mein Vorschlag sofort öffentlich?",
        a: "Nein. Er wird zunächst geprüft. Als Entwurf übernommen bedeutet, dass daraus ein redaktioneller Entwurf entstanden ist. Öffentlich wird der Spot erst nach Veröffentlichung.",
      },
      {
        q: "Wie melde ich falsche Angaben?",
        a: (
          <>
            Nutze die vorhandene Korrekturfunktion an einem Spot, sofern
            angeboten, oder die{" "}
            <Link to="/kontakt" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
              Kontaktseite
            </Link>
            . Nenne Spotlink, betroffene Angabe und möglichst eine aktuelle
            Quelle.
          </>
        ),
      },
    ],
  },
];

const GROUPS_EN: Group[] = [
  {
    id: "spots", title: "Discover spots", items: [
      { q: "What is Surfwinddata?", a: "Surfwinddata helps you discover watersports spots and put conditions into context for planning. It combines spot and region information with forecasts and seasonal wind data." },
      { q: "Which sports does it cover?", a: "The catalogue distinguishes surfing, windsurfing, kitesurfing and wing foiling. A spot page shows which sports are recorded there; foil disciplines can have different requirements." },
      { q: "Can I browse without an account?", a: "Yes. The catalogue, map and spot information are public. An account is needed for personal favourites, visits, setup details and account-linked suggestions." },
      { q: "Is the spot catalogue complete?", a: "No. The catalogue is being expanded and may have gaps. You can suggest a missing spot from your account." },
      { q: "Is a listed spot a safety approval?", a: "No. Check current weather, currents, water level, local rules, closures and your own ability on site. If in doubt, do not go on the water." },
    ],
  },
  {
    id: "forecast-climate", title: "Forecasts, data and seasons", items: [
      { q: "How reliable are forecasts?", a: "Forecasts are model calculations, not guarantees. Local effects and changing conditions can differ from them, and uncertainty generally grows further into the future." },
      { q: "What is the difference between a forecast and wind climatology?", a: "A forecast describes expected conditions over the coming days. Wind climatology summarises typical conditions from past periods; it cannot predict the weather on a particular future date." },
      { q: "Are seasonal percentages a weather guarantee?", a: "No. They describe frequencies for the labelled period and threshold. Always check the chart's units, time window and method." },
      { q: "What does a missing value mean?", a: "No usable data is currently available for that value. It does not mean calm wind, no waves or safe conditions." },
      { q: "How do I read wind direction?", a: "It describes where the wind comes from. Whether it is onshore, cross-shore or offshore depends on the local coastline and your exact launch point." },
      { q: "Where does the data come from?", a: "Editorial information comes from the operator and community contributions. Weather values come from forecast models; maps use OpenStreetMap and external map services. The active services are listed in the privacy notice." },
      { q: "Why do values differ from other weather apps?", a: "Apps may use different models, update times, heights, forecast steps and display intervals. Compare the source and reference time as well as the number itself." },
      { q: "Why is regional wind availability marked unknown?", a: "Surfwinddata does not yet turn individual spot forecasts into a regional promise. It remains unknown until a documented aggregation rule has been validated." },
    ],
  },
  {
    id: "account", title: "Account and setup", items: [
      { q: "What is My setup for?", a: "It stores your kite equipment and riding preferences to support personal spot selection. The detailed setup currently focuses on kitesurfing." },
      { q: "Do I have to enter a home location?", a: "No. It is optional and can be changed or removed at any time. An approximate starting point is enough for planning." },
      { q: "Who can see my profile?", a: "There is currently no public profile page. Published community contributions have their own visibility rules." },
      { q: "Are weather alerts available?", a: "Not yet. Alerts will only be introduced once reliable thresholds and delivery times are defined." },
    ],
  },
  {
    id: "contribute", title: "Contribute", items: [
      { q: "How can I suggest a spot?", a: "Open Add spots in your account, enter the name, region and position, and check first whether the spot already exists." },
      { q: "Is my suggestion public immediately?", a: "No. It is reviewed first. A public entry is created only after editorial approval and publication." },
      { q: "How do I report incorrect information?", a: "Use the correction option on the spot when available, or contact us. Include the spot link, the affected claim and a current source where possible." },
    ],
  },
];

export default function FAQ() {
  const { t, i18n } = useTranslation();
  const groups = i18n.resolvedLanguage === "en" ? GROUPS_EN : GROUPS;
  useEffect(() => {
    document.title = `${t("faq.title")} — surfwind data`;
  }, [t, i18n.resolvedLanguage]);

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-content px-4 pb-24 pt-32 sm:px-8">
        <h1 className="text-heading-lg font-semibold text-ink">{t("faq.title")}</h1>
        <p className="mt-3 text-body leading-relaxed text-ink-soft">
          {t("faq.intro")}
        </p>

        <div className="mt-10 space-y-12">
          {groups.map((group) => (
            <section id={group.id} key={group.id} aria-labelledby={`faq-${group.id}`} className="scroll-mt-24">
              <h2 id={`faq-${group.id}`} className="text-lead font-semibold text-ink">
                {group.title}
              </h2>
              <div className="mt-4 divide-y divide-line border-y border-line">
                {group.items.map((item) => (
                  <details key={item.q} className="group">
                    <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 py-4 text-left text-body font-semibold text-ink [&::-webkit-details-marker]:hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
                      {item.q}
                      <ChevronDownIcon className="shrink-0 text-lead text-muted transition-transform duration-base group-open:rotate-180 motion-reduce:transition-none" />
                    </summary>
                    <div className="max-w-measure pb-4 text-ui leading-relaxed text-ink-soft">
                      {item.a}
                    </div>
                  </details>
                ))}
              </div>
            </section>
          ))}
        </div>

        <div className="mt-12 border-t border-line pt-6">
          <p className="text-body font-semibold text-ink">{t("faq.open")}</p>
          <Link
            to="/kontakt"
            className="mt-3 inline-flex min-h-11 items-center rounded-card bg-ink px-5 text-ui font-semibold text-surface transition-opacity hover:opacity-90"
          >
            {t("faq.contact")}
          </Link>
        </div>
      </main>
      <Footer />
    </div>
  );
}
