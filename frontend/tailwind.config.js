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
        muted: "#7A6F66",
        // Hairline borders/dividers.
        line: "#E6E1DA",
        // Surfaces: white is the default surface, `band` is the alternating
        // section background (was `cream`).
        surface: "#FFFFFF",
        band: "#F5F3F0",
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
        orange: "#E0823C",
        // Data accent, shared with the wind-speed scale. Passes AA as text
        // (4.6:1).
        green: "#4A8159",
      },
      fontFamily: {
        sans: ["Poppins", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        // Display face used only for the "surfwind" wordmark (local .otf).
        display: ["MADE Mountain", "Poppins", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 10px 30px -12px rgba(36, 28, 23, 0.25)",
        bar: "0 8px 24px -10px rgba(36, 28, 23, 0.22)",
        pill: "0 4px 14px -6px rgba(36, 28, 23, 0.25)",
        // Two layers: a tighter, darker near-shadow to ground the card + the
        // original soft wide one for ambient depth — reads as a stronger pull
        // downward than a single soft shadow, standing in for the divider
        // rule the identity card doesn't have.
        float: "0 24px 32px -16px rgba(36, 28, 23, 0.24), 0 48px 80px -24px rgba(36, 28, 23, 0.30)", // overlapping conditions card
        lift: "0 12px 32px -16px rgba(36, 28, 23, 0.20)", // sticky subnav
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
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
        lede: ["clamp(1.1875rem, 1.4vw, 1.375rem)", { lineHeight: "1.65" }], // 19–22px — editorial lede copy
        title: ["1.375rem", { lineHeight: "1.25", letterSpacing: "-0.01em" }], // 22px — module/panel titles
        stat: ["clamp(3rem, 5vw, 4.25rem)", { lineHeight: "0.85", letterSpacing: "-0.03em" }], // big live numbers
        // Editorial display scale — fluid hero/section titles (travel-journal).
        "display-1": ["clamp(2.5rem, 6vw, 5rem)", { lineHeight: "1.02", letterSpacing: "-0.03em" }],
        "display-2": ["clamp(1.75rem, 3.5vw, 2.75rem)", { lineHeight: "1.08", letterSpacing: "-0.02em" }],
      },
    },
  },
  plugins: [],
};
