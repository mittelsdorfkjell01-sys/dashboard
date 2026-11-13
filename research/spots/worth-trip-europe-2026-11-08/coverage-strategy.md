# Europaweite Abdeckung auf dem Weg zu circa 400 Spots

Die Zielgröße von ungefähr 400 gilt für **bestätigte** `worth_trip`-Datensätze, nicht für eine ungeprüfte Namensliste. Es gibt keine Länderquote. Die Recherche wird dennoch aktiv über verschiedene europäische Küsten- und Reviertypen verteilt, damit einzelne bekannte Surfregionen den Bestand nicht dominieren.

## Auswahlprinzip

Ein Spot zählt erst zum Zielbestand, wenn alle folgenden Punkte erfüllt sind:

1. Sportnutzung und konkreter Reisegrund sind durch mehrere Quellen belegt.
2. Der Spot ist unterhalb der World-Class-Stufe abgrenzbar.
3. Einstieg oder Startbereich ist ausreichend genau verortet.
4. Öffentlicher Live-Bestand ist auf Namen, Aliasse und geografische Nähe geprüft.
5. Eine vorhandene Datenbankregion und gültige Taxonomiewerte sind nutzbar.
6. Regeln, Einschränkungen und Einrichtungen sind feldbezogen belegt oder bleiben ausdrücklich unbekannt.

## Geografische Recherchebahnen

Die Batches wechseln zwischen diesen Bahnen; die Reihenfolge ist keine Qualitäts- oder Länderquote:

- **Atlantik und Biskaya:** Portugal, Nordspanien, französische Atlantikküste, Cornwall, Irland und Nordschottland.
- **Nord- und Ostsee:** Niederlande, Deutschland und Südjütland; weitere Länder erst nach Anlage passender Regionen.
- **Westliches Mittelmeer:** Languedoc, Sardinien und Sizilien.
- **Ägäis:** Kos, Naxos, Paros, Rhodos und Limnos.
- **Atlantische Inseln:** Kanaren mit den vorhandenen Regionen Fuerteventura, Gran Canaria, Lanzarote und Teneriffa.
- **Binnen- und weitere europäische Reviere:** werden als Regionlücke dokumentiert, solange keine passende Live-Region vorhanden ist.

## Strukturelle Abdeckungsgrenze und Erweiterung des Live-Systems

Der öffentliche Regionsendpunkt enthält aktuell 30 nutzbare Regionen in zehn Ländern: Deutschland, Dänemark, Spanien, Frankreich, Vereinigtes Königreich, Griechenland, Irland, Italien, Niederlande und Portugal. Zwei veröffentlichte Spots belegen zusätzlich die schon vorhandenen, aber dort nicht ausgegebenen Regionen `Dalmatien` und `Noord-Holland`. Große europäische Wassersportgebiete unter anderem in Norwegen, Schweden, Polen, im Baltikum sowie an alpinen Seen besitzen weiterhin keine öffentlich auffindbare passende Region.

Der Nutzer hat die Anlage fehlender Regionen inzwischen ausdrücklich autorisiert. `regions-expansion-001.json` enthält deshalb 40 geografisch etablierte Regionsentwürfe. Sie wurden über den vorhandenen Regions-Importer in die lokale PostGIS-Datenbank geschrieben und starten sämtlich als `draft`; kein Eintrag wurde veröffentlicht. Vor einem Cloud-Import müssen sie nochmals gegen alle sichtbaren und administrativ erreichbaren Regionen geprüft werden. Die Cloud-Persistierung bleibt wegen fehlender Adminauthentifizierung offen.

## Fortschrittsmessung

- Zielgröße: circa 400 bestätigte Kandidaten.
- Aktuell vorbereitet: 18.
- Zusätzlich blockiert: 1 Kandidat ohne gesicherte Einstiegskordinate.
- Ausschlüsse werden separat gezählt und erhöhen nicht den Zielstand.
- Ein Kandidat erhöht den Zielstand erst nach Quellen-, Taxonomie-, World-Class- und öffentlicher Live-Duplikatsprüfung.

