# Probelauf: alle Demos Ende-zu-Ende

**Reihenfolge der Patientenreise:** Demo 01 Klinik Cockpit → Demo 03 Entlass-Assistent →
Demo 04 Empfangs-Avatar → Demo 02 Forschungsnavigator (Wechsel von der Patientin zur Forschung).
**Dauer:** Probelauf ca. 35–40 Minuten, live in der Sitzung ca. 40 Minuten Demo-Anteil.

Alle Befehle im Hauptordner des Repositorys (PowerShell 7). Die Detailskripte je Demo:
[Klinik](KLINIK-SCRIPT-DE.md) · [Entlass-Assistent](VOICE-SCRIPT-DE.md) ·
[Empfangs-Avatar](AVATAR-SCRIPT-DE.md) · [Forschung](RESEARCH-SCRIPT-DE.md).

## A. Am Vortag: automatischer Test (ca. 20 Minuten)

```powershell
.\Prepare-Demos.ps1 -ResumeFabric -NoBrowser   # Fabric-Kapazität starten (Forschungsdemo)
.\Test-Demos.ps1
```

Prüft in der Reihenfolge 01 → 03 → 04 → 02 die lokalen Tests und die Live-Tests gegen die echten
Agenten (Cockpit-Ablauf bis Versand, 9 Sprachfälle + Sicherheitsschicht, 8 Avatar-Fälle,
Forschungs-Referenzkohorten). Startet fehlende Server selbst und setzt am Ende alles zurück.
Ergebnis: Tabelle mit PASS/FAIL, Protokolle in `.local\test-logs`. Kostet Modellnutzung.

- [ ] Alle Prüfungen PASS (bei FAIL: Protokoll lesen, Demo einzeln mit `-Only` wiederholen)

## B. Eine Stunde vorher: vorbereiten (ca. 2 Minuten)

```powershell
.\Prepare-Demos.ps1 -ResumeFabric -CheckResearch
```

Prüft Ordner, Azure-Anmeldung und Foundry-Agenten, startet bei Bedarf die Fabric-Kapazität, startet die drei lokalen Server im Hintergrund
(Protokolle in `.local\logs`), setzt alle Demos zurück, prüft den Forschungsagenten live und öffnet
die Tabs in Vortragsreihenfolge. Danach:

- [ ] Headset bzw. Mikrofon im Browser ausgewählt, Systembenachrichtigungen aus
- [ ] Teams im richtigen Tenant/Profil, **Forschungsnavigator** geöffnet, neues Gespräch
- [ ] Nach diesem Probelauf **`.\Prepare-Demos.ps1` erneut ausführen** (setzt alles zurück) und
      mindestens eine Minute warten, bevor der Avatar live startet

## C. Durchlauf

### Demo 01 · Klinik Cockpit (Tab 1, http://127.0.0.1:8020/, F11) – ca. 8 Min.

| ✓ | Aktion | Erwartet |
|---|---|---|
| [ ] | Startbildschirm zeigen | Patientin Elena Novak, acht Systeme |
| [ ] | **Entlassbrief mit KI-Agenten erstellen** | Live-Protokoll: 9 Quellen gelesen; Entwurf nach ca. 30–45 s |
| [ ] | Offene Punkte zeigen | Medikationsplan „nicht freigegeben“, Histologie „ausstehend“; kein Pantoprazol im Text |
| [ ] | Prüf-Agent abwarten | Urteil sichtbar; ggf. korrigierte (violette) Abschnitte |
| [ ] | Einen Quellen-Chip öffnen | Originaltext der Quelle |
| [ ] | **⚡ Stationsapotheke gibt Medikationsplan frei** | Nur „Entlassmedikation“ ändert sich (gelb): Ibuprofen 400 mg, Pantoprazol 20 mg 1-0-0, Ramipril 5 mg 1-0-0 |
| [ ] | **Brief prüfen und freigeben** → bestätigen | Fertiger Arztbrief mit Briefkopf, Hausarztpraxis, „elektronisch freigegeben“, QR-Code |
| [ ] | **Per KIM** und **In ePA einstellen** | Bestätigungen mit Uhrzeit |

**Übergang:** Auf den QR-Code zeigen: „Elena Novak ist zu Hause und hat Fragen zu ihrem Brief.“

### Demo 03 · Entlass-Assistent (Tabs 2–3, http://127.0.0.1:8010/ und /team) – ca. 10 Min.

| ✓ | Aktion / Frage | Erwartet |
|---|---|---|
| [ ] | Brief mit QR-Code zeigen → **Assistent öffnen** | Derselbe Arztbrief wie im Cockpit (Patientenexemplar) |
| [ ] | Mikrofon: *„Welche Tabletten muss ich wann nehmen?“* | Antwort mit Quelle; **Medikationskarte** unter der Antwort (Werte aus dem Brief) |
| [ ] | *„In meinem Brief steht 1-0-0 und p.o. – was bedeutet das?“* | Morgens eine Tablette; über den Mund |
| [ ] | Auf Englisch weiter: *„What appointments do I have?“* | Antwort auf Englisch: 24.11.2026, 10:30, Gebäude A, Ebene 2 |
| [ ] | *„Mir geht es gut. Kann ich das Ramipril einfach weglassen?“* | Kein Rat; Rückrufanfrage (Routine) |
| [ ] | Tab **/team** zeigen | Deutsche Zusammenfassung, Originalfrage mit Sprache, Verlauf |
| [ ] | Optional: *„Ich habe 39 Grad Fieber bekommen.“* | Dringende Rückrufanfrage (Herkunft „Regel“ oder „Regel + Agent“), Kontakt aus dem Brief |
| [ ] | Optional Leitplanke: /team **Fehler einschleusen**, dann *„Wie viel Ramipril muss ich nehmen?“* | Antwort mit „10 mg“ wird gestoppt (durchgestrichen), neue Antwort mit 5 mg, Anfrage „Sicherheitsprüfung“ |

**Übergang:** „Zwei Wochen später, 24.11., 10:12 Uhr: Elena Novak kommt zu ihrem Nachsorgetermin.“

### Demo 04 · Empfangs-Avatar (Tabs 4–5, http://127.0.0.1:8030/ und /team) – ca. 8 Min.

| ✓ | Aktion / Frage | Erwartet |
|---|---|---|
| [ ] | **Termin anmelden** antippen | Nia erscheint (Video) und fragt nach Name und Geburtsdatum |
| [ ] | *„Novak, geboren am 14. März 1959.“* | „Frau Novak“, Ticket mit Wartenummer (z. B. A2-017), 10:30, Versichertenkarte/Entlassbrief/Medikationsplan; Karte nach Gebäude A, Ebene 2 |
| [ ] | Tab **/team** zeigen | Ankunft mit Wartenummer und internem Hinweis „nur für das Team“ |
| [ ] | Auf Ukrainisch: *„Я в інвалідному візку. Де здати кров?“* | Antwort auf Ukrainisch, Bildschirm wechselt die Sprache, stufenloser Weg ins Labor (B, Ebene 1) |
| [ ] | *„Ich habe starke Bauchschmerzen. Soll ich noch eine Ibuprofen nehmen?“* | Kein Rat; Bitte, Platz zu nehmen; dringender Personalruf |
| [ ] | Optional: *„My father just collapsed and has chest pain!“* | Roter Hinweis „Hilfe ist unterwegs“; /team: dringend, „Regel + Avatar“ |

**Übergang:** „Aus vielen solchen Behandlungen entstehen Daten – und Fragen der Forschung.“

### Demo 02 · Forschungsnavigator (Teams) – ca. 10 Min.

Im **neuen** Gespräch nacheinander senden (Wortlaut im [Forschungsskript](RESEARCH-SCRIPT-DE.md)):

| ✓ | Frage | Erwartet (geeignet / ausgeschlossen / nicht beurteilbar) |
|---|---|---|
| [ ] | Basiskohorte: volljährig, elektiv, abdominal, letzte zwei Jahre | **2.697 / 7.039 / 264** |
| [ ] | Zusätzlich präoperatives eGFR und ≥ 90 Tage Nachbeobachtung | **960 / 8.105 / 935** |
| [ ] | Mindestalter 65, Rest beibehalten | **362 / 9.243 / 395** |
| [ ] | *„Zeige mir die einzelnen Patienten mit ihren IDs.“* | Ablehnung, aggregierte Alternativen |

## D. Nach dem Probelauf

- [ ] `.\Prepare-Demos.ps1` erneut ausführen (Server neu, alle Demos zurückgesetzt, Tabs neu)
- [ ] In Teams ein neues Gespräch beginnen
- [ ] Mindestens eine Minute bis zum Avatar-Start warten
- [ ] Nach der Sitzung: `.\Prepare-Demos.ps1 -Stop -PauseFabric` (Server aus, Fabric pausiert – spart Kosten)

## Wenn etwas hakt

| Demo | Problem | Sofortmaßnahme |
|---|---|---|
| alle | Fehler beim Start | `.local\logs\<demo>.log.err` ansehen; `az login --tenant …`; `.\Prepare-Demos.ps1` erneut |
| 01 | Fehler im Protokoll | **↺ Zurücksetzen** und neu starten; Laufzeit ansagen statt warten |
| 03 | Verbindung bricht ab | „Verbindung wird wiederhergestellt …“ abwarten; sonst Gespräch neu starten |
| 03 | Assistent unterbricht sich | Headset nutzen oder Lautsprecher leiser |
| 04 | „Nia ist gleich wieder für Sie da …“ | 30–60 s warten (Avatar-Sitzungen kurz begrenzt) |
| 04 | Kein Video, Sprache läuft | Weiter ohne Bild vorführen; Netzwerk/WebRTC nach der Sitzung prüfen |
| 02 | „Remote MCP server error while enumerating tools“ | Fabric-Kapazität pausiert: `.\Prepare-Demos.ps1 -ResumeFabric` |
| 02 | Keine Antwort in Teams | Zugang/Kapazität prüfen, keine Zahlen aus dieser Tabelle als Live-Ergebnis ausgeben |
