from uuid import uuid4

from fastapi import HTTPException

from .data import document
from .store import audit, now

ROLES = [
    {"id": "ward-team", "label": "Behandelndes Stationsteam", "system": "Demo-Aufgabenmanagement"},
    {"id": "discharge-team", "label": "Entlassmanagement", "system": "Demo-Aufgabenmanagement"},
]


def laboratory_status(case: dict) -> dict:
    report = next(doc for doc in case["documents"] if doc["kind"] == "Mikrobiologie")
    return {
        "system": "Simuliertes Laborinformationssystem", "case_id": case["id"],
        "document_id": report["id"], "status": report["status"],
        "result_available": report["status"] == "available", "updated_at": report["date"],
        "note": "Befundinhalt und Originalbeleg ausschließlich mit read_case_document abrufen.",
    }


def followup_context(case: dict) -> dict:
    return {
        "system": "Simuliertes Aufgabenmanagement", "case_id": case["id"],
        "available_roles": ROLES, "tasks": case["followup_tasks"],
        "external_document_ids": [doc["id"] for doc in case["documents"] if doc.get("intake_id")],
        "policy": "Nur Vorschläge. Keine Aufgaben anlegen, Personen oder Fristen erfinden oder klinischen Abschluss behaupten.",
    }


def queue_event(case: dict, kind: str, title: str):
    if not case["event_automation"]["enabled"]:
        return
    events = case["event_automation"]["events"]
    events.append({"id": str(uuid4()), "at": now(), "kind": kind, "title": title,
                   "status": "queued", "run_id": None, "error": None})
    # Retain every pending event and a bounded visible history.
    case["event_automation"]["events"] = [
        item for index, item in enumerate(events)
        if index >= len(events) - 24 or item["status"] in {"queued", "running"}
    ]


def set_automation(case: dict, enabled: bool, reviewer: str):
    case["event_automation"]["enabled"] = enabled
    if not enabled:
        for item in case["event_automation"]["events"]:
            if item["status"] == "queued":
                item.update(status="superseded")
    audit(case, "Ereignisprüfung " + ("aktiviert" if enabled else "deaktiviert"),
          "Neue bestätigte Scanquellen, Aufgaben und Laborbefunde lösen lokale echte Foundry-Aufrufe aus. "
          "Keine automatische Briefübernahme, Freigabe oder klinische Aktion.", reviewer)


def confirm_task(case: dict, run: dict, role_id: str, reviewer: str):
    if run["status"] != "awaiting_approval" or not run["proposal"]:
        raise HTTPException(409, "Kein offener Vorschlag für eine neue Aufgabe.")
    if run["base_revision"] != case["revision"] or run["source_version"] != case["source_version"]:
        raise HTTPException(409, "Aufgabenvorschlag ist veraltet. Aktuellen Quellenstand erneut prüfen.")
    assessment = run["proposal"].get("followup")
    if not assessment or assessment["action"] != "create":
        raise HTTPException(409, "Dieser Agentenauftrag schlägt keine neue Aufgabe vor.")
    role = next((role for role in ROLES if role["id"] == role_id), None)
    if not role:
        raise HTTPException(422, "Eine der konfigurierten Demo-Rollen auswählen.")
    if case["followup_tasks"]:
        raise HTTPException(409, "Für diesen Aufenthalt ist bereits eine Befundnachverfolgung angelegt. Keine doppelte Aufgabe.")
    if laboratory_status(case)["result_available"]:
        raise HTTPException(409, "Der Abschlussbefund ist bereits vorhanden. Keine ausstehende Nachverfolgung anlegen.")
    identifier = str(uuid4())
    task = {
        "id": identifier, "title": assessment["title"], "reason": assessment["reason"],
        "role_id": role_id, "role_label": role["label"], "status": "waiting_for_result",
        "created_at": now(), "reviewer": reviewer, "citations": assessment["citations"],
        "run_id": run["id"], "completed_at": None, "completed_by": None,
    }
    case["followup_tasks"].append(task)
    source = document(
        f"{case['id'].lower()}-task-{identifier}", "Bestätigte Befundnachverfolgung",
        "Aufgabenbestätigung", "Menschlich bestätigtes Demo-Aufgabenmanagement", now(),
        f"Nachverfolgung des mikrobiologischen Abschlussbefunds für {case['id']} ausdrücklich "
        f"zugeordnet an: {role['label']}. Aufgabe: {task['title']}. Bestätigt durch {reviewer}. "
        "Der Abschlussbefund steht weiterhin aus. Keine klinische Signatur und keine Therapieentscheidung.",
    )
    case["documents"].append(source)
    case["source_version"] += 1
    case["approval"] = None
    case["status"] = "draft" if case["draft"] else "new"
    case["decisions"] = {
        key: value for key, value in case["decisions"].items()
        if key == "conflicting-followup" and case.get("followup_resolution")
    }
    run["status"] = "rejected"
    run["events"].append({"at": now(), "kind": "task_confirmed",
                           "title": "Aufgabe bestätigt. Briefvorschlag wird mit neuer Bestätigungsquelle erneut ermittelt."})
    audit(case, "Befundnachverfolgung ausdrücklich angelegt",
          f"{role['label']} · {identifier}. Bestätigung ist eine neue Quelle. Alter Briefvorschlag nicht übernommen.", reviewer)
    queue_event(case, "task_confirmed", "Nachverfolgung bestätigt – Brief mit neuer Quelle aktualisieren")


def result_arrived(case: dict):
    for task in case["followup_tasks"]:
        if task["status"] == "waiting_for_result":
            task["status"] = "awaiting_review"
            task["result_at"] = now()
    queue_event(case, "laboratory_result", "Verspäteter Laborbefund eingetroffen – Dokumentation erneut prüfen")
