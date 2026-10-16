import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

/**
 * "Kontakt" — a real, public contact page without a support backend. The only
 * channel is the operator's configured, actually-monitored mailbox: a `mailto:`
 * and a copy-to-clipboard affordance. No simulated form submission, no promised
 * delivery, no invented department or response-time SLA.
 *
 * The email comes from VITE_LEGAL_EMAIL (same source as Impressum/Datenschutz).
 * When it is unconfigured in a development view, the page says so honestly
 * instead of printing a dead placeholder address.
 */
const CONTACT_EMAIL = (import.meta.env.VITE_LEGAL_EMAIL || "").trim();
const EMAIL_CONFIGURED = CONTACT_EMAIL !== "" && !CONTACT_EMAIL.endsWith(".invalid");

export default function Kontakt() {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  useEffect(() => {
    document.title = "Kontakt — surfwind data";
  }, []);

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

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-content px-4 pb-24 pt-32 sm:px-8">
        <h1 className="text-heading-lg font-semibold text-ink">Kontakt</h1>
        <p className="mt-3 text-body leading-relaxed text-ink-soft">
          Du hast eine Frage, findest einen Fehler oder möchtest etwas zu
          Surfwinddata beitragen? Schreib dem Betreiber.
        </p>

        {/* Primary channel: the operator mailbox */}
        <section className="mt-8 rounded-card border border-line bg-surface p-5 sm:p-6">
          {EMAIL_CONFIGURED ? (
            <>
              <p className="text-caption font-semibold uppercase tracking-wide text-muted">
                E-Mail
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
                  E-Mail schreiben
                </a>
                <button
                  type="button"
                  onClick={() => void copy()}
                  className="inline-flex min-h-11 items-center justify-center rounded-card border border-line bg-surface px-5 text-ui font-semibold text-ink transition-colors hover:bg-band"
                >
                  Adresse kopieren
                </button>
              </div>
              <p role="status" aria-live="polite" className="mt-3 min-h-5 text-ui text-muted">
                {copied && "E-Mail-Adresse kopiert."}
                {copyError && "Kopieren nicht möglich. Markiere die Adresse oben und kopiere sie manuell."}
              </p>
            </>
          ) : (
            <p role="status" className="text-ui text-muted">
              Die Kontaktadresse ist in dieser Ansicht noch nicht konfiguriert.
              In der Produktionsumgebung steht hier die betreute E-Mail-Adresse
              des Betreibers.
            </p>
          )}
        </section>

        {/* What to include per topic */}
        <section className="mt-10">
          <h2 className="text-lead font-semibold text-ink">Worum geht es?</h2>
          <p className="mt-1 text-ui text-muted">
            Je genauer deine Angaben, desto schneller lässt sich helfen.
          </p>
          <dl className="mt-5 space-y-5">
            <Topic term="Fehler an einem Spot">
              Nenne den Spotlink, die betroffene Angabe, eine möglichst aktuelle
              Quelle und – falls bekannt – das Datum.
            </Topic>
            <Topic term="Hilfe zum Konto">
              Beschreibe den Schritt und das Problem. Deine Konto-E-Mail nur
              soweit nötig. Sende niemals dein Passwort, einen Code oder einen
              Wiederherstellungslink.
            </Topic>
            <Topic term="Technischer Fehler">
              Nenne Seite, Gerät, Browser sowie erwartetes und tatsächliches
              Verhalten. Entferne personenbezogene Daten aus Screenshots.
            </Topic>
            <Topic term="Neuen Spot vorschlagen">
              Neue Spots reichst du direkt über dein Konto ein:{" "}
              <Link to="/konto/spots" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
                Spots hinzufügen
              </Link>
              . Dafür ist eine Anmeldung nötig.
            </Topic>
            <Topic term="Rechtswidrige Inhalte melden">
              Für Bilder nutzt du die Meldefunktion direkt am Beitrag. Für alle
              übrigen rechtswidrigen oder rechtsverletzenden Inhalte schreib dem
              Betreiber mit Link zum Beitrag, einer Beschreibung und – soweit
              möglich – der rechtlichen Einordnung. Das Vorgehen ist in den{" "}
              <Link to="/nutzungsbedingungen" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
                Nutzungsbedingungen
              </Link>{" "}
              beschrieben.
            </Topic>
            <Topic term="Datenschutz">
              Verwende die Kontaktadresse oben. Hintergründe findest du in der{" "}
              <Link to="/datenschutz" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
                Datenschutzerklärung
              </Link>{" "}
              und in den{" "}
              <Link to="/konto/einstellungen" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
                Kontoeinstellungen
              </Link>
              .
            </Topic>
            <Topic term="Sicherheitslücke">
              Melde Sicherheitslücken vertraulich über den privaten
              Security-Advisory-Weg des Repositorys (GitHub: Tab „Security“ →
              „Report a vulnerability“). Sende keine Zugangsdaten oder Secrets im
              Klartext.
            </Topic>
          </dl>
        </section>

        {/* Honest expectations */}
        <section className="mt-10 border-t border-line pt-6">
          <p className="text-ui text-muted">
            Surfwinddata wird als nicht monetarisiertes Webtool von einer
            Einzelperson betreut. Eine feste Antwortzeit wird nicht zugesagt.
          </p>
          <p className="mt-2 text-ui text-muted">
            Diese Kontaktadresse ist kein Notfall- oder Rettungsdienst.
          </p>
        </section>
      </main>
      <Footer />
    </div>
  );
}

function Topic({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-body font-semibold text-ink">{term}</dt>
      <dd className="mt-1 max-w-measure text-ui leading-relaxed text-ink-soft">{children}</dd>
    </div>
  );
}
