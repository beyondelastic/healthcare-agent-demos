# Moderationsleitfaden: 90 Minuten

## Ziel und roter Faden

**Von verteilten Informationen zu nachvollziehbaren Vorschlaegen und Antworten
im Arbeitsalltag.** Nicht die Foundry-Oberflaeche vorfuehren, sondern zwei
konkrete Aufgaben zeigen. Technik nur zur Einordnung oeffnen.

| Zeit | Inhalt |
|---|---|
| 0-10 Min. | Ziele, heutige Medienbrueche, Erwartungen der Teilnehmenden |
| 10-20 Min. | Agentenprinzip: Quellen, Werkzeuge, Identitaet, menschliche Verantwortung |
| 20-35 Min. | [Klinik Cockpit: KI-Agenten erstellen und pruefen den Entlassbrief](KLINIK-SCRIPT-DE.md) |
| 35-45 Min. | [Entlass-Assistent: Fragen zum Brief per Sprache](VOICE-SCRIPT-DE.md) |
| 45-60 Min. | [Forschungsnavigator in Teams](RESEARCH-SCRIPT-DE.md) |
| 60-70 Min. | Architektur, Zugriffsrechte, Betrieb und Grenzen |
| 70-90 Min. | Diskussion: eigener Pilot, fachliche Verantwortung, Erfolgskriterien |

Der Entlass-Assistent setzt die Geschichte des Cockpits aus Sicht der Patientin
fort: Der im Cockpit freigegebene Arztbrief traegt einen QR-Code, ueber den die
Patientin ihn in der eigenen Sprache erklaert bekommt (gleiche Patientin, gleiche
Fakten). Beide Demos laufen technisch unabhaengig.

## Vorbereitung am Vortag

1. Beide technischen Setups abschliessen; nicht waehrend des Termins
   Ressourcen bereitstellen oder Teams-Freigaben beantragen.
2. Beide Skripte mit den tatsaechlichen Praesentationskonten durchspielen.
   Die Forschungsantworten mit der Referenztabelle vergleichen.
3. Klinik Cockpit und Entlass-Assistent mit **Zuruecksetzen** auf den Startzustand
   bringen; beide halten ihren Zustand nur im Arbeitsspeicher.
4. Fuer Teams einen eigenen Browser/ein eigenes Profil im richtigen Tenant
   verwenden. Konto, Foundry-Zugriff und Fabric-Zugriff vorab pruefen.
5. Netz, Azure-Anmeldung, Modellverfuegbarkeit und aktive Fabric-Kapazitaet
   pruefen. Keine garantierte Antwortzeit versprechen; im Aufbau wurden
   teilweise etwa 50 Sekunden beobachtet.
6. Eigene Aufzeichnungen als klar gekennzeichnete Reserve vorbereiten. Keine
   echten Patienteninformationen oder fremden Kontoangaben aufnehmen.

## Fuenf Minuten vorher

1. Klinik Cockpit auf `http://127.0.0.1:8020` im Vollbild oeffnen und
   **↺ Zuruecksetzen** klicken (Patientin Elena Novak, fiktiv).
2. Forschungsnavigator in Teams oeffnen; einen frischen Gespraechskontext
   verwenden oder die Basiskriterien ausdruecklich vollstaendig setzen.
3. Entlass-Assistent auf `http://127.0.0.1:8010/` oeffnen, Team-Ansicht
   `http://127.0.0.1:8010/team` zuruecksetzen, Mikrofon/Headset pruefen.
4. Benachrichtigungen ausblenden; technische Konfiguration und Admin-Portale
   aus der Bildschirmfreigabe nehmen.
5. Zu Beginn sagen: **"Alle Daten und Einrichtungen sind erfunden.
   Wir demonstrieren Arbeitsablaeufe, keine klinische Entscheidung."**

## Gute Abschlussfragen an die Runde

- Welcher Medienbruch verursacht heute den groessten Aufwand?
- Wer traegt fachlich die Verantwortung fuer Quellen, Freigaben und Betrieb?
- Welche messbare Verbesserung wuerde einen begrenzten Pilot rechtfertigen?

Nicht behaupten: produktive KIS-Integration, autonome Signatur, klinisch
validierte Qualitaetspruefung, Deutschland-only-Verarbeitung oder produktive
Compliance. Die beigelegten Quelltexte enthalten keine Praesentationsfolien.
