// Admin theme — dark only.
//
// The admin back office ships a single dark design; there is no light mode and
// no toggle. This provider just puts the `admin-scope` class on <body> while an
// admin route is mounted (removed on unmount), which activates the admin token
// layer + brand-utility remap in ui/admin-theme.css. Scoping on <body> (rather
// than a wrapper div) means portaled dialogs (Modal → document.body) inherit the
// tokens too. The stylesheet is imported here so it ships only in the admin
// bundle.

import { useLayoutEffect, type ReactNode } from "react";
import "./ui/admin-theme.css";

export function AdminThemeProvider({ children }: { children: ReactNode }) {
  // Layout effect so the class lands before first paint (no unstyled flash).
  useLayoutEffect(() => {
    const { body } = document;
    body.classList.add("admin-scope");
    return () => body.classList.remove("admin-scope");
  }, []);

  return <>{children}</>;
}
