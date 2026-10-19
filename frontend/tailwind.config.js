/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ['selector', 'html[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Text scale. `ink` = headings/primary text, `ink-soft` = running body
        // copy, `muted` = secondary text/captions.
        ink: {
          DEFAULT: "var(--sw-ink)",
          soft: "var(--sw-ink-soft)",
        },
        muted: "var(--sw-muted)",
        // Hairline borders/dividers.
        line: {
          DEFAULT: "var(--sw-line)",
          soft: "var(--sw-line-soft)",
        },
        // Surfaces: surface is the default card surface, `band` is the alternating
        // section background (was `cream`).
        surface: "var(--sw-surface)",
        band: "var(--sw-band)",
        // Page/body background — cards sit on this as surface.
        page: "var(--sw-page)",
        // Restricted action accent. Product direction keeps this blue only on
        // controls that already use it and the Spot Info/Daten underline.
        teal: {
          DEFAULT: "var(--sw-teal)",
          hover: "var(--sw-teal-hover)",
        },
        // Accent *text* colour (links/icons) — same deep blue as `teal` in light
        // mode, but a lighter blue in dark mode so it clears WCAG AA as thin text
        // on the near-black page (plain `teal` is a fill colour and fails there).
        // Use `text-accent` for interactive text/icons; keep `bg-teal` for fills.
        accent: {
          DEFAULT: "var(--sw-accent)",
          hover: "var(--sw-accent-hover)",
        },
        // Attention color — wordmark, map markers, the live-status pulse, the
        // best-season highlight. Never a button, never a link, never body text.
        orange: "var(--sw-orange)",
        // Data accent, shared with the wind-speed scale. NOT a status colour
        // — see `danger`/`success` below for error/confirmation text.
        green: "var(--sw-green)",
        // Status tokens — the only allowed source for error/success colour
        // on the public site. Admin has its own equivalents (admin-danger/
        // admin-success); never mix the two systems.
        danger: {
          DEFAULT: "var(--sw-danger)",
          bg: "var(--sw-danger-bg)",
          border: "var(--sw-danger-border)",
        },
        success: {
          DEFAULT: "var(--sw-success)",
          bg: "var(--sw-success-bg)",
        },
        // Warning/caution status — public counterpart to admin-warning. The
        // only allowed source for amber/caution colour on the public site
        // ("in Prüfung" badges, soft upload/tide cautions). Never a data accent.
        warning: {
          DEFAULT: "var(--sw-warning)",
          bg: "var(--sw-warning-bg)",
        },
        // Text on photos and the always-dark map/instrument overlays. Two
        // steps instead of eight ad-hoc white alphas: `on-photo` for primary
        // text and controls, `on-photo-muted` for secondary text and units.
        "on-photo": {
          DEFAULT: "rgb(255 255 255 / 0.92)",
          muted: "rgb(255 255 255 / 0.66)",
        },
        // Wind-climatology-V3 weekly-reliability bar scale (low → high). The
        // 0 band reuses `line`, the 3 band reuses `teal` — chart fills, not
        // buttons/surfaces/links, so the teal restriction above doesn't apply.
        reliability: {
          0: "var(--sw-line)",
          1: "var(--sw-reliability-sand)",
          2: "var(--sw-reliability-blue)",
          3: "var(--sw-teal)",
        },

        // --- Admin back-office palette (independent design system) ---------
        // CSS-var-backed semantic tokens for the admin dashboard ONLY. The
        // variables are defined + theme-switched in
        // components/admin/ui/admin-theme.css under `.admin-scope`, so these
        // classes render correctly only inside the admin (which is where they
        // are used). The public site never references `admin-*` classes, so
        // this addition is inert for it. See that file for the full rationale.
        admin: {
          bg: "var(--a-bg)",
          surface: "var(--a-surface)",
          elevated: "var(--a-elevated)",
          hover: "var(--a-hover)",
          active: "var(--a-active)",
          border: "var(--a-border)",
          "border-subtle": "var(--a-border-subtle)",
          "border-strong": "var(--a-border-strong)",
          fg: "var(--a-fg)",
          fg2: "var(--a-fg2)",
          muted: "var(--a-muted)",
          faint: "var(--a-faint)",
          primary: "var(--a-primary)",
          "primary-hover": "var(--a-primary-hover)",
          "primary-fg": "var(--a-primary-fg)",
          "primary-bg": "var(--a-primary-bg)",
          success: "var(--a-success-fg)",
          "success-bg": "var(--a-success-bg)",
          "success-border": "var(--a-success-border)",
          warning: "var(--a-warning-fg)",
          "warning-bg": "var(--a-warning-bg)",
          "warning-border": "var(--a-warning-border)",
          danger: "var(--a-danger-fg)",
          "danger-strong": "var(--a-danger)",
          "danger-bg": "var(--a-danger-bg)",
          "danger-border": "var(--a-danger-border)",
          info: "var(--a-info)",
          "info-bg": "var(--a-info-bg)",
          ring: "var(--a-ring)",
        },
      },
      fontFamily: {
        sans: ["Poppins", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        // Display face used only for the "surfwind" wordmark (local .otf).
        display: ["MADE Mountain", "Poppins", "system-ui", "sans-serif"],
        // Figures face: Poppins for letters, Manrope for digits and numeric
        // punctuation only (the "SW Figures" @font-face in index.css is Manrope
        // restricted by unicode-range). Poppins ships no tabular figures;
        // Manrope does, so `font-figures tabular-nums` keeps columns of wind,
        // gust and wave values from jumping. Applied to the whole Daten page.
        figures: ["SW Figures", "Poppins", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        // Full Manrope, for the rare block that is numbers end to end.
        num: ["Manrope", "Poppins", "system-ui", "sans-serif"],
      },
      boxShadow: {
        // The only two shadows allowed on the PUBLIC site (admin has its own
        // pair below). `float` originally stood in for the spot page header
        // card's missing divider rule; every other public surface separates
        // with a hairline (`border-line`) instead. Two layers: a tighter,
        // darker near-shadow to ground the card + a soft wide one for
        // ambient depth.
        float: "0 24px 32px -16px rgba(36, 28, 23, 0.24), 0 48px 80px -24px rgba(36, 28, 23, 0.30)",
        // Soft, subtle elevation for a white surface that reads as raised
        // (the Info-tab comment box, the auth-choice dialog).
        card: "0 12px 34px -18px rgba(36, 28, 23, 0.20)",
        // Admin's own elevation pair (independent design system, dark-only —
        // see admin-theme.css `--a-shadow-*`). Popovers/dropdowns/tooltips
        // get `admin-pop`, real modal dialogs get `admin-dialog`; never the
        // generic shadow-sm/md/lg/xl utilities in admin UI.
        "admin-pop": "var(--a-shadow-pop)",
        "admin-dialog": "var(--a-shadow-dialog)",
      },
      // Uppercase label tracking — one value for every versal eyebrow/label so
      // they no longer drift between 0.08em…0.18em. `data-label` bakes the same
      // 0.14em; use `tracking-caps` everywhere else instead of an arbitrary value.
      letterSpacing: {
        caps: "0.14em",
      },

      // --- Layout widths ----------------------------------------------------
      // Three container tokens instead of a dozen ad-hoc max-widths:
      //   page    — the outer frame every public page aligns to (header, hero,
      //             grids, footer share the same edges)
      //   content — single-column pages (legal, FAQ, account, intro copy)
      //   measure — a comfortable reading line for running text
      // Component-specific widths (dialogs, compasses, popovers) stay local.
      maxWidth: {
        page: "1570px",
        content: "760px",
        measure: "62ch",
        // The ONE admin content width. AdminShell's <main> owns it; admin pages
        // must not set their own max-width, or the body jumps between routes
        // (Hero used 1200px, Rider-Modell 6xl, Windfeld-Shadow 7xl).
        admin: "1440px",
      },

      // --- Stacking layers --------------------------------------------------
      // Named global layers. Values are the exact numbers the app used before
      // (several sit above Leaflet's own panes: tiles 200, overlays 400,
      // markers 600, popups 700, controls 800–1000), so the order is
      // unchanged — only the names are new. Small numbers (z-1…z-50) remain
      // for stacking inside one component.
      zIndex: {
        1: "1",
        5: "5",
        "map-overlay": "450", // decorative layers above map tiles
        "map-control": "500", // in-map buttons
        "map-ui": "600", // attribution, map chrome
        sticky: "700", // sticky bars inside pages
        header: "1000", // site headers
        scrim: "1100", // overlay scrims and floating map controls
        overlay: "1101", // the panel sitting on its scrim
        modal: "1200", // dialogs
        sheet: "1300", // search panels, filter sheets, upload sheets
        fullscreen: "1400", // full-screen map / media layers
        menu: "2000", // account menu and anything that must win
      },

      // --- Motion -----------------------------------------------------------
      // One house easing (soft exponential settle) and three durations, backed
      // by CSS variables in index.css so hand-written CSS uses the same values.
      // `transition` / `transition-colors` utilities pick up the DEFAULTs.
      transitionTimingFunction: {
        DEFAULT: "var(--sw-ease)",
        brand: "var(--sw-ease)",
      },
      transitionDuration: {
        DEFAULT: "var(--sw-dur-fast)",
        fast: "var(--sw-dur-fast)", // 150ms — hover, press, colour
        base: "var(--sw-dur-base)", // 200ms — toggles, small moves
        slow: "var(--sw-dur-slow)", // 300ms — panels, sheets
      },

      // --- Type scale -------------------------------------------------------
      // One modular scale (ratio ≈ 1.2) on whole pixels, each step paired with
      // its line-height and, for large sizes, a slight negative tracking that
      // Poppins needs at display sizes:
      //   10 · 12 · 14 · 16 · 19 · 23 · 28 · 34 · 48 · 58  (+ fluid hero)
      // `micro` is the floor and is only for chart ticks and dense legends.
      // `data-*` are role aliases on the same steps for the Daten instrument.
      // Public code uses ONLY these. `text-[Npx]`, Tailwind's default sizes
      // and the legacy keys below are not allowed in public code.
      fontSize: {
        micro: ["0.625rem", { lineHeight: "1.3" }], // 10px — chart ticks, dense legends
        caption: ["0.75rem", { lineHeight: "1.45" }], // 12px — captions, meta
        ui: ["0.875rem", { lineHeight: "1.5" }], // 14px — controls, labels, chips, UI copy
        body: ["1rem", { lineHeight: "1.6" }], // 16px — reading copy
        lead: ["1.1875rem", { lineHeight: "1.5" }], // 19px — lede paragraphs, prominent values
        title: ["1.4375rem", { lineHeight: "1.25", letterSpacing: "-0.005em" }], // 23px — card/module titles
        heading: ["1.75rem", { lineHeight: "1.15", letterSpacing: "-0.01em" }], // 28px — section headings
        "heading-lg": ["2.125rem", { lineHeight: "1.1", letterSpacing: "-0.015em" }], // 34px — page titles
        display: ["3rem", { lineHeight: "1.05", letterSpacing: "-0.02em" }], // 48px — display
        "display-lg": ["3.625rem", { lineHeight: "1", letterSpacing: "-0.02em" }], // 58px — wordmark, big display
        hero: ["clamp(2.5rem, 6vw, 5rem)", { lineHeight: "1.02", letterSpacing: "-0.02em" }], // fluid hero title
        "data-label": ["0.75rem", { lineHeight: "1.2", letterSpacing: "0.14em" }], // 12px — Daten: section labels, uppercase
        "data-value": ["0.875rem", { lineHeight: "1.4" }], // 14px — Daten: table values
        "data-caption": ["0.75rem", { lineHeight: "1.4" }], // 12px — Daten: axes, units

        // --- Legacy (admin dashboard only) ----------------------------------
        // Kept so the admin back office renders exactly as before. Public code
        // was migrated to the scale above and must not use these.
        label: "0.8125rem", // 13px
        "sz-8": "0.5rem", // 8px
        "sz-10": "0.625rem", // 10px
        "sz-11": "0.6875rem", // 11px
        "sz-16": "1rem", // 16px
        "sz-17": "1.0625rem", // 17px
        "sz-18": "1.125rem", // 18px
        "sz-19": "1.1875rem", // 19px
        "sz-20": "1.25rem", // 20px
        "sz-22": "1.375rem", // 22px
        "sz-24": "1.5rem", // 24px
        "sz-26": "1.625rem", // 26px
        "sz-28": "1.75rem", // 28px
        "sz-30": "1.875rem", // 30px
        "sz-32": "2rem", // 32px
        "sz-34": "2.125rem", // 34px
        "sz-58": "3.625rem", // 58px
      },
    },

    // --- Corner radius ------------------------------------------------------
    // ONE radius for the whole public site: 14px. Every named step resolves to
    // it, so `rounded`, `rounded-lg`, `rounded-t-xl` … all land on the same
    // corner. Use `rounded-card` in new code. `full` stays for true circles
    // (avatars, round icon buttons, dots, spinners, slider thumbs) — a circle
    // is a shape, not a corner radius. Overrides Tailwind's defaults on
    // purpose (not `extend`). The admin dashboard restores its own radii in
    // components/admin/ui/admin-theme.css under `.admin-scope`.
    borderRadius: {
      none: "0",
      DEFAULT: "0.875rem",
      sm: "0.875rem",
      md: "0.875rem",
      lg: "0.875rem",
      xl: "0.875rem",
      "2xl": "0.875rem",
      "3xl": "0.875rem",
      card: "0.875rem", // 14px — canonical
      full: "9999px",
    },
  },
  plugins: [],
};

// Figures: Poppins ships no tabular figures (verified in headless Chromium:
// digit widths 51px–102px at 40px, `tabular-nums` is a no-op). Digits on the
// Daten page therefore come from Manrope via `font-figures` (see the
// "SW Figures" @font-face in index.css), where `tabular-nums` does work.
// Fixed-width, right-aligned numeric columns remain good practice anyway.
