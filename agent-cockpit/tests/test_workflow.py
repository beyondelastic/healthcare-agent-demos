import pytest
from fastapi.testclient import TestClient

import workflow
from app import app
from case import SECTIONS


@pytest.fixture(autouse=True)
def clean():
    workflow.reset()
    yield
    workflow.reset()


def draft(medication_text="Plan noch in Prüfung.", medication_sources=(), points=None):
    sections = [{"id": sid, "text": f"Text {sid}", "source_ids": ["kis-aufnahme"]} for sid in SECTIONS]
    for section in sections:
        if section["id"] == "medication":
            section.update(text=medication_text, source_ids=list(medication_sources))
    if points is None:
        points = [{"kind": "pending", "title": "Histologie", "detail": "ausstehend", "section_id": "findings", "source_ids": ["patho-histologie"]},
                  {"kind": "unreleased", "title": "Medikationsplan", "detail": "in Prüfung", "section_id": "medication", "source_ids": ["med-entlassplan"]}]
    return {"summary": "s", "sections": sections, "open_points": points}


def test_unreleased_plan_content_is_never_returned():
    result = workflow.read_source("med-entlassplan")
    assert result["status"] == "unreleased" and result["content"] is None
    assert "med-entlassplan" not in workflow.STATE["stats"]["sources_read"]
    assert workflow.read_source("unknown")["ok"] is False


def test_valid_draft_passes_and_citing_unreleased_plan_fails():
    read = {s["id"] for s in workflow.STATE["sources"]}
    assert workflow.validate_draft(draft(), read, read) == []
    bad = draft("Pantoprazol 20 mg", ["med-entlassplan"])
    problems = workflow.validate_draft(bad, read, read)
    assert any("zitiert nicht gelesene" in p for p in problems) and any("Inhalte des nicht freigegebenen Plans" in p for p in problems)


def test_unread_sources_missing_sections_and_dropped_open_points_fail():
    read = {s["id"] for s in workflow.STATE["sources"]}
    assert any("nicht gelesen" in p for p in workflow.validate_draft(draft(), read - {"lis-labor"}, read))
    incomplete = draft()
    incomplete["sections"] = incomplete["sections"][:5]
    assert any("sechs Abschnitte" in p for p in workflow.validate_draft(incomplete, read, read))
    assert any("patho-histologie" in p for p in workflow.validate_draft(draft(points=[]), read, read))


def test_released_plan_must_close_its_open_point():
    from case import release_medication
    release_medication(workflow.STATE["sources"])
    read = {s["id"] for s in workflow.STATE["sources"]}
    problems = workflow.validate_draft(draft("Ibuprofen 400 mg", ["med-entlassplan"]), read, read)
    assert any("erledigt" in p for p in problems)
    fixed = draft("Ibuprofen 400 mg", ["med-entlassplan"], points=[draft()["open_points"][0]])
    assert workflow.validate_draft(fixed, read, read) == []


def test_diff_marks_only_changed_sections():
    before = {"sections": [{"id": sid, "text": f"Text {sid}", "source_ids": []} for sid in SECTIONS]}
    after = [dict(s) for s in before["sections"]]
    after[4] = {**after[4], "text": "Neu"}
    result = workflow._diff_sections(before, after)
    assert [s["id"] for s in result if s["changed"]] == ["medication"]
    assert next(s for s in result if s["id"] == "medication")["previous_text"] == "Text medication"


def test_event_and_approval_are_guarded():
    with pytest.raises(RuntimeError):
        workflow.approve("Dr. Demo")
    workflow.release_medication_event(background=False)  # no draft yet: releases plan, starts nothing
    assert workflow.snapshot()["busy"] is False
    with pytest.raises(RuntimeError):
        workflow.release_medication_event(background=False)
    workflow.STATE.update(phase="ready", draft={"version": 1, "sections": [], "open_points": [], "summary": ""})
    workflow.approve("Dr. Demo")
    assert workflow.snapshot()["approval"]["by"] == "Dr. Demo"
    with pytest.raises(RuntimeError):
        workflow.prepare(background=False)


def test_dispatch_only_after_approval():
    with pytest.raises(RuntimeError):
        workflow.dispatch("kim")
    workflow.STATE.update(phase="ready", draft={"version": 1, "sections": [], "open_points": [], "summary": ""})
    workflow.approve("Dr. Demo")
    for channel in ("kim", "epa", "print"):
        workflow.dispatch(channel)
    state = workflow.snapshot()
    assert set(state["dispatch"]) == {"kim", "epa", "print"}
    assert any("KIM" in e["title"] and "Simulation" in e["title"] for e in state["events"])
    with pytest.raises(RuntimeError):
        workflow.dispatch("fax")


def test_qr_points_to_voice_assistant():
    response = TestClient(app).get("/api/qr.svg")
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["x-target-url"].endswith("/patient?brief=DEMO-EB-2026-1106")


def test_api_requires_confirmation_and_hides_unreleased_text():
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.post("/api/reset").json()["agents"]["writer"]
    assert client.get("/api/sources/med-entlassplan").json()["text"] is None
    assert client.get("/api/sources/kis-aufnahme").json()["text"]
    assert client.get("/api/sources/nope").status_code == 404
    workflow.STATE.update(phase="ready", draft={"version": 1, "sections": [], "open_points": [], "summary": ""})
    assert client.post("/api/approve", json={"physician": "Dr. Demo", "confirmed": False}).status_code == 422
    assert client.post("/api/approve", json={"physician": "Dr. Demo", "confirmed": True}).json()["agents"]["reviewer"]
    assert client.post("/api/approve", json={"physician": "Dr. Demo", "confirmed": True}).status_code == 409
    assert client.post("/api/reset").json()["phase"] == "idle"
