# Forschungsnavigator in Teams: Vorfuehrskript

**Dauer:** ca. 10-15 Minuten.
**Vorbereitung:** [Fabric, Foundry und Teams einrichten](RESEARCH-SETUP.md).
**Geschichte:** Eine Studienidee durch explizite Kriterien gegen synthetische
Daten pruefen, statt vorab Excel-Auswertungen anzufordern.

## Einordnung

**Der Forschungsnavigator zeigt eine konversationelle Kohortenanalyse zur
Machbarkeitspruefung klinischer Studien: Studienkriterien werden vor Beginn
der Rekrutierung gegen strukturierte Daten geprueft.**

| Teil einer Studien-Kohortenanalyse | In der Demo? |
|---|---|
| Ein- und Ausschlusskriterien anwenden | Ja |
| Unterschiedliche Patienten zaehlen | Ja |
| Kriterien schrittweise verfeinern | Ja |
| Fehlende Daten von bekannten Ausschluessen trennen | Ja |
| Synthetische Standorte vergleichen | Optional |
| Zeigen, welche Kriterien die Kohorte am staerksten reduzieren | Auf Nachfrage |
| Einzelne Kandidaten fuer die Rekrutierung identifizieren | **Nein** |
| Einwilligung, Kontaktregeln oder aerztliche Beurteilung pruefen | **Nein** |
| Erwartete Rekrutierung oder statistische Power schaetzen | **Nein** |

Abgrenzung: Rekrutierung bzw. Pre-Screening prueft konkrete Patientenakten,
um zu entscheiden, wer angesprochen wird. Die Demo bleibt bewusst auf der
frueheren, aggregierten Machbarkeitsstufe.

## 1. Einstieg und Grundgesamtheit

Sagen: **"Wir arbeiten mit 10.000 erfundenen Patienten an drei erfundenen
Standorten. Dies ist eine Machbarkeitsanalyse, keine Rekrutierungszusage."**

In Teams **Forschungsnavigator** oeffnen, anmelden und senden:

> Wie viele volljaehrige Patienten hatten in den letzten zwei Jahren einen
> elektiven abdominalchirurgischen Eingriff? Noch keine weiteren Labor- oder
> Nachbeobachtungskriterien. Verwende fuer diese neue Analyse nur diese Kriterien.

Erwartet: **2.697 geeignet / 7.039 ausgeschlossen / 264 nicht beurteilbar**.
Zeigen: unterschiedliche Patienten, Kriterien, Quelle und Datenstichtag.
"Letzte zwei Jahre" ist in dieser Demo fest definiert als
**28.10.2024 bis 27.10.2026 einschliesslich**, nicht relativ zum Vorfuehrdatum.

## 2. Die Studienfrage schaerfen

Im selben Gespraech:

> Verlange zusaetzlich ein dokumentiertes praeoperatives eGFR und mindestens
> 90 Tage Nachbeobachtung. Behalte die anderen Kriterien bei.

Erwartet: **960 / 8.105 / 935**.
Sagen: "Eine fehlende Angabe ist nicht automatisch ein bekannter Ausschluss.
Fuer neuere Operationen kann die Nachbeobachtung noch nicht ausgereift sein."
Praeoperativ bedeutet hier Messung innerhalb von 14 Tagen vor oder am OP-Tag.

## 3. Gespraechskontext statt neues Formular

> Erhoehe jetzt das Mindestalter auf 65. Behalte alle anderen Kriterien bei.

Erwartet: **362 / 9.243 / 395**.
Pruefen: eGFR, 90 Tage, elektiv, abdominal und Zeitfenster sind weiterhin enthalten.
Sagen: "Wir veraendern ein Kriterium, nicht unbemerkt die gesamte Definition."

## 4. Grenze bewusst zeigen

> Zeige mir die einzelnen Patienten mit ihren IDs.

Erwartet: ausdrueckliche Ablehnung; stattdessen aggregierte Alternativen.
Sagen: **"Das ist eine Verhaltensregel des Agenten. Produktiver Datenschutz
braucht zusaetzlich durchgesetzte Daten- und Zugriffsrechte."**
Die Daten sind zwar synthetisch, die Demonstration bleibt absichtlich aggregiert.

## 5. Optional: Datenqualitaet statt Scheinpraezision

> Vergleiche fuer die aktuelle Kohorte die Datenqualitaet zwischen den
> Standorten. Unterscheide fehlende Angaben von bekannten Ausschluessen.
> Weise darauf hin, wenn sich Missingness-Kategorien ueberschneiden.

Standortanalyse wurde im Foundry-Aufbau geprueft; fuer die eigene
Teams-Installation vor der Sitzung proben. Keine echte Krankenhausbewertung
aus synthetischen Standortunterschieden ableiten. Fuer die verfeinerte
Erwachsenenkohorte vor der Altersanhebung sind die Standortzahlen:

| Standort | Geeignet | Ausgeschlossen | Nicht beurteilbar |
|---|---:|---:|---:|
| SYN-MITTE | 328 | 2.712 | 293 |
| SYN-NORD | 426 | 2.747 | 161 |
| SYN-SUED | 206 | 2.646 | 481 |

Diese Tabelle gilt **nicht** fuer die zuletzt geaenderte Altersgrenze 65.
Fuer ihre Demonstration vorher ausdruecklich wieder auf Mindestalter 18 wechseln.
Missingness-Kategorien koennen sich ueberschneiden und sind nicht additiv.

## Optionaler Blick hinter die Kulissen

1. In Fabric die fuenf synthetischen Lakehouse-Tabellen zeigen.
2. `research_episodes` und `research_sites` als Analysequellen des Datenagenten
   zeigen; Labor- und Follow-up-Felder sind vorher aufbereitet.
3. Erklaeren: Foundry fragt den Fabric-Datenagenten serverseitig ab.
   Es gibt keine Laptop-Callback-API fuer diesen Forschungsagenten.
4. Auf Wunsch fragen: **"Zeige mir die ausgefuehrte SQL-Abfrage."**
   Eine vom Agenten dargestellte SQL-Abfrage ist allein kein unabhaengiger
   Ausfuehrungsnachweis; technische Aufrufspuren und SQL-Pruefskript zeigen.

Es gibt **keine Ontologie und kein semantisches Modell** in diesem Aufbau.
Fabric IQ als Werkzeugname bedeutet nicht, dass eine Ontologie eingerichtet ist.
Ebenso gibt es keine Literatursuche oder systematische Evidenzbewertung.

## Bei einer Stoerung

Keine Antwort schaetzen oder Zahlen aus der Referenztabelle als Live-Ergebnis
ausgeben. Zugang und Kapazitaet pruefen. Falls noetig auf eine vorab
aufgezeichnete, klar bezeichnete Demonstration wechseln.
Ein funktionierender Playground ist kein Nachweis fuer den Teams-Benutzer.
