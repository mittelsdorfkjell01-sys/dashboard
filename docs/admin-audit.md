# Admin-Tool — Audit & Überarbeitungsliste

**Stand:** 2026-07-27 · **Scope:** Admin-Frontend (`frontend/src/pages/Admin*.tsx`, `AdminShell`, `adminRoutes`) + Admin-Backend (`app/api/admin*.py`, `app/admin/*`), abgeglichen mit dem überarbeiteten Public-Frontend.
**Ziel:** Public-Seite im Team moderieren · volle Kontrolle über die Public-Seite · Bedienung auf höchstem Niveau.
**Methode:** Code-Analyse (nicht visuell/eingeloggt gelaufen). Punkte mit „Infra" bitte gegenprüfen.

## Reifegrad
| Bereich | Reife (1–5) | Kurzbefund |
|---|---|---|
| Spot-CRUD | 3,5 | inhaltlich stark; Publish/Klima/Attribution + Locking fehlen |
| Region-CRUD | 3,0 | Grundfunktionen; Löschen/Country/Bulk fehlen |
| Benutzer/Rollen | 2,5 | Basis ok; Invite/Granularität/2FA fehlen |
| Team-Arbeit | 2,0 | Notizen/Audit da; Board tot, keine Notifs, Mods eingeschränkt |
| Moderation | 2,5 | Bilder/Einreichungen gut; Kommentare/Threads schwach |
| Design/UX/Mobil | 2,0 | funktioniert; nicht auf Public-Niveau |

**Fazit:** Backend nahezu vollständig — das Admin-Erlebnis (Frontend/UX/Team-Flows) ist es noch nicht.

## Prioritäten
- **P0** kritisch (blockiert effektives/team-sicheres Arbeiten)
- **P1** hoch (volle Kontrolle / Kernnutzen)
- **P2** mittel (Effizienz)
- **P3** Politur (Design/UX)

---

## A · Infrastruktur / Deployment
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| A1 | Vercel-„dashboard"-Projekt hängt an falscher DB-Branch | **BESTÄTIGT (kritisch).** Admin läuft als eigenes Vercel-Projekt (`dashboard`, Domain `dashboardsurfwind.vercel.app`, gleiches Repo, `VITE_INCLUDE_ADMIN`+`JWT_SECRET`+`ADMIN_BOOTSTRAP_*` gesetzt). Live-API-Vergleich: Admin zeigt **alten Seed** (Arte Vida `kitesurf/wing/windsurf`, **0 Bilder**), Public zeigt **neuen Seed** (`kitesurf/wavekite/surf`, 28 Bilder). → Admin und Public hängen an **verschiedenen Neon-Branches**; das Admin editiert eine **veraltete DB, Änderungen erreichen die Public-Seite nicht**. (`DATABASE_URL` ist „sensitive"/nicht lesbar → per Live-API diagnostiziert.) | Admin-`DATABASE_URL`(+`_UNPOOLED`) auf **denselben Wert wie Public-Production** setzen (`ep-polished-block` pooled) und das `dashboard`-Projekt **neu deployen**. Danach teilen Admin + Public eine DB → Moderation steuert die Live-Seite. | P0 |
| A2 | Admin-Zugang / Bootstrap | Erster Admin nur via `ADMIN_BOOTSTRAP_*` beim Cold-Start. | Sicherstellen, dass die Bootstrap-Vars gesetzt sind und der erste Login klappt; danach Bootstrap-Passwort ändern. | P0 |

## B · Spots — anlegen & bearbeiten
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| B1 | Publish-Fluss zerstreut | Speichern (Draft) im Form; **Veröffentlichen nur in der Spots-Liste** (Go-Live-Button, 409 zeigt Lücken). Zwei Orte, unintuitiv. | **Publish-Button direkt im SpotForm** mit Live-Readiness-Panel; fehlende Felder anklickbar → zum Feld springen. | P1 |
| B2 | ERA5 / Klimatologie | Trigger nur als Listen-Action; Status im Form nicht klar sichtbar. Readiness braucht Klima **+** Bild. | ERA5-Trigger **+ Klima-Status** in den SpotForm holen; Readiness-Panel zeigt beide Gates. | P1 |
| B3 | Wettermodell pro Spot (`model_pref`) | Nur Region-Default editierbar; Spot-Override nicht im UI. | `model_pref`-Auswahl in den SpotForm aufnehmen (Optionen aus `MODEL_PREF_OPTIONS`). | P1 |
| B4 | Hero-Attribution | Hero-Upload ok, aber **Credit/Lizenz/Quelle nicht editierbar** → Commons-Angaben nicht korrigierbar (Copyright-relevant). | Felder Credit/Lizenz/Quelle im „Header-Bild"-Block editierbar machen; auf `spot.image` JSONB schreiben. | P1 |
| B5 | Optimistic Locking / Versionierung | PATCH ohne Version/`updated_at`-Check → im **Team überschreibt der letzte Speichernde still** die Änderung des anderen. | `updated_at`/Version mitschicken; bei Konflikt 409 + „wurde inzwischen geändert"-Hinweis (Reload/Merge). | P0 |
| B6 | Galerie-Verwaltung | Bilder entfernen + Commons-Fetch vorhanden; kein „als Hero setzen", keine Reihenfolge, kein Approve/Reject am Spot. | „Als Hero verwenden", Drag-Reihenfolge, Approve/Reject direkt am Spot. | P2 |
| B7 | Geocoding-Hilfe | Backend `/admin/geocode` vorhanden; im Form evtl. ungenutzt. | Adresse→Koordinaten-Button im Form (schnelleres Eintragen). | P2 |
| B8 | „Vorschau als Public" | Keine Draft-Vorschau im Public-Layout. | Link/Modal „Als Public ansehen" pro Spot (auch für Drafts). | P2 |
| B9 | Design-Debt im Form | `text-[Npx]` (19× allein hier), `rounded-xl`, altes Styling. | Auf `ui/*`-Komponenten + Tokens (8 px-Radius, Typo-Tokens) umstellen. | P3 |

## C · Regionen — anlegen & bearbeiten
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| C1 | Region löschen | **Kein DELETE-Endpoint** → falsche/leere Region bleibt bestehen. | Lösch-Endpoint + UI (mit Schutz, wenn Spots zugeordnet sind). | P1 |
| C2 | Region-`country` editierbar | `country` wird beim Anlegen gesetzt, aber im Bearbeiten-Form **nicht sichtbar** editierbar → Breadcrumb „Ort › Land" nicht pflegbar. | Country-Feld in den RegionForm aufnehmen. | P1 |
| C3 | Bulk-Zuordnung / Vorschau | Einzelzuordnung von Spots; kein Bulk, keine Region-Vorschau als Public. | Mehrfachauswahl beim Zuordnen; „Als Public ansehen"-Link. | P2 |

## D · Benutzer, Admins & Moderatoren (Rollen)
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| D1 | Onboarding / Invite | **Kein Invite-Flow**: Admin tippt Passwort manuell (`window.prompt`) und teilt es außerhalb mit; kein „User setzt eigenes Passwort", kein Force-Change beim ersten Login. | E-Mail-Invite mit Einmal-Link; Nutzer setzt eigenes Passwort; optional Force-Change. | P0 |
| D2 | Rollen-Granularität | Nur `admin` / `curator`. **Curator darf fast alles** (Spots/Regionen anlegen/bearbeiten/veröffentlichen/löschen) — nur Benutzerverwaltung ist admin-only. „Moderator" ≠ nur moderieren. | Feinere Rechte definieren (z. B. „darf publishen", „darf Spots editieren", „nur Kommentare/Bilder") oder eine dritte Rolle „Moderator" (nur Review). | P1 |
| D3 | Self-Service-Passwort | Kein Passwortwechsel für den eingeloggten Nutzer selbst. | „Passwort ändern" im Admin-Header/Profil. | P2 |
| D4 | 2FA für Admins | Keine Zwei-Faktor-Absicherung. | TOTP-2FA für Admin-Rolle (bei „voller Kontrolle" empfohlen). | P2 |
| D5 | Passwort-Reset-UX | `window.prompt` für neues Passwort. | Echter Dialog mit Feld + Stärke-Check. | P3 |

## E · Team-Zusammenarbeit
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| E1 | Kanban-Board | Backend `/admin/board/tasks` (CRUD) + API-Funktionen vorhanden, **aber KEIN UI** → totes Feature. | Board-UI bauen (Spalten/Karten/Zuweisung) **oder** Feature entfernen. | P1 |
| E2 | Team-Notizen für Moderatoren | Posting-Formular liegt auf der **admin-only** Benutzer-Seite → Curatoren sehen Notizen (Übersicht), können aber nicht mitschreiben. | Notizen-Composer auf die Übersicht (für admin **und** curator) verschieben. | P1 |
| E3 | Benachrichtigungen | Keine Notifs bei neuer Meldung/Einreichung/Kommentar → Team muss die Review-Queue manuell pollen. | Notif-System (In-App-Badge/E-Mail) für neue Review-Items; `Notification`-Model existiert bereits. | P1 |
| E4 | Aufgaben/Coordination | Kein Zuweisen/Erledigt, keine @Mentions, kein „von wem in Bearbeitung". | Zuweisung + Status an Review-Items/Tasks; „in Bearbeitung durch X"-Anzeige. | P2 |

## F · Moderation (Kommentare / Bilder / Einreichungen)
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| F1 | Kommentare kaum moderierbar | Review-Tab „Tips & Bewertungen" zeigt **nur automatisch geflaggte** Tips; keine pro-Spot-Kommentarliste; kein Hide für beliebige Kommentare. | Pro-Spot-Kommentaransicht + Hide/Restore für **jeden** Kommentar (nicht nur geflaggte). | P0 |
| F2 | Antworten (Threads) ohne Kontext | Neuer `parent_id`-Thread nicht abgebildet → geflaggter Reply erscheint ohne Ursprungskommentar. | In der Moderation Thread-Kontext anzeigen (Original + Reply). | P0 |
| F3 | Moderations-Notizen | `window.prompt("Notiz (optional)")` an mehreren Stellen. | Echter Dialog mit Textfeld (mobil-tauglich). | P3 |
| F4 | Bild-Moderation-Kontext | Reported/Pending-Bilder ohne verlässliche Vorschau/Link/Lightbox. | Thumbnail + „auf Spot ansehen" + Lightbox in der Review-Queue. | P2 |
| F5 | Bulk-Aktionen | Kein Sammel-Publish/-Freigeben; bei 40 Drafts + vielen Bildern zäh. | Mehrfachauswahl + Sammelaktionen (publishen, freigeben, ablehnen). | P2 |

## G · Konsistenz Public ↔ Admin
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| G1 | Anzeige vs. Editierbarkeit | Public zeigt Hero+Attribution, Beschreibung, Sportarten (inkl. `wavekite`), Facilities, Galerie, Kommentare (Threads), Karte. Admin deckt das inhaltlich, **außer**: Hero-Attribution (B4), `model_pref` (B3), Kommentar-Threads (F1/F2). | Siehe B3/B4/F1/F2. | P1 |
| G2 | Score/„Punkte" | Aus Public entfernt (Frontend); Backend-Rating bleibt. Admin hat nichts zu editieren. | Konsistent — keine Aktion nötig. | — |
| G3 | Klima/Forecast („Daten"-Tab) | Public zeigt Forecast/Klimatologie; Admin-Status/Trigger nur teilweise sichtbar. | Siehe B2 (Status+Trigger im Form). | P1 |

## H · Design / UX / Mobil
| # | Punkt | Zustand | Lösung | Prio |
|---|---|---|---|---|
| H1 | Design-Bruch zum Public | Admin nutzt altes Styling (`text-[Npx]`, `rounded-xl`, `bg-band`, `window.prompt/alert`) — passt nicht zum neuen Public-Look (8 px, `#F7F7F7`, Typo-Tokens). | Admin auf dieselben Tokens/Komponenten heben; `prompt/alert` durch Dialoge ersetzen. | P3 |
| H2 | Mobil | Tabellen + horizontale Nav; Team-Moderation unterwegs schwierig. | Responsive Listen/Karten, mobil-taugliche Aktionen. | P2 |
| H3 | Übersicht-Klicktiefe | „Offene Punkte/Entwürfe/Gemeldet" gut angelegt, aber viele Klicks bis zum fehlenden Feld. | Direkt zum Draft + zum fehlenden Feld verlinken; Inline-Quick-Actions. | P3 |

---

## Empfohlene Reihenfolge
1. **P0 Infra:** A1/A2 — `dashboard`-Env verifizieren.
2. **P0 Team-sicher:** B5 (Locking), D1 (Invite), E2 (Mod-Notizen), F1/F2 (Kommentar-Moderation + Threads).
3. **P1 Kontrolle:** B1/B2/B3/B4 (Publish/Klima/Modell/Attribution im Form), C1/C2 (Region löschen/Country), D2 (Rollen), E1/E3 (Board/Notifs).
4. **P2 Effizienz:** B6/B7/B8, C3, D3/D4, F4/F5, H2.
5. **P3 Politur:** B9, D5, F3, H1/H3 (Admin auf Public-Design-Niveau).
