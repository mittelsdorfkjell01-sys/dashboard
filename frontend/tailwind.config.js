/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Text scale. `ink` = headings/primary text, `ink-soft` = running body
        // copy, `muted` = secondary text/captions. On dark surfaces text stays
        // white — these three are for light surfaces only.
        ink: "#241C17",
        "ink-soft": "#3D332C",
        muted: "#6B625B",
        // Hairline borders/dividers.
        line: "#E6E1DA",
        // Surfaces: white is the default surface, `band` is the alternating
        // section background (was `cream`).
        surface: "#FFFFFF",
        band: "#F5F3F0",
        // Page/body background — cards sit on this as white surfaces.
        page: "#F7F7F7",
        // Interaction color — every button, link, hover, focus ring, active
        // tab indicator. Never used for large text blocks the way `ink` is,
        // but passes AA as both text-on-white and white-on-fill (5.9:1).
        teal: {
          DEFAULT: "#1E6E7E",
          hover: "#195C6A",
        },
        // Attention color — wordmark, map markers, the live-status pulse, the
        // best-season highlight. Never a button, never a link, never body
        // text (2.8:1 on white — fails AA as text).
        orange: "#B45309",
        // Data accent, shared with the wind-speed scale. Passes AA as text
        // (4.6:1).
        green: "#4A8159",

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
      },
      boxShadow: {
        // The only shadow left in the app — the spot page's header card,
        // where it stands in for the divider rule the card doesn't have.
        // Every other surface separates with a hairline (`border-line`)
        // instead. Two layers: a tighter, darker near-shadow to ground the
        // card + a soft wide one for ambient depth.
        float: "0 24px 32px -16px rgba(36, 28, 23, 0.24), 0 48px 80px -24px rgba(36, 28, 23, 0.30)",
        // Soft, subtle elevation for a white surface that reads as raised
        // (the Info-tab comment box, the auth-choice dialog).
        card: "0 12px 34px -18px rgba(36, 28, 23, 0.20)",
      },
      borderRadius: {
        // Corner radius unified to a crisp 8px across cards/tiles/overlays
        // and pill/icon buttons (avatars/dots keep rounded-full).
        "2xl": "0.5rem", // 8px
        "3xl": "0.5rem", // 8px
      },
      // Semantic type scale — the app's recurring UI text steps as tokens
      // (single source of truth). Font-size only, so values match the previously
      // hard-coded `text-[Npx]` exactly; adopting them is visually a no-op while
      // making sizes semantic and consistent. `text-[Npx]` is not allowed in new
      // code — extend this scale instead.
      fontSize: {
        caption: "0.75rem", // 12px — captions, meta, legends
        label: "0.8125rem", // 13px — control labels, chips, buttons (sm)
        ui: "0.875rem", // 14px — default control/body-UI text
        body: "0.9375rem", // 15px — reading copy
        title: ["1.375rem", { lineHeight: "1.25", letterSpacing: "0" }], // 22px — module/panel titles
        stat: ["clamp(3rem, 5vw, 4.25rem)", { lineHeight: "0.85", letterSpacing: "0" }], // big live numbers
        // Editorial display scale — fluid hero/section titles (travel-journal).
        "display-1": ["clamp(2.5rem, 6vw, 5rem)", { lineHeight: "1.02", letterSpacing: "0" }],
        "display-2": ["clamp(1.75rem, 3.5vw, 2.75rem)", { lineHeight: "1.08", letterSpacing: "0" }],

        // --- spot-page dual type system ------------------------------------
        // The Info tab (travel-magazine) and Daten tab (weather instrument)
        // read as two different products sharing one brand, so they get two
        // separate type sets instead of one compromise scale.
        "editorial-1": ["5.5rem", { lineHeight: "1.02", letterSpacing: "0" }], // 88px — Info: page title
        "editorial-2": ["3.5rem", { lineHeight: "1.08", letterSpacing: "0" }], // 56px — Info: section headings
        "editorial-3": ["3rem", { lineHeight: "1.08", letterSpacing: "0" }], // 48px — Info: header-card h1 (Figma Frame_9)
        "editorial-4": ["2rem", { lineHeight: "1.1", letterSpacing: "0" }], // 32px — Info: spot name + inline score (Figma Frame_9)
        lede: ["1.25rem", { lineHeight: "1.7" }], // 20px — Info: first paragraph
        prose: ["1.0625rem", { lineHeight: "1.75" }], // 17px — Info: running body copy, max-w-[62ch]
        "data-label": ["0.8125rem", { lineHeight: "1.2", letterSpacing: "0.14em" }], // 13px — Daten: section labels, uppercase
        "data-value": ["0.875rem", { lineHeight: "1.4" }], // 14px — Daten: table values
        "data-caption": ["0.75rem", { lineHeight: "1.4" }], // 12px — Daten: axes, units
      },
    },
  },
  plugins: [],
};

// Verified (headless Chromium, Poppins 400, 40px, `tabular-nums` applied):
// digit widths ranged 51px ("1") to 102px ("6") — Poppins ships no tabular
// figures, so the OpenType feature has nothing to switch on and the CSS
// property is a no-op. `tabular-nums` still doesn't hurt (harmless if a
// future font adds the feature), but it cannot be relied on for column
// alignment. The Daten-tab hour table (Sprint 6) must give numeric columns a
// fixed width and right-align them instead — that's the only way parallel
// rows of digits stay put here.
