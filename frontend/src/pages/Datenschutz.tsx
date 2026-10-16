import type { ReactNode } from "react";
import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

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
        <h1 className="break-words text-heading font-semibold leading-tight text-ink [hyphens:auto] sm:text-heading-lg">
          Datenschutzerklärung
        </h1>
        <div className="mt-6 space-y-8 text-body leading-relaxed text-ink-soft">
          <p>
            Diese Erklärung beschreibt, welche personenbezogenen Daten beim Besuch und bei der Nutzung
            von Surfwinddata verarbeitet werden. Grundlage ist der tatsächliche Funktionsumfang der
            Plattform. Begriffe wie „wir" beziehen sich auf die verantwortliche Stelle.
          </p>

          <Section title="1. Verantwortlicher und Datenschutzkontakt">
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

          <Section title="2. Websiteaufruf, Server-Protokolle und Missbrauchsschutz">
            <p>
              Beim Aufruf der Seite verarbeitet die Infrastruktur technisch notwendige Verbindungsdaten
              (etwa IP-Adresse, Zeitpunkt, angeforderte Ressource), um die Seite auszuliefern und den
              Betrieb abzusichern. Zum Schutz vor Missbrauch verwenden wir kurzlebige, gehashte
              IP-Adressen; sie werden nach 90 Tagen anonymisiert.
            </p>
            <p>Rechtsgrundlage: berechtigtes Interesse an einem sicheren, funktionsfähigen Betrieb.</p>
          </Section>

          <Section title="3. Konto, Bestätigung, Anmeldung und Passwortwiederherstellung">
            <p>
              Für ein Konto verarbeiten wir Ihre E-Mail-Adresse, einen frei wählbaren Anzeigenamen und
              Ihr Passwort (ausschließlich als Hash). Für Bestätigung, Anmeldung, Adresswechsel und
              Passwortwiederherstellung versenden wir transaktionale E-Mails mit Bestätigungslinks. Die
              Anmeldung wird über ein technisch notwendiges, serverseitig gesetztes Sitzungs-Cookie
              (httpOnly) gehalten.
            </p>
            <p>Rechtsgrundlage: Vertragserfüllung (Bereitstellung des Kontos).</p>
          </Section>

          <Section title="4. Favoriten, Sportarten, Einheiten und persönliche Einstellungen">
            <p>
              In Ihrem Konto speichern wir Ihre Favoriten, bevorzugte Sportarten, Anzeigeeinheiten und
              vergleichbare persönliche Einstellungen, damit die Plattform für Sie nutzbar und
              vorkonfiguriert bleibt.
            </p>
            <p>Rechtsgrundlage: Vertragserfüllung.</p>
          </Section>

          <Section title="5. Rider- und Kite-Setup (Personalisierung)">
            <p>
              Wenn Sie „Mein Setup" ausfüllen, verarbeiten wir freiwillige Angaben wie Gewicht, Level,
              Ausrüstung, Fahrvorlieben und optional einen ungefähren Heimatort. Diese Angaben dienen der
              persönlichen Spot-Auswahl und sind jederzeit änder- oder löschbar.
            </p>
            <p>Rechtsgrundlage: Vertragserfüllung bzw. Ihre Einwilligung bei freiwilligen Angaben.</p>
          </Section>

          <Section title="6. Spotvorschläge und Community-Beiträge">
            <p>
              Reichen Sie einen Spot vor oder veröffentlichen Sie Bewertungen, Tipps oder Fotos, werden
              diese Inhalte mit dem von Ihnen gewählten Namen verarbeitet und können öffentlich sichtbar
              sein. Für Fotos bestätigen Sie vor dem Hochladen eine Rechte- und Einwilligungserklärung.
              Beiträge werden vor einer Veröffentlichung bzw. im laufenden Betrieb redaktionell moderiert.
            </p>
            <p>Rechtsgrundlage: Ihre Einwilligung für freiwillige Veröffentlichungen.</p>
          </Section>

          <Section title="7. Nutzungsereignisse und Reichweitenmessung">
            <p>
              Zur Verbesserung und Qualitätsmessung erfassen wir Nutzungsereignisse (zum Beispiel
              Ansichten, Klicks, Suchen und Favoriten-Aktionen). Dafür wird im Browser eine zufällige,
              nicht an Ihren Namen gebundene Kennung gespeichert. Angemeldeten Konten zugeordnete
              Ereignisse sind im Datenexport enthalten und werden mit dem Konto gelöscht; anonyme
              Ereignisse werden standardmäßig nach 180 Tagen gelöscht.
            </p>
            <p>Rechtsgrundlage: berechtigtes Interesse an Reichweiten- und Qualitätsmessung.</p>
          </Section>

          <Section title="8. Cookies und lokale Speicherung">
            <p>Wir setzen keine Werbe- oder Tracking-Cookies Dritter. Verwendet werden:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li>
                ein technisch notwendiges Sitzungs-Cookie (httpOnly) für die Anmeldung;
              </li>
              <li>
                lokale Speicherung im Browser (localStorage) für funktionale Zwecke wie Ihr Farbschema,
                Ihre Anzeigeeinheiten/Einstellungen und zuletzt gesuchte Spots;
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

          <Section title="9. Dienste und Empfänger (Auftragsverarbeiter)">
            <p>Zum Betrieb der Plattform setzen wir je nach Deployment folgende Dienste ein:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li>Hosting und Serverfunktionen: Vercel.</li>
              <li>Datenbank: Neon (PostgreSQL).</li>
              <li>Medienspeicher: lokaler Server-Speicher oder Vercel Blob.</li>
              <li>E-Mail-Versand: der konfigurierte SMTP-Dienstleister.</li>
              <li>
                Karten: Kartenkacheln von CARTO, Esri/ArcGIS und MapTiler auf Basis von
                OpenStreetMap-Daten.
              </li>
              <li>Wetterdaten: Open-Meteo.</li>
            </ul>
            <p>
              Beim Laden von Karten können technisch bedingt Verbindungsdaten (einschließlich
              IP-Adresse) an den jeweiligen Kartenanbieter übermittelt werden. Wetterdaten werden
              serverseitig bezogen; dabei wird Ihre IP-Adresse nicht an den Wetteranbieter übermittelt.
            </p>
          </Section>

          <Section title="10. Übermittlung in Drittländer">
            <p>
              Soweit einzelne der genannten Anbieter Daten außerhalb der EU bzw. des EWR (etwa in den
              USA) verarbeiten, erfolgt dies auf Grundlage geeigneter Garantien im Sinne der DSGVO, zum
              Beispiel eines Angemessenheitsbeschlusses oder von Standardvertragsklauseln. Eine
              Übermittlung findet nur statt, soweit sie für den beschriebenen Betrieb erforderlich ist.
            </p>
          </Section>

          <Section title="11. Speicherdauer, Kontolöschung und Backups">
            <p>
              Kontodaten werden bis zur Löschung des Kontos gespeichert. Den Datenexport und die
              Kontolöschung finden Sie in den Kontoeinstellungen. Bei einer Löschung werden
              Kontoverknüpfungen und Autorendaten entfernt; bereits veröffentlichte Beiträge können
              anonymisiert erhalten bleiben. In Freitexten oder Bildern enthaltene Angaben werden dadurch
              nicht automatisch vollständig unkenntlich. Technische Sicherungskopien können für eine
              begrenzte Zeit fortbestehen, bis sie planmäßig überschrieben werden.
            </p>
          </Section>

          <Section title="12. Rechtsgrundlagen im Überblick">
            <p>
              Die Kontobereitstellung erfolgt zur Vertragserfüllung (Art. 6 Abs. 1 lit. b DSGVO),
              Sicherheits- und Reichweitenmaßnahmen auf Grundlage berechtigter Interessen (lit. f) und
              freiwillige Veröffentlichungen auf Grundlage Ihrer Einwilligung (lit. a). Eine erteilte
              Einwilligung können Sie mit Wirkung für die Zukunft widerrufen.
            </p>
          </Section>

          <Section title="13. Ihre Rechte und zuständige Aufsichtsbehörde">
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

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-body font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}
