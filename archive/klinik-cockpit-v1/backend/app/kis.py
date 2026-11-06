from fastapi import HTTPException

from .data import document, findings
from .store import audit
from .followup import followup_context, laboratory_status, queue_event


def prepared_medication(case: dict) -> dict:
    return document(
        f"{case['id'].lower()}-medication", "Freigegebener Entlassmedikationsplan",
        "Medikation", "Medikationsmodul · Demo", "2026-10-24T12:00:00+02:00",
        "Ärztlich freigegebener synthetischer Entlassmedikationsplan: "
        "Amlodipin 5 mg, oral, morgens, unverändert gegenüber der Vormedikation. "
        "Keine weitere Entlassmedikation in diesem Plan.",
        "Allergiestatus: ärztlich geprüft, keine bekannten Arzneimittelallergien dokumentiert. "
        "Stand: 24.10.2026. Ausschließlich vorbereiteter Demo-Inhalt.",
    )


def release_medication(case: dict, reviewer: str):
    if case["kis"]["medication_released"] or any(d["kind"] == "Medikation" for d in case["documents"]):
        raise HTTPException(409, "Der Medikationsplan ist bereits freigegeben.")
    case["documents"].append(prepared_medication(case))
    case["kis"]["medication_released"] = True
    case["source_version"] += 1
    case["decisions"].pop("missing-medication", None)
    case["approval"] = None
    case["status"] = "draft" if case["draft"] else "new"
    audit(case, "Demo-KIS: Medikationsplan freigegeben",
          "Vorbereiteter synthetischer Plan ist jetzt als Quelle abrufbar. "
          "Ein vorhandener Brief bleibt unverändert und ist veraltet.", reviewer)
    queue_event(case, "medication_released", "Medikationsplan freigegeben – neue Quelle erneut prüfen")


def read_tool(case: dict, name: str, arguments: dict) -> dict:
    if case["kis"]["retrieval_fault"]:
        raise HTTPException(503, "Demo-KIS-Abrufstörung aktiv. Dies ist kein Nachweis fehlender Dokumente.")
    if name == "list_case_documents":
        items = [
            {k: doc[k] for k in ["id", "title", "kind", "system", "date", "status"]}
            for doc in case["documents"]
        ]
        if not case["kis"]["medication_released"]:
            items.append({
                "id": f"{case['id'].lower()}-medication", "title": "Vorbereiteter Medikationsplan",
                "kind": "Medikation", "system": "Medikationsmodul · Demo",
                "date": "2026-10-24T12:00:00+02:00", "status": "not_released",
            })
        return {"case_id": case["id"], "source_version": case["source_version"], "documents": items}
    if name == "read_case_document":
        identifier = arguments["document_id"]
        doc = next((doc for doc in case["documents"] if doc["id"] == identifier), None)
        if doc:
            return {
                "case_id": case["id"], "source_version": case["source_version"], "document": doc,
                "source_refs": [{"document_id": doc["id"], "paragraph_id": p["id"]}
                                for p in doc["paragraphs"]],
            }
        if identifier == f"{case['id'].lower()}-medication" and not case["kis"]["medication_released"]:
            return {"case_id": case["id"], "document_id": identifier, "status": "not_released",
                    "message": "Vorbereiteter Demo-Plan vorhanden, aber nicht freigegeben. Kein Inhalt zur Übernahme verfügbar."}
        raise HTTPException(404, "Dokument gehört nicht zum ausgewählten Aufenthalt oder ist unbekannt.")
    if name == "get_case_workflow":
        return {
            "case_id": case["id"], "source_version": case["source_version"],
            "followup_resolution": case.get("followup_resolution"),
            "checklist": [f for f in findings(case) if not f.get("resolved")],
            "medication_status": "released" if case["kis"]["medication_released"] else "not_released",
            "writeback_policy": "Kein Schreibzugriff für den Agenten. Übernahme nur nach menschlicher Prüfung.",
        }
    if name == "get_laboratory_status":
        return laboratory_status(case)
    if name == "get_followup_context":
        return followup_context(case)
    raise HTTPException(422, "Unzulässiges Agentenwerkzeug.")
