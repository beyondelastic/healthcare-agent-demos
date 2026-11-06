from copy import deepcopy

from .models import Citation, Document, Paragraph, Section

SECTION_TITLES = {
    "admission": "Aufnahmegrund und Anamnese",
    "diagnoses": "Dokumentierte Diagnosen",
    "findings": "Relevante Befunde",
    "course": "Therapie und Verlauf",
    "medication": "Entlassmedikation",
    "followup": "Weiterbehandlung und offene Befunde",
}


def document(identifier, title, kind, system, date, *texts, status="available"):
    return Document(
        id=identifier,
        title=title,
        kind=kind,
        system=system,
        date=date,
        status=status,
        paragraphs=[
            Paragraph(id=f"p{i + 1}", text=text) for i, text in enumerate(texts)
        ],
    ).model_dump()


def build_case(identifier: str, name: str, age: int, variant: str) -> dict:
    prefix = identifier.lower()
    docs = [
        document(
            f"{prefix}-admission", "Aufnahmebericht", "Aufnahme", "KIS · Demo",
            "2026-10-20T09:15:00+02:00",
            f"{name}, {age} Jahre. Aufnahme am 20.10.2026 bei Fieber, Husten und reduzierter Belastbarkeit.",
            "Dokumentierte Aufnahmediagnose: ambulant erworbene Pneumonie. Als Nebendiagnose ist eine arterielle Hypertonie vermerkt.",
            "Allergiestatus bei Aufnahme: noch nicht erhoben.",
        ),
        document(
            f"{prefix}-radiology", "Radiologischer Befund · Thorax", "Radiologie",
            "RIS · Demo", "2026-10-20T12:40:00+02:00",
            "Röntgen Thorax vom 20.10.2026: rechtsbasales Infiltrat. Kein Pleuraerguss. Freigegebener schriftlicher Befund.",
        ),
        document(
            f"{prefix}-lab", "Laborverlauf", "Labor", "LIS · Demo",
            "2026-10-24T07:30:00+02:00",
            "CRP: 20.10.2026 86 mg/l; 22.10.2026 41 mg/l; 24.10.2026 12 mg/l. Referenzbereich: < 5 mg/l.",
            "Leukozyten: 20.10.2026 13,2 /nl; 24.10.2026 7,8 /nl. Referenzbereich: 4,0–10,0 /nl.",
        ),
        document(
            f"{prefix}-course", "Ärztlicher Verlauf", "Verlauf", "KIS · Demo",
            "2026-10-24T10:00:00+02:00",
            "Stationäre antibiotische Therapie dokumentiert. Am 24.10.2026 seit 48 Stunden fieberfrei, klinisch gebessert und ohne zusätzlichen Sauerstoffbedarf.",
            "Die stationäre antibiotische Therapie ist laut ärztlicher Verlaufsdokumentation abgeschlossen. Eine Fortführung nach Entlassung ist nicht dokumentiert.",
            "Entlassung am 24.10.2026 nach ärztlicher Beurteilung vorgesehen. Dieser Vermerk ersetzt keine aktuelle Entlassentscheidung.",
        ),
        document(
            f"{prefix}-nursing", "Pflegerische Überleitung", "Pflege",
            "Pflegedokumentation · Demo", "2026-10-24T10:30:00+02:00",
            "Patientin selbstständig mobil. Entlassung in die häusliche Umgebung vorgesehen. Kein zusätzlicher Unterstützungsbedarf dokumentiert.",
        ),
    ]
    if variant != "missing":
        docs.append(document(
            f"{prefix}-medication", "Freigegebener Entlassmedikationsplan",
            "Medikation", "Medikationsmodul · Demo", "2026-10-24T11:00:00+02:00",
            "Ärztlich freigegebener Entlassmedikationsplan: Amlodipin 5 mg, oral, morgens, unverändert gegenüber der Vormedikation. Keine weitere Entlassmedikation in diesem Plan.",
            "Allergiestatus: ärztlich geprüft, keine bekannten Arzneimittelallergien dokumentiert. Stand: 24.10.2026.",
        ))
    docs.append(document(
        f"{prefix}-followup", "Dokumentierte Weiterbehandlung", "Nachsorge",
        "KIS · Demo", "2026-10-24T11:15:00+02:00",
        "Hausärztliche Verlaufskontrolle ist für den 29.10.2026 dokumentiert. Weitere Maßnahmen nur nach ärztlicher Festlegung.",
    ))
    if variant == "conflict":
        docs.append(document(
            f"{prefix}-appointment", "Terminbestätigung", "Termin",
            "Terminverwaltung · Demo", "2026-10-24T11:20:00+02:00",
            "Hausärztliche Verlaufskontrolle: Termin am 30.10.2026. Der Eintrag bezeichnet denselben Kontrolltermin wie die dokumentierte Weiterbehandlung. Keine Stornierung oder Umbuchung vermerkt.",
        ))
    docs.append(document(
        f"{prefix}-microbiology", "Mikrobiologischer Abschlussbefund",
        "Mikrobiologie", "LIS · Demo", "2026-10-24T11:30:00+02:00",
        *(
            ["Blutkulturen vom 20.10.2026: kein Wachstum im abgeschlossenen Bebrütungszeitraum. Final freigegeben am 24.10.2026 um 11:30 Uhr."]
            if variant == "complete" else
            ["Blutkulturen vom 20.10.2026: Abschlussbefund noch ausstehend. Zuständigkeit für Befundnachverfolgung in den bereitgestellten Quellen nicht dokumentiert."]
        ),
        status="available" if variant == "complete" else "pending",
    ))
    return {
        "id": identifier,
        "name": name,
        "age": age,
        "initials": "".join(part[0] for part in name.split()),
        "department": "Innere Medizin · Station M3",
        "admitted": "20.10.2026",
        "discharge": "24.10.2026",
        "label": {
            "conflict": "Widerspruch & ausstehender Befund",
            "complete": "Vollständige Demo-Quellen",
            "missing": "Fehlender Medikationsplan",
        }[variant],
        "variant": variant,
        "documents": docs,
        "revision": 0,
        "source_version": 1,
        "draft": None,
        "decisions": {},
        "audit": [],
        "status": "new",
        "approval": None,
        "intakes": [],
        "followup_tasks": [],
        "event_automation": {"enabled": False, "events": []},
        "kis": {"medication_released": variant != "missing", "retrieval_fault": False, "letters": []},
    }


CASES = {
    item["id"]: item for item in [
        build_case("DEMO-014", "Marlene Beispiel", 67, "conflict"),
        build_case("DEMO-027", "Clara Muster", 58, "complete"),
        build_case("DEMO-031", "Nora Testfall", 73, "missing"),
    ]
}


def initial_case(identifier: str) -> dict:
    return deepcopy(CASES[identifier])


def has_followup_extensions(case: dict) -> bool:
    return bool(case.get("followup_tasks")) or any(doc.get("intake_id") for doc in case["documents"])


def resolved_followup(case: dict) -> Section:
    resolution = case["followup_resolution"]
    confirmation = next(d for d in case["documents"] if d["id"] == resolution["document_id"])
    docs = {doc["kind"]: doc for doc in case["documents"]}
    text = (
        f"Hausärztliche Verlaufskontrolle am {resolution['date']}, "
        "nach ausdrücklicher Terminklärung im Demo-Workflow bestätigt. "
        "Weitere Maßnahmen nur nach ärztlicher Festlegung.\n\n"
        + docs["Mikrobiologie"]["paragraphs"][0]["text"]
    )
    sources = [confirmation, docs["Nachsorge"], docs["Mikrobiologie"]]
    return Section(
        id="followup", title=SECTION_TITLES["followup"], text=text,
        citations=[
            Citation(document_id=doc["id"], paragraph_id=doc["paragraphs"][0]["id"],
                     quote=doc["paragraphs"][0]["text"])
            for doc in sources
        ],
    )


def findings(case: dict) -> list[dict]:
    docs = {doc["kind"]: doc for doc in case["documents"]}
    result = []
    if "Medikation" not in docs:
        result.append({
            "id": "missing-medication", "type": "missing", "severity": "blocking",
            "title": "Freigegebener Entlassmedikationsplan fehlt",
            "description": "In den verfügbaren Demo-Quellen ist kein freigegebener Entlassmedikationsplan vorhanden. Vormedikation darf nicht als Entlassmedikation übernommen werden.",
            "action": "Freigegebenen Plan ergänzen oder die fehlende Quelle nachvollziehbar zur weiteren Bearbeitung dokumentieren.",
            "document_ids": [docs["Aufnahme"]["id"]],
            "section_ids": ["medication"],
        })
    if "Termin" in docs:
        resolution = case.get("followup_resolution")
        result.append({
            "id": "conflicting-followup", "type": "conflict", "severity": "blocking",
            "title": "Kontrolltermin ausdrücklich geklärt" if resolution else "Zwei Angaben zum selben Kontrolltermin",
            "description": (
                f"Gültiger Termin: {resolution['date']}. Bestätigt durch {resolution['reviewer']}. "
                "Die widersprüchlichen Originalangaben bleiben zur Nachvollziehbarkeit erhalten."
                if resolution else
                "Weiterbehandlung: 29.10.2026. Terminbestätigung: 30.10.2026. Eine Terminänderung ist nicht dokumentiert."
            ),
            "action": (
                "Bestätigten Termin und aktualisierten Nachsorgeabschnitt prüfen."
                if case["draft"] else
                "Bestätigung ist als Quelle gespeichert und wird beim ersten Entwurf berücksichtigt."
            ) if resolution else "Termin ärztlich bzw. organisatorisch klären. Nicht automatisch den neueren Eintrag auswählen.",
            "document_ids": [docs["Nachsorge"]["id"], docs["Termin"]["id"]] + ([resolution["document_id"]] if resolution else []),
            "resolved": bool(resolution),
            "section_ids": ["followup"],
        })
    if docs["Mikrobiologie"]["status"] == "pending":
        task = next((task for task in case.get("followup_tasks", []) if task["status"] != "completed"), None)
        result.append({
            "id": "pending-microbiology", "type": "pending", "severity": "blocking",
            "title": "Abschlussbefund weiterhin ausstehend" if task else "Abschlussbefund und Nachverfolgung offen",
            "description": (
                f"Der mikrobiologische Abschlussbefund steht aus. Nachverfolgung ausdrücklich zugeordnet an: {task['role_label']}. Die Aufgabe ersetzt nicht den Abschlussbefund."
                if task else
                "Der mikrobiologische Abschlussbefund steht aus. Eine verantwortliche Stelle zur Nachverfolgung ist in den verfügbaren Quellen nicht genannt."
            ),
            "action": "Als ausstehend kennzeichnen und Nachverfolgung klären. Für die Demo kann der vorbereitete Abschlussbefund bereitgestellt werden.",
            "document_ids": [docs["Mikrobiologie"]["id"]],
            "section_ids": ["findings", "followup"],
        })
    return result


def public_case(case: dict) -> dict:
    result = deepcopy(case)
    result["findings"] = [
        {**finding, "review": case["decisions"].get(finding["id"])}
        for finding in findings(case)
    ]
    result["synthetic"] = True
    return result
