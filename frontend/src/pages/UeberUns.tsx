import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

/**
 * "Über das Projekt" — an editorial, calm page that frames what Surfwinddata is
 * and, just as importantly, where its data ends. Public, no sign-in. Uses the
 * public editorial register (LandingHeader/Footer, max-w prose column). No
 * invented founder story, partnerships, funding or certification — the project
 * is a single person's non-monetised tool and says exactly that.
 */
export default function UeberUns() {
  useEffect(() => {
    document.title = "Über das Projekt — surfwind data";
  }, []);

  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader onLight />
      <main className="mx-auto max-w-content px-4 pb-24 pt-32 sm:px-8">
        <h1 className="text-heading-lg font-semibold text-ink">Über Surfwinddata</h1>
        <p className="mt-3 text-lead text-ink-soft">
          Spots entdecken. Bedingungen verstehen. Zeit auf dem Wasser planen.
        </p>

        <p className="mt-6 text-body leading-relaxed text-ink-soft">
          Surfwinddata bringt Informationen über Wassersport-Spots, Wetter und
          saisonale Windverhältnisse an einem Ort zusammen. Das Tool soll dir
          helfen, Orte zu entdecken und die nächsten Schritte deiner Planung
          besser einzuordnen.
        </p>

        <Section title="Zwei Fragen, ein Ausgangspunkt">
          <p>
            Manchmal weißt du bereits, wo du hinmöchtest: Du suchst einen Spot
            oder eine Region und möchtest verstehen, was dich dort erwartet.
          </p>
          <p>
            Manchmal steht zuerst dein Zeitfenster fest: Du hast ein Wochenende
            oder eine Reise vor dir und suchst nach interessanten Orten.
          </p>
          <p>
            Surfwinddata entwickelt Werkzeuge für beide Wege. Welche Funktionen
            bereits verfügbar sind, erkennst du auf der Plattform.
          </p>
        </Section>

        <Section title="Ein Ort ist mehr als ein Wetterwert">
          <p>
            Einstieg, Wassercharakter, örtliche Regeln und geeignete Sportarten
            gehören ebenso zu einem Spot wie Wind und Wellen. Deshalb stehen
            redaktionelle Informationen und Wetterdaten nebeneinander.
          </p>
        </Section>

        <Section title="Daten mit ihren Grenzen">
          <p>
            Vorhersagen können sich ändern. Saisonale Daten beschreiben typische
            Verhältnisse, keine Zusage für einen Reisetag. Fehlende Angaben
            sollen als fehlend erkennbar bleiben. Die Entscheidung vor Ort hängt
            von aktuellen Bedingungen, lokalen Informationen und deinem Können ab.
          </p>
        </Section>

        <Section title="Ein persönliches Projekt">
          <p>
            Surfwinddata ist aktuell ein nicht monetarisiertes Webtool. Es wird
            von einer Einzelperson in Deutschland entwickelt und betreut. Neue
            Funktionen entstehen schrittweise. Noch nicht verfügbare Bereiche
            werden entsprechend gekennzeichnet.
          </p>
          <p>
            <Link to="/impressum" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
              Zum Impressum
            </Link>
          </p>
        </Section>

        <Section title="Wissen vor Ort hilft">
          <p>
            Du kennst einen Spot, eine geänderte Regel oder einen Fehler? Deine
            Hinweise können helfen, den Katalog zu verbessern. Neue Spots kannst
            du über dein Konto vorschlagen. Für Korrekturen und andere Hinweise
            erreichst du den Betreiber über die Kontaktseite.
          </p>
        </Section>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Link
            to="/search"
            className="inline-flex min-h-11 items-center justify-center rounded-card bg-ink px-5 text-ui font-semibold text-surface transition-opacity hover:opacity-90"
          >
            Spots entdecken
          </Link>
          <Link
            to="/konto/spots"
            className="inline-flex min-h-11 items-center justify-center rounded-card border border-line bg-surface px-5 text-ui font-semibold text-ink transition-colors hover:bg-band"
          >
            Spot vorschlagen
          </Link>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-lead font-semibold text-ink">{title}</h2>
      <div className="mt-3 space-y-4 text-body leading-relaxed text-ink-soft">
        {children}
      </div>
    </section>
  );
}
