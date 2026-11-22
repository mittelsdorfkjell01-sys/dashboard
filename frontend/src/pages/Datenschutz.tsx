import type { ReactNode } from "react";
import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";
import PageBackLink from "../components/PageBackLink";
import ScrollBackButton from "../components/ScrollBackButton";
import { DATENSCHUTZ_SECTIONS, legalTitle, type DatenschutzSectionId } from "../lib/infoSections";

/**
 * Datenschutzerklärung — structured along the data flows that are actually
 * active in this codebase (account/session cookie, favourites, rider setup,
 * community posts, anonymous reach events) rather than a generic template. The
 * controller block is env-driven (same source as the Impressum); in a
 * development view it shows honest placeholders instead of real operator data.
 * Legal text addresses the reader with "Sie".
 */
const controller = {
  operator: import.meta.env.VITE_LEGAL_OPERATOR || "Nicht für Produktion freigegeben",
  street: import.meta.env.VITE_LEGAL_STREET || "Entwicklungsansicht",
  postalCity: import.meta.env.VITE_LEGAL_POSTAL_CITY || "Entwicklungsansicht",
  email: import.meta.env.VITE_LEGAL_EMAIL || "nicht-konfiguriert@example.invalid",
};

export default function Datenschutz() {
  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-content px-4 pb-24 pt-32 sm:px-8">
        <PageBackLink className="mb-2" />
        <ScrollBackButton />
        <h1 className="break-words text-title font-semibold leading-tight text-ink [hyphens:auto]">
          Datenschutzerklärung
        </h1>
        <div className="mt-5 space-y-7 text-ui leading-relaxed text-ink-soft">
          <p>
            Diese Erklärung beschreibt, welche personenbezogenen Daten beim Besuch und bei der Nutzung
            von Surfwinddata verarbeitet werden. Grundlage ist der tatsächliche Funktionsumfang der
            Plattform. Begriffe wie „wir" beziehen sich auf die verantwortliche Stelle.
          </p>

          <Section id="verantwortlicher">
            <p>
              {controller.operator}
              <br />
              {controller.street}
              <br />
              {controller.postalCity}
              <br />
              <a className="text-ink underline" href={`mailto:${controller.email}`}>
                {controller.email}
              </a>
            </p>
            <p>
              Für Fragen zum Datenschutz erreichen Sie uns unter der genannten Adresse. Ein gesonderter
              Datenschutzbeauftragter ist für diesen Dienst nicht bestellt.
            </p>
          </Section>

          <Section id="websiteaufruf">
            <p>
              Beim Aufruf der Seite verarbeitet die Infrastruktur technisch notwendige Verbindungsdaten
              (etwa IP-Adresse, Zeitpunkt, angeforderte Ressource), um die Seite auszuliefern und den
              Betrieb abzusichern. Zum Schutz vor Missbrauch verwenden wir kurzlebige, gehashte
              IP-Adressen; sie werden nach 90 Tagen anonymisiert.
            </p>
            <p>Rechtsgrundlage: berechtigtes Interesse an einem sicheren, funktionsfähigen Betrieb.</p>
          </Section>

          <Section id="konto">
            <p>
              Für ein Konto verarbeiten wir Ihre E-Mail-Adresse, einen frei wählbaren Anzeigenamen und
              Ihr Passwort (ausschließlich als Hash). Für Bestätigung, Anmeldung, Adresswechsel und
              Passwortwiederherstellung versenden wir transaktionale E-Mails mit Bestätigungslinks. Die
              Anmeldung wird über ein technisch notwendiges, serverseitig gesetztes Sitzungs-Cookie
              (httpOnly) gehalten.
            </p>
            <p>
              Sie können sich alternativ mit Ihrem Google- oder Apple-Konto anmelden. Dann werden Sie zur
              Anmeldeseite von Google (Google Ireland Limited) bzw. Apple (Apple Distribution
              International Ltd.) weitergeleitet; dort gelten deren Datenschutzbestimmungen. Wir erhalten
              von dort eine dauerhafte Kennung Ihres Kontos, Ihre E-Mail-Adresse und ob diese bestätigt
              ist sowie, falls übermittelt, Ihren Namen. Bei Apple kann die E-Mail-Adresse eine
              Weiterleitungsadresse sein. Gibt es bereits ein Konto mit derselben bestätigten
              E-Mail-Adresse, wird die Anmeldung mit diesem Konto verknüpft. Für den Ablauf setzen wir ein
              technisch notwendiges Cookie (httpOnly, höchstens 10 Minuten), das ihn an Ihren Browser
              bindet.
            </p>
            <p>Rechtsgrundlage: Vertragserfüllung (Bereitstellung des Kontos).</p>
          </Section>

          <Section id="einstellungen">
            <p>
              In Ihrem Konto speichern wir Ihre Favoriten, bevorzugte Sportarten, Anzeigeeinheiten und
              vergleichbare persönliche Einstellungen, damit die Plattform für Sie nutzbar und
              vorkonfiguriert bleibt.
            </p>
            <p>
              Auf der Karte eines Spots können Sie einen eigenen Standort festlegen, entweder über die
              Standortfreigabe Ihres Browsers oder indem Sie ihn auf der Karte wählen. Wir speichern
              diesen Standort nur, wenn Sie ihn selbst setzen, auf etwa 10 Meter gerundet. Er wird
              nicht im Hintergrund verfolgt. Er liegt in Ihrem Browser und, wenn Sie angemeldet sind,
              zusätzlich in Ihrem Konto, damit er auf Ihren Geräten gleich ist. Er dient nur dazu, die
              Entfernung zum Spot anzuzeigen und eine Route zu öffnen. Über „Entfernen" auf der Karte
              löschen Sie ihn im Browser und im Konto.
            </p>
            <p>
              Tippen Sie auf „Route", öffnen wir Apple Karten bzw. Google Maps mit dem Ziel und,
              falls gesetzt, Ihrem Standort als Startpunkt. Ab dann gelten die Datenschutzhinweise des
              jeweiligen Anbieters.
            </p>
            <p>
              Rechtsgrundlage: Vertragserfüllung; für den Standort Ihre Einwilligung, die Sie durch das
              Setzen erteilen und durch „Entfernen" jederzeit widerrufen können.
            </p>
          </Section>

          <Section id="setup">
            <p>
              Wenn Sie „Mein Setup" ausfüllen, verarbeiten wir freiwillige Angaben wie Gewicht, Level,
              Ausrüstung, Fahrvorlieben und optional einen ungefähren Heimatort. Diese Angaben dienen der
              persönlichen Spot-Auswahl und sind jederzeit änder- oder löschbar.
            </p>
            <p>Rechtsgrundlage: Vertragserfüllung bzw. Ihre Einwilligung bei freiwilligen Angaben.</p>
          </Section>

          <Section id="beitraege">
            <p>
              Reichen Sie einen Spot vor oder veröffentlichen Sie Bewertungen, Tipps oder Fotos, werden
              diese Inhalte mit dem von Ihnen gewählten Namen verarbeitet und können öffentlich sichtbar
              sein. Für Fotos bestätigen Sie vor dem Hochladen eine Rechte- und Einwilligungserklärung.
              Beiträge werden vor einer Veröffentlichung bzw. im laufenden Betrieb redaktionell moderiert.
            </p>
            <p>Rechtsgrundlage: Ihre Einwilligung für freiwillige Veröffentlichungen.</p>
          </Section>

          <Section id="reichweite">
            <p>
              Zur Verbesserung und Qualitätsmessung erfassen wir Nutzungsereignisse (zum Beispiel
              Ansichten, Klicks, Suchen und Favoriten-Aktionen). Dafür wird im Browser eine zufällige,
              nicht an Ihren Namen gebundene Kennung gespeichert. Angemeldeten Konten zugeordnete
              Ereignisse sind im Datenexport enthalten und werden mit dem Konto gelöscht; anonyme
              Ereignisse werden standardmäßig nach 180 Tagen gelöscht.
            </p>
            <p>Rechtsgrundlage: berechtigtes Interesse an Reichweiten- und Qualitätsmessung.</p>
          </Section>

          <Section id="cookies">
            <p>Wir setzen keine Werbe- oder Tracking-Cookies Dritter. Verwendet werden:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li>
                ein technisch notwendiges Sitzungs-Cookie (httpOnly) für die Anmeldung;
              </li>
              <li>
                nach einer Registrierung ein technisch notwendiges Cookie (httpOnly, höchstens 24 Stunden)
                mit einer Zufallskennung. Es erkennt, dass Sie den Bestätigungslink in demselben Browser
                öffnen, und wird bei der Bestätigung gelöscht. Öffnen Sie den Link auf einem anderen
                Gerät, legen Sie Ihr Passwort dort fest;
              </li>
              <li>
                lokale Speicherung im Browser (localStorage) für funktionale Zwecke wie Ihr Farbschema,
                Ihre Anzeigeeinheiten/Einstellungen, zuletzt gesuchte Spots und einen von Ihnen
                gesetzten Kartenstandort (siehe Punkt 4);
              </li>
              <li>
                eine zufällige, nicht namensbezogene Kennung für die unter Punkt 7 beschriebene
                Reichweitenmessung.
              </li>
            </ul>
            <p>
              Diese Speicherung ist technisch notwendig bzw. funktional. Lokale Einträge können Sie
              jederzeit über Ihren Browser löschen.
            </p>
          </Section>

          <Section id="dienste">
            <p>Zum Betrieb der Plattform setzen wir je nach Deployment folgende Dienste ein:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li>Hosting und Serverfunktionen: Vercel.</li>
              <li>Datenbank: Neon (PostgreSQL).</li>
              <li>Medienspeicher: lokaler Server-Speicher oder Vercel Blob.</li>
              <li>E-Mail-Versand: der konfigurierte SMTP-Dienstleister.</li>
              <li>
                Karten: Kartenkacheln und Schriften von OpenFreeMap, CARTO, Esri/ArcGIS und MapTiler
                auf Basis von OpenStreetMap-Daten.
              </li>
              <li>
                Orte in der Nähe eines Spots (Cafés, Parkplätze u. a.): OpenStreetMap über einen
                Overpass-Dienst, serverseitig abgefragt.
              </li>
              <li>Wetterdaten: Open-Meteo.</li>
            </ul>
            <p>
              Beim Laden von Karten können technisch bedingt Verbindungsdaten (einschließlich
              IP-Adresse) an den jeweiligen Kartenanbieter übermittelt werden. Wetterdaten werden
              serverseitig bezogen; dabei wird Ihre IP-Adresse nicht an den Wetteranbieter übermittelt.
              Dasselbe gilt für die Orte in der Nähe eines Spots. Ihr eigener Standort wird an keinen
              dieser Dienste übermittelt.
            </p>
          </Section>

          <Section id="drittlaender">
            <p>
              Soweit einzelne der genannten Anbieter Daten außerhalb der EU bzw. des EWR (etwa in den
              USA) verarbeiten, erfolgt dies auf Grundlage geeigneter Garantien im Sinne der DSGVO, zum
              Beispiel eines Angemessenheitsbeschlusses oder von Standardvertragsklauseln. Eine
              Übermittlung findet nur statt, soweit sie für den beschriebenen Betrieb erforderlich ist.
            </p>
          </Section>

          <Section id="speicherdauer">
            <p>
              Kontodaten werden bis zur Löschung des Kontos gespeichert. Den Datenexport und die
              Kontolöschung finden Sie in den Kontoeinstellungen. Bei einer Löschung werden
              Kontoverknüpfungen und Autorendaten entfernt; bereits veröffentlichte Beiträge können
              anonymisiert erhalten bleiben. In Freitexten oder Bildern enthaltene Angaben werden dadurch
              nicht automatisch vollständig unkenntlich. Technische Sicherungskopien können für eine
              begrenzte Zeit fortbestehen, bis sie planmäßig überschrieben werden.
            </p>
          </Section>

          <Section id="rechtsgrundlagen">
            <p>
              Die Kontobereitstellung erfolgt zur Vertragserfüllung (Art. 6 Abs. 1 lit. b DSGVO),
              Sicherheits- und Reichweitenmaßnahmen auf Grundlage berechtigter Interessen (lit. f) und
              freiwillige Veröffentlichungen auf Grundlage Ihrer Einwilligung (lit. a). Eine erteilte
              Einwilligung können Sie mit Wirkung für die Zukunft widerrufen.
            </p>
          </Section>

          <Section id="rechte">
            <p>
              Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung,
              Datenübertragbarkeit und Widerspruch. Außerdem besteht ein Beschwerderecht bei einer
              Datenschutzaufsichtsbehörde. Zuständig ist die Aufsichtsbehörde des Bundeslandes, in dem
              die verantwortliche Stelle ihren Sitz hat; Sie können sich auch an die Behörde Ihres
              gewöhnlichen Aufenthalts wenden.
            </p>
          </Section>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function Section({ id, children }: { id: DatenschutzSectionId; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 space-y-3">
      <h2 className="text-body font-semibold text-ink">{legalTitle(DATENSCHUTZ_SECTIONS, id)}</h2>
      {children}
    </section>
  );
}
