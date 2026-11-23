import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";
import PageBackLink from "../components/PageBackLink";
import ScrollBackButton from "../components/ScrollBackButton";
import { IMPRESSUM_SECTIONS, legalTitle } from "../lib/infoSections";

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
      <LandingHeader onLight />
      <main className="mx-auto max-w-content px-4 pb-24 pt-32 sm:px-8">
        <PageBackLink className="mb-2" />
        <ScrollBackButton />
        <h1 className="text-title font-semibold leading-tight text-ink">Impressum</h1>
        <div className="mt-5 space-y-4 text-ui leading-relaxed text-ink-soft">
          <h2 id="angaben" className="scroll-mt-24 text-body font-semibold text-ink">{legalTitle(IMPRESSUM_SECTIONS, "angaben")}</h2>
          <p>
            {legal.operator}
            <br />
            {legal.street}
            <br />
            {legal.postalCity}
            <br />
            {legal.country}
          </p>

          <h2 id="kontakt" className="scroll-mt-24 text-body font-semibold text-ink">{legalTitle(IMPRESSUM_SECTIONS, "kontakt")}</h2>
          <p>
            {legal.phone && <>Telefon: {legal.phone}<br /></>}
            E-Mail: <a className="text-ink underline" href={`mailto:${legal.email}`}>{legal.email}</a>
          </p>

          <h2 id="verantwortlich" className="scroll-mt-24 text-body font-semibold text-ink">
            {legalTitle(IMPRESSUM_SECTIONS, "verantwortlich")}
          </h2>
          <p>{legal.responsible}, {legal.street}, {legal.postalCity}</p>
        </div>
      </main>
      <Footer />
    </div>
  );
}
