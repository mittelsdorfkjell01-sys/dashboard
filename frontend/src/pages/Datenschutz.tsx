import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

const controller = {
  operator: import.meta.env.VITE_LEGAL_OPERATOR || "Nicht für Produktion freigegeben",
  street: import.meta.env.VITE_LEGAL_STREET || "Entwicklungsansicht",
  postalCity: import.meta.env.VITE_LEGAL_POSTAL_CITY || "Entwicklungsansicht",
  email: import.meta.env.VITE_LEGAL_EMAIL || "nicht-konfiguriert@example.invalid",
};

export default function Datenschutz() {
  return (
    <div className="relative min-h-screen bg-white">
      <LandingHeader />
      <main className="mx-auto max-w-[760px] px-4 pb-24 pt-32 sm:px-8">
        <h1 className="text-[28px] font-semibold text-ink">Datenschutzerklärung</h1>
        <div className="mt-6 space-y-4 text-[15px] leading-relaxed text-ink-soft">
          <h2 className="text-[16px] font-semibold text-ink">Verantwortliche Stelle</h2>
          <p>
            {controller.operator}<br />{controller.street}<br />{controller.postalCity}<br />
            <a className="text-teal underline" href={`mailto:${controller.email}`}>{controller.email}</a>
          </p>

          <h2 className="text-[16px] font-semibold text-ink">Verarbeitete Daten und Zwecke</h2>
          <p>
            Wir verarbeiten Konto-, Favoriten-, Einreichungs- und Communitydaten zur Bereitstellung
            der Plattform. Kurzlebige, gehashte IP-Adressen dienen dem Missbrauchsschutz und werden
            nach 90 Tagen anonymisiert. Kontodaten werden bis zur Löschung des Kontos gespeichert;
            veröffentlichte Beiträge bleiben danach anonymisiert erhalten.
          </p>

          <h2 className="text-[16px] font-semibold text-ink">Dienste und Empfänger</h2>
          <p>
            Für Hosting, Datenbank und Dateispeicherung werden die im jeweiligen Deployment
            konfigurierten Auftragsverarbeiter eingesetzt. Karten- und Wetteransichten können
            Verbindungen zu CARTO, OpenStreetMap, MapTiler und Open-Meteo herstellen. Dabei kann
            die IP-Adresse technisch an den jeweiligen Anbieter übermittelt werden.
          </p>

          <h2 className="text-[16px] font-semibold text-ink">Rechtsgrundlagen</h2>
          <p>
            Die Kontobereitstellung erfolgt zur Vertragserfüllung, Sicherheitsmaßnahmen beruhen auf
            berechtigten Interessen und freiwillige Veröffentlichungen auf Ihrer Einwilligung. Eine
            erteilte Einwilligung kann mit Wirkung für die Zukunft widerrufen werden.
          </p>

          <h2 className="text-[16px] font-semibold text-ink">Ihre Rechte</h2>
          <p>
            Sie haben das Recht auf Auskunft, Berichtigung, Löschung,
            Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch.
            Außerdem besteht ein Beschwerderecht bei einer Datenschutzaufsichtsbehörde. Den
            Datenexport und die Kontolöschung finden Sie in den Kontoeinstellungen.
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}
