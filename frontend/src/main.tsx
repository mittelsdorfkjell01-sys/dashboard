import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
  type RouteObject,
} from "react-router-dom";
import "leaflet/dist/leaflet.css";
import "./index.css";
import { LenisProvider } from "./lib/lenis";
import ScrollManager from "./components/ScrollManager";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";
import ErrorBoundary from "./components/ErrorBoundary";
import RouteError from "./components/RouteError";
import { ADMIN_DEPLOY } from "./lib/target";
import { AuthProvider } from "./context/AuthContext";
import { PrefsProvider } from "./context/PrefsContext";
import { initializeTheme } from "./lib/theme";

initializeTheme();

const MapView = React.lazy(() => import("./pages/MapView"));
const SpotDetail = React.lazy(() => import("./pages/SpotDetail"));
const RegionDetail = React.lazy(() => import("./pages/RegionDetail"));
const SearchResults = React.lazy(() => import("./pages/SearchResults"));
const Impressum = React.lazy(() => import("./pages/Impressum"));
const Datenschutz = React.lazy(() => import("./pages/Datenschutz"));
const Auth = React.lazy(() => import("./pages/Auth"));
const AccountLayout = React.lazy(() => import("./pages/account/AccountLayout"));
const Profil = React.lazy(() => import("./pages/account/Profil"));
const Favoriten = React.lazy(() => import("./pages/account/Favoriten"));
const MeineSpots = React.lazy(() => import("./pages/account/MeineSpots"));
const Einstellungen = React.lazy(() => import("./pages/account/Einstellungen"));

function RouteFallback() {
  return <div role="status" className="grid min-h-[40vh] place-items-center text-[14px] text-muted">Lädt…</div>;
}

// A deploy replaces every hashed chunk file; a tab left open across that
// deploy still references the old filenames. The next lazy import (a route,
// or LocatorMap loading as it scrolls into view) 404s, Vite's import()
// wrapper dispatches this event, and — left unhandled — the rejected import
// surfaces as an uncaught render error that trips the top-level ErrorBoundary
// over what a reload fixes in place. The sessionStorage guard stops a reload
// loop if the asset is actually missing for good.
window.addEventListener("vite:preloadError", () => {
  const key = "swd-preload-reload";
  if (sessionStorage.getItem(key)) return;
  sessionStorage.setItem(key, "1");
  window.location.reload();
});

// The admin back office is code-split behind a build flag: the public build
// (surfwinddata.com) never imports ./adminRoutes, so none of the admin UI ships.
// The admin build (kjellmittelsdorf.de, VITE_INCLUDE_ADMIN=true) pulls it in and
// opens the dashboard at "/". See lib/target.ts.
async function bootstrap() {
  // The admin-only deployment redirects "/" into the dashboard but keeps every
  // other public route mounted, so "Öffentliche Vorschau" for a spot or a
  // region resolves on the admin domain instead of 404-ing (the public build
  // lives on a separate domain; the admin cannot link across).
  const routes: RouteObject[] = [
    { path: "/", element: ADMIN_DEPLOY ? <Navigate to="/admin" replace /> : <Landing /> },
    { path: "/map", element: <MapView /> },
    { path: "/search", element: <SearchResults /> },
    { path: "/spot/:spotName", element: <SpotDetail /> },
    { path: "/spot/:spotName/info", element: <SpotDetail /> },
    { path: "/spot/:spotName/daten", element: <SpotDetail /> },
    { path: "/region/:slug", element: <RegionDetail /> },
    { path: "/impressum", element: <Impressum /> },
    { path: "/datenschutz", element: <Datenschutz /> },
    { path: "/anmelden", element: <Auth /> },
    {
      path: "/konto",
      element: <AccountLayout />,
      children: [
        { index: true, element: <Navigate to="/konto/profil" replace /> },
        { path: "profil", element: <Profil /> },
        { path: "favoriten", element: <Favoriten /> },
        { path: "spots", element: <MeineSpots /> },
        { path: "einstellungen", element: <Einstellungen /> },
      ],
    },
  ];

  if (__INCLUDE_ADMIN__) {
    routes.push(...(await import("./adminRoutes")).default);
  }

  // Unknown paths (including /admin on the public build, where the admin routes
  // aren't registered) render a real 404 instead of a silent redirect home.
  routes.push({ path: "*", element: <NotFound /> });

  // Every route gets a render-error fallback instead of a blank screen.
  for (const r of routes) if (!r.errorElement) r.errorElement = <RouteError />;

  // Pathless root layout: mounts ScrollManager inside the router (owns route
  // scroll-reset + hash anchors under Lenis) and renders the matched route.
  const router = createBrowserRouter([
    {
      element: (
        <>
          <ScrollManager />
          <Suspense fallback={<RouteFallback />}>
            <Outlet />
          </Suspense>
        </>
      ),
      errorElement: <RouteError />,
      children: routes,
    },
  ]);
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <ErrorBoundary>
        <PrefsProvider>
          <AuthProvider>
            <LenisProvider>
              <RouterProvider router={router} />
            </LenisProvider>
          </AuthProvider>
        </PrefsProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
}

void bootstrap();
