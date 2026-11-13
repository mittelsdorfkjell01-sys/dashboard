/**
 * German message catalogue — the source language.
 *
 * Structure mirrors the UI surfaces rather than the component tree: a string
 * that appears in several components still belongs under one surface key, and
 * moving a component between files must never force a key rename. `common`
 * holds the handful of words that genuinely recur across surfaces.
 *
 * This catalogue only ever contains strings that are actually referenced from
 * a migrated component. It grows one tranche at a time; speculative keys for
 * surfaces nobody has migrated yet would rot silently, because nothing fails
 * when an unused key drifts out of sync with the screen it was meant for.
 *
 * `as const` is load-bearing: it turns every key into a literal type, which is
 * what lets `t()` reject a typo at compile time (see ../i18next.d.ts). Keep the
 * object literal inline — extracting a sub-object into a `let` widens it to
 * `string` and silently loses that checking.
 *
 * Only the public site lives here. The admin back office stays hard-coded in
 * German on purpose: it ships in a separate chunk (scripts/check-bundle.mjs
 * fails the public build if an admin chunk leaks in), and routing its strings
 * through this catalogue would pull them into the public bundle for an
 * audience of operators who will never need another language.
 */
export const de = {
  common: {
    loading: "Lädt…",
    retry: "Erneut versuchen",
    back: "Zurück",
    cancel: "Abbrechen",
    close: "Schließen",
    sending: "Senden…",
  },
  // Rendered by both the footer and the account menu — see lib/siteLinks.ts,
  // which owns the routes and their order.
  siteLinks: {
    faq: "Daten & Fragen",
    contact: "Kontakt",
    terms: "Nutzungsbedingungen",
    imprint: "Impressum",
    privacy: "Datenschutz",
  },
  footer: {
    copyright: "© {{year}} surfwind data",
  },
  header: {
    searchPlaceholder: "Ort, Region oder Spot",
    tagline: "Die besten Surfspots im Überblick",
    openSearch: "Suche öffnen",
    addSpots: "Spots hinzufügen",
  },
  language: { label: "Sprache", german: "Deutsch", english: "English", switchTo: "Zu {{language}} wechseln" },
  region: {
    notFound: "Region nicht gefunden", overview: "Übersicht", backOverview: "Zurück zur Übersicht",
    spotCount_one: "{{count}} Spot in der Region", spotCount_other: "{{count}} Spots in der Region",
    descriptionPending: "Für diese Region ist noch keine Beschreibung verfügbar.", top: "Spot-Auswahl in {{name}}", when: "Wann hinfahren",
    windUnknown: "Windverfügbarkeit für Regionen: Unbekannt", windHelp: "Warum ist die regionale Windverfügbarkeit noch unbekannt?",
    spots: "Die Spots", noSpots: "Keine Spots für diese Auswahl.", map: "Auf der Karte", similar: "Ähnliche Regionen",
  },
  dataHelp: { label: "Erklärung öffnen", suffix: "Mehr unter Daten & Fragen" },
  recommendations: { limits: "Katalogauswahl zur Orientierung. Vorhersagen sind Modellwerte, keine Garantie; Quelle und Aktualität stehen an den Wetterdaten.", currentTitle: "Spot-Auswahl", nextWeekTitle: "Für nächste Woche vormerken", seasonTitle: "Saisonale Spot-Auswahl", allSpots: "Alle Spots entdecken", map: "Karte" },
  // --- Daten & Fragen -------------------------------------------------------
  // One public page carries help, project background and contact (see
  // pages/Fragen.tsx); it replaced the former FAQ/Kontakt/UeberUns pages, where
  // the same statements stood up to three times and English was missing.
  // German is the source language — en.ts must stay structurally identical.
  help: {
    title: "Daten & Fragen",
    lede: "Woher die Daten kommen, wo ihre Grenzen liegen, wie Konto und Mitmachen funktionieren – und wie du den Betreiber erreichst.",
    jump: {
      label: "Auf dieser Seite",
      safety: "Sicherheit",
      project: "Projekt",
      spots: "Spots",
      weather: "Wetter",
      season: "Saison",
      map: "Karte",
      account: "Konto",
      contribute: "Mitmachen",
      contact: "Kontakt",
    },
    section: {
      safety: "Sicherheit",
      project: "Das Projekt",
      spots: "Spots & Katalog",
      weather: "Wetter, Wellen & Gezeiten",
      season: "Saison & Windklimatologie",
      map: "Karte",
      account: "Konto, Einheiten & Setup",
      contribute: "Mitmachen & Community",
      contact: "Kontakt",
    },
    safety: {
      approval: {
        title: "Ein Spoteintrag ist keine Sicherheitsfreigabe",
        p1: "Surfwinddata beschreibt Spots und Bedingungen. Ob du aufs Wasser gehst, entscheidest du vor Ort. Ein Eintrag im Katalog, ein Vorhersagewert oder eine gute Saisonkurve heißen nicht, dass ein Spot heute sicher ist oder zu dir passt.",
        checkTitle: "Prüfe vor jeder Session:",
        check1: "die aktuellen Bedingungen vor Ort, nicht nur die Vorhersage",
        check2: "Strömung, Wasserstand und Gezeiten",
        check3: "lokale Regeln, Sperrzonen und Schutzgebiete",
        check4: "Einstieg, Hindernisse und Untergrund",
        check5: "dein Können und deine Ausrüstung",
        ask: "Frag Schulen, Stationen oder Rider vor Ort, wenn du einen Spot nicht kennst. Im Zweifel fahr nicht hinaus.",
        emergency: "Surfwinddata ist kein Notfall- oder Rettungsdienst. In der EU erreichst du Rettungsdienste unter 112.",
      },
      mark: {
        q: "Was bedeutet das rote ! am Spot?",
        p1: "Das rote Ausrufezeichen steht vor einer Sicherheitsinfo, zum Beispiel ablandigem Wind, einer Gefahrenstelle oder einer Sperrzeit. Dahinter folgt immer ein sachlicher Satz, etwa: „Ablandig. Der Wind weht vom Strand aufs Wasser.“ Rot verwenden wir nur für dieses Zeichen.",
        p2: "Fehlt das Zeichen, heißt das nicht, dass ein Spot sicher ist. Es erscheint nur, wenn die Daten den Hinweis tragen. Ablandigen Wind zeigen wir nur, wenn der Küstenverlauf am Spot geprüft ist und eine aktuelle Vorhersage vorliegt.",
        p3: "Warum keine Ampel? Ob ein Spot passt, hängt von deinem Sport, deinem Können, deiner Ausrüstung und dem Einstieg ab. Ein grünes Licht würde eine Sicherheit vortäuschen, die keine Vorhersage hat. Deshalb gibt es keine Ampeln, Scores oder ausgegrauten Stunden – nur Fakten und, wo nötig, einen klaren Hinweis.",
      },
    },
    project: {
      what: {
        title: "Was Surfwinddata ist",
        p1: "Surfwinddata ist eine Sammlung von Wassersport-Spots mit den Daten, die du für deine Planung brauchst. Zu jedem Spot stehen redaktionelle Angaben wie Einstieg, Wassercharakter, örtliche Regeln und geeignete Sportarten neben Vorhersage, Gezeiten und saisonalen Windverhältnissen. Denn ein Ort ist mehr als ein Wetterwert.",
        p2: "Surfwinddata wird von einem kleinen Team entwickelt, das selbst begeistert auf dem Wasser ist – beim Kitesurfen und in anderen Wassersportarten. Es ist ein Projekt von der Community für die Community: Wer einen Spot kennt, eine geänderte Regel bemerkt oder einen Fehler findet, macht den Katalog für alle besser.",
        p3: "Surfwinddata ist nicht darauf ausgelegt, Gewinn zu machen. Derzeit gibt es keine Werbung und keine Bezahlfunktion. Wenn sich das Projekt künftig selbst tragen muss, fließen die Einnahmen in gute Daten und eine stabile Serverleistung, nicht in Profit. Deine Daten werden nicht verkauft. Welche Dienste technisch eingesetzt werden, steht in der <privacy>Datenschutzerklärung</privacy>, wer hinter dem Projekt steht, im <imprint>Impressum</imprint>.",
      },
      browse: {
        title: "Suchen oder stöbern",
        p1: "Manchmal steht der Ort fest, und du willst wissen, was dich dort erwartet. Manchmal steht das Zeitfenster fest – ein Wochenende, eine Reise – und du suchst passende Orte. Und manchmal stöberst du einfach durch die Sammlung und triffst auf Spots, die du vorher gar nicht auf dem Schirm hattest. Surfwinddata soll beides können: gezielt suchen und frei entdecken. Was davon noch nicht nutzbar ist, ist als „Geplant“ gekennzeichnet.",
      },
      limits: {
        title: "Daten und ihre Grenzen",
        p1: "Vorhersagen sind Modellberechnungen, keine Messungen. Lokale Effekte wie Thermik, Abdeckung durch Gelände oder Düseneffekte können abweichen, und je weiter ein Termin entfernt ist, desto unsicherer wird die Vorhersage. Saisonale Daten beschreiben, wie es in vergangenen Jahren typischerweise war. Über einen bestimmten Reisetag sagen sie nichts.",
        p2: "Fehlt ein Wert, steht dort „—“ oder „nicht verfügbar“. Das heißt: Es liegen keine verwendbaren Daten vor. Es heißt nicht Windstille, keine Wellen oder gefahrlose Bedingungen.",
        p3: "Die Entscheidung vor Ort hängt von den aktuellen Bedingungen, lokalen Informationen und deinem Können ab.",
      },
      languages: {
        title: "Sprachen",
        p1: "Surfwinddata wird auf Deutsch geschrieben, die deutsche Fassung ist die Quelle. Englische Texte kommen schrittweise dazu. Fehlt eine Übersetzung, siehst du den deutschen Text.",
      },
    },
    spots: {
      sports: {
        q: "Für welche Sportarten ist Surfwinddata gedacht?",
        p1: "Der Katalog unterscheidet Surfen, Windsurfen, Kitesurfen und Wingfoilen. Welche Sportarten an einem Spot möglich sind, steht auf seiner Detailseite.",
        p2: "Windfoil und Kitefoil führen wir als eigene Varianten. Foilen braucht genug Wassertiefe, einen passenden Startbereich und oft ein anderes Windfenster. Ein Spot, der zum Windsurfen mit Finne oder zum klassischen Kiten passt, ist deshalb nicht automatisch ein Foil-Spot. Solange die Redaktion eine Foil-Variante an einem Spot nicht geprüft hat, steht dort „unbekannt“. Wir schätzen sie nicht aus der Hauptsportart ab, denn eine falsche Angabe kann hier zu Grundberührung oder einem ungeeigneten Start führen. „Unbekannt“ heißt nicht ungeeignet, sondern ungeprüft.",
      },
      noAccount: {
        q: "Kann ich ohne Konto nach Spots suchen?",
        p1: "Ja. Den öffentlichen Katalog, die Karte und Spotinformationen kannst du ohne Anmeldung nutzen. Für persönliche Favoriten, Besuche, dein Setup und kontobezogene Vorschläge brauchst du ein Konto.",
      },
      find: {
        q: "Wie finde ich einen Spot oder eine Region?",
        p1: "Über die Suche oben auf jeder Seite oder auf der <map>Karte</map>.",
      },
      complete: {
        q: "Ist die Spotliste vollständig?",
        p1: "Nein. Der Katalog wird erweitert und kann Lücken enthalten. Fehlende Spots kannst du über dein Konto <spotSuggest>vorschlagen</spotSuggest>.",
      },
      missingFromList: {
        q: "Warum fehlt ein Spot in einer Empfehlungsliste?",
        p1: "Empfehlungslisten sind eine Auswahl und kein vollständiger Spotkatalog. Nutze die Suche oder Karte, wenn du einen bestimmten Spot suchst. Sein Fehlen in einer Liste bedeutet nicht, dass er ungeeignet ist.",
      },
      originMark: {
        q: "Was bedeutet das Zeichen am Spotnamen?",
        p1: "Es kennzeichnet einen Spot, den wir selbst erfasst haben. Spots ohne dieses Zeichen hat jemand aus der Community eingetragen; am Fuß der Spotseite steht, wer. Das Zeichen ist keine Qualitäts- oder Sicherheitsbewertung: Jeder Spot geht durch dieselbe Freigabe, und es sagt nur, wer die Angaben eingetragen hat.",
      },
    },
    weather: {
      forecastVsClimate: {
        q: "Was unterscheidet Vorhersage und Windklimatologie?",
        p1: "Die Vorhersage beschreibt erwartete Bedingungen der kommenden Tage. Die Windklimatologie beschreibt typische Verhältnisse aus vergangenen Zeiträumen. Sie hilft bei saisonaler Planung, sagt aber nicht das Wetter an einem bestimmten zukünftigen Tag voraus.",
      },
      windDirection: {
        q: "Wie lese ich die Windrichtung?",
        p1: "Sie beschreibt, aus welcher Richtung der Wind kommt. Ob er auflandig, seitlich oder ablandig weht, hängt vom Küstenverlauf und deinem konkreten Einstieg ab. Ablandigen Wind kennzeichnen wir mit dem roten ! (siehe <safety>Sicherheit</safety>).",
      },
      sources: {
        q: "Woher stammen die Daten?",
        p1: "Redaktionelle Spot- und Regionsinformationen stammen vom Betreiber und aus Community-Beiträgen. Wetterdaten basieren auf Wettermodellen; die Kartendarstellung nutzt OpenStreetMap-Daten und externe Kartenanbieter. Die aktuell eingesetzten Dienste sind in der <privacy>Datenschutzerklärung</privacy> genannt.",
      },
      otherApps: {
        q: "Warum weichen Werte von anderen Wetter-Apps ab?",
        p1: "Anwendungen können unterschiedliche Modelle, Aktualisierungszeiten, Höhen, Zeitpunkte und Darstellungsintervalle verwenden. Vergleiche deshalb auch Quelle und Bezugszeit.",
      },
      tides: {
        q: "Gezeiten: Für welchen Ort und in welcher Zeit?",
        p1: "Die Gezeiten werden für einen Modellpunkt an der Küste nahe dem Spot berechnet, nicht für deinen genauen Einstieg. In Buchten, Flussmündungen und hinter Inseln können Zeiten und Hub deutlich abweichen. Neben der Überschrift steht, wie gut der Punkt abgesichert ist: „Modell“, „Geprüfter Modellpunkt“, „Lokal kalibriert“ oder „Messstation-kalibriert“.",
        p2: "Alle Zeiten stehen in der Ortszeit des Spots, nicht in der Zeitzone deines Geräts. Hoch- und Niedrigwasser sind ungefähr: Sie stehen mit „ca.“ oder als Zeitspanne da.",
        p3: "Die astronomische Tide zeigt den relativen Verlauf des Wasserstands, keine absolute Wassertiefe. Wetter, Sturmflut, Abfluss und Strömung sind darin nicht enthalten. Steht dort „Modellierter Meeresspiegel“, sind Wetteranteile enthalten, nahe der Küste ist der Wert aber ungenauer. Beides ist nicht zur Navigation oder als Sturmflutwarnung gedacht.",
        p4: "„Momentan nicht verfügbar“ heißt: Für diesen Spot liegt keine belastbare Gezeitenberechnung vor. Das sagt nichts darüber, ob es dort Tide gibt.",
      },
      waves: {
        q: "Wellen: Gesamtwelle, Windsee, Dünung",
        p1: "Der Seegang setzt sich aus mehreren Anteilen zusammen:",
        total: "Gesamtwelle: alle Anteile zusammen. Das kommt dem am nächsten, was du vom Strand aus siehst.",
        windSea: "Windsee: Wellen, die der Wind in der Nähe gerade erzeugt – kurz, steil und unregelmäßig.",
        primary: "Primärdünung: der stärkste Dünungszug, oft weit entfernt entstanden – länger, gleichmäßiger, mit längerer Periode.",
        secondary: "Sekundärdünung: ein zweiter Dünungszug aus einer anderen Richtung, falls es einen gibt.",
        p2: "Die Höhen sind signifikante Wellenhöhen aus dem Modell, berechnet für offenes Wasser vor der Küste. Am Strand kann die Brandung durch Untergrund, Riff und Küstenform deutlich höher oder niedriger ausfallen. Diese Umrechnung macht Surfwinddata derzeit nicht.",
        p3: "Warum bleiben Felder leer? Nicht jedes Modell liefert jeden Anteil. In Seen, Lagunen, Flachwasser und geschützten Buchten gibt es oft keine verwertbaren Wellendaten. Ein leeres Feld heißt „keine Daten“, nicht „keine Wellen“.",
      },
    },
    season: {
      percentages: {
        q: "Sind saisonale Prozentwerte eine Wettergarantie?",
        p1: "Nein. Sie beschreiben Häufigkeiten für das angegebene Zeitfenster und die dargestellten Bedingungen. Beachte die Beschriftung und die Methodik des jeweiligen Diagramms.",
        p2: "So entsteht die Windzuverlässigkeit auf der Spotseite:",
        data: "Daten: ERA5-Reanalyse, Wind in 10 m Höhe, stündlich.",
        period: "Zeitraum: die letzten 20 abgeschlossenen Kalenderjahre.",
        place: "Ort: eine Rasterzelle von etwa 0,25° um den Spot, also rund 20 bis 30 km Kantenlänge.",
        threshold: "Schwelle: das Windfenster, das du einstellst. Wenn du „Passende Windrichtung berücksichtigen“ wählst, zählen nur die geprüften Windrichtungen des Spots.",
        counting: "Zählung: nur Stunden bei Tageslicht. Eine Session sind mindestens drei aufeinanderfolgende Stunden im Fenster. Ein brauchbarer Windtag hat mindestens eine Session. Eine Woche gilt in einem Jahr als erfolgreich, wenn sie mindestens zwei brauchbare Windtage hat.",
        percentage: "Prozentwert: in wie vielen der Jahre diese Kalenderwoche erfolgreich war. Gibt es weniger als 15 vollständige Jahre, zeigen wir keinen Wert.",
        p3: "Warum wird daraus kein Tagesdatum? Zwanzig Jahre zeigen, wie oft eine Woche funktioniert hat, aber nicht, an welchem Tag. Das Wetter eines bestimmten Tages ist Sache der Vorhersage, und die reicht nur wenige Tage voraus. Lokale Thermik und Geländeeffekte bildet eine Zelle dieser Größe nicht ab.",
      },
      regionUnknown: {
        q: "Warum ist die regionale Windverfügbarkeit unbekannt?",
        p1: "Eine Region umfasst viele Spots mit unterschiedlicher Ausrichtung und eigenem Wind. Eine einzige Aussage für die ganze Region braucht eine geprüfte Regel, sonst klingt sie zuverlässiger, als sie ist. Bis eine solche Regel dokumentiert und überprüft ist, steht dort „Unbekannt“. Vorhersage und Windzuverlässigkeit findest du auf den einzelnen Spotseiten.",
      },
    },
    map: {
      how: {
        q: "Wie funktioniert die Karte?",
        p1: "Die Karte hat zwei Modi. Spots zeigt alle veröffentlichten Spots; nah beieinanderliegende werden zu Gruppen zusammengefasst, die sich beim Hineinzoomen auflösen. Wind zeigt die Wind- oder Wellenvorhersage als Farbfläche mit Strömungslinien. Beim Wechsel bleibt der Kartenausschnitt gleich. Tippst du im Wind-Modus auf eine Stelle, siehst du die stündliche Vorhersage für diesen Punkt. Tippst du auf einen Spot, siehst du dessen Vorhersage.",
        p2: "Warum bleibt die Grundkarte hell, auch im dunklen Modus? Die Farben für Wind und Wellen brauchen einen hellen Untergrund, damit sie sich gut unterscheiden lassen.",
        p3: "Warum kann ich im Wind-Modus nicht weiter hineinzoomen? Das Wettermodell rechnet in Zellen von einigen Kilometern Größe. Innerhalb einer Zelle gibt es nur einen Wert. Weiter hineingezoomt wäre die Fläche einfarbig, und alle Linien zeigten in dieselbe Richtung. Das sähe genauer aus, als die Daten sind. Deshalb endet der Zoom dort, wo die Daten nichts mehr unterscheiden. Ein angetippter Punkt zeigt den Wert seiner Modellzelle, nicht den gemessenen Wind genau an dieser Stelle.",
      },
    },
    account: {
      units: {
        q: "Welche Einheiten gibt es, und wo stelle ich sie um?",
        wind: "Wind: Knoten (kn), Beaufort (Bft), Meter pro Sekunde (m/s)",
        waves: "Wellenhöhe: Meter (m), Fuß (ft)",
        temperature: "Temperatur: Celsius (°C), Fahrenheit (°F)",
        distance: "Entfernung: Kilometer (km), Meilen (mi)",
        p1: "Alle vier stellst du in den <settings>Einstellungen</settings> unter „Einheiten & Anzeige“ ein. Deine Auswahl gilt überall, wo Wind, Wellen, Temperatur und Entfernungen angezeigt oder eingegeben werden. Mit Konto wird sie gespeichert und gilt auf jedem Gerät, auf dem du angemeldet bist. Ohne Konto kannst du die Windeinheit (kn oder m/s) direkt auf der Datenseite eines Spots wechseln; sie bleibt in diesem Browser gespeichert.",
        p2: "Die Umstellung ändert nur die Anzeige. Intern rechnet Surfwinddata immer in kn, m, °C und km, die Daten selbst bleiben gleich. Beaufort ist eine Stufenskala: 17 kn und 21 kn sind beide 5 Bft. Werte in Bft sind deshalb gröber.",
      },
      setup: {
        q: "Wozu dient Mein Setup?",
        p1: "Hier kannst du deine Kite-Ausrüstung und Fahrvorlieben hinterlegen. Angaben wie Gewicht, Level, Kites und Board-Typ unterstützen die persönliche Spot-Auswahl. Die detaillierte Setup-Funktion ist derzeit auf Kitesurfen ausgerichtet.",
      },
      home: {
        q: "Muss ich meinen Heimatort angeben?",
        p1: "Nein. Er ist optional und lässt sich ändern oder entfernen. Ein ungefährer Ausgangspunkt für deine Planung reicht aus.",
      },
      profile: {
        q: "Wer kann mein Profil sehen?",
        p1: "Die Profilübersicht ist Teil deines Kontos. Eine öffentliche Profilseite gibt es derzeit nicht. Für veröffentlichte Community-Beiträge gelten <community>eigene Regeln</community>.",
      },
      exportDelete: {
        q: "Wie exportiere oder lösche ich meine Daten?",
        exportP: "Export: <settings>Einstellungen</settings> → „Privatsphäre & Inhalte“ → „Datenexport herunterladen“. Du erhältst eine JSON-Datei mit einer Kopie deiner Kontodaten.",
        deleteP: "Löschen: Einstellungen → „Konto löschen“ → Passwort eingeben → „Endgültig löschen“. Die Löschung wirkt sofort und lässt sich nicht rückgängig machen.",
        d1: "Gelöscht werden dein Konto, deine Favoriten, besuchten Spots, Reisen, dein Setup und deine persönlichen Vorschläge.",
        d2: "Veröffentlichte Bewertungen, Tipps und Spot-Vorschläge bleiben anonymisiert stehen: Statt deines Namens steht dort „Gelöschtes Konto“. E-Mail-Adresse und Verknüpfung zu dir werden entfernt.",
        d3: "Hochgeladene Bilder bleiben ohne Verknüpfung zu dir erhalten.",
        p3: "Deine Kommentare kannst du vorher selbst löschen. Soll ein anderer Beitrag ganz verschwinden, beantrage das vor der Kontolöschung beim Betreiber, mit Link zum Beitrag. Kannst du dich nicht mehr anmelden, nutze die <contact>Kontaktadresse</contact>. Sende dabei nie dein Passwort.",
      },
      mail: {
        q: "Warum kommt keine Bestätigungs- oder Passwort-Mail an?",
        p1: "Prüfe die eingegebene E-Mail-Adresse und den Spamordner. Nutze die erneute Anforderung, sofern angeboten. Wenn das nicht hilft, kontaktiere den Betreiber. Sende keine Passwörter oder Bestätigungslinks.",
      },
      planned: {
        q: "Was bedeutet „Geplant“?",
        p1: "Bereiche mit dem Hinweis „Geplant“ sind vorgesehen, aber noch nicht nutzbar. Die Kennzeichnung nennt bewusst keinen Termin, weil neue Funktionen schrittweise entstehen. Derzeit geplant sind unter anderem:",
        alerts: "Wetteralarme für Favoriten – erst, wenn zuverlässige Schwellen und Versandzeiten feststehen.",
        notifications: "E-Mail-Benachrichtigungen zu deinen Spot-Vorschlägen – sobald der Versand eingerichtet ist.",
        publicProfile: "ein öffentliches Profil.",
        p2: "Geplantes kann sich ändern oder wegfallen.",
      },
    },
    contribute: {
      suggest: {
        q: "Wie schlage ich einen Spot vor?",
        p1: "Du kennst einen Spot, der fehlt? Öffne <addSpots>Spots hinzufügen</addSpots> in deinem Konto; dafür musst du angemeldet sein. Prüfe vorher über Suche oder Karte, ob es den Spot schon gibt. Trage Name, Region und Position ein; Sportarten und weitere Angaben kannst du ergänzen. Wissen von Leuten, die einen Spot kennen, macht den Katalog besser.",
      },
      review: {
        q: "Ist mein Vorschlag sofort öffentlich?",
        p1: "Nein. Er wird zunächst geprüft. „Als Entwurf übernommen“ bedeutet, dass daraus ein redaktioneller Entwurf entstanden ist. Öffentlich wird der Spot erst nach Veröffentlichung.",
      },
      report: {
        q: "Wie melde ich falsche Angaben?",
        p1: "Nutze die Korrekturfunktion am Spot, wo sie angeboten wird, oder schreib dem Betreiber über den <contact>Kontakt</contact>. Nenne den Link zum Spot, die betroffene Angabe, was stattdessen stimmt, eine möglichst aktuelle Quelle und – falls bekannt – das Datum. Bei geänderten Regeln oder Sperrungen hilft ein Link zur offiziellen Bekanntmachung.",
      },
      images: {
        q: "Woher kommen die Bilder?",
        p1: "Die Titel- und Galeriebilder stammen aus drei Quellen: Aufnahmen des Betreibers, freie Bildarchive wie Unsplash, Pexels, Wikimedia Commons und Openverse sowie Uploads aus der Community. Jedes Bild trägt eine Urhebernennung – Fotograf, Quelle und, wo nötig, Lizenz – am Bild oder in der großen Ansicht. Bilder aus Wikimedia Commons sind zusätzlich mit „Commons“ markiert. Wer ein Bild hochlädt, bestätigt, dass er die Rechte daran hat.",
        p2: "Ein Bild zeigt einen Spot zu einem bestimmten Zeitpunkt, nicht die heutigen Bedingungen.",
        p3: "Ist ein Bild falsch zugeordnet oder verletzt es deine Rechte? Nutze „Melden“ am Bild. Bei dringenden Rechtefragen schreib dem Betreiber mit Link zum Bild.",
      },
      contributions: {
        q: "Was passiert mit meinen Beiträgen?",
        ratings: "Bewertungen und Tipps erscheinen sofort auf der Spotseite und werden danach moderiert. Auffällige Beiträge werden automatisch zur Prüfung markiert.",
        gallery: "Galeriebilder erscheinen in der Regel sofort. Als Titelbild vorgeschlagene Bilder erscheinen erst nach einer Prüfung.",
        suggestions: "Spot-Vorschläge werden immer vor der Veröffentlichung geprüft.",
        p1: "Der Betreiber kann Beiträge bearbeiten, ausblenden oder entfernen, etwa bei falschen, beleidigenden oder rechtswidrigen Inhalten. Die Regeln stehen in den <terms>Nutzungsbedingungen</terms>.",
        p2: "Namensnennung: Bist du angemeldet, steht dein Anzeigename am Beitrag. Ohne Anmeldung steht dort „Anonym“; Bilder werden dann ohne Namen veröffentlicht. Deine E-Mail-Adresse wird nie angezeigt.",
        p3: "Löschung: Deine eigenen Kommentare löschst du über das Menü am Beitrag. Hat ein Kommentar bereits Antworten, entfernt ihn der Betreiber auf Anfrage – sonst würden fremde Beiträge mit verschwinden. Für Bewertungen, Bilder und andere Beiträge beantragst du die Löschung ebenfalls beim Betreiber, mit Link zum Beitrag. Was beim Löschen deines Kontos mit Beiträgen passiert, steht unter <account>Export & Löschung</account>.",
      },
    },
    contact: {
      intro: "Fragen, Fehler oder Hinweise? Schreib dem Betreiber per E-Mail.",
      emailLabel: "E-Mail",
      write: "E-Mail schreiben",
      copy: "Adresse kopieren",
      copied: "E-Mail-Adresse kopiert.",
      copyFailed: "Kopieren nicht möglich. Markiere die Adresse oben und kopiere sie manuell.",
      unconfigured: "Die Kontaktadresse ist in dieser Ansicht noch nicht konfiguriert. In der Produktionsumgebung steht hier die betreute E-Mail-Adresse des Betreibers.",
      topicsTitle: "Worum geht es?",
      topicsHint: "Je genauer deine Angaben, desto schneller lässt sich helfen.",
      topics: {
        spotErrorTerm: "Fehler an einem Spot",
        spotErrorBody: "Was hilfreich ist, steht unter <contribute>Falsche Angaben melden</contribute>.",
        accountTerm: "Hilfe zum Konto",
        accountBody: "Beschreibe den Schritt und das Problem. Deine Konto-E-Mail nur soweit nötig. Sende niemals dein Passwort, einen Code oder einen Wiederherstellungslink.",
        technicalTerm: "Technischer Fehler",
        technicalBody: "Nenne Seite, Gerät, Browser sowie erwartetes und tatsächliches Verhalten. Entferne personenbezogene Daten aus Screenshots.",
        newSpotTerm: "Neuen Spot vorschlagen",
        newSpotBody: "Neue Spots reichst du direkt über dein Konto ein, siehe <spotSuggest>Spot vorschlagen</spotSuggest>.",
        unlawfulTerm: "Rechtswidrige Inhalte melden",
        unlawfulBody: "Für Bilder nutzt du die Meldefunktion direkt am Beitrag. Für alle übrigen rechtswidrigen oder rechtsverletzenden Inhalte schreib dem Betreiber mit Link zum Beitrag, einer Beschreibung und – soweit möglich – der rechtlichen Einordnung. Das Vorgehen ist in den <terms>Nutzungsbedingungen</terms> beschrieben.",
        privacyTerm: "Datenschutz",
        privacyBody: "Verwende die Kontaktadresse oben. Hintergründe findest du in der <privacy>Datenschutzerklärung</privacy> und in den <settings>Kontoeinstellungen</settings>.",
        securityTerm: "Sicherheitslücke",
        securityBody: "Melde Sicherheitslücken vertraulich über den privaten Security-Advisory-Weg des Repositorys (GitHub: Tab „Security“ → „Report a vulnerability“). Sende keine Zugangsdaten oder Secrets im Klartext.",
      },
      responseTime: "Eine feste Antwortzeit gibt es nicht. Wir kümmern uns so bald wie möglich um dein Anliegen.",
      notEmergency: "Diese Kontaktadresse ist kein Notfall- oder Rettungsdienst.",
    },
    outro: {
      claim: "Spots entdecken. Bedingungen verstehen. Zeit auf dem Wasser planen.",
      discover: "Spots entdecken",
      suggest: "Spot vorschlagen",
    },
  },
  // The accessibility statement lives with the terms: for a service the
  // accessibility information belongs in the terms or an equivalent
  // document. The rest of /nutzungsbedingungen is German-only prose in the
  // component; these keys keep this one statement bilingual.
  terms: {
    accessibility: {
        q: "Barrierefreiheit",
        p1: "Surfwinddata soll für alle nutzbar sein, auch mit Tastatur, Screenreader oder starker Vergrößerung. Hinweise stehen als Text, nicht nur als Farbe. Die Barrierefreiheit wurde bereits geprüft; die Umsetzung der Ergebnisse wird derzeit noch getestet.",
        p2: "Bekannte Grenze: Die Wind- und Wellenfläche auf der Karte ist eine rein visuelle Darstellung. Dieselben Vorhersagewerte findest du als Text auf der Datenseite des Spots.",
        p3: "Stößt du auf ein Hindernis, schreib dem Betreiber über den <contact>Kontakt</contact>: welche Seite, was du tun wolltest und welches Hilfsmittel du nutzt, zum Beispiel Screenreader und Browser.",
    },
  },

  trips: {
    title: "Reiseplaner", intro: "Plane Termine, Spots und Vorbereitung manuell — ohne automatische Wetterversprechen.",
    new: "Neue Reise", emptyTitle: "Noch keine Reise geplant", emptyBody: "Lege eine Reise an und sammle die Spots, die du besuchen möchtest.",
    loadFailed: "Reisen konnten nicht geladen werden.", saveFailed: "Reise konnte nicht gespeichert werden.", deleteFailed: "Reise konnte nicht gelöscht werden.", copyFailed: "Reise konnte nicht kopiert werden.", shareFailed: "Freigabe konnte nicht geändert werden.",
    name: "Name der Reise", start: "Startdatum", end: "Enddatum", notes: "Notizen", notesPlaceholder: "Anreise, Unterkunft, lokale Kontakte …",
    spots: "Geplante Spots", spotSearch: "Spot suchen", search: "Suchen", noSearch: "Keine passenden öffentlichen Spots gefunden.", add: "Hinzufügen", remove: "Entfernen",
    moveUp: "Nach oben", moveDown: "Nach unten", plannedDate: "Geplanter Tag", stopNotes: "Notiz zu diesem Stopp",
    days: "Reisetage", daysHint: "Notizen bleiben privat. Ein Freigabelink zeigt sie nur, wenn du das später ausdrücklich erlaubst.",
    day: { notes: "Tagesnotiz", accommodation: "Unterkunft", travel: "Anreise" },
    role: "Rolle", mainSpot: "Hauptspot", alternativeSpot: "Alternative", noDaySpots: "Für diesen Tag ist noch kein Spot eingetragen.", openSpot: "Spot öffnen", planSpot: "Zum Reiseplan hinzufügen",
    checklist: "Checkliste", checklistPlaceholder: "z. B. Neoprenanzug einpacken", addChecklist: "Punkt hinzufügen",
    status: "Status", draft: "Entwurf", planned: "Geplant", completed: "Abgeschlossen", cancelled: "Abgesagt",
    save: "Reise speichern", saving: "Speichert …", cancel: "Abbrechen", edit: "Bearbeiten", copy: "Kopieren", share: "Link kopieren", revokeShare: "Freigabe beenden", sharedCopied: "Der Nur-Lesen-Link ist aktiv und wurde kopiert.", delete: "Löschen", confirmDelete: "Wirklich löschen?",
    contentChanged: "Mindestens ein gespeicherter Spot wurde seit der Planung geändert oder ist nicht mehr öffentlich. Bitte prüfe ihn erneut.",
    sharedLabel: "Geteilter Reiseplan", sharedNotFound: "Reiseplan nicht verfügbar", sharedNotFoundBody: "Der Link ist ungültig oder wurde widerrufen.", sharedManualNote: "Dieser Plan wurde manuell zusammengestellt. Bedingungen, lokale Regeln und Vorhersagen müssen für jeden Reisetag aktuell geprüft werden.",
    dateError: "Das Enddatum darf nicht vor dem Startdatum liegen.", manualNote: "Vorhersagen und lokale Hinweise prüfst du weiterhin aktuell vor jedem Reisetag.",
  },
  visits: {
    title: "Spots besucht", add: "Als besucht markieren", added: "Als besucht markiert", remove: "Besuchsmarkierung entfernen",
    emptyTitle: "Noch keine besuchten Spots", emptyBody: "Markiere auf einer Spotseite, wo du tatsächlich auf dem Wasser warst.", discover: "Spots entdecken",
    loadFailed: "Besuchte Spots konnten nicht geladen werden.", actionFailed: "Besuch konnte nicht gespeichert werden.", visitedOn: "Besucht am {{date}}", feedback: "Rückmeldung", outcome: "Hat sich der Besuch gelohnt?", noOutcome: "Keine Bewertung", worthwhile: "Hat sich gelohnt", neutral: "Neutral", notWorthwhile: "Hat sich nicht gelohnt", notes: "Was stimmte vor Ort – und was nicht?", save: "Rückmeldung speichern",
  },
  favorites: {
    title: "Gespeichert", emptyTitle: "Noch nichts gespeichert", emptyBody: "Tippe an einem Spot auf das Lesezeichen, um ihn hier zu sammeln.", discover: "Spots entdecken",
    count_one: "{{count}} Spot gespeichert", count_other: "{{count}} Spots gespeichert", removeFailed: "Spot konnte nicht entfernt werden. Bitte versuche es erneut.", remove: "{{name}} aus Gespeichert entfernen", plan: "Planen",
    compare: "Spots vergleichen", compareHint: "Es werden nur vorhandene, strukturierte Angaben verglichen. Fehlende Werte bleiben unbekannt.", property: "Eigenschaft", sports: "Sportarten", level: "Niveau", water: "Wassercharakter", region: "Region", unknown: "Unbekannt",
  },
  account: {
    loading: "Konto wird geladen …",
    unavailableTitle: "Konto derzeit nicht erreichbar",
  },
  accountNav: {
    profile: "Profil",
    setup: "Mein Setup",
    saved: "Saved",
    visited: "Spots besucht",
    trips: "Reiseplaner",
    addSpots: "Spots hinzufügen",
    settings: "Einstellungen",
  },
  menu: {
    trigger: "Kontomenü",
    account: "Konto",
    close: "Menü schließen",
    areas: "Konto-Bereiche",
    myProfile: "Mein Profil",
    welcome: "Willkommen",
    welcomeBody: "Melde dich an, um Favoriten und eigene Spots zu verwalten.",
    signIn: "Anmelden",
    createAccount: "Konto erstellen",
    planned: "Geplant",
    signOut: "Abmelden",
    // The mobile sheet sets its rows in lower case; keeping it a separate key
    // means a future locale can diverge without one of the two going wrong.
    signOutSheet: "abmelden",
  },
  settings: {
    pageTitle: "Einstellungen",
    planned: "Geplant",
    units: {
      title: "Einheiten & Anzeige",
      description:
        "Deine Auswahl gilt überall auf der Seite, wo Wind, Wellenhöhe, Temperatur und Entfernungen angezeigt werden.",
      wind: "Wind",
      wave: "Wellenhöhe",
      temp: "Temperatur",
      distance: "Entfernung",
      preview: "Vorschau: Wind {{wind}} · Welle {{wave}} · Wasser {{water}} · Station {{station}}",
      saving: "Einheiten werden gespeichert …",
    },
    account: {
      title: "Konto",
      description: "Deine persönlichen Angaben und dein Passwort.",
    },
    profile: {
      name: "Anzeigename",
      submit: "Speichern",
      submitting: "Speichere …",
      saved: "Profil gespeichert.",
      failed: "Speichern fehlgeschlagen.",
    },
    email: {
      heading: "E-Mail-Adresse ändern",
      current: "Aktuell: {{email}}",
      pending: " · Bestätigung ausstehend für {{email}}",
      newLabel: "Neue E-Mail-Adresse",
      currentPassword: "Aktuelles Passwort",
      submit: "Bestätigungslink senden",
      submitting: "Sende …",
      sent: "Bestätigungslink an die neue E-Mail-Adresse gesendet. Bis zur Bestätigung bleibt deine bisherige Adresse gültig.",
      failed: "Adresswechsel fehlgeschlagen.",
    },
    password: {
      heading: "Passwort ändern",
      current: "Aktuelles Passwort",
      new: "Neues Passwort",
      hint: "Mindestens 8 Zeichen.",
      submit: "Passwort ändern",
      submitting: "Ändere …",
      changed: "Passwort geändert.",
      failed: "Ändern fehlgeschlagen.",
    },
    privacy: {
      title: "Privatsphäre & Inhalte",
      description: "Steuere die Sichtbarkeit deines Profils und deiner Beiträge sowie deine Kontodaten.",
      plannedNote:
        "Ein öffentliches Profil und die Sichtbarkeit einzelner Beiträge kannst du noch nicht selbst steuern. Veröffentlichte Beiträge werden serverseitig gespeichert und moderiert; dein Konto selbst bleibt privat — nur du siehst deine Favoriten und Vorschläge.",
      dataHeading: "Deine Daten",
      dataBody: "Lade eine Kopie deiner Kontodaten herunter oder lösche dein Konto endgültig.",
      exportSubmit: "Datenexport herunterladen",
      exporting: "Export wird erstellt …",
      exportFailed: "Datenexport fehlgeschlagen. Bitte versuche es erneut.",
      deleteSubmit: "Konto löschen",
      deleteTitle: "Konto endgültig löschen",
      deleteBody: "Favoriten werden gelöscht. Veröffentlichte Beiträge bleiben anonymisiert erhalten.",
      deletePassword: "Passwort zur Bestätigung",
      deleteConfirm: "Endgültig löschen",
      deleting: "Lösche …",
      deleteFailed: "Konto konnte nicht gelöscht werden.",
      discardTitle: "Löschung abbrechen?",
      discardMessage: "Das eingegebene Passwort wird verworfen.",
      discardConfirm: "Verwerfen",
    },
    notifications: {
      title: "Benachrichtigungen",
      description: "Wähle, welche Nachrichten du zu deinen Vorschlägen erhalten möchtest.",
      plannedNote:
        "E-Mail-Benachrichtigungen sind derzeit nicht verfügbar. Sobald der Versand eingerichtet ist, kannst du hier über Entscheidungen zu deinen Vorschlägen informiert werden.",
      submissionEmails: "E-Mail bei Entscheidung über meinen Spot-Vorschlag",
      saveFailed: "Einstellung konnte nicht gespeichert werden.",
      alertsNote: "Wetteralarme für Favoriten folgen, sobald zuverlässige Schwellen und Versandzeiten feststehen.",
    },
  },
  setup: {
    pageTitle: "Mein Setup",
    intro:
      "Verwalte dein Kite-Setup und deine Fahrvorlieben. Die detaillierte Setup-Funktion ist derzeit auf Kitesurfen ausgerichtet.",
    loading: "Setup wird geladen …",
    loadFailed: "Dein Setup konnte nicht geladen werden.",
    saveFailed: "Speichern fehlgeschlagen. Bitte versuche es erneut.",
    submit: "Setup speichern",
    submitting: "Speichert …",
    incomplete: "Noch offen: Gewicht, Level oder Kite.",
    required: "Pflichtfeld",
    optional: "Optional",
    choose: "Bitte wählen",
    unitKg: "kg",
    unitKm: "km",
    basics: {
      title: "Grundangaben",
      intro: "Gewicht, Level und ein Kite reichen für den Start.",
      weight: "Gewicht",
      level: "Kite-Level",
    },
    gear: {
      title: "Deine Ausrüstung",
      intro: "Trage deine aktiven Kites und den Board-Typ ein.",
    },
    style: {
      title: "Fahrstil",
      weighting: "{{style}} Gewichtung",
      intro:
        "Stelle für jeden Stil ein, wie wichtig er dir ist: 0 steht für unwichtig, 3 für besonders wichtig.",
    },
    water: {
      title: "Wasser",
      intro: "Optional: Wähle die Bedingungen, die du besonders gern fährst.",
    },
    travel: {
      title: "Unterwegs",
      intro: "Heimatort und Reisemodus sind optional und jederzeit änderbar.",
      lat: "Breitengrad",
      lon: "Längengrad",
      home: "Heimatort",
      mode: "Reisemodus",
      maxDistance: "Maximale Entfernung",
      dayTrip: "Tagesausflug",
      weekend: "Wochenende",
      trip: "Reise",
      camper: "Camper",
    },
    // Rider levels and the style/water lists. Several of these are sport terms
    // that read the same in English ("Freeride", "Big Air", "Chop"); they still
    // live here, because whether a term travels is a translator's call, not
    // ours, and one rule ("visible text lives in the catalogue") beats an
    // exception list nobody will remember.
    levels: {
      beginner: "Einsteiger",
      advanced: "Fortgeschritten",
      expert: "Experte",
      competition: "Competition",
    },
    styles: {
      freeride: "Freeride",
      freestyle: "Freestyle",
      bigAir: "Big Air",
      waveRiding: "Wave Riding",
      wavekite: "Wavekite",
    },
    waterKinds: {
      flach: "Flachwasser",
      chop: "Chop",
      welleKlein: "Kleine Welle",
      welleGross: "Große Welle",
      tiefesWasser: "Tiefes Wasser",
    },
  },
  community: {
    commons: {
      badge: "Commons",
      full: "Aus Wikimedia Commons",
    },
    // The licence confirmation wraps a button in running text, so it stays three
    // keys rather than one: a sentence with embedded markup would need <Trans>,
    // and the trailing full stop is punctuation the lint guard already allows.
    license: {
      confirm: "Ich bestätige die",
      linkLabel: "Rechte- & Einwilligungserklärung",
      version: " ({{version}})",
    },
    gallery: {
      enlarge: "Bild vergrößern",
      enlargeCredited: "Bild vergrößern — {{credit}}",
      viewAll: "Alle {{count}} Bilder ansehen",
      addPhotos: "Bilder hinzufügen",
      suggestHero: "Titelbild vorschlagen",
      emptyTitle: "Aktuell noch kein Bild vorhanden",
      uploadAria: "Bilder hochladen",
    },
    composer: {
      prompt: "Wie war's am {{spot}}?",
      starsAria: "{{count}} Sterne",
      textPlaceholder: "Wie waren die Bedingungen? Was sollten andere wissen? (Pflichtfeld)",
      sport: "Sportart",
      level: "Level",
      visitDate: "Besuchsdatum",
      namePlaceholder: "Vorname oder Vor- und Nachname (Pflichtfeld)",
      submit: "Veröffentlichen",
      errStars: "Bitte eine Sternebewertung wählen.",
      errText: "Bitte kurz schreiben, wie es war.",
      errName: "Bitte Vorname (oder Vor- und Nachname) angeben.",
      errLicense: "Bitte die Rechteerklärung fürs Foto bestätigen.",
      sendFailed: "Senden fehlgeschlagen.",
    },
    feed: {
      emptyTitle: "Sei der Erste, der von hier berichtet.",
      emptyBody: "Hilfreiche Beiträge nennen Bedingungen, Level und was andere vor Ort wissen sollten.",
      sortNewest: "Neueste",
      sortHelpful: "Hilfreichste",
    },
    post: {
      helpful: "Hilfreich",
      helpfulCounted: "Hilfreich · {{count}}",
      moreActions: "Weitere Aktionen",
      report: "Melden",
      // Only offered on the viewer's own comments (see SpotCommunity).
      delete: "Kommentar löschen",
      deleteConfirm: "Diesen Kommentar endgültig löschen?",
      deleteFailed: "Löschen fehlgeschlagen. Bitte versuche es erneut.",
    },
    lightbox: {
      label: "Bildergalerie, groß",
      prev: "Vorheriges Bild",
      next: "Nächstes Bild",
    },
    report: {
      title: "Bild melden",
      thanks: "Danke, deine Meldung ist eingegangen.",
      contact: "Bei dringenden Rechtefragen: {{contact}}",
      notePlaceholder: "Anmerkung (optional)",
      submit: "Melden",
      failed: "Meldung fehlgeschlagen.",
      reasons: {
        copyright: "Urheberrecht / mein Bild",
        inappropriate: "Unangemessen",
        wrongSpot: "Falscher Spot",
        other: "Sonstiges",
      },
    },
    upload: {
      title: "Bild hinzufügen",
      note: "Wird sofort hochgeladen, ist aber erst nach kurzer Prüfung für alle sichtbar.",
      removeImage: "Bild entfernen",
      pick: "Bild auswählen",
      formats: "JPG, PNG oder WebP",
      creditPlaceholder: "Credit: Name oder Instagram (optional)",
      submit: "Hochladen",
      submitting: "Hochladen…",
      queued: "Danke! Dein Bild wartet auf Freigabe.",
      failed: "Upload fehlgeschlagen.",
    },
    hero: {
      title: "Titelbild vorschlagen",
      requirements: "Mind. {{width}}×{{height}} px, Querformat, JPG/PNG/WebP.",
      submit: "Vorschlagen",
      queued: "Danke! Dein Titelbild-Vorschlag wartet auf Freigabe.",
      invalid: "Bild erfüllt die Hero-Vorgaben nicht.",
    },
  },
} as const;
