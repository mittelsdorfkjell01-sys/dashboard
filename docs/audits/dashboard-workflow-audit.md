# Dashboard-Workflow-Audit

## 1. Executive Summary

Das Surfwinddata-Back-Office ist ein **inhaltlich sehr breites, betrieblich tragfähiges Steuerwerkzeug** mit einer erstaunlich vollständigen API-Oberfläche (95 Admin-Routen) und echten Sicherheits- und Konsistenz-Kontrollen. Der vollständige Spot- und Regionen-Lebenszyklus (Anlegen → Veröffentlichen → Depublizieren → Archivieren → Reaktivieren) wurde **in der laufenden Anwendung** ausgeführt und funktioniert; optimistisches Locking, Duplikaterkennung, Provenance-Overrides und ein umfangreicher Tide-Steuerstand sind vorhanden und greifen. Die öffentliche Wirkung wurde verifiziert: ein im Dashboard veröffentlichter Spot erscheint sofort in der öffentlichen `/spots`-Liste und Detailansicht.

Das Werkzeug ist damit deutlich mehr als eine CRUD-Tabelle. Die Reibungen liegen nicht in fehlenden Funktionen, sondern in **Governance und Qualitäts-Guardrails**: Veröffentlichen ist nicht mehr an die Readiness gebunden (der im README dokumentierte „409 until ready"-Schutz existiert nicht mehr), sodass Spots ohne Titelbild, Beschreibung und Kategorien öffentlich live gehen — sichtbar an 11 veröffentlichten Seed-Spots, die alle „Kein Hero / Angaben fehlen" tragen. Das Rollenmodell kennt nur zwei Stufen (`admin`, `curator`), wobei der Curator bis hin zum **irreversiblen Hartlöschen** von Spots und Regionen praktisch alles darf außer Benutzerverwaltung. Und der einzige globale Tastatur-Fokusindikator ist im dunklen Admin faktisch unsichtbar (laufzeit-bestätigt).

**Gesamtbewertung: 70/100 — „brauchbar, mit strukturellen Reibungen"** (indikativ; Betrieb/Jobs und Moderation mit echten Meldeinhalten konnten mangels externer ERA5-Anbindung bzw. Testdaten nur teilweise verifiziert werden). **Reifegrad der Steuerungsmacht: Stufe 3 — „Operativ nutzbar"**, mit klarem Weg zu Stufe 4.

**Drei stärkste Eigenschaften**
1. Breite, kohärente Kontrollabdeckung inkl. vollständigem Publikations-Lebenszyklus, Provenance-Overrides und Audit-/Aktivitäts-Trail — laufzeitverifiziert.
2. Echte Schutzmechanismen: CSRF-Double-Submit auf allen Writes, Login-Rate-Limiting (8/900 s), serverseitige Auth, optimistisches Locking, Duplikaterkennung.
3. Starke Listen-/Filter-UX mit inline Readiness-Checkliste und automatischer Regions-Geokodierung, die eine klassische Abhängigkeit (fehlende Koordinaten) auflöst.

**Fünf größte Risiken/Reibungen**
1. **[P1]** Veröffentlichen ohne Readiness-Gate → unvollständige Spots (kein Bild/Beschreibung) gehen öffentlich live.
2. **[P1]** Tastatur-Fokus im gesamten Admin praktisch unsichtbar (WCAG 2.4.7).
3. **[P2]** Grobes Zwei-Stufen-Rollenmodell: Curator darf irreversibel löschen/veröffentlichen.
4. **[P2]** Harte, irreversible Löschungen (Spot inkl. Ratings/Tips/Bilder/Klima) mit nur einem Bestätigungs-Toast.
5. **[P2]** Datenvollständigkeit ist systemisch schwach (alle Seed-Spots „Kein Hero"), ohne Bulk-Vervollständigung.

**Wichtigste nächste Entscheidung:** Soll „Veröffentlichen" ein hartes Gate auf public-kritische Felder (Titelbild, Beschreibung) erhalten, oder bleibt Readiness bewusst nur beratend — und wenn ja, mit welcher Absicherung gegen versehentliche unvollständige Public-Veröffentlichung?

---

## 2. Auftrag, Umfang und Grenzen

- **Auditfrage:** Bilden IA, Navigation, Formulare, Abhängigkeiten, Guardrails, Rechte, Moderation, Betriebsfeedback und Public-Anbindung des Admin-Dashboards einen kohärenten, mächtigen Workflow?
- **Datum:** 2026-08-15
- **Geprüfter Stand:** lokaler Arbeitsbaum, Branch `main` (Commit-Nähe `6dfe2061`), Migrationen bis `0036_weather_shadow_study`.
- **Auditmodus:** **Vollständiger Laufzeitaudit** (Kernabläufe real ausgeführt), ergänzt um Code- und Visual-Evidenz.
- **Umgebung:** lokal, wegwerfbare Docker-DB (`postgis/postgis:16-3.4`) + Redis; Backend `uvicorn` @127.0.0.1:8000 (`DEPLOYMENT_MODE=admin`, `ENABLE_ADMIN_API=true`); Frontend Vite @localhost:5173; Seed „core + Europe" (28 Regionen, 51 Spots).
- **Rollen/Konten:** zwei Testkonten lokal angelegt — `admin` und `curator` (ausschließlich lokale DB).
- **Viewports/Browser:** Chromium (Playwright 1.62), Desktop 1440×900 und Mobile 390×844.
- **Geprüft:** Auth/RBAC-Grundlinie, Spot-Lebenszyklus end-to-end inkl. Public-Wirkung, Regionen-Anlage, optimistisches Locking, Duplikaterkennung, Override/Revert, Tide-Admin-Erreichbarkeit, Review-Queue/Media-Worklist-Erreichbarkeit, Aktivitäts-Trail, Curator-Löschrecht, Formular-Rendering (Login/Liste/Editor), Responsive, Fokus-Sichtbarkeit.
- **Nicht bzw. nur teilweise geprüft (nicht verifiziert):** ERA5-/Forecast-Joblauf und dessen Public-Wirkung (externe Datenquelle, kein Live-Key), Tide-Override end-to-end mit echten Anker-/Tidedaten, Medien-Upload/Adopt end-to-end, Moderation mit echten gemeldeten Inhalten/Kommentar-Threads (keine Meldedaten geseedet), Community-Upvote-Missbrauchsschutz.
- **Sicherheitsbeschränkung — kritisch:** Die lokale `.env` verweist mit `DATABASE_URL` auf eine **entfernte Neon-Cloud-Datenbank** (mutmaßlich Produktion). Alle mutierenden Tests liefen **ausschließlich** gegen die lokale Docker-DB (Override per Umgebungsvariable, empirisch verifiziert); die Neon-DB wurde **nie** beschrieben. Siehe Kapitel 17.
- **Evidenz:** API-Testskript `wf.py` (32 Schritte, 30 PASS), Playwright-Skript `ui.mjs`, Screenshots `shot-01…06`, Code-Referenzen. Testdaten wurden nach dem Lauf wieder gelöscht.

---

## 3. System- und Workflow-Landkarte

**Hauptbereiche (Sidebar):** Übersicht · Spots · Wetterprofile · Regionen · Review · Karte · Aktivität · Benutzer (nur `admin`).

**Zentrale Entitäten & Beziehungen (laufzeit-/code-verifiziert):**
Region *(1)* → *(n)* Spot; Spot → Editorial/Kategorien/Facilities, Hero-/Galerie-Medien, Klimatologie, Tideprofil (+Overrides), Forecast (ERA5-Job), Kommentare/Tips (+Upvotes), Ratings. Übergreifend: Board-Aufgaben, Team-Notizen, Notifications, Aktivitäts-/Audit-Trail, Media-Budget, Review-Queue.

**Rollen:** genau zwei — `admin`, `curator` (`app.auth.service.ROLES == ('admin','curator')`).

**Wichtigste End-to-End-Abläufe:** Region anlegen (mit Auto-Geokodierung) → Spot als Entwurf anlegen → Readiness prüfen → Felder/Medien vervollständigen → Veröffentlichen → öffentliche Wirkung (Liste/Detail/Suche/Karte) → depublizieren/archivieren/reaktivieren; parallel Moderation (Review-Queue → Bild/Tip/Rating verbergen/entfernen) und Betrieb (ERA5/Klima-Jobs, Tide-Kalibrierung).

**Public-Anbindung:** gemeinsame Entitäten/Statusregeln zwischen `/admin/*` und öffentlichen `/spots`, `/regions`, `/search`, `/map`. Veröffentlichter Spot verifiziert öffentlich sichtbar.

---

## 4. Scorecard

| Dimension | Gewicht | Wert 0–5 | Punkte | Konfidenz | Kernaussage |
|---|--:|--:|--:|---|---|
| Informationsarchitektur & Auffindbarkeit | 10 | 4 | 8 | hoch | Nav nach Arbeitsbereichen, starke Filter, Jump-to-Gap |
| Kernworkflows & Effizienz | 15 | 4 | 12 | hoch | Lebenszyklus vollständig; Bulk-Vervollständigung fehlt |
| Formular- & Interaktionskonsistenz | 15 | 4 | 12 | mittel | gemeinsame Field/Chip/CollapsibleSection-Grammatik |
| Blockaden, Fehler & Wiederaufnahme | 15 | 4 | 12 | hoch | Locking, Dup-/Conflict-Dialoge, Unsaved-Guard, Auto-Geocode |
| Public-to-Dashboard-Kontrollabdeckung | 20 | 3 | 12 | mittel | breit, aber Publish-Gate fehlt; Forecast-Wirkung n/v |
| Moderation, Datenqualität & Governance | 10 | 3 | 6 | mittel | Queue+Trail vorhanden; Vollständigkeit nicht erzwungen |
| Rollen, Rechte & riskante Aktionen | 5 | 2 | 2 | hoch | grob; Curator darf hart löschen |
| Betriebsfeedback & Hintergrundprozesse | 5 | 3 | 3 | niedrig | Statusflächen da; Joblauf nicht verifiziert |
| Responsive & Barrierearmut | 5 | 3 | 3 | hoch | responsive gut; Fokus unsichtbar (P1) |
| **Gesamt** | **100** | | **70** | | **brauchbar, mit strukturellen Reibungen** |

> Indikativ: Betrieb (Jobs) und Moderation-mit-Realinhalten sind nur teilweise verifiziert; die verbale Begründung wiegt schwerer als die Zahl.

**Reifegrad der Steuerungsmacht: Stufe 3 („Operativ nutzbar").** Belege: breite Abdeckung, Rollen, Audit-Trail, Bulk-Region-Zuweisung, verifizierte Public-Wirkung. Zur Stufe 4 fehlen: Publish-Gate/Qualitäts-Guardrail, feinere Rollen, verifizierbares Job-/Forecast-Betriebsfeedback, Skalierungshilfen (Bulk-Vervollständigung).

---

## 5. Top-Befunde

### [WF-A] Veröffentlichen ist nicht an Readiness gebunden — unvollständige Spots gehen öffentlich live
- **Priorität:** P1 · **Bereich:** Public Control / Lifecycle · **Evidenz:** Laufzeit + Code + Visual · **Konfidenz:** hoch
- **Betroffene Rollen:** admin, curator · **Objekte:** `POST /admin/spots/{id}/live`, öffentliche `/spots`
- **Reproduktion:** 1) Spot als Entwurf anlegen (nur Name/Region/lat/lon/sport). 2) `GET …/readiness` → `ready=false`, `gaps=[bottom_type, editorial.description, level, water_character, water_type, climatology, image]`. 3) `POST …/live`.
- **Beobachtung:** Antwort **200**, `status=published`, `ready=false`; der Spot erscheint anschließend in öffentlicher `/spots` (`appears on public /spots: True`). Visuell tragen alle 11 veröffentlichten Seed-Spots „Kein Hero" + „2–3 Angaben fehlen" (shot-04).
- **Ursache (belegt):** Bewusstes Design — `app/admin/spots.py:398 set_spot_live` „Publishing is always allowed — readiness is advisory"; `app/api/admin.py:641 go_live` „Go-live is always allowed now". Weicht vom dokumentierten Vertrag ab (README: „Publish (409 with gaps until ready)").
- **Auswirkung:** Öffentliche Spot-Seiten ohne Titelbild/Beschreibung/Kategorien; Qualitäts- und SEO-Schaden; der beabsichtigte Redaktions-Guardrail ist wirkungslos.
- **Empfehlung:** Zwischen *harten* public-kritischen Lücken (Titelbild, Beschreibung, Pflichtkategorien) und *weichen* Lücken (Klimatologie, die on-go-live ohnehin berechnet wird) trennen. Harte Lücken → Veröffentlichen blockieren **oder** einen expliziten „Trotzdem veröffentlichen"-Bestätigungsschritt mit Nennung der fehlenden Felder erzwingen. README-Vertrag angleichen.
- **Akzeptanzkriterien:** (a) Spot ohne Titelbild/Beschreibung kann nicht ohne bewusste Bestätigung veröffentlicht werden; (b) `ready`/`gaps` werden im UI vor dem Publish prominent gezeigt; (c) API verweigert oder markiert Publish bei harten Lücken nachvollziehbar; (d) direkte API-Requests sind identisch abgesichert.
- **Aufwand:** M · **Abhängigkeiten:** Definition „harte vs. weiche" Readiness-Gaps.

### [WF-B] Tastatur-Fokus im Admin praktisch unsichtbar
- **Priorität:** P1 · **Bereich:** Querschnitt/Accessibility · **Evidenz:** Laufzeit + Code · **Konfidenz:** hoch
- **Reproduktion:** Admin (Standard-Theme hell) öffnen; im Browser `--sw-ink` und Body-Hintergrund im `.admin-scope` auslesen.
- **Beobachtung (Laufzeit):** `--sw-ink = #241C17` auf Body-Hintergrund `rgb(10,10,10)`; `data-theme=light`, `admin-scope=true`. Der globale Fokus-Ring `outline: 2px solid var(--sw-ink)` (index.css:103/113) wird damit nahezu schwarz auf fast-schwarz gezeichnet (~1,1:1).
- **Ursache (belegt):** Der Admin aktiviert Dark über `.admin-scope` auf `<body>`, setzt aber kein `data-theme="dark"`; `admin-theme.css` überschreibt `--sw-ink` nicht. Formularfelder tragen zusätzlich `outline-none`.
- **Auswirkung:** WCAG 2.4.7-Verstoß; Tastatur-/AT-Nutzer verlieren die Fokusspur im gesamten Back-Office.
- **Empfehlung:** In `.admin-scope` `--sw-ink` (und `--sw-line`) auf helle Admin-Tokens spiegeln, z. B. `.admin-scope{ --sw-ink: var(--a-fg); }`, oder dedizierten Fokus-Outline gegen `--a-ring`.
- **Akzeptanzkriterien:** sichtbarer Fokus (≥3:1 zum Hintergrund) auf allen Links/Buttons/Feldern im Admin; per Tastatur verifiziert.
- **Aufwand:** S

### [WF-C] Grobes Rollenmodell: Curator darf irreversibel löschen und veröffentlichen
- **Priorität:** P2 · **Bereich:** Rollen/Rechte · **Evidenz:** Laufzeit + Code · **Konfidenz:** hoch
- **Reproduktion:** Als `curator` `DELETE /admin/regions/{id}` einer leeren Region.
- **Beobachtung:** **204** (erfolgreich gelöscht). Curator kann ebenso Spots hart löschen, veröffentlichen, archivieren, overriden.
- **Ursache (belegt):** Router-Dependency `Depends(require_role("admin","curator"))` (admin.py:75); `delete_region`, `delete_spot`, `go_live` haben keine feinere Rolle. Nur Benutzerverwaltung ist admin-exklusiv. `ROLES == ('admin','curator')`.
- **Auswirkung:** Keine Trennung von Redaktion, Datenpflege, Moderation und Systemhoheit; die schwächere Rolle besitzt destruktive, öffentlich wirksame Macht.
- **Empfehlung:** Rechtematrix nach Aufgaben statt zwei Pauschalstufen: destruktive/publish-kritische Aktionen an `admin` (oder neue Rollen `editor`/`moderator`/`viewer`) binden; UI-Sichtbarkeit an dieselbe serverseitige Prüfung koppeln.
- **Akzeptanzkriterien:** Curator kann nicht hart löschen/global publizieren; Verweigerung serverseitig (403) und im UI konsistent; bestehende Abläufe für `admin` unverändert.
- **Aufwand:** M–L · **Abhängigkeiten:** Rollenmodell-Entscheidung, ggf. Migration.

### [WF-D] Harte, irreversible Löschungen mit minimaler Absicherung
- **Priorität:** P2 · **Bereich:** Riskante Aktionen · **Evidenz:** Code + Laufzeit · **Konfidenz:** hoch
- **Beobachtung:** `delete_spot` „Permanently delete a spot and its dependent rows (irreversible)" (admin.py:725) entfernt Spot inkl. Ratings/Tips/Bilder/Klimatologie; im UI nur ein `ConfirmToast`. Regionslöschung ist immerhin gegen zugeordnete Spots geschützt (409).
- **Auswirkung:** Datenverlustrisiko; kombiniert mit WF-C für die schwächere Rolle besonders kritisch.
- **Empfehlung:** Archivieren als Standardpfad priorisieren; Hartlöschen hinter Tippbestätigung (Objektname eingeben) + Nennung abhängiger Objekte/Public-Wirkung; optional Soft-Delete/Wiederherstellfrist.
- **Akzeptanzkriterien:** Löschbestätigung nennt Objekt+Konsequenz+abhängige Daten; Hartlöschen nur `admin`; Archiv als empfohlener Default sichtbar.
- **Aufwand:** S–M

### [WF-E] Datenvollständigkeit ist systemisch schwach; keine Bulk-Vervollständigung
- **Priorität:** P2 · **Bereich:** Datenqualität/Skalierung · **Evidenz:** Laufzeit/Visual · **Konfidenz:** hoch
- **Beobachtung:** Alle 51 Spots (inkl. 11 veröffentlichter) sind „Kein Hero", die Übersicht listet 50 Spots unter „Viel zu tun" (shot-06); `media=no_hero` liefert alle 51. Es gibt Filter/Worklist, aber keine Bulk-Zuweisung von Medien/Feldern — nur Einzel-Editor.
- **Auswirkung:** Bei realer Menge ist Vervollständigung nur durch Öffnen jeder Detailseite leistbar; skaliert nicht.
- **Empfehlung:** Bulk-Medien-Adopt/-Feldpflege über Auswahl in der Liste; „bereit zum Veröffentlichen"-Ansicht; Media-Worklist stärker mit dem Publish-Gate (WF-A) verzahnen.
- **Akzeptanzkriterien:** Mehrfachauswahl in der Spotliste mit Bulk-Aktion (Region, Medien, Status) inkl. Vorschau/Teilfehlerbericht.
- **Aufwand:** M–L

---

## 6. Informationsarchitektur und Auffindbarkeit

Die Navigation folgt Arbeitsbereichen (Übersicht/Spots/Wetterprofile/Regionen/Review/Karte/Aktivität/Benutzer), nicht bloß Datenbanktabellen — gut. Die Übersicht ist handlungsorientiert (priorisierte „Was ist zu tun?"-Liste, Board, „Fertigstellen"-Arbeitsliste), Rohzähler sind bewusst nach unten demoviert. Einstiege in offene Arbeit sind vorhanden (Review, region-lose Spots als roter Top-Alarm).

Reibungen: (a) In der Übersicht ziehen die großen Zähler-Kacheln optisch mehr Aufmerksamkeit als die priorisierte Aufgabenliste (Gewichts-Inversion — separat im Layout-Audit belegt). (b) Alle Admin-Seiten führen einen `sr-only`-Seitentitel; sichtbarer Einstieg ist teils die erste `h2` („Board"). Kein Betriebsschaden, aber Feinschliff möglich.

---

## 7. Kernworkflows

| ID | Aufgabe | Rolle | Ergebnis | Reibung | Blockade | Befunde |
|---|---|---|---|---|---|---|
| WF-01 | Spot finden (Suche/Filter) | admin | ✓ 200; q=Tarifa→5, status=published→11 | gering | – | – |
| WF-02 | Region anlegen | admin | ✓ 201 (Auto-Geocode; unauflösbarer Name→422) | gering | – | positiv |
| WF-03 | Spot anlegen→Readiness→Publish→Public | admin | ✓ published + öffentlich sichtbar | – | – | **WF-A** |
| WF-04 | Bearbeiten mit optim. Locking | admin | ✓ 409 bei stale `expected_values` | – | – | positiv |
| WF-05 | Duplikat anlegen | admin | ✓ 409 erkannt | – | (Schutz) | positiv |
| WF-06 | Depublizieren/Archivieren/Reaktivieren | admin | ✓ 200, korrekte Statuskette | – | – | positiv |
| WF-07 | Override setzen/zurücknehmen | admin | ✓ 200 erreichbar | – | – | (n/v Wirkung) |
| WF-08 | Tide-Admin | admin | ✓ 200 erreichbar | – | – | n/v end-to-end |
| WF-09 | Review-Queue / Media-Worklist / Tips | admin | ✓ 200 | – | – | n/v m. Realinhalt |
| WF-10 | Aktivitäts-/Audit-Trail | admin | ✓ 200, Eintrag nach Aktion | – | – | positiv |
| WF-11 | Curator löscht Region | curator | ✓ 204 (erlaubt) | – | – | **WF-C** |

Besonders positiv: der Publikations-Lebenszyklus ist vollständig und statuskonsistent; optimistisches Locking und Duplikaterkennung greifen serverseitig; die öffentliche Wirkung ist verifiziert (kein „scheinbarer Erfolg").

---

## 8. Konsistenz der Masken

| Maske | Einstieg | Layouttyp | Feldlogik | Validierung | Save/Publish | Cancel/Recovery | Mobile | Konsistenz | Befund |
|---|---|---|---|---|---|---|---|---|---|
| Login | /admin/login | Seite | 2 Felder + Labels | inline, `role=alert` | – | – | ✓ | – | ok |
| Spot-Editor | Liste→Bearbeiten | Seite + fixe Rechts-Rail | `Field`/`Chip`/`CollapsibleSection`; Enum-Chips | client + server (422 feldgenau), Duplikat-/Conflict-Dialog | Ops-Panel + Sticky-Bar (mobil) | Unsaved-Guard, AdminBackButton | ✓ Sticky-Bar `min-h-11` | hoch | – |
| Region-Form | Regionen | Seite | Name/Land/Koordinaten; Auto-Geocode | 422 bei unauflösbar | – | Unsaved-Guard | ✓ | hoch | – |
| Benutzer-Anlage | Benutzer (admin) | Modal | E-Mail/Name/Passwort ≥12 | inline, `noValidate` | – | ConfirmDialog Discard | ✓ | hoch | – |

**Gemeinsame Formulargrammatik ist erkennbar** (`components/ui` + `components/admin/ui` + `CollapsibleSection`): einheitliche Feld-/Chip-Muster, konsistente Unsaved-Changes-Behandlung (`useUnsavedChangesGuard`), einheitliche Fehler-/Erfolgs-Banner (`role=alert`/`role=status`). Anlegen↔Bearbeiten sind konsistent (identisches `SpotForm` für new/edit, PATCH baut Changed-Fields-Diff mit `expected_values`). Fachlich begründete Abweichung: Benutzer als Modal (geringes Risiko/Umfang) vs. Spot als eigene Seite (hohe Komplexität) — angemessen. Keine unbegründeten Abweichungen im geprüften Umfang.

---

## 9. Blockaden, Abhängigkeiten und Sackgassen

| ID | Ort | Voraussetzung | Klassifikation | Nutzen | Reibung | Recovery | Empfehlung |
|---|---|---|---|---|---|---|---|
| B1 | Spot-Anlage | Region nötig | verständliche Voraussetzung | hoch | gering | Regionen inline anlegbar + Auto-Geocode | beibehalten |
| B2 | Region-Anlage | Koordinaten | verständliche Voraussetzung | hoch | gering | Auto-Geocode; sonst 422 mit Hinweis | Hinweistext prüfen |
| B3 | Speichern (parallel geändert) | frischer Stand | notwendige Schutzbarriere | hoch | gering | 409 + Conflict-Dialog „Neu laden" | beibehalten |
| B4 | Duplikat | eindeutiger Name/Koord. | notwendige Schutzbarriere | hoch | gering | 409 + Override-Dialog | beibehalten |
| B5 | Region löschen | keine Spots zugeordnet | notwendige Schutzbarriere | hoch | gering | 409 | beibehalten |
| B6 | **Veröffentlichen** | *keine* (Readiness beratend) | **fehlende Schutzbarriere** | – | – | – | **einführen (WF-A)** |

Bemerkenswert positiv: die klassische „fehlende Region blockiert erst beim Speichern"-Sackgasse ist durch Auto-Geokodierung und inline erstellbare Regionen weitgehend entschärft. Die einzige relevante *fehlende* Barriere ist der Publish-Gate (B6/WF-A).

---

## 10. Public-to-Dashboard-Kontrollmatrix

| Public-Funktion | Quelle | Dashboard-Ort | Anzeigen | Bearbeiten/Steuern | Status/Qualität | Historie | Public geprüft | Bewertung |
|---|---|---|---|---|---|---|---|---|
| Spot-Stammdaten | manuell | Spot-Editor | ✓ | ✓ | ✓ Readiness | ✓ Aktivität | ✓ | vollständig |
| Spot-Region | manuell | Editor + Bulk-assign | ✓ | ✓ (+bulk) | ✓ | ✓ | ✓ | vollständig |
| Region-Koordinaten | Geocode/manuell | Region-Form | ✓ | ✓ Auto-Geocode | teilweise | ✓ | teilw. | teilweise |
| Wind-Forecast | ERA5-Job | Spot `/era5`, Übersicht | ✓ | ✓ Trigger | teilweise | ✓ | **n/v** | nicht verifiziert |
| Forecast-Aktualität | Job | Übersicht/Klima-Notiz | ✓ | indirekt | teilweise | – | **n/v** | nicht verifiziert |
| Klimatologie | Berechnung | Spot, on-go-live | ✓ | ✓ compute-months | ✓ Status | ✓ | teilw. | teilweise |
| Tideereignisse | Berechnung | Tide-Panel | ✓ | ✓ | ✓ | ✓ history | **n/v** | nicht verifiziert |
| Tidekorrektur | Override | Tide-Panel | ✓ | ✓ override/rollback | ✓ | ✓ history | **n/v** | nicht verifiziert |
| Karte/Koordinaten | manuell | SpotMapEditor | ✓ | ✓ | ✓ | ✓ | teilw. | teilweise |
| Kommentare/Tips | User | Editor + Review | ✓ | ✓ verbergen/entfernen | ✓ | ✓ | teilw. | teilweise |
| Upvotes | User | (Community) | teilw. | – | – | – | **n/v** | nicht verifiziert |
| Medien | Adopt/Upload | Editor + Worklist | ✓ | ✓ (kein Bulk) | ✓ Flags | ✓ | teilw. | teilweise |
| Suche nach Spot/Region | Index | – (öffentlich) | ✓ | indirekt via Status | teilw. | – | ✓ | teilweise |
| Publikations-Status | manuell | Editor/Ops | ✓ | ✓ | ⚠ kein Gate | ✓ | ✓ | **Lücke (WF-A)** |

**Coverage (nur erforderliche, verifizierbare Zeilen):** hoch bei Stammdaten/Region/Status/Kommentare/Medien; die `nicht verifiziert`-Zeilen (Forecast, Tideereignisse/-korrektur, Upvotes) betreffen extern-datenabhängige bzw. nicht geseedete Bereiche und sind separat als Folgeprüfung geführt — nicht als Null gewertet. Hauptbefund: **Dashboard-Regler ohne durchgesetzte Public-Qualitäts-Guardrail** (Publish-Gate) statt fehlender Regler.

---

## 11. Moderations- und Steuerungsmacht

- **Inhaltspflege:** stark — vollständiger Editor, Provenance-Override/Revert, Attribution, Galerie.
- **Community-Moderation:** Strukturen vorhanden (Review-Queue mit `submissions/hero_candidates/pending_gallery_images/reported_images/tips/ratings`; Bild approve/reject/remove, Rating hide/restore, Tip-Liste). **Nicht mit echten Meldeinhalten verifiziert** (keine Reports geseedet) — Queue-Erreichbarkeit ja, Fallbearbeitung/Threads/Einspruch offen.
- **Datenqualität/Overrides:** Readiness-Checkliste, Media-Flags, Override/Revert; Schwäche: keine Erzwingung vor Publish (WF-A), keine Bulk-Vervollständigung (WF-E).
- **Rollen/Governance:** Audit-/Aktivitäts-Trail vorhanden (Eintrag nach Aktion verifiziert); Rollenmodell grob (WF-C).
- **Bulk/Skalierung:** Region-Bulk-assign/-unassign vorhanden; sonst wenig Bulk (WF-E).
- **Jobs/Betrieb:** Flächen vorhanden (ERA5-Trigger, Media-Budget „x/500/h", Klima-Statusnotiz, Tide-Monitoring), **Joblauf/Public-Aktualisierung nicht verifiziert**.
- **Notfall/Recovery:** optimistisches Locking, Conflict-/Unsaved-Dialoge, Reaktivierung aus Archiv — gut; Hartlöschen ohne Wiederherstellung — Risiko (WF-D).

**Reifegrad Stufe 3.** Zur Stufe 4 fehlen: Publish-Guardrail, feinere Rollen, verifizierbares Job-Betriebsfeedback, Bulk-Skalierung.

---

## 12. Rollen und riskante Aktionen

| Fähigkeit | admin | curator | UI | Backend | Anmerkung |
|---|---|---|---|---|---|
| Übersicht/Listen lesen | ✓ | ✓ | ✓ | ✓ | – |
| Spot anlegen/bearbeiten | ✓ | ✓ | ✓ | ✓ | – |
| Spot veröffentlichen | ✓ | ✓ | ✓ | ✓ | kein Readiness-Gate (WF-A) |
| Spot **hart löschen** | ✓ | ✓ | ✓ (Toast) | ✓ | irreversibel (WF-D) |
| Region löschen | ✓ | ✓ (204 verifiziert) | ✓ | ✓ | (WF-C) |
| Benutzerverwaltung | ✓ | ✗ | nur admin sichtbar | ✓ | einzige Trennung |
| Anonym (kein Login) | – | – | – | 401 verifiziert | serverseitig geschützt |

UI-Sichtbarkeit und Backend stimmen für Benutzerverwaltung überein (Nav nur für `admin`). Diskrepanz besteht nicht in der Durchsetzung, sondern in der **Grobheit** des Modells: destruktive/öffentlich wirksame Aktionen sind nicht von der schwächeren Rolle getrennt.

---

## 13. Responsive, Accessibility und visuelle Konsistenz

- **Responsive (verifiziert):** Desktop-Tabelle ↔ Mobile-Kartenliste (Spots), Sidebar ↔ horizontale Top-Nav, Editor-Rechts-Rail ↔ Sticky-Bottom-Bar (`min-h-11`). Mobile-Übersicht (390 px) sauber (shot-06).
- **Accessibility:** starke Semantik (Landmarks, `aria-current`, `aria-label` auf Selects, `role=alert/status`, Badges mit Punkt+Label). **Aber:** Tastatur-Fokus faktisch unsichtbar (WF-B, P1). `--a-faint`-Fließtext teils <4,5:1 (aus Layout-/Theming-Audit).
- **Visuelle Konsistenz:** kohärentes, monochromes Admin-Designsystem; kleinere Rhythmus-/Radius-Ausreißer (separate Layout-/Theming-Audits). Keine funktionalen Blockaden.
- **Konsolen-Laufzeit:** außer erwarteten 401 (vor Login) keine JS-Fehler; App rendert stabil.

---

## 14. Empfohlenes Zielbild

- **Publikationsmodell:** zweistufige Readiness (hart/weich) mit Publish-Gate oder bewusster Übersteuerung; „bereit zum Veröffentlichen"-Ansicht.
- **Rollen/Governance:** aufgabenbasierte Rollen (mind. `admin`/`editor`/`moderator`/`viewer`); destruktive und publish-kritische Rechte an `admin`; UI==Backend.
- **Sichere Aktionen:** Archiv als Default, Hartlöschen mit Tippbestätigung + Abhängigkeits-/Public-Wirkungshinweis.
- **Datenqualität/Skalierung:** Bulk-Medien-/Feldpflege + Worklist↔Publish-Verzahnung.
- **Betriebssicht:** konsolidierte Job-/Aktualitätsansicht (ERA5/Klima/Tide) mit letztem Lauf, Fehlerkategorie, sicherem Retry, erwarteter Public-Wirkung.
- **A11y-Basis:** admin-eigene Fokus-Tokens (sichtbarer Ring in Dark).

---

## 15. Priorisierte Roadmap

**1 — Sofort absichern (P0/P1, Integrität & Zugang)**
- WF-B Fokus-Sichtbarkeit (S): `--sw-ink`/`--sw-line` im `.admin-scope` spiegeln.
- WF-A Publish-Guardrail (M): harte vs. weiche Readiness; Gate oder Bestätigung; README angleichen.

**2 — Workflow stabilisieren (P2, Grundlagen & Recovery)**
- WF-D Löschabsicherung (S–M): Tippbestätigung + Abhängigkeitsanzeige; Archiv als Default.
- WF-C Rollen-Granularität (M–L): destruktive/publish-Rechte an `admin`/neue Rollen.

**3 — Steuerungsabdeckung schließen (P2, Betrieb & Moderation)**
- Betriebssicht für Jobs (M): Status/letzter Lauf/Retry/erwartete Public-Wirkung (schließt `n/v`-Zeilen).
- Moderations-Fallbearbeitung mit Realinhalt end-to-end verifizieren/ergänzen (Gründe, Einspruch, Threads).

**4 — Skalieren & optimieren (P2/P3)**
- WF-E Bulk-Medien-/Feldpflege (M–L); „bereit zum Veröffentlichen"-Ansicht.
- Übersicht: Gewichts-Inversion & Rhythmus (aus Layout-Audit).

Regeln eingehalten: jede Maßnahme referenziert einen Befund; Datenintegrität/Rechte zuerst; gemeinsame Grundmuster vor Detailoptimierung.

---

## 16. Quick Wins

1. **WF-B** Fokus-Token im Admin spiegeln (S, P1) — ein Einzeiler behebt eine WCAG-Lücke im ganzen Back-Office.
2. **WF-D** Löschbestätigung um Objektname-Eingabe + Konsequenztext erweitern (S).
3. Publish-Button: fehlende harte Readiness-Felder direkt am Button anzeigen (S, Teil von WF-A).
4. README-Publish-Vertrag an „advisory readiness" angleichen (S) — Doku/Verhalten synchron.
5. `hover:bg-red-100` u. a. un-gemappte Admin-Utilities auf Tokens ziehen (S, aus Theming-Audit).
6. Übersicht: Zähler-Kacheln optisch zurücknehmen zugunsten der Aufgabenliste (S).

---

## 17. Offene Fragen und nicht verifizierte Bereiche

- **Sicherheitsbefund (Betrieb):** lokale `.env` → Neon-Cloud-DB (mutmaßlich Produktion). Empfehlung: dev-`.env` auf lokale DB stellen bzw. eindeutig trennen (`.env` nie mit Prod-Credentials im Arbeitsbaum). Für diesen Audit strikt umgangen; nichts an Neon geschrieben.
- **Nicht verifiziert (fehlende externe Anbindung/Testdaten):** ERA5-/Forecast-Joblauf und Public-Wirkung; Tide-Override/-Ereignisse end-to-end; Medien-Upload/Adopt end-to-end; Moderation mit echten gemeldeten Inhalten und Kommentar-Threads; Upvote-Missbrauchsschutz.
- **Fachliche Entscheidung offen:** Ist „advisory readiness" gewollt (dann Absicherung nötig) oder soll das dokumentierte Hard-Gate zurück?
- **Empfohlene Folgeprüfungen:** Laufzeit-Moderationstest mit geseedeten Reports; Joblauf gegen Test-ERA5/Fixtures; Lasttest der Listen/Filter mit realistisch großer Datenmenge; vollständiger Tastatur-Durchlauf nach WF-B-Fix.

---

## 18. Anhang: Testprotokoll und Evidenzindex

**Laufzeitumgebung:** Docker `postgis/postgis:16-3.4` + `redis:7`; `uvicorn app.main:app` (admin-Mode) @127.0.0.1:8000; Vite @localhost:5173; Seed 28 Regionen/51 Spots; Konten `admin@local.test`, `curator@local.test` (lokal).

**API-Workflows (`wf.py`, 32 Schritte, 30 PASS):** RBAC (anon 401, admin/curator 200); WF-01 Listen/Filter/Suche; WF-02 Region-Create (201 / 422 unauflösbar); WF-03 Spot draft→readiness(false)→live(200,published)→public(True); WF-04 stale-lock 409; WF-05 Duplikat 409; WF-06 unpublish/archive/reactivate 200; WF-07 override/revert 200; WF-08 tide GET 200; WF-09 review-queue/worklist/tips 200; WF-10 activity 200; WF-11 curator delete region 204; Cleanup 204. Zwei „FAIL": (a) Publish-trotz-Lücken=200 → **WF-A** (kein Bug im Code, sondern Design/Guardrail-Befund); (b) patch 422 → Testdaten-Enumfehler meinerseits (kein Produktbefund).
**Zusatz-Evidenz Publish-Gate:** `readiness.ready=False, gaps=[…,image]` → `go_live 200 published` → `public /spots: True`.

**UI (`ui.mjs`, Playwright/Chromium):** Login-Formular (nur E-Mail/Passwort), Anmeldung, 25 Tabellenzeilen geladen, Editor geöffnet; Fokus-Auslesung `--sw-ink=#241C17` auf `rgb(10,10,10)` (data-theme=light) → **WF-B**.
**Screenshots:** `shot-01-login`, `-02-overview`, `-03-focus`, `-04-spots` (veröffentlichte Spots „Kein Hero/Angaben fehlen"), `-05-spot-editor`, `-06-mobile-overview` (50er „Viel zu tun"-Liste, Zähler 40/11/0/28).

**Zentrale Code-Referenzen:** `app/admin/spots.py:398` (advisory publish), `app/api/admin.py:641` (go_live), `:725` (harte Spot-Löschung), `:75` (`require_role("admin","curator")`), `:1044` (Region-Delete ohne Extra-Rolle), `app/csrf.py` (Double-Submit), `app/api/auth.py:63` (Login-Rate-Limit 8/900 s), `frontend/src/index.css:103/113` (globaler Fokus-Outline `var(--sw-ink)`), `frontend/src/components/admin/ui/admin-theme.css` (kein `--sw-ink`-Remap).

**Keine unbeauftragten Produktänderungen.** Es wurde ausschließlich gegen die lokale Wegwerf-DB getestet; erzeugte Testobjekte wurden gelöscht.
