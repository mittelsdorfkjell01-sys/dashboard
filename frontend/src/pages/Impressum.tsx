import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

const legal = {
  operator: import.meta.env.VITE_LEGAL_OPERATOR || "Nicht für Produktion freigegeben",
  street: import.meta.env.VITE_LEGAL_STREET || "Entwicklungsansicht",
  postalCity: import.meta.env.VITE_LEGAL_POSTAL_CITY || "Entwicklungsansicht",
  country: import.meta.env.VITE_LEGAL_COUNTRY || "Deutschland",
  email: import.meta.env.VITE_LEGAL_EMAIL || "nicht-konfiguriert@example.invalid",
  phone: import.meta.env.VITE_LEGAL_PHONE || "",
  responsible: import.meta.env.VITE_LEGAL_RESPONSIBLE || import.meta.env.VITE_LEGAL_OPERATOR || "Nicht freigegeben",
};

export default function Impressum() {
  return (
    <div className="relative min-h-screen bg-page">
      <LandingHeader />
      <main className="mx-auto max-w-[760px] px-4 pb-24 pt-32 sm:px-8">
        <h1 className="text-sz-32 font-semibold text-ink">Impressum</h1>
        <div className="mt-6 space-y-4 text-body leading-relaxed text-ink-soft">
          <h2 className="text-sz-16 font-semibold text-ink">Angaben gemäß § 5 DDG</h2>
          <p>
            {legal.operator}
            <br />
            {legal.street}
            <br />
            {legal.postalCity}
            <br />
            {legal.country}
          </p>

          <h2 className="text-sz-16 font-semibold text-ink">Kontakt</h2>
          <p>
            {legal.phone && <>Telefon: {legal.phone}<br /></>}
            E-Mail: <a className="text-teal underline" href={`mailto:${legal.email}`}>{legal.email}</a>
          </p>

          <h2 className="text-sz-16 font-semibold text-ink">
            Verantwortlich für den Inhalt
          </h2>
          <p>{legal.responsible}, {legal.street}, {legal.postalCity}</p>
        </div>
      </main>
      <Footer />
    </div>
  );
}
