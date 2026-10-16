import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

/**
 * Nutzungsbedingungen (Terms of Service) for the public account and the
 * user-generated content on the platform. Written in "Sie" (legal register),
 * honest about the project being a non-monetised, single-person tool — no
 * invented company, no commercial/SLA boilerplate. Includes a DSA-style
 * notice-and-action section for reporting illegal content, mapped to the
 * existing report function and the contact mailbox.
 */
const contactEmail = (import.meta.env.VITE_LEGAL_EMAIL || "").trim();
const emailConfigured = contactEmail !== "" && !contactEmail.endsWith(".invalid");

export default function Nutzungsbedingungen() {
  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-content px-4 pb-24 pt-32 sm:px-8">
        <h1 className="break-words text-heading font-semibold leading-tight text-ink [hyphens:auto] sm:text-heading-lg">
          Nutzungsbedingungen
        </h1>
        <div className="mt-6 space-y-8 text-body leading-relaxed text-ink-soft">
          <p>
            Diese Nutzungsbedingungen regeln die Nutzung von Surfwinddata, insbesondere des Kontos und
            der von Nutzerinnen und Nutzern beigetragenen Inhalte. Mit der Registrierung oder der Nutzung
            entsprechender Funktionen erklären Sie sich mit ihnen einverstanden.
          </p>

          <Section title="1. Anbieter und Angebot">
            <p>
              Surfwinddata ist derzeit ein nicht monetarisiertes Webtool und wird von einer Einzelperson
              in Deutschland entwickelt und betrieben. Angaben zum Anbieter finden Sie im{" "}
              <Link to="/impressum" className="text-ink underline">
                Impressum
              </Link>
              . Es bestehen keine kostenpflichtigen Angebote, Abonnements oder Buchungen.
            </p>
          </Section>

          <Section title="2. Leistung und Verfügbarkeit">
            <p>
              Die Plattform wird ohne Zusage einer bestimmten Verfügbarkeit bereitgestellt. Funktionen
              können sich ändern, zeitweise nicht verfügbar sein oder eingestellt werden. Noch nicht
              verfügbare Bereiche werden gekennzeichnet. Ein Anspruch auf einen bestimmten Funktionsumfang
              besteht nicht.
            </p>
          </Section>

          <Section title="3. Konto und Mindestalter">
            <p>
              Für bestimmte Funktionen ist ein Konto erforderlich. Ihre Angaben müssen zutreffend sein,
              und Sie sind für die Sicherheit Ihrer Zugangsdaten verantwortlich. Für die Nutzung eines
              Kontos müssen Sie mindestens 16 Jahre alt sein. Sie können Ihr Konto jederzeit in den
              Kontoeinstellungen löschen.
            </p>
          </Section>

          <Section title="4. Nutzerinhalte und Regeln">
            <p>
              Für von Ihnen beigetragene Inhalte (Spotvorschläge, Bewertungen, Tipps, Fotos) sind Sie
              verantwortlich. Sie dürfen nur Inhalte einstellen, an denen Sie die erforderlichen Rechte
              besitzen und die keine Rechte Dritter oder geltendes Recht verletzen. Unzulässig sind
              insbesondere rechtswidrige, beleidigende, irreführende oder die Privatsphäre Dritter
              verletzende Inhalte sowie Spam.
            </p>
          </Section>

          <Section title="5. Rechte an Inhalten">
            <p>
              Die Rechte an Ihren Inhalten verbleiben bei Ihnen. Sie räumen dem Anbieter ein einfaches,
              widerrufliches Recht ein, Ihre beigetragenen Inhalte im Rahmen der Plattform zu speichern,
              anzuzeigen und für die Darstellung technisch aufzubereiten. Bei Fotos gilt zusätzlich die
              beim Hochladen bestätigte Rechte- und Einwilligungserklärung.
            </p>
          </Section>

          <Section title="6. Moderation und Entfernung">
            <p>
              Beiträge können vor einer Veröffentlichung geprüft und im laufenden Betrieb moderiert
              werden. Inhalte, die gegen diese Bedingungen oder geltendes Recht verstoßen, können
              bearbeitet, ausgeblendet oder entfernt werden.
            </p>
          </Section>

          <Section title="7. Meldung rechtswidriger Inhalte (Notice-and-Action)">
            <p>
              Rechtswidrige oder rechtsverletzende Inhalte können Sie melden. Für Bilder nutzen Sie die
              Meldefunktion direkt am Beitrag; für alle übrigen Hinweise wenden Sie sich an den Betreiber{" "}
              {emailConfigured ? (
                <>
                  unter{" "}
                  <a href={`mailto:${contactEmail}`} className="text-ink underline">
                    {contactEmail}
                  </a>
                </>
              ) : (
                <>über die Kontaktseite</>
              )}
              . Hilfreich sind der Link zum Beitrag, eine Beschreibung des Problems und – soweit möglich –
              die rechtliche Einordnung.
            </p>
            <p>
              Eingehende Meldungen werden geprüft. Sofern Sie eine Kontaktadresse angeben, informieren wir
              Sie über das Ergebnis und die wesentliche Begründung einer getroffenen Entscheidung. Gegen
              eine Entscheidung können Sie uns gegenüber Einwände erheben. Weitere Hinweise finden Sie auf
              der{" "}
              <Link to="/kontakt" className="text-ink underline">
                Kontaktseite
              </Link>
              .
            </p>
          </Section>

          <Section title="8. Haftung und Hinweise">
            <p>
              Wetter- und Spotangaben beruhen auf Modellen und Beiträgen und stellen keine Zusicherung
              dar. Sie ersetzen keine eigene Beurteilung der Bedingungen vor Ort. Die Nutzung erfolgt auf
              eigene Verantwortung. Eine Haftung besteht nur nach den gesetzlichen Vorschriften,
              insbesondere für Vorsatz und grobe Fahrlässigkeit sowie für Schäden aus der Verletzung von
              Leben, Körper oder Gesundheit.
            </p>
          </Section>

          <Section title="9. Beendigung">
            <p>
              Sie können Ihr Konto jederzeit löschen. Der Anbieter kann die Nutzung bei Verstößen gegen
              diese Bedingungen oder geltendes Recht einschränken oder beenden.
            </p>
          </Section>

          <Section title="10. Änderungen dieser Bedingungen">
            <p>
              Diese Bedingungen können angepasst werden, etwa bei Änderungen des Funktionsumfangs oder der
              Rechtslage. Die jeweils aktuelle Fassung ist auf dieser Seite abrufbar.
            </p>
          </Section>

          <Section title="11. Anwendbares Recht">
            <p>
              Es gilt das Recht der Bundesrepublik Deutschland unter Ausschluss des UN-Kaufrechts.
              Zwingende verbraucherschützende Vorschriften Ihres Aufenthaltsstaates bleiben unberührt.
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
