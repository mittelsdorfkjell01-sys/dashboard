import { Link } from "react-router-dom";
import LandingHeader from "../components/LandingHeader";
import Footer from "../components/Footer";

/** 404 page for unmatched routes — replaces the previous silent redirect home,
 *  which left users guessing why a mistyped/stale link dumped them elsewhere. */
export default function NotFound() {
  return (
    <div className="relative flex min-h-screen flex-col bg-page">
      <LandingHeader />
      <main className="grid flex-1 place-items-center px-6 pt-32 text-center">
        <div>
          <p className="text-label font-semibold uppercase tracking-[0.18em] text-teal">
            Fehler 404
          </p>
          <h1 className="mt-2 text-sz-32 font-semibold text-ink">
            Seite nicht gefunden
          </h1>
          <p className="mx-auto mt-2 max-w-md text-body text-muted">
            Diese Seite gibt es nicht (mehr). Vielleicht hilft die Übersicht oder
            die Karte weiter.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              to="/"
              className="px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
            >
              Zur Übersicht
            </Link>
            <Link
              to="/map"
              className="px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
            >
              Zur Karte
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
