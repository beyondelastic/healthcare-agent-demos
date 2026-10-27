import json
from copy import deepcopy
from unittest.mock import patch

import httpx
import pymupdf
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.agent import build_proposal, definition, drain_events
from app.config import Settings
from app.data import CASES, findings, initial_case
from app.followup import confirm_task, followup_context, laboratory_status, queue_event
from app.generation import rehearsal
from app.intake import MAX_FILE_BYTES, analyze, analyze_intake, begin_intake, extraction, operation_url, sample_scan, scan_pages
from app.kis import read_tool
from app.main import create_app
from app.models import AgentResult
from app.store import Store


def service_result(name="Nora Testfall", case_id="DEMO-031"):
    # Small fixture matching the GA response shape verified with real Azure OCR.
    source = "D(1,10,20,70,20,70,35,10,35)"
    return {"analyzerId": "testAnalyzer", "contents": [{
        "kind": "document", "pages": [{"pageNumber": 1, "width": 100, "height": 200}],
        "fields": {
            "PatientName": {"valueString": name, "confidence": 0.95, "source": source},
            "CaseId": {"valueString": case_id, "confidence": 0.94, "source": source},
            "FollowupRecommendation": {"valueString": "Abschlussbefund kontrollieren.", "confidence": 0.61, "source": source},
        },
        "paragraphs": [
            {"content": f"Patientin: {name}. Fallnummer: {case_id}.", "source": source},
            {"content": "Mikrobiologischen Abschlussbefund kontrollieren. Zuständigkeit organisieren.", "source": source},
        ],
    }]}


@pytest.fixture()
def client(tmp_path):
    settings = Settings(database_path=tmp_path / "paper.sqlite3", foundry_agent_version="test",
                        content_understanding_endpoint="https://example.services.ai.azure.com",
                        content_understanding_analyzer="testAnalyzer", _env_file=None)
    with patch("app.main.drain_events"), patch("app.intake.analyze", return_value=service_result()):
        with TestClient(create_app(settings, serve_frontend=False)) as test:
            test.test_config = settings
            yield test


def current(client):
    return client.get("/api/cases/DEMO-031").json()


def post(client, path, **extra):
    return client.post(path, json={"revision": current(client)["revision"],
                                   "reviewer": "Demo-Prüfung", "confirmed": True, **extra})


def upload(client):
    response = client.post(
        f"/api/cases/DEMO-031/intakes?revision={current(client)['revision']}&synthetic_only=true&filename=scan.png",
        content=sample_scan(initial_case("DEMO-031")), headers={"Content-Type": "image/png"})
    assert response.status_code == 202, response.text
    return current(client)["intakes"][-1]


def accept_source(client, monitor=True):
    item = upload(client)
    response = post(client, f"/api/cases/DEMO-031/intakes/{item['id']}/accept",
                    synthetic_only=True, monitor_events=monitor)
    assert response.status_code == 200, response.text
    return item


def proposal(client, action="create"):
    store = client.app.state.store
    case = store.get("DEMO-031")
    run, snapshot = store.start_run(case["id"], case["revision"])
    base = rehearsal(case)
    external = next(doc for doc in case["documents"] if doc.get("intake_id"))
    report = next(doc for doc in case["documents"] if doc["kind"] == "Mikrobiologie")
    parsed = AgentResult(
        sections=[{"id": section.id, "text": section.text,
                   "source_refs": [{"document_id": cite.document_id, "paragraph_id": cite.paragraph_id}
                                   for cite in section.citations]} for section in base.sections],
        summary="Expliziter Testvorschlag.", next_actions=["Menschlich prüfen."],
        followup={"action": action, "title": "Abschlussbefund nachverfolgen", "reason": "Externes Original verlangt Kontrolle.",
                  "role_id": "ward-team", "source_refs": [
                      {"document_id": external["id"], "paragraph_id": "p2"},
                      {"document_id": report["id"], "paragraph_id": "p1"},
                  ]})
    result = build_proposal(parsed, snapshot, {doc["id"] for doc in snapshot["documents"]}, "test", {}, 1, [])
    store.update_run(run["id"], lambda item: item.update(status="awaiting_approval", proposal=result))
    return store.runs(case["id"])[0], parsed


def test_actual_raster_sample_and_bounded_previews():
    case = initial_case("DEMO-031")
    scan = sample_scan(case)
    assert scan.startswith(b"\x89PNG")
    assert len(scan_pages(scan, "image/png")) == 1
    with pymupdf.open() as doc:
        for _ in range(4):
            doc.new_page()
        with pytest.raises(HTTPException, match="ein bis drei"):
            scan_pages(doc.tobytes(), "application/pdf")
    for raw, mime in [(b"", "image/png"), (b"x" * (MAX_FILE_BYTES + 1), "image/png"),
                      (b"<svg/>", "image/png"), (scan, "text/plain")]:
        with pytest.raises(HTTPException):
            scan_pages(raw, mime)


@pytest.mark.parametrize("identifier", ["DEMO-014", "DEMO-027", "DEMO-031"])
def test_sample_consult_report_has_context_without_inventing_a_result_or_owner(identifier):
    rendered = []
    render = pymupdf.Page.get_pixmap

    def capture(page, *args, **kwargs):
        rendered.append(page.get_text())
        assert all(pymupdf.Rect(word[:4]) in page.rect for word in page.get_text("words"))
        return render(page, *args, **kwargs)

    with patch.object(pymupdf.Page, "get_pixmap", capture):
        scan = sample_scan(initial_case(identifier))
    text = " ".join(rendered[0].split())
    assert scan.startswith(b"\x89PNG")
    assert "EXTERNER KONSILBERICHT" in text
    assert "Konsildienst Infektiologie" in text
    assert "Klinikum Beispielstadt (fiktiv)" in text
    assert "Universitätsklinikum Musterstadt (fiktiv)" in text
    assert initial_case(identifier)["name"] in text
    assert identifier in text
    assert "24.10.2026" in text
    assert "Blutkulturen vom 20.10.2026" in text
    assert "Mikrobiologischen Abschlussbefund der Blutkulturen kontrollieren." in text
    assert "Eine verantwortliche Stelle ist in diesem Schreiben nicht benannt." in text
    assert "Dies ist kein Laborbefund." in text
    assert "Laborinformationssystem" in text
    assert "KEINE ECHTEN PATIENTENDATEN" in text
    assert "Keine Therapieempfehlung." in text
    assert "kein Wachstum" not in text


def test_real_response_grounding_and_no_fabricated_confidence():
    parsed = extraction(service_result(), initial_case("DEMO-031"))
    assert parsed["matched"]
    assert parsed["fields"]["PatientName"]["regions"] == [
        {"page": 1, "x": 0.1, "y": 0.1, "width": 0.6, "height": 0.075}]
    assert parsed["fields"]["DocumentDate"]["confidence"] is None
    assert not parsed["fields"]["DocumentDate"]["regions"]
    assert parsed["fields"]["FollowupRecommendation"]["confidence"] == 0.61
    assert len(parsed["paragraphs"]) == 2


@pytest.mark.parametrize("name,identifier", [("Marlene Muster", "DEMO-031"), ("Nora Testfall", "DEMO-014"), ("", "")])
def test_wrong_or_missing_identity_not_associated(name, identifier):
    assert not extraction(service_result(name, identifier), initial_case("DEMO-031"))["matched"]


def test_identity_values_must_exist_in_original_and_have_grounding():
    response = service_result()
    response["contents"][0]["paragraphs"][0]["content"] = "Andere Person."
    assert not extraction(response, initial_case("DEMO-031"))["matched"]
    response = service_result()
    response["contents"][0]["fields"]["CaseId"].pop("source")
    assert not extraction(response, initial_case("DEMO-031"))["matched"]


def test_unreadable_or_too_large_extracted_text_fails_explicitly():
    response = service_result()
    response["contents"][0]["paragraphs"] = []
    with pytest.raises(ValueError, match="Originalabsätze"):
        extraction(response, initial_case("DEMO-031"))
    response["contents"][0]["paragraphs"] = [{"content": "x" * 40001}]
    with pytest.raises(ValueError, match="Zu viel"):
        extraction(response, initial_case("DEMO-031"))


def test_result_polling_must_not_exfiltrate_bearer_token():
    endpoint = "https://example.services.ai.azure.com"
    assert operation_url(endpoint + "/contentunderstanding/analyzerResults/abc", endpoint)
    for location in ["http://example.services.ai.azure.com/contentunderstanding/x",
                     "https://evil.example/contentunderstanding/x",
                     endpoint + "/other", ""]:
        with pytest.raises(ValueError):
            operation_url(location, endpoint)


def test_scan_does_not_become_source_before_confirmation(client):
    before = current(client)
    item = upload(client)
    after = current(client)
    assert item["status"] == "ready" and item["extraction"]["matched"]
    assert after["source_version"] == before["source_version"]
    assert after["documents"] == before["documents"]
    assert not after["event_automation"]["enabled"]
    assert client.get(f"/api/cases/DEMO-031/intakes/{item['id']}/pages/1").content.startswith(b"\x89PNG")
    assert client.get(f"/api/cases/DEMO-014/intakes/{item['id']}/pages/1").status_code == 404
    assert client.get(f"/api/cases/DEMO-031/intakes/{item['id']}/pages/2").status_code == 404


def test_upload_requires_synthetic_consent_and_correct_revision(client):
    scan = sample_scan(initial_case("DEMO-031"))
    for query, expected in [("revision=0&filename=a.png", 422),
                            ("revision=999&filename=a.png&synthetic_only=true", 409)]:
        assert client.post(f"/api/cases/DEMO-031/intakes?{query}", content=scan,
                           headers={"Content-Type": "image/png"}).status_code == expected
    assert not current(client)["intakes"]


def test_repeated_scan_rejected_and_four_document_limit_is_transactional(client):
    item = upload(client)
    assert item["status"] == "ready"
    raw = sample_scan(initial_case("DEMO-031"))
    response = client.post(f"/api/cases/DEMO-031/intakes?revision={current(client)['revision']}&synthetic_only=true&filename=same.png",
                           content=raw, headers={"Content-Type": "image/png"})
    assert response.status_code == 409
    store = client.app.state.store
    case = store.get("DEMO-031")
    store.mutate(case["id"], case["revision"], lambda data: data["intakes"].extend(
        [{**deepcopy(item), "id": str(index), "sha256": str(index)} for index in range(3)]))
    case = store.get(case["id"])
    with pytest.raises(HTTPException, match="Maximal vier"):
        store.add_intake(case["id"], case["revision"], {**item, "id": "fifth"}, raw, "image/png", [])
    assert len(store.get(case["id"])["intakes"]) == 4


def test_source_confirmation_revokes_approval_not_historical_copy(client):
    store = client.app.state.store
    case = store.get("DEMO-031")
    def seed(data):
        sections = [section.model_dump() for section in rehearsal(data).sections]
        data["draft"] = {"sections": sections, "source_version": data["source_version"]}
        data.update(status="approved", approval={"reviewer": "Alt-Prüfung", "at": "old"})
        data["kis"]["letters"].append({"id": "old", "sections": deepcopy(sections), "source_version": data["source_version"]})
    store.mutate(case["id"], case["revision"], seed)
    before = current(client)
    item = accept_source(client)
    after = current(client)
    assert after["approval"] is None and after["status"] == "draft"
    assert after["draft"] == before["draft"]
    assert after["kis"]["letters"] == before["kis"]["letters"]
    assert after["source_version"] == before["source_version"] + 1
    doc = after["documents"][-1]
    assert doc["intake_id"] == item["id"]
    assert doc["paragraphs"][1]["text"] == item["extraction"]["paragraphs"][1]["text"]
    assert after["event_automation"]["events"][-1]["status"] == "queued"
    assert post(client, f"/api/cases/DEMO-031/intakes/{item['id']}/accept", synthetic_only=True, monitor_events=True).status_code == 409


def test_wrong_patient_source_cannot_be_confirmed(client):
    with patch("app.intake.analyze", return_value=service_result("Wrong Person")):
        item = upload(client)
    assert not item["extraction"]["matched"]
    assert post(client, f"/api/cases/DEMO-031/intakes/{item['id']}/accept", synthetic_only=True, monitor_events=True).status_code == 422
    assert not current(client)["event_automation"]["events"]


def test_azure_failure_is_persistent_visible_and_retry_is_explicit(client):
    with patch("app.intake.analyze", side_effect=httpx.ConnectError("test service unavailable")):
        item = upload(client)
    assert item["status"] == "failed" and item["error"]
    assert current(client)["source_version"] == 1
    response = post(client, f"/api/cases/DEMO-031/intakes/{item['id']}/retry")
    assert response.status_code == 202
    assert current(client)["intakes"][0]["status"] == "ready"


def test_task_requires_current_proposal_role_consent_and_no_duplicates(client):
    accept_source(client)
    run, _ = proposal(client)
    path = f"/api/cases/DEMO-031/agent-runs/{run['id']}/task"
    assert post(client, path, role_id="invented-role").status_code == 422
    assert post(client, path, role_id="ward-team", confirmed=False).status_code == 422
    response = post(client, path, role_id="ward-team")
    assert response.status_code == 200, response.text
    case = current(client)
    assert len(case["followup_tasks"]) == 1
    assert case["followup_tasks"][0]["status"] == "waiting_for_result"
    assert case["documents"][-1]["kind"] == "Aufgabenbestätigung"
    assert case["documents"][-1]["id"] in json.dumps(case)
    assert case["source_version"] == 3
    assert client.app.state.store.runs(case["id"])[0]["status"] == "rejected"
    assert post(client, path, role_id="ward-team").status_code == 409
    finding = next(item for item in case["findings"] if item["type"] == "pending")
    assert "Stationsteam" in finding["description"] and not finding.get("resolved")


def test_task_proposal_is_invalidated_by_source_changes(client):
    accept_source(client)
    run, _ = proposal(client)
    assert client.post("/api/cases/DEMO-031/release-report", json={"revision": current(client)["revision"]}).status_code == 200
    assert post(client, f"/api/cases/DEMO-031/agent-runs/{run['id']}/task", role_id="ward-team").status_code == 409
    assert not current(client)["followup_tasks"]


def test_lab_result_queues_real_recheck_but_not_task_completion(client):
    accept_source(client)
    run, _ = proposal(client)
    assert post(client, f"/api/cases/DEMO-031/agent-runs/{run['id']}/task", role_id="ward-team").status_code == 200
    response = client.post("/api/cases/DEMO-031/release-report", json={"revision": current(client)["revision"]})
    assert response.status_code == 200
    case = current(client)
    assert case["followup_tasks"][0]["status"] == "awaiting_review"
    assert case["event_automation"]["events"][-1]["kind"] == "laboratory_result"
    task_id = case["followup_tasks"][0]["id"]
    assert post(client, f"/api/cases/DEMO-031/tasks/{task_id}/complete").status_code == 409
    store = client.app.state.store
    store.mutate(case["id"], case["revision"], lambda data: data.update(draft={"source_version": data["source_version"]}))
    assert post(client, f"/api/cases/DEMO-031/tasks/{task_id}/complete").status_code == 200
    completed = current(client)["followup_tasks"][0]
    assert completed["status"] == "completed" and completed["completed_by"] == "Demo-Prüfung"


def test_laboratory_and_task_tools_are_case_scoped_read_only(client):
    case = client.app.state.store.get("DEMO-031")
    lab = read_tool(case, "get_laboratory_status", {})
    context = read_tool(case, "get_followup_context", {})
    assert lab["status"] == "pending" and "paragraphs" not in lab
    assert not context["tasks"] and len(context["available_roles"]) == 2
    assert context["case_id"] == case["id"]
    case["kis"]["retrieval_fault"] = True
    for tool in ["get_laboratory_status", "get_followup_context"]:
        with pytest.raises(HTTPException):
            read_tool(case, tool, {})


def test_event_claim_coalesces_and_waits_for_active_job(client):
    store = client.app.state.store
    case = store.get("DEMO-031")
    run, _ = store.start_run(case["id"], case["revision"])
    def publish(data):
        data["event_automation"]["enabled"] = True
        queue_event(data, "one", "first")
        queue_event(data, "two", "second")
    store.mutate(case["id"], case["revision"], publish)
    assert store.start_event_run(case["id"]) is None
    store.update_run(run["id"], lambda item: item.update(status="failed"))
    run, snapshot = store.start_event_run(case["id"])
    assert run["trigger"]["title"] == "second" and run["base_revision"] == snapshot["revision"]
    events = store.get(case["id"])["event_automation"]["events"]
    assert [item["status"] for item in events] == ["superseded", "running"]
    assert store.start_event_run(case["id"]) is None
    store.update_run(run["id"], lambda item: item.update(status="awaiting_approval"))
    completed = store.runs(case["id"])[0]
    store.finish_event(case["id"], completed)
    assert store.get(case["id"])["revision"] == snapshot["revision"]
    assert store.get(case["id"])["event_automation"]["events"][-1]["status"] == "ready"


def test_manual_start_claims_pending_event_without_double_inference(client):
    accept_source(client)
    store = client.app.state.store
    case = store.get("DEMO-031")
    run, _ = store.start_run(case["id"], case["revision"])
    assert run["trigger"]["kind"] == "external_document"
    assert not any(item["status"] == "queued" for item in store.get(case["id"])["event_automation"]["events"])
    store.update_run(run["id"], lambda item: item.update(status="awaiting_approval"))
    assert store.start_event_run(case["id"]) is None


def test_disabling_automation_prevents_queued_calls(client):
    accept_source(client)
    assert post(client, "/api/cases/DEMO-031/automation", enabled=False).status_code == 200
    store = client.app.state.store
    assert store.start_event_run("DEMO-031") is None
    assert current(client)["event_automation"]["events"][-1]["status"] == "superseded"


def test_restart_marks_pending_work_failed_without_silent_replay(client):
    accept_source(client)
    store = client.app.state.store
    store.start_event_run("DEMO-031")
    store.recover_runs()
    case = current(client)
    assert case["event_automation"]["events"][-1]["status"] == "failed"
    assert store.runs(case["id"])[0]["status"] == "failed"
    assert store.start_event_run(case["id"]) is None


def test_reset_blocks_late_intake_and_agent_resurrection(client):
    item = accept_source(client)
    store = client.app.state.store
    run, snapshot = store.start_event_run("DEMO-031")
    revisions = {identifier: store.get(identifier)["revision"] for identifier in CASES}
    backup, _ = store.reset(revisions)
    assert backup
    assert current(client)["intakes"] == [] and current(client)["followup_tasks"] == []
    assert store.runs("DEMO-031") == []
    assert client.get(f"/api/cases/DEMO-031/intakes/{item['id']}/pages/1").status_code == 404
    with pytest.raises(HTTPException):
        store.update_intake("DEMO-031", item["id"], lambda entry: entry.update(status="ready"))
    store.finish_event("DEMO-031", {**run, "status": "failed"})
    assert not store.get("DEMO-031")["event_automation"]["events"]
    assert store.get("DEMO-031")["revision"] > snapshot["revision"]
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM intake_files").fetchone()[0] == 1
        assert item["id"] in db.execute("SELECT state FROM demo_backups WHERE id=?", (backup,)).fetchone()[0]


def test_new_remote_schema_requires_nullable_followup_but_old_results_remain_readable():
    schema = definition(Settings(foundry_model="test", _env_file=None)).text["format"]["schema"]
    assert "followup" in schema["required"]
    assert "default" not in schema["properties"]["followup"]


def test_task_provenance_rejects_fabricated_references(client):
    accept_source(client)
    run, parsed = proposal(client)
    case = client.app.state.store.get("DEMO-031")
    parsed.followup.source_refs[0].paragraph_id = "invented"
    with pytest.raises(ValueError, match="Originalreferenz"):
        build_proposal(parsed, case, {doc["id"] for doc in case["documents"]}, "test", {}, 1, [])


def test_confirmed_owner_cannot_be_omitted_from_new_letter_evidence(client):
    accept_source(client)
    run, parsed = proposal(client)
    assert post(client, f"/api/cases/DEMO-031/agent-runs/{run['id']}/task", role_id="ward-team").status_code == 200
    case = client.app.state.store.get("DEMO-031")
    parsed.followup.action = "none"
    with pytest.raises(ValueError, match="NEUE menschlich bestätigte Zuständigkeit"):
        build_proposal(parsed, case, {doc["id"] for doc in case["documents"]}, "test", {}, 1, [])


def test_event_worker_rechecks_new_publication_after_active_run(client):
    accept_source(client)
    store = client.app.state.store
    versions = []
    def worker(db, run, snapshot, settings):
        versions.append(snapshot["revision"])
        if len(versions) == 1:
            db.mutate(snapshot["id"], snapshot["revision"],
                      lambda case: queue_event(case, "laboratory_result", "Noch eine neue Quelle"))
            db.update_run(run["id"], lambda item: item.update(status="failed", error="Quellen geändert"))
        else:
            db.update_run(run["id"], lambda item: item.update(status="awaiting_approval"))
    with patch("app.agent.run_agent", side_effect=worker):
        drain_events(store, "DEMO-031", client.test_config)
    assert len(versions) == 2 and versions[1] > versions[0]
    assert [item["status"] for item in current(client)["event_automation"]["events"]] == ["failed", "ready"]
    assert store.start_event_run("DEMO-031") is None


def test_interrupted_analysis_requires_explicit_retry(client):
    store = client.app.state.store
    case = store.get("DEMO-031")
    updated = begin_intake(store, case, sample_scan(case), "image/png", "interrupted.png")
    assert updated["intakes"][0]["status"] == "analyzing"
    store.recover_runs()
    case = store.get(case["id"])
    assert case["intakes"][0]["status"] == "failed" and case["intakes"][0]["error"]
    assert case["source_version"] == 1


def test_additive_migration_preserves_existing_presenter_state(client):
    store = client.app.state.store
    case = store.get("DEMO-031")
    case.update(revision=20, status="approved", approval={"at": "old", "reviewer": "Existing"})
    case["kis"]["letters"] = [{"id": "existing-copy", "sections": []}]
    for key in ["intakes", "followup_tasks", "event_automation"]:
        case.pop(key)
    with store.connection() as db:
        db.execute("UPDATE cases SET state=? WHERE id=?", (json.dumps(case), case["id"]))
    migrated = Store(store.path).get(case["id"])
    for key, value in case.items():
        assert migrated[key] == value
    assert migrated["intakes"] == [] and migrated["followup_tasks"] == []
    assert migrated["event_automation"] == {"enabled": False, "events": []}


@pytest.mark.parametrize("mode", ["foundry", "rehearsal"])
def test_legacy_generation_cannot_discard_extended_context(client, mode):
    accept_source(client)
    response = client.post("/api/cases/DEMO-031/generate",
                           json={"revision": current(client)["revision"], "mode": mode})
    assert response.status_code == 409 and "Agentenworkflow" in response.json()["detail"]
    assert current(client)["draft"] is None


def test_appointment_confirmation_does_not_replace_scan_or_task_context(client):
    store = client.app.state.store
    def seed(case):
        case["draft"] = {
            "sections": [section.model_dump() for section in rehearsal(case).sections],
            "source_version": case["source_version"], "edited": False,
        }
        case["documents"].append({
            "id": "external-appointment-test", "kind": "Fremddokument", "title": "Geprüfte Empfehlung",
            "system": "Explizite Testquelle", "date": "2026-10-24", "status": "available",
            "intake_id": "fixture", "paragraphs": [{"id": "p1", "text": "Befund nachverfolgen."}],
        })
        case["source_version"] += 1
        case["event_automation"]["enabled"] = True
    store.mutate("DEMO-014", 0, seed)
    before = store.get("DEMO-014")
    response = client.post("/api/cases/DEMO-014/resolve-followup", json={
        "revision": before["revision"], "date": "30.10.2026", "note": "Explizite Terminprüfung",
        "reviewer": "Demo-Prüfung", "confirmed": True,
    })
    assert response.status_code == 200, response.text
    case = store.get("DEMO-014")
    assert case["draft"] == before["draft"]
    assert case["draft"]["source_version"] < case["source_version"]
    assert case["event_automation"]["events"][-1]["kind"] == "appointment_confirmed"
    assert case["followup_resolution"]["date"] == "30.10.2026"
    assert any(doc["id"] == "external-appointment-test" for doc in case["documents"])


def test_medication_publication_also_queues_enabled_event_check(client):
    accept_source(client)
    response = post(client, "/api/kis/cases/DEMO-031/release-medication")
    assert response.status_code == 200
    assert current(client)["event_automation"]["events"][-1]["kind"] == "medication_released"
