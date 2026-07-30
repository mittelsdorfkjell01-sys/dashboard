import { Link, useLocation } from "react-router-dom";
import LandingHeader from "../components/LandingHeader";
import HeroImage from "../components/HeroImage";
import SearchBar from "../components/SearchBar";
import TopSpotsRow from "../components/TopSpotsRow";
import Footer from "../components/Footer";
import { MapIcon } from "../lib/icons";

/**
 * "surfwind data" landing (Frame_1/5): one full-bleed hero photo carrying the
 * header, the Airbnb search bar and the "aktuelle Top Spots" grid stacked near
 * the bottom (bar directly above the grid). The photo is a -z-10 layer behind
 * everything — including the top-spots tiles — so no white band shows. Content
 * stays in the root stacking context (no wrapping z-layer) so the search bar's
 * z-[1200] wrapper still sits above its body-portalled scrim (z-1100) and stays
 * clickable.
 */
export default function Landing() {
  const location = useLocation();
  // Remember where the map is opened from, so its close button can return here.
  const from = location.pathname + location.search;

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Full-bleed static hero (Frame_1/5 photo), behind all content. */}
      <div className="absolute inset-0 -z-10">
        <HeroImage
          src="/hero-surfwind.jpg"
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-[rgba(30,110,126,0.35)]" />
      </div>

      <LandingHeader />

      <main className="flex min-h-screen flex-col">
        <h1 className="sr-only">
          surfwind data — die beste Sammlung von Surf- und Windspots
        </h1>

        {/* Hero breathing room pushes the search + top spots to the lower area. */}
        <div className="flex-1" />

        {/* Search — wide, sitting directly above the Top Spots. */}
        <div className="mb-8 flex justify-center px-4 sm:px-6">
          <div className="relative z-[1200] w-full max-w-[760px]">
            <SearchBar />
          </div>
        </div>

        {/* aktuelle Top Spots — title left, map button right (same row). The
            larger bottom padding lifts the whole search + top-spots block up a bit
            from the very bottom of the hero. */}
        <div className="mx-auto w-full max-w-[1300px] pb-16">
          <div className="mb-3 flex items-center justify-between gap-4 px-4 sm:px-10">
            <h2 className="text-[18px] font-semibold text-white drop-shadow">
              aktuelle Top Spots
            </h2>
            <Link
              to="/map"
              state={{ from }}
              aria-label="Karte öffnen"
              className="inline-flex shrink-0 items-center gap-2 rounded-2xl bg-teal px-3.5 py-2 text-[15px] font-medium text-white transition-colors hover:bg-teal-hover"
            >
              <MapIcon className="text-[18px]" />
              <span className="hidden sm:inline">Karte</span>
            </Link>
          </div>
          <TopSpotsRow />
        </div>
      </main>

      <Footer />
    </div>
  );
}
