import { Link } from "react-router-dom";

/** Site footer carrying the legally required links (Impressum / Datenschutz). */
export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-line bg-white">
      <div className="mx-auto flex max-w-[1400px] flex-col items-center justify-between gap-3 px-4 py-6 text-[13px] text-muted sm:flex-row sm:px-8">
        <span>© {year} surfwind data</span>
        <nav className="flex items-center gap-4">
          <Link to="/impressum" className="hover:text-teal">
            Impressum
          </Link>
          <Link to="/datenschutz" className="hover:text-teal">
            Datenschutz
          </Link>
        </nav>
      </div>
    </footer>
  );
}
