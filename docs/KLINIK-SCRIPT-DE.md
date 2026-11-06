# Klinik Cockpit · KI-Agenten: Vorführskript

**Dauer:** ca. 6–8 Minuten · **Botschaft:** *KI-Agenten erledigen die Fleißarbeit über viele
Systeme, prüfen sich gegenseitig und reagieren auf neue Information – die Ärztin entscheidet
einmal, am Ende.*
**Vorbereitung:** [technisches Setup](KLINIK-SETUP.md) · Code: [agent-cockpit/](../agent-cockpit/README.md)

## Vorbereitung

1. `.\Start-AgentCockpit.ps1` im Ordner `agent-cockpit` starten, <http://127.0.0.1:8020/> im
   Vollbild (F11) öffnen.
2. **↺ Zurücksetzen** klicken. Startbildschirm zeigt die acht angebundenen Systeme.
3. Einmal vorab durchspielen (Azure-Anmeldung, Laufzeit).

## Ablauf

| # | Aktion | Was passiert | Was Sie sagen |
|---|---|---|---|
| 1 | Startbildschirm zeigen | Acht Systeme: KIS, Radiologie, Labor, OP, Pflege, Pathologie, Medikation, Termine | „Entlassung heute. Die Informationen liegen in acht Systemen – heute sucht eine Ärztin sie zusammen.“ |
| 2 | **Entlassbrief mit KI-Agenten erstellen** | Live-Protokoll: der Dokumentations-Agent findet 9 Quellen und liest sie parallel | „Der Agent arbeitet wie ein Mensch – nur parallel: Er fragt die Systeme selbst ab. Jede Zeile ist ein echter Werkzeugaufruf.“ |
| 3 | Auf **nicht freigegeben** / **ausstehend** zeigen | Medikationsplan in Prüfung der Stationsapotheke, Histologie ausstehend | „Was nicht freigegeben ist, bekommt der Agent nicht – und er rät nicht. Er markiert es als offenen Punkt.“ |
| 4 | Prüf-Agent beobachten | Zweiter Agent (anderes, stärkeres Modell) liest die Quellen selbst und prüft jede Aussage | „Vier-Augen-Prinzip, aber mit Agenten: Einer schreibt, einer prüft – unabhängig.“ |
| 5 | Falls Prüfbefund: violette Abschnitte zeigen | „x Fehler gefunden → korrigiert“, z.B. fehlende Uhrzeit des Nachsorgetermins | „Der Prüf-Agent hat eine Lücke gefunden, der Schreib-Agent hat sie selbst korrigiert. Kein Mensch musste eingreifen.“ |
| 6 | Quellen-Chip anklicken | Originaltext der Quelle | „Jede Aussage ist bis zur Quelle nachvollziehbar.“ |
| 7 | **⚡ Demo-Ereignis: Stationsapotheke gibt Medikationsplan frei** | Agent liest nur den neuen Plan, aktualisiert nur „Entlassmedikation“ (gelb), Prüf-Agent prüft erneut | „Neue Information – die Agenten reagieren selbst. Nur der betroffene Abschnitt ändert sich, alles andere bleibt wortgleich.“ |
| 8 | **Brief prüfen und freigeben** → bestätigen | Der Entwurf wird zum fertigen Arztbrief: Briefkopf, Empfänger (Hausarztpraxis), Anrede, Unterschrift „elektronisch freigegeben“, QR-Code für die Patientin | „Eine einzige menschliche Entscheidung – und der Brief ist fertig.“ |
| 9 | Rechts **Versand**: **Per KIM an Hausarztpraxis**, **In ePA einstellen** | Bestätigung mit Uhrzeit, Eintrag im Protokoll (Simulation) | „Die Hausarztpraxis hat den Brief sofort – über KIM in der Telematikinfrastruktur, und er liegt in der ePA der Patientin.“ |
| 10 | Optional: **Patientenexemplar drucken** | Druckdialog mit dem fertigen Brief und QR-Code | „Und die Patientin bekommt ihr Exemplar – mit QR-Code.“ |

**Übergang zur Sprach-Demo:** Auf den QR-Code zeigen: „Elena Novak hat jetzt ihren Brief. Und wenn
sie zu Hause Fragen hat – vielleicht auf Türkisch?“ → Entlass-Assistent. Die Inhalte (Medikation,
Termine, Warnzeichen, Kontakte) stimmen in beiden Demos überein.

## Wissen für Rückfragen

- **Echt:** zwei Foundry-Agenten (Schreiben: gpt-4.1, Prüfen: gpt-5.5), echte Werkzeugaufrufe,
  serverseitige Prüfung jeder Quellenangabe, Korrekturschleife zwischen den Agenten.
- **Simuliert:** die Klinik-Systeme und ihre Daten, die Freigabe durch die Apotheke, der Versand
  per KIM und in die ePA, die Ablage im KIS. Alle Daten fiktiv.
- In Deutschland ist der Entlassbrief ein Arztbrief an die weiterbehandelnde Praxis; die Patientin
  erhält ein Exemplar. Der Entlass-Assistent erklärt genau diesen Brief in einfacher Sprache.
- Der Prüf-Agent findet nicht in jedem Lauf einen Fehler – das ist echt, nicht inszeniert.
- Laufzeit: erster Entwurf ca. 30–45 s, Aktualisierung ca. 15–30 s.
- Die Freigabe ist kein elektronisches Signieren; Agenten-Prüfung ersetzt nicht die ärztliche
  Verantwortung.

## Wenn etwas hakt

| Problem | Lösung |
|---|---|
| Fehlermeldung im Protokoll | **↺ Zurücksetzen**, Anmeldung prüfen (`az login`), erneut starten |
| Prüf-Agent zeigt „überarbeiten“ nach zwei Runden | Offen ansprechen: „Genau dafür gibt es die ärztliche Freigabe.“ |
| Ereignis-Knopf ausgegraut | Erst nach dem ersten Entwurf aktiv, und nur einmal pro Durchlauf |
