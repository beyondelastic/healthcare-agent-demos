# Entlass-Assistent: Vorführskript

**Dauer:** ca. 8–10 Minuten · **Rollen:** Patientin (Sie) und Behandlungsteam (zweiter Tab)
**Botschaft:** *Ärztinnen und Ärzte verantworten den Inhalt. KI macht freigegebene Information
in der Sprache der Patientin verständlich – ohne neue medizinische Entscheidungen.*

## Vorbereitung (vor der Sitzung)

1. `.\Start-VoiceDemo.ps1` starten; Edge oder Chrome, Mikrofon/Headset prüfen.
2. Tab 1: <http://127.0.0.1:8010/> (Brief mit QR-Code).
   Tab 2: <http://127.0.0.1:8010/team> → **Demo zurücksetzen**.
3. Einmal kurz durchsprechen (Sprachqualität, Lautstärke, Antwortzeit).
4. Ersatz für laute Räume: Fragen in das Textfeld tippen – gleiche Antworten, ohne Spracheingabe.

## Ablauf

| # | Aktion / Frage | Was passiert | Was Sie sagen |
|---|---|---|---|
| 1 | Brief zeigen, QR-Code zeigen, **Assistent öffnen** | Patientenansicht, Brief „ärztlich freigegeben“ | „Die Patientin bekommt den freigegebenen Brief. Der QR-Code führt zum Assistenten – im echten Betrieb über das Patientenportal mit Anmeldung.“ |
| 2 | **Deutsch**, Mikrofon starten: *„Welche Tabletten muss ich wann nehmen?“* | Liest Abschnitt Medikamente, erklärt einfach; Quelle wird angezeigt | „Jede Antwort kommt aus dem freigegebenen Brief – sichtbar an der Quelle.“ |
| 3 | Sprache wechseln, einfach weitersprechen: *„What appointments do I have?“* (oder Türkisch: *„Bir sonraki randevum ne zaman?“*) | Antwort in der neuen Sprache, Daten und Uhrzeiten exakt | „Sprachbarrieren sind Alltag. Daten, Dosierungen und Telefonnummern bleiben exakt wie im Brief.“ |
| 4 | **Rückfrage ans Team:** *„Mir geht es gut. Kann ich das Ramipril einfach weglassen?“* | Keine Empfehlung; wiederholt den Brief; **Rückrufanfrage (Routine)** wird angezeigt | „Die KI trifft keine Therapieentscheidung. Sie gibt die Frage an das Team weiter.“ |
| 5 | Tab 2 (**/team**) zeigen | Deutsche Zusammenfassung, Originalfrage mit Sprache, genutzte Briefabschnitte, Verlauf | „Das Team sieht strukturiert, was gefragt wurde – auf Deutsch, auch wenn auf Englisch gefragt wurde.“ |
| 6 | Optional – Warnzeichen: *„Ich habe 39 Grad Fieber. Was soll ich tun?“* | Warnzeichen und Kontakt aus dem Brief, **dringende** Rückrufanfrage | „Warnzeichen kommen aus dem Brief, nicht aus dem Modellwissen.“ |
| 7 | Optional – Notfall: *„Ich habe plötzlich starke Brustschmerzen und bekomme schlecht Luft.“* | Sofort „Rufen Sie 112“, roter Hinweis, **Notfall** im Team-Tab | „Bei akuten Gefahrenzeichen verweist der Assistent sofort auf den Notruf.“ |

Abschluss: *„Freigegebener Inhalt, jede Sprache, klare Grenzen und eine Übergabe an Menschen –
das entlastet Hotline und Station, ohne neue medizinische Aussagen zu erzeugen.“*

## Weitere Fragen, falls Zeit ist

- *„Was ist mit der Gewebeuntersuchung?“* → erklärt nur, wann und wie das Ergebnis kommt.
- *„Darf ich duschen? Wann darf ich wieder Auto fahren?“* → Alltag aus dem Brief.
- *„Wann kann ich wieder arbeiten?“* → steht nicht im Brief; der Assistent **bietet** einen
  Rückruf an – mit *„Ja, bitte“* antworten, damit die Anfrage entsteht.
- Arabisch oder Ukrainisch zeigen, dass auch nicht-lateinische Sprachen funktionieren
  (Arabisch: Seite wechselt auf rechts-nach-links).

## Wissen für Rückfragen

- **Echt:** Foundry-Sprachagent (Echtzeitmodell, mehrsprachige Stimme), Werkzeugaufrufe,
  Rückfragen im Team-Tab.
- **Simuliert:** QR-Identitätsprüfung, Patientenportal, Brief-Quelle, Benachrichtigung des Teams.
  Alle Daten sind fiktiv.
- Übersetzungen sind nicht klinisch validiert; Dosierungen und Daten werden wörtlich übernommen.
- Gesprochene Sprache wird pro Frage erkannt; der Sprachknopf setzt nur Startsprache und Oberfläche.
- Smartphone per QR braucht eine HTTPS-Adresse (Tunnel oder Bereitstellung); in der Demo den
  Laptop-Browser nutzen.

## Wenn etwas hakt

| Problem | Lösung |
|---|---|
| Assistent unterbricht sich selbst | Headset nutzen oder Lautsprecher leiser stellen |
| Keine Antwort / Fehler | Gespräch beenden und neu starten; Anmeldung (`az login`) prüfen |
| „Verbindung wird wiederhergestellt …“ | Bricht die Verbindung zum Sprachdienst ab, verbindet die App automatisch neu (bis zu 3-mal) und setzt das Gespräch fort; einfach weitersprechen |
| Raum zu laut | Fragen eintippen |
| Rückfrage erscheint nicht | Frage 4 verwenden (zuverlässigster Auslöser); Team-Tab aktualisiert alle 3 Sekunden |
