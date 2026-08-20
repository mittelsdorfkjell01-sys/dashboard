// Admin back-office routes — dynamically imported by main.tsx ONLY when the admin
// build flag is on (see lib/target.ts). Because the public build never imports
// this module, Rollup drops it (and every admin page/component it pulls in) from
// the public bundle entirely. The AuthProvider wraps the whole admin subtree here
// (not the app root), so the public build has no auth context and makes no
// /auth/me call.

import React from "react";
import { Outlet, type RouteObject } from "react-router-dom";
import AdminShell from "./components/AdminShell";
import RequireAuth from "./components/RequireAuth";
import { AuthProvider } from "./lib/auth";
import { AdminThemeProvider } from "./components/admin/theme";

const AdminLogin = React.lazy(() => import("./pages/AdminLogin"));
const AdminHome = React.lazy(() => import("./pages/AdminHome"));
const AdminSpots = React.lazy(() => import("./pages/AdminSpots"));
const AdminHero = React.lazy(() => import("./pages/AdminHero"));
const AdminRegions = React.lazy(() => import("./pages/AdminRegions"));
const AdminRegionForm = React.lazy(() => import("./pages/AdminRegionForm"));
const AdminRegionCreate = React.lazy(() => import("./pages/AdminRegionCreate"));
const AdminReview = React.lazy(() => import("./pages/AdminReview"));
const AdminMap = React.lazy(() => import("./pages/AdminMap"));
const AdminActivity = React.lazy(() => import("./pages/AdminActivity"));
const AdminOperations = React.lazy(() => import("./pages/AdminOperations"));
const AdminSpotForm = React.lazy(() => import("./pages/AdminSpotForm"));
const AdminUsers = React.lazy(() => import("./pages/AdminUsers"));
const AdminWeatherProfiles = React.lazy(() => import("./pages/AdminWeatherProfiles"));
const AdminWeatherProfile = React.lazy(() => import("./pages/AdminWeatherProfile"));

const adminRoutes: RouteObject[] = [
  {
    // Pathless layout: provides the auth context + admin theme (light/dark,
    // scoped to <body>) to /admin/login and /admin/*.
    element: (
      <AuthProvider>
        <AdminThemeProvider>
          <Outlet />
        </AdminThemeProvider>
      </AuthProvider>
    ),
    children: [
      { path: "/admin/login", element: <AdminLogin /> },
      {
        path: "/admin",
        element: (
          <RequireAuth>
            <AdminShell />
          </RequireAuth>
        ),
        children: [
          { index: true, element: <AdminHome /> },
          { path: "spots", element: <AdminSpots /> },
          { path: "hero", element: <AdminHero /> },
          { path: "weather", element: <AdminWeatherProfiles /> },
          { path: "weather/:spotId", element: <AdminWeatherProfile /> },
          { path: "regions", element: <AdminRegions /> },
          { path: "region/new", element: <AdminRegionCreate /> },
          { path: "region/:id/edit", element: <AdminRegionForm /> },
          { path: "review", element: <AdminReview /> },
          { path: "map", element: <AdminMap /> },
          { path: "activity", element: <AdminActivity /> },
          { path: "operations", element: <AdminOperations /> },
          { path: "spot/new", element: <AdminSpotForm /> },
          { path: "spot/:id/edit", element: <AdminSpotForm /> },
          {
            path: "users",
            element: (
              <RequireAuth role="admin">
                <AdminUsers />
              </RequireAuth>
            ),
          },
        ],
      },
    ],
  },
];

export default adminRoutes;
