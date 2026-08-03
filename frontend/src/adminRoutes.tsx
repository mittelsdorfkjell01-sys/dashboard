// Admin back-office routes — dynamically imported by main.tsx ONLY when the admin
// build flag is on (see lib/target.ts). Because the public build never imports
// this module, Rollup drops it (and every admin page/component it pulls in) from
// the public bundle entirely. The AuthProvider wraps the whole admin subtree here
// (not the app root), so the public build has no auth context and makes no
// /auth/me call.

import { Outlet, type RouteObject } from "react-router-dom";
import AdminLogin from "./pages/AdminLogin";
import AdminHome from "./pages/AdminHome";
import AdminSpots from "./pages/AdminSpots";
import AdminRegions from "./pages/AdminRegions";
import AdminRegionForm from "./pages/AdminRegionForm";
import AdminReview from "./pages/AdminReview";
import AdminMap from "./pages/AdminMap";
import AdminActivity from "./pages/AdminActivity";
import AdminSpotForm from "./pages/AdminSpotForm";
import AdminUsers from "./pages/AdminUsers";
import AdminShell from "./components/AdminShell";
import RequireAuth from "./components/RequireAuth";
import { AuthProvider } from "./lib/auth";
import { AdminThemeProvider } from "./components/admin/theme";

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
          { path: "regions", element: <AdminRegions /> },
          { path: "region/:id/edit", element: <AdminRegionForm /> },
          { path: "review", element: <AdminReview /> },
          { path: "map", element: <AdminMap /> },
          { path: "activity", element: <AdminActivity /> },
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
