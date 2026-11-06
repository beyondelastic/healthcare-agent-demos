import logging
import sqlite3
import base64
from contextlib import asynccontextmanager
from copy import deepcopy
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import ROOT, Settings, settings
from .agent import drain_events, run_agent
from .data import CASES, document, findings, has_followup_extensions, public_case, resolved_followup
from .generation import generate, validate_sections
from .models import ApproveRequest, DecisionRequest, FollowupResolutionRequest, GenerateRequest, HumanConfirmation, KisFaultRequest, Mutation, ResetRequest, SaveRequest, Section
from .kis import prepared_medication, release_medication
from .store import Store, audit, now
from .followup import ROLES, confirm_task, laboratory_status, queue_event, result_arrived, set_automation
from .intake import MAX_FILE_BYTES, accept_intake, analyze_intake, begin_intake, sample_scan
from .models import AutomationConfirmation, IntakeConfirmation, TaskConfirmation

logging.basicConfig(level=logging.INFO)


def create_app(config: Settings = settings, *, serve_frontend: bool = True) -> FastAPI:
    store = Store(config.database_path)

    @asynccontextmanager
    async def lifespan(_app):
        store.recover_runs()
        yield

    app = FastAPI(title="Klinik Studio · Synthetic Demo", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"],
    )
    app.state.store = store

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        return {
            "status": "ok", "synthetic_only": True,
            "foundry": {
                "project": config.foundry_project_endpoint,
                "model": config.foundry_model,
                "configured": bool(config.foundry_model),
                "authentication": "Azure CLI / Managed Identity",
                "note": "Konfiguration ist kein Nachweis erfolgreicher Inferenz.",
            },
            "agent": {"name": config.foundry_agent_name, "version": config.foundry_agent_version,
                      "configured": bool(config.foundry_agent_version), "tools": "read-only",
                      "tracing": "Lokale echte Tool-Ereignisse und Foundry Response-IDs; kein Application-Insights-Monitor eingerichtet."},
            "document_analysis": {
                "configured": bool(config.content_understanding_endpoint and config.content_understanding_analyzer),
                "service": "Azure Content Understanding", "synthetic_only": True,
                "note": "PDF/PNG/JPEG, maximal 5 MiB und drei Seiten. Konfiguration ist kein erfolgreicher Analysenachweis.",
            },
            "followup_roles": ROLES,
        }

    @app.get("/api/cases")
    def list_cases():
        return [
            {key: case[key] for key in [
                "id", "name", "age", "initials", "department", "label", "status", "revision",
            ]} | {
                "open_findings": sum(
                    item["id"] not in case["decisions"] for item in findings(case)
                ),
                "documents": len(case["documents"]),
            }
            for case in [store.get(identifier) for identifier in CASES]
        ]

    @app.get("/api/cases/{identifier}")
    def get_case(identifier: str):
        return public_case(store.get(identifier))

    @app.get("/api/cases/{identifier}/sample-scan.png")
    def prepared_scan(identifier: str):
        return Response(sample_scan(store.get(identifier)), media_type="image/png",
                        headers={"Content-Disposition": f'attachment; filename="Demo-Scan-{identifier}.png"'})

    @app.post("/api/cases/{identifier}/intakes", status_code=202)
    async def upload_scan(identifier: str, request: Request, background: BackgroundTasks,
                          revision: int = Query(ge=0),
                          synthetic_only: bool = Query(False),
                          filename: str = Query(min_length=1, max_length=180)):
        if not synthetic_only:
            raise HTTPException(422, "Ausschließlich synthetische Demo-Dokumente ausdrücklich bestätigen.")
        if not config.content_understanding_endpoint or not config.content_understanding_analyzer:
            raise HTTPException(503, "Content Understanding ist nicht konfiguriert. Keine vorgetäuschte Dokumentanalyse.")
        case = store.get(identifier)
        if revision != case["revision"]:
            raise HTTPException(409, "Fall geändert. Vor dem Scan-Eingang aktuellen Stand laden.")
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_FILE_BYTES:
                raise HTTPException(413, "Datei überschreitet 5 MiB.")
            raw.extend(chunk)
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        updated = begin_intake(store, case, bytes(raw), content_type, filename)
        background.add_task(analyze_intake, store, identifier, updated["intakes"][-1]["id"], config)
        return public_case(updated)

    @app.get("/api/cases/{identifier}/intakes/{intake_id}/pages/{page}")
    def scan_preview(identifier: str, intake_id: str, page: int):
        _, _, previews = store.intake_file(identifier, intake_id)
        if not 1 <= page <= len(previews):
            raise HTTPException(404, "Scan-Seite nicht vorhanden.")
        return Response(base64.b64decode(previews[page - 1]), media_type="image/png")

    @app.get("/api/cases/{identifier}/intakes/{intake_id}/original")
    def scan_original(identifier: str, intake_id: str):
        raw, content_type, _ = store.intake_file(identifier, intake_id)
        suffix = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[content_type]
        return Response(raw, media_type=content_type, headers={
            "Content-Disposition": f'attachment; filename="Demo-Original-{intake_id}.{suffix}"',
        })

    @app.post("/api/cases/{identifier}/intakes/{intake_id}/retry", status_code=202)
    def retry_scan(identifier: str, intake_id: str, body: HumanConfirmation, background: BackgroundTasks):
        def apply(case):
            item = next((item for item in case["intakes"] if item["id"] == intake_id), None)
            if not item or item["status"] != "failed":
                raise HTTPException(409, "Nur eine fehlgeschlagene Analyse ausdrücklich erneut starten.")
            item.update(status="analyzing", error=None)
            audit(case, "Dokumentanalyse erneut gestartet", "Weiterer echter Azure-Aufruf; keine Quelle übernommen.", body.reviewer)
        updated = store.mutate(identifier, body.revision, apply)
        background.add_task(analyze_intake, store, identifier, intake_id, config)
        return public_case(updated)

    @app.post("/api/cases/{identifier}/intakes/{intake_id}/accept")
    def confirm_scan(identifier: str, intake_id: str, body: IntakeConfirmation, background: BackgroundTasks):
        updated = store.mutate(identifier, body.revision,
                               lambda case: accept_intake(case, intake_id, body.reviewer, body.monitor_events))
        background.add_task(drain_events, store, identifier, config)
        return public_case(updated)

    @app.post("/api/cases/{identifier}/automation")
    def configure_automation(identifier: str, body: AutomationConfirmation):
        return public_case(store.mutate(identifier, body.revision,
                                       lambda case: set_automation(case, body.enabled, body.reviewer)))

    @app.post("/api/cases/{identifier}/events/{event_id}/retry", status_code=202)
    def retry_event(identifier: str, event_id: str, body: HumanConfirmation, background: BackgroundTasks):
        def apply(case):
            item = next((item for item in case["event_automation"]["events"] if item["id"] == event_id), None)
            if not case["event_automation"]["enabled"] or not item or item["status"] != "failed":
                raise HTTPException(409, "Nur ein fehlgeschlagenes Ereignis bei aktivierter Ereignisprüfung erneut starten.")
            item.update(status="queued", error=None, run_id=None)
            audit(case, "Ereignisprüfung erneut bestätigt", "Weiterer echter Foundry-Aufruf mit aktuellen Quellen.", body.reviewer)
        updated = store.mutate(identifier, body.revision, apply)
        background.add_task(drain_events, store, identifier, config)
        return public_case(updated)

    @app.post("/api/cases/{identifier}/agent-runs/{run_id}/task")
    def create_followup_task(identifier: str, run_id: str, body: TaskConfirmation, background: BackgroundTasks):
        updated = store.commit_run(identifier, run_id, body.revision,
                                   lambda case, run: confirm_task(case, run, body.role_id, body.reviewer))
        background.add_task(drain_events, store, identifier, config)
        return public_case(updated)

    @app.post("/api/cases/{identifier}/tasks/{task_id}/complete")
    def complete_followup_task(identifier: str, task_id: str, body: HumanConfirmation):
        def apply(case):
            task = next((item for item in case["followup_tasks"] if item["id"] == task_id), None)
            if not task or task["status"] != "awaiting_review" or not laboratory_status(case)["result_available"]:
                raise HTTPException(409, "Nur eine Aufgabe mit eingetroffenem Befund menschlich abschließen.")
            if not case["draft"] or case["draft"]["source_version"] != case["source_version"]:
                raise HTTPException(409, "Zuerst aktuellen Briefvorschlag übernehmen und Befund sowie Dokumentation fachlich prüfen.")
            task.update(status="completed", completed_at=now(), completed_by=body.reviewer)
            audit(case, "Befundnachverfolgung menschlich abgeschlossen",
                  f"{task_id}. Befund und aktuelle Dokumentation ausdrücklich geprüft. Kein automatischer klinischer Abschluss.", body.reviewer)
        return public_case(store.mutate(identifier, body.revision, apply))

    @app.post("/api/demo/reset")
    def reset_demo(body: ResetRequest):
        try:
            backup_id, restored = store.reset(body.revisions)
        except (OSError, sqlite3.Error) as exc:
            logging.getLogger(__name__).exception("Demo reset could not be committed")
            raise HTTPException(500, "Zurücksetzen fehlgeschlagen. Sicherung und Zurücksetzen wurden nicht gespeichert; die bisherigen Demo-Fälle bleiben erhalten.") from exc
        return {"backup_id": backup_id, "cases": [public_case(case) for case in restored]}

    def reopen(case):
        case["approval"] = None
        case["status"] = "draft" if case["draft"] else "new"

    @app.get("/api/kis/cases/{identifier}")
    def kis_case(identifier: str):
        case = store.get(identifier)
        return {"case": public_case(case),
                "prepared_medication": None if case["kis"]["medication_released"] else prepared_medication(case)}

    @app.post("/api/kis/cases/{identifier}/release-medication")
    def kis_release_medication(identifier: str, body: HumanConfirmation, background: BackgroundTasks):
        updated = store.mutate(identifier, body.revision, lambda case: release_medication(case, body.reviewer))
        background.add_task(drain_events, store, identifier, config)
        return public_case(updated)

    @app.post("/api/kis/cases/{identifier}/retrieval-fault")
    def kis_fault(identifier: str, body: KisFaultRequest):
        def apply(case):
            case["kis"]["retrieval_fault"] = body.enabled
            audit(case, "Demo-KIS: Abrufstörung " + ("aktiviert" if body.enabled else "beendet"),
                  "Explizite technische Störung für Agentenwerkzeuge. Kein fehlendes Dokument.")
        return public_case(store.mutate(identifier, body.revision, apply))

    @app.post("/api/kis/cases/{identifier}/writeback")
    def kis_writeback(identifier: str, body: HumanConfirmation):
        def apply(case):
            if (case["status"] != "approved" or not case["approval"] or not case["draft"]
                    or case["draft"]["source_version"] != case["source_version"]
                    or any(f["id"] not in case["decisions"] for f in findings(case))):
                raise HTTPException(409, "Nur einen aktuellen, ausdrücklich Demo-freigegebenen Entwurf ins Demo-KIS übernehmen.")
            if case["kis"]["letters"] and case["kis"]["letters"][-1]["sections"] == case["draft"]["sections"]:
                raise HTTPException(409, "Dieser Briefstand ist bereits im Demo-KIS gespeichert.")
            case["kis"]["letters"].append({
                "id": str(uuid4()), "at": now(), "reviewer": body.reviewer,
                "source_version": case["source_version"], "sections": deepcopy(case["draft"]["sections"]),
                "label": "Geprüfter Demo-Entwurf · keine klinische Signatur",
            })
            audit(case, "Entwurf ins Demo-KIS übernommen",
                  "Explizit bestätigte lokale Kopie. Kein echtes KIS, kein Versand, keine klinische Signatur.", body.reviewer)
        return public_case(store.mutate(identifier, body.revision, apply))

    @app.get("/api/cases/{identifier}/agent-runs")
    def agent_runs(identifier: str):
        store.get(identifier)
        return store.runs(identifier)

    @app.post("/api/cases/{identifier}/agent-runs", status_code=202)
    def start_agent(identifier: str, body: Mutation, background: BackgroundTasks):
        if not config.foundry_agent_version:
            raise HTTPException(503, "Foundry-Agent noch nicht eingerichtet.")
        run, snapshot = store.start_run(identifier, body.revision)
        def work():
            run_agent(store, run, snapshot, config)
            current = next((item for item in store.runs(identifier) if item["id"] == run["id"]), None)
            if current:
                store.finish_event(identifier, current)
            drain_events(store, identifier, config)
        background.add_task(work)
        return run

    @app.post("/api/cases/{identifier}/agent-runs/{run_id}/accept")
    def accept_agent(identifier: str, run_id: str, body: HumanConfirmation):
        def apply(case, run):
            if run["status"] != "awaiting_approval" or not run["proposal"]:
                raise HTTPException(409, "Kein offener Agentenvorschlag zur Übernahme.")
            if run["base_revision"] != case["revision"] or run["source_version"] != case["source_version"]:
                raise HTTPException(409, "Fall seit dem Vorschlag geändert. Agentenauftrag neu starten; nichts wurde überschrieben.")
            proposal = run["proposal"]
            try:
                validate_sections([Section(**s) for s in proposal["sections"]], case)
            except ValueError as exc:
                raise HTTPException(422, f"Vorschlag enthält ungültige Quellenreferenzen: {exc}") from exc
            case["draft"] = {key: deepcopy(proposal[key]) for key in [
                "sections", "mode", "model", "usage", "duration_seconds", "source_version", "edited",
            ]}
            case["draft"]["agent_run_id"] = run_id
            reopen(case)
            run["status"] = "applied"
            run["reviewer"] = body.reviewer
            run["events"].append({"at": now(), "kind": "accepted", "title": f"Vorschlag übernommen durch {body.reviewer}"})
            audit(case, "Agentenvorschlag ausdrücklich übernommen",
                  f"Auftrag {run_id} · {len(proposal['changed_section_ids'])} Abschnitte geändert. "
                  "Keine automatische Freigabe. Brief fachlich prüfen.", body.reviewer)
        return public_case(store.commit_run(identifier, run_id, body.revision, apply))

    @app.post("/api/cases/{identifier}/agent-runs/{run_id}/reject")
    def reject_agent(identifier: str, run_id: str, body: HumanConfirmation):
        def apply(case, run):
            if run["status"] != "awaiting_approval":
                raise HTTPException(409, "Kein offener Vorschlag zum Verwerfen.")
            run["status"] = "rejected"
            audit(case, "Agentenvorschlag verworfen", f"Auftrag {run_id}. Brief unverändert.", body.reviewer)
        return public_case(store.commit_run(identifier, run_id, body.revision, apply))

    @app.post("/api/cases/{identifier}/generate")
    def generate_letter(identifier: str, body: GenerateRequest):
        snapshot = store.get(identifier)
        if snapshot["revision"] != body.revision:
            raise HTTPException(409, "Der Fall wurde geändert. Bitte neu laden.")
        draft = generate(snapshot, body.mode, config)

        def apply(case):
            case["draft"] = draft
            reopen(case)
            audit(case, "Entwurf erstellt", f"{body.mode} · {draft['model']} · Quellenstand {case['source_version']}")

        return public_case(store.mutate(identifier, body.revision, apply))

    @app.put("/api/cases/{identifier}/draft")
    def save_draft(identifier: str, body: SaveRequest):
        def apply(case):
            if not case["draft"]:
                raise HTTPException(409, "Zuerst einen Entwurf erstellen.")
            try:
                validate_sections(body.sections, case)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            case["draft"]["sections"] = [s.model_dump() for s in body.sections]
            case["draft"]["edited"] = True
            reopen(case)
            audit(case, "Entwurf bearbeitet", "Manuelle Änderungen gespeichert; Quellenverweise sind Herkunftsbelege, keine automatische Bestätigung des geänderten Textes.")

        return public_case(store.mutate(identifier, body.revision, apply))

    @app.post("/api/cases/{identifier}/findings/{finding_id}")
    def decide(identifier: str, finding_id: str, body: DecisionRequest):
        if not body.note.strip() or not body.reviewer.strip():
            raise HTTPException(422, "Name und nachvollziehbare Begründung sind erforderlich.")

        def apply(case):
            if finding_id not in {f["id"] for f in findings(case)}:
                raise HTTPException(404, "Prüfpunkt nicht gefunden.")
            if finding_id == "conflicting-followup" and case.get("followup_resolution"):
                raise HTTPException(409, "Der Termin ist ausdrücklich bestätigt. Änderungen über die Terminklärung vornehmen.")
            case["decisions"][finding_id] = {
                "decision": body.decision, "note": body.note.strip(),
                "reviewer": body.reviewer.strip(), "at": now(),
            }
            reopen(case)
            audit(case, "Prüfpunkt bewertet", f"{finding_id}: {body.decision} · {body.note.strip()}", body.reviewer.strip())

        return public_case(store.mutate(identifier, body.revision, apply))

    @app.post("/api/cases/{identifier}/resolve-followup")
    def resolve_followup(identifier: str, body: FollowupResolutionRequest, background: BackgroundTasks):
        def apply(case):
            if not any(doc["kind"] == "Termin" for doc in case["documents"]):
                raise HTTPException(409, "Dieser Fall enthält keinen Terminkonflikt.")
            previous_version = case["source_version"]
            extended = has_followup_extensions(case)
            timestamp = now()
            confirmation_id = f"{identifier.lower()}-followup-confirmation-{case['revision'] + 1}"
            confirmation = document(
                confirmation_id, "Bestätigte Terminklärung", "Terminklärung",
                "Menschliche Bestätigung · Demo", timestamp,
                f"Hausärztliche Verlaufskontrolle: gültiger Termin {body.date}. "
                f"Ausdrücklich bestätigt durch {body.reviewer}. Begründung: {body.note} "
                "Diese Bestätigung klärt die früheren Angaben zum 29.10.2026 und 30.10.2026. "
                "Lokale Demo-Eingabe; keine Änderung im KIS oder Terminsystem.",
            )
            case["documents"].append(confirmation)
            case["followup_resolution"] = {
                "date": body.date, "note": body.note, "reviewer": body.reviewer,
                "at": timestamp, "document_id": confirmation_id,
            }
            case["source_version"] += 1
            if case["draft"] and not extended:
                replacement = resolved_followup(case)
                sections = [
                    replacement.model_dump() if s["id"] == "followup" else s
                    for s in case["draft"]["sections"]
                ]
                validate_sections([Section(**s) for s in sections], case)
                case["draft"]["sections"] = sections
                case["draft"]["edited"] = True
                if case["draft"]["source_version"] == previous_version:
                    case["draft"]["source_version"] = case["source_version"]
            previous = case["decisions"].get("conflicting-followup")
            if previous:
                audit(case, "Bisherige Terminbewertung ersetzt",
                      f"{previous['decision']} · {previous['note']}", previous["reviewer"])
            case["decisions"]["conflicting-followup"] = {
                "decision": "acknowledged", "note": f"Gültiger Termin {body.date}. {body.note}",
                "reviewer": body.reviewer, "at": timestamp,
            }
            reopen(case)
            if extended:
                queue_event(case, "appointment_confirmed", "Termin ausdrücklich geklärt – Scan- und Aufgabenkontext erhalten")
            audit(case, "Termin bestätigt – Agentenprüfung erforderlich" if extended else
                  "Termin bestätigt und Nachsorgeabschnitt aktualisiert" if case["draft"] else "Termin vor Entwurfserstellung bestätigt",
                  f"{body.date} · {body.note} · " + (
                      "Bestätigung als neue Quelle gespeichert. Bestehender Entwurf bleibt vollständig erhalten und ist veraltet. "
                      "Keine Scanempfehlung oder Zuständigkeit durch einen Textbaustein ersetzt. Mit Agent erneut prüfen."
                      if extended else
                      "Nur Abschnitt followup ersetzt, übrige Abschnitte unverändert. "
                      "Quellenbasierte Textübernahme ohne neuen KI-Aufruf. Erneut fachlich prüfen."
                      if case["draft"] else
                      "Bestätigung als zusätzliche Quelle gespeichert. Noch kein Brief erstellt. "
                      "Der bestätigte Termin wird beim ersten Entwurf berücksichtigt. Kein KI-Aufruf."
                  ),
                  body.reviewer)

        updated = store.mutate(identifier, body.revision, apply)
        background.add_task(drain_events, store, identifier, config)
        return public_case(updated)

    @app.post("/api/cases/{identifier}/release-report")
    def release_report(identifier: str, body: Mutation, background: BackgroundTasks):
        def apply(case):
            report = next(d for d in case["documents"] if d["kind"] == "Mikrobiologie")
            if report["status"] != "pending":
                raise HTTPException(409, "Der Abschlussbefund ist bereits vorhanden.")
            report["status"] = "available"
            report["date"] = "2026-10-24T14:30:00+02:00"
            report["paragraphs"] = [{
                "id": "p1",
                "text": "Blutkulturen vom 20.10.2026: kein Wachstum im abgeschlossenen Bebrütungszeitraum. Final freigegeben am 24.10.2026 um 14:30 Uhr.",
            }]
            case["source_version"] += 1
            case["decisions"] = {
                key: value for key, value in case["decisions"].items()
                if key == "conflicting-followup" and case.get("followup_resolution")
            }
            reopen(case)
            result_arrived(case)
            audit(case, "Demo-Befund ergänzt", "Vorbereiteter synthetischer Abschlussbefund bereitgestellt. Vorhandener Entwurf bleibt erhalten, ist aber veraltet. Bewertungen wurden zur erneuten Prüfung zurückgesetzt; ausdrückliche Terminklärungen bleiben erhalten.")

        updated = store.mutate(identifier, body.revision, apply)
        background.add_task(drain_events, store, identifier, config)
        return public_case(updated)

    @app.post("/api/cases/{identifier}/approve")
    def approve(identifier: str, body: ApproveRequest):
        if not body.reviewer.strip():
            raise HTTPException(422, "Prüfender Name ist erforderlich.")

        def apply(case):
            if not case["draft"]:
                raise HTTPException(409, "Kein Entwurf vorhanden.")
            if case["draft"]["source_version"] != case["source_version"]:
                raise HTTPException(409, "Quellenstand geändert. Einen neuen Entwurf erstellen und prüfen.")
            if any(f["id"] not in case["decisions"] for f in findings(case)):
                raise HTTPException(409, "Alle offenen Prüfpunkte müssen mit Begründung bewertet werden.")
            case["status"] = "approved"
            case["approval"] = {"reviewer": body.reviewer.strip(), "at": now()}
            audit(case, "Demo-Entwurf freigegeben", "Lokale Demo-Freigabe; keine klinische Signatur und keine Entlassentscheidung.", body.reviewer.strip())

        return public_case(store.mutate(identifier, body.revision, apply))

    @app.get("/api/cases/{identifier}/export")
    def export(identifier: str):
        case = public_case(store.get(identifier))
        if not case["draft"]:
            raise HTTPException(409, "Kein Entwurf zum Export vorhanden.")
        lines = [
            "SYNTHETISCHE DEMO · NICHT ZUR PATIENTENVERSORGUNG",
            "ENTLASSBRIEF-ENTWURF · KEINE KLINISCHE SIGNATUR",
            f"Fall: {case['id']} · {case['name']}",
            f"Aufenthalt: {case['admitted']} – {case['discharge']}",
            f"Modus: {case['draft']['mode']} · Modell: {case['draft']['model']}",
            f"Quellenstand: Entwurf {case['draft']['source_version']} / aktuell {case['source_version']}",
            f"Demo-Status: {case['status']} · manuell bearbeitet: {case['draft']['edited']}",
            "",
        ]
        for section in case["draft"]["sections"]:
            lines.extend([section["title"].upper(), section["text"], "Quellen:"])
            for ref in section["citations"]:
                lines.append(f"- {ref['document_id']} / {ref['paragraph_id']}: {ref['quote']}")
            lines.append("")
        lines.append("QUALITÄTSPRÜFUNG")
        for item in case["findings"]:
            review = item["review"]
            lines.append(f"- {item['title']}: " + (
                f"{review['decision']} · {review['reviewer']} · {review['note']}"
                if review else "OFFEN"
            ))
        lines.append("\nDEMO-PRÜFPROTOKOLL")
        for event in case["audit"]:
            lines.append(f"{event['at']} · {event['reviewer']} · {event['action']}: {event['detail']}")
        return Response(
            "\n".join(lines),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{identifier}-Entwurf.txt"'},
        )

    dist = ROOT / "frontend" / "dist"
    if serve_frontend and (dist / "index.html").is_file() and (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        @app.get("/demo-kis")
        def frontend():
            return FileResponse(dist / "index.html")
    else:
        @app.get("/")
        def frontend_not_built():
            return JSONResponse(
                {"detail": "Frontend fehlt. In frontend: npm install und npm run build ausführen."},
                status_code=503,
            )
    return app


app = create_app()
