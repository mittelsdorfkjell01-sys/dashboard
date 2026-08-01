import React from "react";
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
import MapView from "./pages/MapView";
import SpotDetail from "./pages/SpotDetail";
import RegionDetail from "./pages/RegionDetail";
import SearchResults from "./pages/SearchResults";
import Impressum from "./pages/Impressum";
import Datenschutz from "./pages/Datenschutz";
import NotFound from "./pages/NotFound";
import ErrorBoundary from "./components/ErrorBoundary";
import RouteError from "./components/RouteError";
import { ADMIN_DEPLOY, INCLUDE_ADMIN } from "./lib/target";
import Auth from "./pages/Auth";
import AccountLayout from "./pages/account/AccountLayout";
import Profil from "./pages/account/Profil";
import Favoriten from "./pages/account/Favoriten";
import MeineSpots from "./pages/account/MeineSpots";
import Einstellungen from "./pages/account/Einstellungen";
import { AuthProvider } from "./context/AuthContext";
import { PrefsProvider } from "./context/PrefsContext";

// The admin back office is code-split behind a build flag: the public build
// (surfwinddata.com) never imports ./adminRoutes, so none of the admin UI ships.
// The admin build (kjellmittelsdorf.de, VITE_INCLUDE_ADMIN=true) pulls it in and
// opens the dashboard at "/". See lib/target.ts.
async function bootstrap() {
  const routes: RouteObject[] = [
    {
      path: "/",
      element: ADMIN_DEPLOY ? <Navigate to="/admin" replace /> : <Landing />,
    },
    { path: "/map", element: <MapView /> },
    { path: "/search", element: <SearchResults /> },
    { path: "/spot/:id", element: <SpotDetail /> },
    { path: "/spot/:id/daten", element: <SpotDetail /> },
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

  if (INCLUDE_ADMIN) {
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
          <Outlet />
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
