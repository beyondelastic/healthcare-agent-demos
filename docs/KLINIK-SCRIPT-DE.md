# Klinik Cockpit: einfaches Vorfuehrskript

**Dauer:** Kapitel A ca. 15-20 Minuten; Kapitel B optional weitere 10-15 Minuten.
**Vorbereitung:** [technisches Setup](KLINIK-SETUP.md).
**Ausgangslage:** Nora Testfall (DEMO-031), keine bisherigen Briefe,
Medikationsplan noch nicht freigegeben, Mikrobiologie noch ausstehend.
Bei abweichendem Zustand vor der Sitzung bewusst zuruecksetzen; niemals
ungefragt vorhandene Ergebnisse loeschen.

## Kapitel A: Vom Quellenproblem zum geprueften Brief

| Schritt | Aktion | Zeigen / sagen |
|---|---|---|
| 1 | Cockpit oeffnen, **Praesentation**, Nora waehlen. | "Informationen liegen verteilt vor. Der freigegebene Medikationsplan fehlt." |
| 2 | **Quellen mit Agent pruefen** auswaehlen. | "Der Agent fragt Werkzeuge ab; er bekommt nicht einfach einen fertigen Brief." |
| 3 | Quellenkarten und **Agentenarbeit** beobachten. Bei Bedarf **Technische Details · Originalprotokoll** oeffnen. | Tatsaechliche Modell-/Werkzeugaufrufe und gelesene Originale zeigen, keine simulierte Gedankenkette. |
| 4 | Bei **Quellenpruefung abgeschlossen** die Luecke zeigen; **Medikationsplan pruefen**, dann **Medikationsmodul oeffnen**. | "Fehlende Medikation wird nicht erfunden." Den unvollstaendigen Vorschlag nicht uebernehmen. |
| 5 | Im blauen Demo-KIS den vorbereiteten Plan ansehen; **Medikationsplan freigeben** mit Bestaetigung. | "Das ist eine menschliche Aktion in einem simulierten System." Den Abschlussbefund noch nicht bereitstellen. |
| 6 | **Zurueck zum Cockpit**; **Neue Quelle mit Agent pruefen**. | "Die Quellen haben sich geaendert. Der alte Vorschlag ist nicht mehr aktuell." |
| 7 | **Briefvorschlag oeffnen**; insbesondere **Entlassmedikation** und Quellenlinks ansehen. | Nachvollziehbarkeit bis zum Originalabsatz zeigen. Quellenbezug beweist keine medizinische Richtigkeit. |
| 8 | **Entwurf pruefen & uebernehmen**, Ersetzung bewusst bestaetigen. | "Jetzt entsteht ein editierbarer Entwurf, noch keine Freigabe." Alle sechs Abschnitte werden uebernommen. |
| 9 | Brief und offene Pruefpunkte ansehen; erforderliche Bewertungen mit Demo-Name und Begruendung erfassen. | Ausstehende Befunde nicht faelschlich als erledigt markieren. Pruefliste ist eine enge deterministische Demo-Regel, kein KI-Fehlerdetektor. |
| 10 | **Demo-Entwurf freigeben**; anschliessend separat **Geprueften Entwurf ins Demo-KIS** bestaetigen. | "Pruefung, Freigabe und Uebergabe sind getrennte menschliche Schritte." |
| 11 | **Erste Briefkopie im Demo-KIS ansehen**. | Die gespeicherte Kopie zeigen. Keine reale Signatur oder Uebertragung in ein Krankenhaus. |

**Kernaussage:** Der Agent reduziert Quellenarbeit und macht Vorschlaege.
Menschen klaeren Luecken, bewerten Inhalte und entscheiden ueber Freigabe.

## Kapitel B: Ein Scan trifft nach der Uebergabe ein

Nur vorfuehren, wenn Content Understanding eingerichtet und vorab getestet ist.
Der Scan ist ein erfundener externer Konsilbericht; der spaetere Laborbefund
kommt aus dem simulierten LIS, nicht aus OCR.

1. **Dokumenteingang oeffnen** und **Demo-Scan auswaehlen**. Synthetische Daten
   und Azure-Verarbeitung bestaetigen; **Scan mit Azure analysieren**.
2. Original, erkannte Fallzuordnung und Fundstellen zeigen. Extraktionskonfidenz
   ist keine medizinische Sicherheit. Bei falscher Zuordnung nicht uebernehmen.
3. **Geprueften Scan als Quelle uebernehmen**. Fuer den Ereignisablauf
   **Neue Quellen automatisch mit Agent pruefen** ausdruecklich aktivieren,
   Demo-Pruefername angeben und bestaetigen.
4. Agentenarbeit zeigen: Originale, Laborstatus und Aufgabenstatus werden mit
   echten Werkzeugaufrufen gelesen; die Zielsysteme bleiben simuliert.
5. **Vorgeschlagene Nachverfolgung bestaetigen**, angebotene Demo-Rolle waehlen
   und bestaetigen. Keine echte Person wird benachrichtigt.
6. Den neuen, verantwortungsbezogenen Briefvorschlag pruefen und uebernehmen.
   Pruefpunkte bearbeiten, freigeben und eine weitere KIS-Kopie uebergeben.
7. Erst jetzt im blauen Demo-KIS **Abschlussbefund bereitstellen**. Der reale
   Agent startet durch lokale Ereignisverarbeitung erneut, wenn diese aktiviert ist.
8. Die Aktualisierung pruefen und uebernehmen. Aufgabe mit
   **Befund geprueft · Aufgabe abschliessen** bewusst abschliessen.
9. Brief erneut pruefen, freigeben und separat uebergeben. Aeltere Briefkopien
   bleiben unveraendert.

**Kernaussage:** Neue Information macht einen alten Entwurf nicht automatisch
richtig. Verantwortung und Abschluss bleiben nachvollziehbar und menschlich.

## Wenn etwas anders aussieht

- Vorhandener Entwurf: gespeicherter Zustand, kein automatischer KI-Aufruf.
  Vor der Sitzung explizit zuruecksetzen oder vom aktuellen Schritt fortfahren.
- Agentenfehler: sichtbar benennen; Anmeldung/Quelle pruefen und bewusst neu
  starten. Nicht als erfolgreiche KI-Antwort darstellen.
- Scan nicht konfiguriert: Kapitel B auslassen; keinen vorbereiteten Text als
  echte OCR verkaufen.
- Geaenderte Quelle/gesperrte Aktion: aktuellen Stand laden und erneut pruefen.
  Ungespeicherte manuelle Texte vorher sichern.
- **Probenmodus** ist nur eine klar gekennzeichnete Textprobe und kein Ersatz
  fuer den Agentenablauf.

## Reset nach der Probe

**Praesentationssteuerung > Demo zuruecksetzen > Bestaetigung >
Alle drei Faelle zuruecksetzen.** Dies betrifft alle drei lokalen Demo-Faelle,
Aufgaben, Briefe und Agentenlaeufe. Ein Snapshot bleibt in derselben lokalen
Datenbank; es gibt keine Wiederherstellungsoberflaeche. Ein Serverneustart
setzt die Faelle nicht zurueck.
