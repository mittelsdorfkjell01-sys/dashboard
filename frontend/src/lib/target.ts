// Build target — splits the single SPA into a public build and an admin build.
//
// The public deployment (surfwinddata.com) ships with NO admin code: no admin
// routes, no auth context, no login entry points. The admin back office is a
// separate deployment (kjellmittelsdorf.de) built with VITE_INCLUDE_ADMIN=true.
// Both talk to their own same-origin /api and share one database.

// Is the admin back office compiled into this build? Always in local dev (so a
// developer has the admin at /admin), and in production only for the admin build.
export const INCLUDE_ADMIN = __INCLUDE_ADMIN__;

// Is this THE dedicated admin deployment? Then the root path opens the dashboard
// and there is no public landing. Dev keeps the public landing at "/" (admin still
// reachable at /admin), so this is intentionally NOT true in dev.
export const ADMIN_DEPLOY = __ADMIN_DEPLOY__;
