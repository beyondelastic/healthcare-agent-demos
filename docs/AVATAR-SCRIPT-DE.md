# Empfangs-Avatar: Vorführskript

**Dauer:** ca. 6–8 Minuten · **Rollen:** Besucherin bzw. Patientin (Sie) und Information/Ambulanz (zweiter Tab)
**Vorbereitung:** [technisches Setup](AVATAR-SETUP.md) · Code: [hospital-avatar/](../hospital-avatar/README.md)
**Botschaft:** *Ein Avatar übernimmt Routine am Empfang – rund um die Uhr, in jeder Sprache. Er
entlastet die Information, ohne medizinische Aussagen zu machen.*

## Vorbereitung (vor der Sitzung)

1. Im Ordner `hospital-avatar` `.\Start-AvatarDemo.ps1` starten; Edge oder Chrome, Headset oder gutes Mikrofon.
2. Tab 1: <http://127.0.0.1:8030/> im Vollbild (F11). Tab 2: <http://127.0.0.1:8030/team> → **Demo zurücksetzen**.
3. Einmal kurz durchsprechen (Avatar erscheint, Ton, Antwortzeit) und das Gespräch beenden.
   **Danach mindestens eine Minute warten**: Der Avatar-Dienst begrenzt direkt aufeinanderfolgende Sitzungen.
4. Ersatz für laute Räume: Fragen in das Textfeld unten rechts tippen.

## Ablauf

| # | Aktion / Frage | Was passiert | Was Sie sagen |
|---|---|---|---|
| 1 | Kiosk zeigen, **Termin anmelden** antippen | Nia erscheint und fragt nach Name und Geburtsdatum | „Wir sind am 24.11., 10:12 Uhr, Haupteingang. Elena Novak kommt zu ihrem Nachsorgetermin – derselbe Termin, der im Arztbrief und im Entlass-Assistenten stand.“ |
| 2 | *„Novak, geboren am 14. März 1959.“* | Ticket mit Wartenummer, Uhrzeit, mitzubringende Unterlagen; Karte mit Weg in Gebäude A, Ebene 2 | „Angemeldet ohne Warteschlange. Die Ambulanz weiß Bescheid – und der Grund des Termins wird im Foyer nicht ausgesprochen.“ |
| 3 | Tab 2 (**/team**) zeigen | Ankunft mit Wartenummer und internem Hinweis „nur für das Team“ | „Das Team sieht, wer da ist – inklusive des Termingrunds, den der Avatar bewusst nicht vorliest.“ |
| 4 | Sprache wechseln, einfach weitersprechen: *„Я в інвалідному візку. Де здати кров?“* (oder Türkisch: *„Radyoloji nerede?“*) | Antwort auf Ukrainisch, Bildschirm wechselt die Sprache, stufenloser Weg ins Labor | „Jede Sprache, ohne Menü. Und barrierefreie Wege, wenn jemand im Rollstuhl sitzt.“ |
| 5 | *„Ich habe starke Bauchschmerzen. Soll ich noch eine Ibuprofen nehmen?“* | Keine Empfehlung; Nia bittet, Platz zu nehmen, und ruft eine Kollegin (dringend) | „Hier ist die Grenze: keine medizinischen Aussagen. Der Avatar holt einen Menschen.“ |
| 6 | Optional – Notfall: *„My father just collapsed and has chest pain!“* | Sofort roter Hinweis „Hilfe ist unterwegs“, im Team-Tab dringend, Herkunft „Regel + Avatar“ | „Bei Notfallbegriffen greift zusätzlich eine feste Regel – unabhängig vom Modell.“ |

Abschluss: *„Vom Arztbrief über die Fragen zu Hause bis zur Ankunft im Klinikum – drei Agenten
begleiten dieselbe Patientin. Der Avatar ist der Einstieg mit dem geringsten Risiko: organisatorisch,
nicht medizinisch.“*

## Weitere Fragen, falls Zeit ist

- *„Wann sind die Besuchszeiten?“*, *„Wo kann ich parken und was kostet das?“*, *„Gibt es WLAN?“*
- *„Wo ist die Cafeteria?“* → Weg nach Gebäude C mit Karte.
- *„Ist Herr Schneider heute hier?“* → keine Auskunft über andere Personen.
- Falsches Geburtsdatum → „kein Termin gefunden“, ohne Hinweise auf andere Termine; Angebot, eine Kollegin zu rufen.

## Wissen für Rückfragen

- **Echt:** Foundry-Sprachagent mit Standard-Video-Avatar (Nia), Echtzeitmodell, mehrsprachige Stimme,
  Werkzeugaufrufe, Übergaben im Team-Tab, Notfallregel in der App.
- **Simuliert:** Lageplan, Termine, Besucherinformationen, Terminsystem, Benachrichtigung des Personals,
  Uhrzeit (Demo-Uhr 10:12).
- **Regulatorisch:** keine medizinische Zweckbestimmung – Wegeleitung, Anmeldung, Besucherinformation.
  Für einen echten Kiosk zusätzlich: Datenschutz für Sprachaufnahmen im öffentlichen Bereich,
  Barrierefreiheit, Anbindung an Terminsystem und Personalruf.
- Avatar-Video kommt per WebRTC direkt in den Browser; die Anmeldedaten bleiben auf dem Server.

## Wenn etwas hakt

| Problem | Lösung |
|---|---|
| „Nia ist gleich wieder für Sie da …“ / *rate-limited* | Avatar-Sitzungen zu schnell hintereinander gestartet: 30–60 Sekunden warten, dann erneut starten |
| Avatar erscheint nicht, Sprache läuft weiter | Nach 15 Sekunden schaltet der Kiosk auf reine Sprache um; Netzwerk/Firewall (WebRTC, TURN) prüfen |
| Mikrofon kurz stummschalten (z. B. während Sie erklären) | Knopf **🔇 Mikrofon aus** neben dem Mikrofon oder Taste **M**; Gespräch bleibt offen, Tippen geht weiter |
| Assistentin unterbricht sich selbst | Headset nutzen oder Lautsprecher leiser stellen |
| Bildschirm zeigt noch die letzte Anmeldung | Auf das Logo oben links tippen (Startseite) – nach Gesprächsende automatisch nach 45 Sekunden |
