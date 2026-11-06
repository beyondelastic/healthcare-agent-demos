"""Synthetic patient record spread over simulated hospital systems.

Everything here is fictional. The medication plan starts unreleased (pharmacy review)
and is released by a simulated system event during the demo.
"""

from copy import deepcopy

PATIENT = {
    "name": "Elena Novak",
    "date_of_birth": "14.03.1959",
    "age": 67,
    "case_id": "DEMO-4711",
    "department": "Allgemein- und Viszeralchirurgie · Station C2",
    "admitted": "03.11.2026",
    "discharge": "06.11.2026",
    "hospital": "Universitätsklinikum Musterstadt (fiktiv)",
}

# Letterhead and recipient for the final letter (all fictional).
LETTER = {
    "letter_id": "DEMO-EB-2026-1106",
    "hospital": "Universitätsklinikum Musterstadt (fiktiv)",
    "clinic": "Klinik für Allgemein- und Viszeralchirurgie",
    "director": "Direktor: Prof. Dr. med. Max Beispiel (fiktiv)",
    "address": "Musterstraße 1 · 00000 Musterstadt",
    "phone": "Chirurgische Ambulanz: 0000 000000-100 (Demo-Nummer)",
    "recipient": ["Hausarztpraxis Dr. med. Anna Hausarzt (fiktiv)", "Beispielweg 5", "00000 Musterstadt"],
    "kim_address": "praxis.hausarzt@demo.kim.telematik (fiktiv)",
    "signer_role": "Oberärztin, Klinik für Allgemein- und Viszeralchirurgie",
}

SECTIONS = {
    "diagnoses": "Diagnosen",
    "history": "Anamnese und Aufnahmegrund",
    "findings": "Befunde",
    "course": "Therapie und Verlauf",
    "medication": "Entlassmedikation",
    "followup": "Procedere und Weiterbehandlung",
}

SYSTEMS = {
    "KIS": "Krankenhausinformationssystem",
    "RIS": "Radiologie",
    "LIS": "Labor",
    "OP": "OP-Dokumentation",
    "PFLEGE": "Pflegedokumentation",
    "PATHO": "Pathologie",
    "MED": "Medikationsmodul",
    "TERMIN": "Terminverwaltung",
}

MEDICATION_RELEASED = (
    "Ärztlich und durch die Stationsapotheke freigegebener Entlassmedikationsplan (06.11.2026, 10:05 Uhr): "
    "1) Ibuprofen 400 mg p.o. bei Bedarf bei Schmerzen, max. 3 x täglich zu den Mahlzeiten, höchstens 5 Tage. "
    "2) Pantoprazol 20 mg p.o. 1-0-0 vor dem Frühstück, solange Ibuprofen eingenommen wird. "
    "3) Ramipril 5 mg p.o. 1-0-0, Hausmedikation unverändert fortführen. "
    "Keine Antibiotikatherapie. Keine bekannten Arzneimittelallergien."
)

SOURCES = [
    {"id": "kis-aufnahme", "system": "KIS", "title": "Aufnahmebefund", "date": "03.11.2026",
     "status": "available",
     "text": "Aufnahme bei seit 3 Monaten rezidivierenden, postprandialen rechtsseitigen Oberbauchschmerzen. "
             "Kein Fieber, kein Ikterus. Vorerkrankung: arterielle Hypertonie. Vormedikation: Ramipril 5 mg 1-0-0. "
             "Allergien: keine bekannt. Elektive Aufnahme zur Cholezystektomie."},
    {"id": "ris-sono", "system": "RIS", "title": "Sonographie Abdomen", "date": "03.11.2026",
     "status": "available",
     "text": "Gallenblase mit mehreren Konkrementen bis 12 mm, Wand nicht verdickt, keine Pericholezystitis. "
             "DHC 5 mm, keine intrahepatische Cholestase. Beurteilung: symptomatische Cholezystolithiasis."},
    {"id": "lis-labor", "system": "LIS", "title": "Laborverlauf", "date": "05.11.2026",
     "status": "available",
     "text": "03.11.: Leukozyten 8,9 /nl, CRP 12 mg/l, Bilirubin gesamt 0,8 mg/dl, GOT/GPT im Normbereich, "
             "Lipase im Normbereich. 05.11.: Leukozyten 9,2 /nl, CRP 18 mg/l. Referenz CRP < 5 mg/l."},
    {"id": "op-bericht", "system": "OP", "title": "OP-Bericht", "date": "04.11.2026",
     "status": "available",
     "text": "Laparoskopische Cholezystektomie am 04.11.2026, komplikationsloser Verlauf. "
             "Gallenblase in toto entfernt und zur histologischen Untersuchung eingesandt. "
             "Hautverschluss mit resorbierbarem Nahtmaterial, kein Fadenzug erforderlich."},
    {"id": "kis-verlauf", "system": "KIS", "title": "Ärztlicher Verlauf", "date": "06.11.2026",
     "status": "available",
     "text": "Postoperativ komplikationsloser Verlauf. Kostaufbau problemlos, schmerzarm unter Ibuprofen bei Bedarf. "
             "Wunden reizlos, afebril. Entlassung am 06.11.2026 in die Häuslichkeit. "
             "Wundkontrolle in der Hausarztpraxis in 3 bis 4 Tagen empfohlen. "
             "Körperliche Schonung, kein Heben über 5 kg für 2 Wochen. Autofahren erst bei Schmerzfreiheit. "
             "Normale Kost, sehr fettreiche Speisen in den ersten Tagen meiden. "
             "Wiedervorstellung bei Fieber über 38,5 °C, zunehmenden Bauchschmerzen, Gelbfärbung von Haut oder Augen, "
             "Rötung, Schwellung oder Sekretion der Wunden sowie anhaltendem Erbrechen. "
             "Bei Atemnot, Brustschmerzen, sehr starken Bauchschmerzen oder Bewusstseinsstörung sofort Notruf 112."},
    {"id": "pflege-ueberleitung", "system": "PFLEGE", "title": "Pflegeüberleitung", "date": "06.11.2026",
     "status": "available",
     "text": "Patientin selbstständig mobil, Versorgung zu Hause durch Ehemann gesichert. "
             "Duschen erlaubt, Wunden trocken tupfen. Baden, Schwimmen und Sauna für 2 Wochen meiden."},
    {"id": "patho-histologie", "system": "PATHO", "title": "Histologie Gallenblase", "date": "06.11.2026",
     "status": "pending",
     "text": "Histologische Untersuchung der Gallenblase eingegangen, Befund noch ausstehend. "
             "Ergebnis wird an die Hausarztpraxis übermittelt und beim Nachsorgetermin besprochen."},
    {"id": "med-entlassplan", "system": "MED", "title": "Entlassmedikationsplan", "date": "06.11.2026",
     "status": "unreleased",
     "text": MEDICATION_RELEASED},
    {"id": "termin-nachsorge", "system": "TERMIN", "title": "Termine und Kontakt", "date": "06.11.2026",
     "status": "available",
     "text": "Wundkontrolle in der Hausarztpraxis am 09.11.2026 oder 10.11.2026, Termin vereinbart die Patientin selbst. "
             "Nachsorgetermin Chirurgische Ambulanz: Dienstag, 24.11.2026, 10:30 Uhr, Gebäude A, Ebene 2 – "
             "Besprechung der Histologie und Verlaufskontrolle. Kontakt Chirurgische Ambulanz: Montag bis Freitag "
             "8 bis 16 Uhr, Telefon 0000 000000-100 (Demo-Nummer); außerhalb dieser Zeiten ärztlicher "
             "Bereitschaftsdienst 116 117."},
]


def initial_sources() -> list[dict]:
    return deepcopy(SOURCES)


def release_medication(sources: list[dict]) -> dict:
    """Simulated pharmacy release: the plan's content becomes readable."""
    source = next(s for s in sources if s["id"] == "med-entlassplan")
    source["status"] = "available"
    source["date"] = "06.11.2026, 10:05"
    return source
