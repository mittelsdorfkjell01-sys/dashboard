"""Initial editorial safety notices supplied for the spot catalogue.

This is seed and migration input only. Once stored, editors own the text in the
admin spot form; runtime reads never fall back to this module.
"""

from __future__ import annotations


INITIAL_SAFETY_NOTICES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("Rodiles",), "Bei guten Bedingungen drängen sich viele Surfer auf engem Raum; an der Flussmündung können starke Strömungen auftreten."),
    (("Mundaka",), "Die Welle bricht steil über einer flachen Sandbank, dazu kommen Rips und ein dichtes, konkurrenzbetontes Line-up."),
    (("Zarautz",), "Der lange Beachbreak ist besonders an guten Tagen voll; Surfkurse und lose Boards erhöhen das Kollisionsrisiko."),
    (("Thurso East",), "Das flache Felsriff, kaltes Wasser und ein kleines, bei guten Bedingungen dicht besetztes Take-off machen den Spot anspruchsvoll."),
    (("Carcavelos",), "Die beliebten Peaks werden besonders an sonnigen Tagen voll; bei größerem Swell kann man auf der harten Sandbank aufschlagen."),
    (("Praia do Guincho",), "Der offene Strand ist für gefährliche Rips bekannt, die bei größerem Swell stärker werden; der Wind kann zudem schnell auffrischen."),
    (("Fistral Beach (Newquay)",), "Rips, Felsen am südlichen Strandende und viele Surfer sowie Badegäste sorgen besonders im Sommer für Kollisions- und Abdriftrisiken."),
    (("Lahinch",), "Es gibt dauerhafte und tideabhängige Rips sowie weitere Strömungen am Flussauslauf; bei hoher Tide kann Wasser Surfer auf die Felsen drücken."),
    (("Neretva Delta",), "An der Flussmündung gibt es Strömung und nahen Schiffsverkehr; das Wasser ist stellenweise so flach, dass Finnen aufsetzen können."),
    (("The Peak (Bundoran)",), "Scharfe Riffkanten, Rinnen und Felsen im Inneren sowie längere Hold-downs treffen auf ein sehr volles Line-up."),
    (("Coxos",), "Der kräftige, hohle Reefbreak bricht über Fels und ist wegen flacher Stellen, lokaler Konkurrenz und dichtem Line-up vor allem für erfahrene Surfer anspruchsvoll."),
    (("Foz do Lizandro",), "Der Beachbreak liegt an einer Flussmündung; bei mehr Swell können Strömungen und wechselnde Sandbänke problematisch werden."),
    (("Ribeira d’Ilhas", "Ribeira d'Ilhas"), "Der beliebte Reefbreak zieht viele Surfer an; Felsboden und starke Wellen bei größerem Swell verlangen sichere Brettkontrolle."),
    (("São Lourenço",), "Bei großem Swell wird der Reefbreak schwer und kraftvoll; die offene Lage und der Felsboden lassen wenig Raum für Fehler."),
    (("Fehmarn Wulfener Hals",), "Das Wasser ist großteils sehr flach und der Spot beliebt; bei viel Betrieb teilen sich Anfänger, Kiter und Windsurfer den Raum."),
    (("Gold – Fehmarn", "Gold - Fehmarn", "Gold (Fehmarn)"), "In der Bucht ist das Wasser sehr flach, außerhalb wird es schnell tiefer; bei stärkerem Wind ändern sich die Bedingungen deutlich."),
    (("El Cotillo",), "Bei größerem Swell können starke Rips und kräftige, teils hohle Wellen auftreten; südlich liegen einzelne Vulkanfelsen im Wasser."),
    (("Flag Beach",), "Bei Niedrigwasser können Felsen im Einstiegsbereich freiliegen; weiter draußen liegt ein Riff, und mehrere Wassersportgruppen teilen sich den Spot."),
    (("Majanicho",), "Die Welle läuft über scharfes Lavareef; bei größerem Swell kommen Strömungen hinzu."),
    (("Matas Bay",), "Die Bucht ist flach und meist ruhig; zu beachten sind die wechselnde Wassertiefe und teils kräftiger Wind."),
    (("Pozo Izquierdo",), "Lavafelsen am Einstieg und starke, böige Winde machen den Spot anspruchsvoll; bei Hochwasser bricht die Welle nah am steinigen Ufer."),
    (("Somo",), "Wenn der Swell zunimmt, wird der Beachbreak kräftig und es bilden sich starke Rips; nach Regen kann der Flussauslauf die Wasserqualität beeinträchtigen."),
    (("Laboe",), "Vor dem Strand gibt es eine tiefe Rinne und Muschelbänke; draußen beginnt die stark befahrene Förde, während Südostwind ablandig sein kann."),
    (("Psalidi",), "Der Meltemi kann böig und schräg ablandig stehen; steiniger Einstieg, schnell abfallender Strand und Schiffsverkehr erfordern Aufmerksamkeit."),
    (("La Gravière (Hossegor)",), "Der Beachbreak bricht hohl und kraftvoll über flachen Sandbänken; starke Rips, heftiger Shorebreak und viele Surfer machen ihn anspruchsvoll."),
    (("Leucate",), "Die Tramontane kann sehr stark und ablandig wehen; in der Lagune kommen flache Stellen, Boote und Austernzucht-Markierungen als Hindernisse hinzu."),
    (("Keros",), "Die Bucht ist meist sandig und flach, doch an den Enden liegen Felsen; im Sommer teilen sich Kiter, Schulen, Boote und Schwimmer begrenzte Zonen."),
    (("Mikri Vigla",), "Der Meltemi kann durch die Bucht deutlich zulegen; der Startbereich wird im Hochsommer voll und am felsigen Kap zwischen den Buchten besteht Kollisionsgefahr."),
    (("Praia do Norte (Nazaré)", "Nazaré"), "Die verstärkten Riesenwellen und die raue Küste machen den Spot selbst für erfahrene Big-Wave-Surfer extrem anspruchsvoll."),
    (("Wijk aan Zee / Noordpier", "Wijk aan Zee", "Noordpier"), "Bei zunehmender Wellenhöhe treten Rips auf; der beliebte Spot kann zudem voll werden."),
    (("Pounda",), "Der Meltemi wird im Kanal oft sehr stark; dazu kommen mögliche Strömungen, Fährverkehr und volle Startzonen im Sommer."),
    (("Baleal",), "Die Lern-Peaks sind oft dicht mit Surfschulen belegt; an den Seiten der Bucht liegen Felsen, und bei Hochwasser kann der Shorebreak kräftig werden."),
    (("Supertubos",), "Der kraftvolle, flache Shorebreak, wechselnde Rips und volle Line-ups bei guten Bedingungen machen den Spot vor allem für erfahrene Surfer geeignet."),
    (("Prasonisi",), "An der Spitze zwischen den beiden Seiten entstehen Querströmungen; die Sandbank kann bei hohem Wasserstand und Swell überspült werden."),
    (("Capo Mannu",), "Der exponierte Reefbreak bricht über Felsen und kann bei guten Bedingungen voll werden."),
    (("Poetto",), "Der lange Stadtstrand ist besonders im Sommer und an Wochenenden stark besucht; bei kräftigem Swell werden die Wellen deutlich anspruchsvoller."),
    (("Porto Pollo",), "Starker Wind ist typisch und kann schnell auffrischen; durch die geteilte Bucht sind viele Windsurfer und Kiter gleichzeitig auf dem Wasser."),
    (("Punta Trettu",), "Boote queren den Hafenkanal; außerdem gibt es Fischernetze und Pfähle im Wasser, und Teile der Uferzone sind für Kites gesperrt."),
    (("Praia Grande",), "Bei Hochwasser kann ein heftiger Shorebreak entstehen; dazu kommen wechselnde Rips und viele Surfer an guten Wochenenden."),
    (("Lo Stagnone",), "Die Lagune ist stellenweise extrem flach, sodass Finnen oder Boards aufsetzen können; Fähren, Bojen und volle Schulbereiche erhöhen das Kollisionsrisiko."),
    (("Kegnaes", "Kegnæs"), "Direkt am Einstieg liegen Steine, Untiefen, Stege und Steinmolen; bei Sturm können die Wellen kräftig und kopfhoch werden."),
    (("Rømø Bilstrand", "Rømø", "Romo Bilstrand"), "Strömung und Gezeiten sind zu beachten, besonders bei ablaufendem Wasser; bei Materialproblemen kann die offene See zum Risiko werden."),
    (("Balneario",), "Bei Levante kann der Wind böig und ablandig stehen; Felsen und harte Strukturen an den Strandrändern schaffen zusätzliche Gefahren."),
    (("Valdevaqueros – Tarifa", "Valdevaqueros - Tarifa", "Valdevaqueros"), "Bei Levante besteht je nach Abschnitt Abdriftgefahr; im Sommer kommen volle Wasserflächen und einzelne Felsen am südlichen Ende hinzu."),
    (("El Médano",), "Am Cabezo liegen scharfes Lavareef und vorgelagerte Felsen; dort können kräftige Wellen und Strömungen auftreten, während die kleine Startzone an guten Tagen voll ist."),
    (("Brouwersdam",), "Die geschützte Startzone hat meist nur leichte Strömung; weiter draußen können die Strömungen deutlich stärker werden."),
)


def initial_safety_notice(name: str) -> str | None:
    for names, notice in INITIAL_SAFETY_NOTICES:
        if name in names:
            return notice
    return None
