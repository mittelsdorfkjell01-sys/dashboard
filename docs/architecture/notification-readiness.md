# Bereitschaftsprüfung für Empfehlungen per Benachrichtigung

Stand: 23. September 2026. Diese Analyse verändert weder `watches` noch
`notifications` und führt keinen Dispatcher ein.

## Messfrage

Für jeden Nutzer und jedes Auswertungsfenster wird die damalige Rangliste aus
`recommendation_log` rekonstruiert. Ein hypothetischer Versand zählt, wenn der
interne Nutzwert die untersuchte Schwelle überschreitet und seit dem letzten
hypothetischen Versand die Frequenzgrenze verstrichen ist. Als Wahrheit gilt:

1. bevorzugt ein zugeordnetes `session_checkin` mit Ausgang `worthwhile` oder
   `not_worthwhile` innerhalb von 72 Stunden;
2. für wetterbezogene Offline-Auswertungen eine tatsächliche Session von
   mindestens drei aufeinanderfolgenden Stunden im Personal Band anhand
   akzeptierter Beobachtungen;
3. ohne eines dieser Wahrheitssignale bleibt der Fall unbewertet und darf die
   Präzision nicht künstlich verschlechtern.

Pro Schwelle werden Versandzahl, Nutzer mit mindestens einem Versand,
Präzision, Abdeckung, Mehrfachsendungen pro Spot und die Verteilung pro
Wochentag ausgewiesen. Die Auswertung muss getrennt nach Parametersatz,
Profilstatus und Surface erfolgen.

## Aktueller Datenstand

Im lokalen Entwicklungsstand ist keine Produktionsdatenbank mit mehreren
Wochen echten Events verbunden. Deshalb gibt es hier keine belastbaren
Istwerte für Versandhäufigkeit oder Präzision. `recommendation_log`,
zugeordnete Check-ins und der Offline-Backtest stellen die benötigten Eingaben
bereit; Zahlen werden erst nach einem Lauf gegen die freigegebene
Produktionsauswertung in diesen Bericht übernommen.

Eine Freigabe sollte mindestens folgende Datenbasis verlangen:

| Kriterium | Mindestwert |
|---|---:|
| Beobachtungsdauer | 8 Wochen |
| Nutzer mit vollständigem Kite-Profil | 100 |
| Zugeordnete Check-ins mit Ausgang | 200 |
| Wahrheitssignale je geprüfter Parametersatz-Version | 50 |
| Spots mit Beobachtungswahrheit | 20 |

## Zu prüfende Schwellen und Frequenzen

Der erste Counterfactual-Lauf soll Nutzwertschwellen `0,20`, `0,30`, `0,40`
und `0,50` prüfen. Das sind Versuchspunkte, keine öffentliche Bewertung und
keine bereits freigegebene Produktschwelle. Zusätzlich wird pro Nutzer nur der
beste Spot eines Fensters betrachtet.

Empfohlener Startkorridor nach ausreichender Datenbasis:

- nur `now` mit mindestens einer machbaren Drei-Stunden-Session;
- Schwelle aus dem kleinsten Versuchspunkt wählen, der im Holdout mindestens
  70 % Präzision erreicht;
- höchstens eine Nachricht in 72 Stunden und höchstens zwei pro sieben Tage;
- denselben Spot frühestens nach sieben Tagen erneut senden;
- keine Nachricht, wenn das Signal seit der letzten Berechnung schwächer wurde;
- lokale Ruhezeit 21:00 bis 08:00 Uhr, Versand danach nur bei weiterhin
  erfüllter Schwelle.

Bleibt keiner der Versuchspunkte über dem Präzisionsziel, lautet die Empfehlung
gegen eine Aktivierung. `next_week` und `season` werden erst separat freigegeben,
weil ihr Zeithorizont und ihre Wahrheitssignale anders sind.

## Späterer Umbau von `watches`

Vor einem Benachrichtigungsbau braucht `watches` ein versioniertes,
nutzerspezifisches Regelmodell mit `sport`, `surface`, optionaler Region oder
Spotmenge, interner Schwelle, Frequenzgrenze, Ruhezeit/Zeitzone und
`params_version`. Der Versandzustand braucht einen Deduplizierungsschlüssel aus
Nutzer, Spot, Surface und Zeitfenster sowie den beim Versand aktiven
Parametersatz.

Die heutige Tabelle wird erst in einer eigenen Benachrichtigungsphase migriert.
Die reservierten Eventtypen `notification_sent`, `notification_opened` und
`notification_dismissed` bleiben bis dahin unbenutzt.

## Freigabeentscheidung

Der technische Unterbau ist auswertbar, die Produktfreigabe ist mangels echter
Langzeitdaten offen. Vor einer Umsetzung müssen der Counterfactual-Lauf, ein
zeitlich getrennter Holdout und eine manuelle Prüfung ungewöhnlich häufiger
Nutzer-Spot-Kombinationen vorliegen.
