# Katalogmigration 0024

Migration `0024_catalog_axes` vereinheitlicht drei Katalogbereiche.

## Untergrund

`spots.bottom_type` wechselt von `varchar` zu `varchar[]`. Ein vorhandener Wert
wird unverändert in eine Ein-Element-Liste übernommen, beispielsweise `sand` zu
`["sand"]`. `NULL` und leere Strings werden zu einer leeren Liste. Zulässig sind
`sand`, `rock`, `reef` und der historische, alleinstehende Wert `mixed`.

Beim Downgrade wird der erste Listenwert wieder zum Skalar. Mehrere ausgewählte
Untergründe können im alten Schema nicht vollständig abgebildet werden; deshalb
ist der Downgrade an dieser Stelle bewusst verlustbehaftet.

## Skill-Level

Die Zuordnung für Spots und bestehende Bewertungen lautet:

| Vorher | Nachher |
| --- | --- |
| `beginner` | `beginner` |
| `intermediate` | `advanced` |
| `advanced` | `advanced` |
| `pro` | `expert` |

Spotlisten werden dabei dedupliziert. Die Reihenfolge ist `beginner`,
`advanced`, `expert`; ein vorhandenes `n/a` bleibt erhalten. Beim Downgrade wird
`expert` zu `pro`. Die zusammengeführte Unterscheidung zwischen `intermediate`
und `advanced` lässt sich danach nicht rekonstruieren.

## Kanban-Autoren

`board_tasks.author_user_id` verweist für neue Aufgaben auf `admin_users.id`.
Bestehende Autoren-E-Mails werden einmalig aufgelöst, bleiben im historischen
`author`-Feld aber unverändert erhalten. Die API gibt ausschließlich den
Anzeigenamen oder `Unbekannter Benutzer` aus.
