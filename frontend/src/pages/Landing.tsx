import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import LandingHeader from "../components/LandingHeader";
import HeroImage from "../components/HeroImage";
import SearchBar from "../components/SearchBar";
import TopSpotsRow from "../components/TopSpotsRow";
import SpotTile from "../components/SpotTile";
import Footer from "../components/Footer";
import { useSpots } from "../lib/hooks";
import { MapIcon } from "../lib/icons";

/**
 * "surfwind data" landing. Two parts that flow into each other on scroll:
 *  1. A full-screen hero photo carrying the header, the search bar and the
 *     "aktuelle Top Spots" row.
 *  2. An extended white section below (no hero photo) with all spots shown as
 *     Airbnb-style cards. A rounded white sheet rises over the hero's bottom for
 *     a seamless hand-off.
 */
export default function Landing() {
  const location = useLocation();
  // Remember where the map is opened from, so its close button can return here.
  const from = location.pathname + location.search;
  const { data: allSpots } = useSpots({ status: "published" });
  const spots = allSpots ?? [];

  // Fade the hero photo out as the page scrolls toward the spots below, so it's
  // gone by the time the white cards sheet is in view. rAF-throttled.
  const [heroOpacity, setHeroOpacity] = useState(1);
  useEffect(() => {
    let ticking = false;
    const update = () => {
      const h = window.innerHeight || 1;
      setHeroOpacity(Math.max(0, Math.min(1, 1 - window.scrollY / (h * 0.85))));
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    update();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="relative bg-white">
      <LandingHeader />

      {/* 1 — Hero screen. `isolate` gives the section its own stacking context so
          the -z-10 hero stays behind the section's own content instead of
          escaping to the root and being covered by the page's white background. */}
      <section className="relative isolate flex min-h-screen flex-col overflow-hidden">
        <div
          className="absolute inset-0 -z-10"
          style={{ opacity: heroOpacity }}
          aria-hidden
        >
          <HeroImage
            src="/hero-surfwind.jpg"
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-[rgba(30,110,126,0.35)]" />
        </div>

        <h1 className="sr-only">
          surfwind data — die beste Sammlung von Surf- und Windspots
        </h1>

        <div className="flex-1" />

        {/* Search — moved further down in the hero; its dropdown now overlaps
            the white section that follows. Top Spots moved into that section. */}
        <div className="flex justify-center px-4 pb-24 sm:px-6 sm:pb-28">
          <div className="relative z-[1200] w-full max-w-[760px]">
            <SearchBar />
          </div>
        </div>
      </section>

      {/* 2 — Extended white section: aktuelle Top Spots (moved here onto the
          white background) + all spots as Airbnb-style cards. The rounded sheet
          rises over the hero for a seamless transition. */}
      <section className="relative z-10 -mt-8 rounded-t-[2rem] bg-white">
        {/* aktuelle Top Spots — title left, map button right, now on white. */}
        <div className="mx-auto w-full max-w-[1300px] pt-14">
          <div className="mb-3 flex items-center justify-between gap-4 px-4 sm:px-10">
            <h2 className="text-[22px] font-semibold text-ink">aktuelle Top Spots</h2>
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

        <div className="mx-auto max-w-[1300px] px-4 pb-20 pt-14 sm:px-10">
          <h2 className="text-[22px] font-semibold text-ink">Alle Spots entdecken</h2>
          <p className="mt-1 text-[15px] text-muted">
            Stöbere durch die ganze Sammlung — Region, Wind- und Wellenspots.
          </p>

          {spots.length > 0 && (
            <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {spots.map((spot) => (
                <SpotTile key={spot.id} spot={spot} />
              ))}
            </div>
          )}
        </div>
      </section>

      <Footer />
    </div>
  );
}
