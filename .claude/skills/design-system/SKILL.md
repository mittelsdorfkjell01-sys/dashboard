---
name: design-system
description: Use BEFORE writing or changing any public-site UI in this repository — a component, a page, a layout, a panel, a card, a tile, a form, a list, an empty state, a notice, a chart frame, or a style change to one. Covers which colour, type, spacing, radius, surface, border, shadow and motion values are allowed, what a tile or a notice may look like, and the named rules that keep new components from drifting away from the rest of the site. Also use when reviewing UI someone else wrote, when a design decision contradicts an existing rule, or when the user says a component "springt raus", looks off, or does not fit the page. Not for the admin dashboard, which is an independent system (docs/admin-design-tokens.md).
---

# Surfwinddata design system

`DESIGN.md` at the repository root is the canonical document. Read it when you
need the reasoning. This skill is the part you need **while writing code**.

## Before you write a component

Work through this. Every line is a decision the design system has already made
for you — making it again, differently, is how a page turns into a patchwork.

1. **Does it already exist?** Search `frontend/src/components` before adding a
   component. A second spelling of an existing pattern is the most common way
   this site drifts.
2. **Surface.** Default is no surface at all: content on the page ground. A
   tile may lift itself by exactly one tone step (`bg-tile`). Only things with
   a real edge get a frame — inputs, dialogs, overlays, media.
3. **Border.** Default none. A hairline (`border-line`) only where two things
   would otherwise run into each other, never as decoration around a group.
4. **Shadow.** Default none. `shadow-card` and `shadow-float` exist for things
   that genuinely float over content. Tailwind's `shadow-sm|md|lg|xl` are not
   part of this system.
5. **Radius.** `rounded-card` (14px) for every rectangle. `rounded-full` only
   when the silhouette is genuinely round — avatars, dots, pills, switches.
6. **Type.** Only the scale: `micro caption ui body lead title heading
   heading-lg display display-lg hero` (+ `data-*` on the Daten page).
   `text-[14px]`, `text-sm`, `text-xl` and the legacy `sz-*` keys are not
   allowed in public code.
7. **Colour.** Only the semantic tokens: `ink ink-soft muted line line-soft
   page band surface tile accent teal orange green danger success warning
   on-photo`. No Tailwind palette colours (`bg-gray-100`, `text-blue-600`), no
   raw hex at a call site.
8. **Spacing.** Tailwind's spacing scale, nothing arbitrary. Vertical rhythm
   comes from the section, not from a margin on the component.
9. **Dark mode.** Every token already flips. If you write a colour that does
   not come from a token, you have just written a light-mode-only component.
10. **320px and touch.** The page must not scroll sideways at 320px, and
    anything tappable is at least 44px high.

## The named rules

These are the ones that get broken. Full text and reasoning in `DESIGN.md`.

- **The Unframed Tile Rule.** A tile gets no frame. It separates itself by one
  minimal tone step (`bg-tile`, 8% of the range away from `page`), never tone *and* stroke,
  never a shadow. Give it real padding instead of a line around it.
- **The Earned Line Rule.** A list of like rows separates by spacing, not by
  dividers. A hairline appears only where the *kind* of content changes.
- **The Flat-by-Default Rule.** Cards, bands and static panels carry no shadow.
- **The One Corner Rule.** New rectangles use `rounded-card`.
- **The No Fat Button Rule.** Navigation, discovery and secondary actions are
  text or outline, never a large filled area.
- **Inform, don't prescribe.** No traffic lights, no dimming, no score. The one
  red mark on a public page is a hazard glyph on a factual sentence.

## When a request contradicts a rule

The user decides — but the document must not be left lying. If a decision
inverts a named rule:

1. Say so in one sentence before implementing.
2. Change the rule in `DESIGN.md` **in the same commit** as the code.
3. Note in the rule what it said before and why it changed, so the next reader
   does not "fix" the code back.

A rule that the code contradicts is worse than no rule: it teaches everyone to
ignore the document.

## Checks

- `npx tsc --noEmit -p tsconfig.json` and `npx eslint <files>` from `frontend/`.
- The ESLint config already bans some of the above — arbitrary `text-[Npx]`,
  the generic `shadow-sm|md|lg|xl` scale and raw Tailwind red/green. If it
  fires, the fix is the token, not a disable comment. The rest of this list
  (surfaces, borders, radius, spacing) is NOT machine-checked — that part is
  on you.
- Look at the result before claiming it works: the repo's Playwright specs can
  screenshot any component (`e2e/daten-page.spec.ts` has the spot-page mocks).
