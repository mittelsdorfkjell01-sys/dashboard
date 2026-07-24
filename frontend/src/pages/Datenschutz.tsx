import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

/**
 * Datenschutzerklärung — required under the GDPR. Ships as a clearly marked
 * placeholder; the operator must supply the real controller, processing
 * purposes, legal bases and third-party services before going live.
 */
export default function Datenschutz() {
  return (
    <div className="relative min-h-screen bg-white">
      <LandingHeader />
      <main className="mx-auto max-w-[760px] px-4 pb-24 pt-32 sm:px-8">
        <h1 className="text-[28px] font-semibold text-ink">Datenschutzerklärung</h1>
        <div className="mt-6 space-y-4 text-[15px] leading-relaxed text-ink-soft">
          <p className="rounded-2xl border border-orange/30 bg-orange/5 p-4 text-[14px] text-ink-soft">
            Platzhalter — hier muss vor dem Live-Gang eine vollständige
            Datenschutzerklärung nach DSGVO eingetragen werden: verantwortliche
            Stelle, verarbeitete Daten, Rechtsgrundlagen, Speicherdauer,
            Betroffenenrechte sowie eingesetzte Dienste (z. B. Hosting,
            Karten-Kacheln, Wetterdaten). Bitte durch die echten Angaben
            ersetzen.
          </p>

          <h2 className="text-[16px] font-semibold text-ink">Verantwortliche Stelle</h2>
          <p>[Name und Anschrift der verantwortlichen Stelle — siehe Impressum]</p>

          <h2 className="text-[16px] font-semibold text-ink">Ihre Rechte</h2>
          <p>
            Sie haben das Recht auf Auskunft, Berichtigung, Löschung,
            Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch.
            Die konkrete Ausgestaltung ergänzt der Betreiber.
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}
