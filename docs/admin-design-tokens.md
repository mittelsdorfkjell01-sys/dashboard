# Admin-Designsystem — verbindliche Token- und Geometrie-Regeln

Das Back-Office ist **dark-only, monochrom, dicht** (Linear/Vercel-nah). Farbe,
Abstand, Radius und Buttons kommen ausschließlich aus den folgenden Regeln —
keine Rohwerte im Admin-Markup.

## Farbe = Bedeutung (Tokens, keine Rohfarben)

Alle Admin-Farben stammen aus den `--a-*`-Tokens in
[`admin-theme.css`](../frontend/src/components/admin/ui/admin-theme.css)
(`bg-admin-*`, `text-admin-*`, `border-admin-*`). Rohe Tailwind-Paletten
(`bg-red-500`, `text-white`, Inline-`style={{color}}`) gehören **nicht** ins
Admin-Markup. Status wird immer über **Farbe *und* Text/Symbol** vermittelt
(siehe `Badge`), nie über Farbe allein.

## Spacing-Skala (4px-Basis)

Erlaubt: `4, 8, 12, 16, 24, 32, 48` px — in Tailwind `1, 2, 3, 4, 6, 8, 12`
(`gap-*`, `p-*`, `m-*`, `space-*`). Keine krummen Einzelwerte.

## Radien — genau zwei

- **Controls** (Buttons, Inputs, Chips, Badges-Pill): `rounded-md` (6px).
- **Flächen** (Panels, Karten, Dialoge): `rounded-lg` (8px).

Kein `rounded-2xl`/`rounded-xl` etc. zur „Betonung"; Dringlichkeit trägt Farbe
und Position, nicht eine Sondergeometrie.

## Buttons — ein Bauteil, fester Varianten-Satz

Alle Aktions-Buttons nutzen `Button` aus
[`components/admin/ui`](../frontend/src/components/admin/ui/index.tsx).
Varianten: **`primary`** (gefüllt, Teal), **`secondary`** (Outline auf Surface),
**`ghost`** (transparent), **`destructive`** (Danger-Outline). Varianten
unterscheiden sich **nur in Farbe/Emphasis**, nie in Größe: identische Höhe,
Padding (`px-3 py-1.5`), Radius (`rounded-md`), Type (`text-label font-medium`).
Emphase entsteht über Variante + `block` (Vollbreite) + Position, nicht über
eine größere Höhe. Zustände (default/hover/focus/active/disabled) sind zentral
definiert; Keyboard-Fokus kommt vom globalen `:focus-visible`-Token.

- **Ein `primary` pro Kontext.** Gleichartige Aktionen sehen gleich aus.
- **Touch:** primäre mobile Aktionen ergänzen `min-h-11` (44px) via `className`.
- **Links bleiben Links** (Navigation) — mit angeglichener Geometrie, nicht als
  `<button>` verkleidet.

### Begründete Ausnahmen (kein `Button`)

Segmented-Toggles, Status-/Filter-Chips, Tab-Leisten, Icon-only-Controls
(Toast ✓/✕, NotificationBell), `CollapsibleSection`-Header, `AdminBackButton`
und das Drag-&-Drop-Zuweisungs-Widget in `AdminRegionForm` tragen bewusst eine
eigene, in sich konsistente Sprache (Kontext/Risiko anders) und werden **nicht**
auf `Button` gezwungen.

## Formulargrammatik

Gemeinsame Primitives (`Field`, `Input`, `Select`, `Textarea`,
`CollapsibleSection`, `useUnsavedChangesGuard`): dauerhaft sichtbare Labels,
gleiche Pflichtfeldkonvention, Feldfehler am Feld (`role="alert"`), einheitliche
Save/Cancel/Unsaved-Logik, klare Trennung Speichern / Vorschau / Veröffentlichen.

> **Hinweis:** Der Benutzer-Tab (`AdminUsers`) ist bewusst ausgenommen und nutzt
> weiterhin die geteilten `ui`-Primitives — nicht anfassen.
