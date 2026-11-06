from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import patch

import pytest
from azure.core.exceptions import AzureError
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.data import CASES, initial_case
from app.generation import attach_evidence, rehearsal, validate_sections
from app.main import create_app
from app.models import EvidenceReference, GeneratedLetter, ModelLetter, ModelSection


@pytest.fixture()
def client(tmp_path):
    config = Settings(database_path=tmp_path / "test.sqlite3", foundry_model="", _env_file=None)
    with TestClient(create_app(config, serve_frontend=False)) as result:
        yield result


def case(client, identifier="DEMO-014"):
    response = client.get(f"/api/cases/{identifier}")
    assert response.status_code == 200
    return response.json()


def generate(client, identifier="DEMO-014"):
    response = client.post(
        f"/api/cases/{identifier}/generate",
        json={"revision": case(client, identifier)["revision"], "mode": "rehearsal"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_case_inventory_and_synthetic_boundary(client):
    assert client.get("/api/health").json()["synthetic_only"] is True
    assert len(client.get("/api/cases").json()) == 3
    assert case(client)["synthetic"] is True
    assert client.get("/api/cases/unknown").status_code == 404


@pytest.mark.parametrize("identifier", ["DEMO-014", "DEMO-027", "DEMO-031"])
def test_rehearsal_has_six_sections_and_real_source_quotes(client, identifier):
    current = generate(client, identifier)
    letter = GeneratedLetter(sections=current["draft"]["sections"])
    validate_sections(letter.sections, current)
    assert current["draft"]["mode"] == "rehearsal"
    assert current["draft"]["usage"] is None
    assert len(letter.sections) == 6
    assert all(section.citations for section in letter.sections)


def test_known_findings_and_temporal_lab_values(client):
    current = case(client)
    assert {f["id"] for f in current["findings"]} == {"pending-microbiology", "conflicting-followup"}
    assert case(client, "DEMO-027")["findings"] == []
    assert {f["id"] for f in case(client, "DEMO-031")["findings"]} == {"pending-microbiology", "missing-medication"}


def test_findings_map_to_relevant_letter_sections(client):
    mappings = {f["id"]: f["section_ids"] for f in case(client)["findings"]}
    assert mappings == {"conflicting-followup": ["followup"],
                        "pending-microbiology": ["findings", "followup"]}
    nora = {f["id"]: f["section_ids"] for f in case(client, "DEMO-031")["findings"]}
    assert nora["missing-medication"] == ["medication"]


@pytest.mark.parametrize("decision", ["acknowledged", "rejected"])
def test_review_does_not_remove_section_warning_mapping(client, decision):
    response = client.post("/api/cases/DEMO-031/findings/pending-microbiology", json={
        "revision": 0, "decision": decision, "reviewer": "Demo",
        "note": "Bewertung dokumentiert, Befund ist weiterhin ausstehend.",
    })
    assert response.status_code == 200
    pending = next(f for f in response.json()["findings"] if f["id"] == "pending-microbiology")
    assert pending["section_ids"] == ["findings", "followup"]
    assert not pending.get("resolved")
    assert pending["review"]["decision"] == decision


def test_missing_medication_never_inferred_from_other_records(client):
    current = generate(client, "DEMO-031")
    text = next(s["text"] for s in current["draft"]["sections"] if s["id"] == "medication")
    assert "kein freigegebener Entlassmedikationsplan" in text
    assert "Amlodipin" not in text


def test_live_mode_never_silently_falls_back(client):
    response = client.post("/api/cases/DEMO-014/generate", json={"revision": 0, "mode": "foundry"})
    assert response.status_code == 503
    assert case(client)["draft"] is None
    assert case(client)["audit"] == []


def test_revision_conflicts_do_not_overwrite_saved_draft(client):
    generate(client)
    response = client.post("/api/cases/DEMO-014/release-report", json={"revision": 0})
    assert response.status_code == 409
    assert case(client)["source_version"] == 1


def test_invalid_citation_rejected_without_writes(client):
    current = generate(client)
    sections = current["draft"]["sections"]
    sections[0]["citations"][0]["quote"] = "Not present in the original source."
    response = client.put("/api/cases/DEMO-014/draft", json={"revision": current["revision"], "sections": sections})
    assert response.status_code == 422
    assert case(client)["revision"] == current["revision"]


def test_cross_patient_citation_rejected(client):
    current = generate(client)
    sections = current["draft"]["sections"]
    sections[0]["citations"][0]["document_id"] = "demo-027-admission"
    assert client.put("/api/cases/DEMO-014/draft", json={"revision": current["revision"], "sections": sections}).status_code == 422


def test_generated_invalid_evidence_is_not_persisted(client):
    bad = rehearsal(case(client))
    bad.sections[0].citations[0].quote = "fabricated quote"
    with patch("app.generation.rehearsal", return_value=bad):
        response = client.post("/api/cases/DEMO-014/generate", json={"revision": 0, "mode": "rehearsal"})
    assert response.status_code == 502
    assert case(client)["draft"] is None


def test_new_report_preserves_text_but_requires_regeneration(client):
    current = generate(client)
    original = current["draft"]["sections"]
    original[0]["text"] += " Manuelle Demo-Ergänzung."
    current = client.put("/api/cases/DEMO-014/draft", json={"revision": current["revision"], "sections": original}).json()
    current = client.post("/api/cases/DEMO-014/release-report", json={"revision": current["revision"]}).json()
    assert current["draft"]["sections"] == original
    assert current["source_version"] == 2
    assert current["draft"]["source_version"] == 1
    assert len(current["findings"]) == 1
    response = client.post("/api/cases/DEMO-014/approve", json={"revision": current["revision"], "reviewer": "Demo", "confirmed": True})
    assert response.status_code == 409
    assert client.post("/api/cases/DEMO-014/release-report", json={"revision": current["revision"]}).status_code == 409


def test_approval_requires_review_and_confirmation(client):
    current = generate(client)
    payload = {"revision": current["revision"], "reviewer": "Demo", "confirmed": True}
    assert client.post("/api/cases/DEMO-014/approve", json=payload).status_code == 409
    payload["confirmed"] = False
    assert client.post("/api/cases/DEMO-014/approve", json=payload).status_code == 422
    for finding in current["findings"]:
        response = client.post(f"/api/cases/DEMO-014/findings/{finding['id']}", json={
            "revision": current["revision"], "reviewer": "Demo-Prüfer",
            "decision": "acknowledged", "note": "Bleibt im Demo-Entwurf ausdrücklich offen.",
        })
        assert response.status_code == 200
        current = response.json()
    response = client.post("/api/cases/DEMO-014/approve", json={
        "revision": current["revision"], "reviewer": "Demo-Prüfer", "confirmed": True,
    })
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["approval"]["reviewer"] == "Demo-Prüfer"


def test_edits_invalidate_approval(client):
    current = generate(client, "DEMO-027")
    current = client.post("/api/cases/DEMO-027/approve", json={"revision": current["revision"], "reviewer": "Demo", "confirmed": True}).json()
    sections = current["draft"]["sections"]
    sections[0]["text"] += " Geprüft."
    current = client.put("/api/cases/DEMO-027/draft", json={"revision": current["revision"], "sections": sections}).json()
    assert current["approval"] is None
    assert current["status"] == "draft"
    assert current["draft"]["edited"] is True


def test_no_export_before_generation_and_watermark_afterwards(client):
    assert client.get("/api/cases/DEMO-014/export").status_code == 409
    generate(client)
    response = client.get("/api/cases/DEMO-014/export")
    assert "SYNTHETISCHE DEMO" in response.text
    assert "KEINE KLINISCHE SIGNATUR" in response.text
    assert "Quellen:" in response.text
    assert "QUALITÄTSPRÜFUNG" in response.text
    assert "rehearsal" in response.text


def test_state_persists_across_application_restart(client):
    current = generate(client)
    config = Settings(database_path=client.app.state.store.path, foundry_model="", _env_file=None)
    with TestClient(create_app(config, serve_frontend=False)) as reopened:
        assert case(reopened)["draft"] == current["draft"]
        assert case(reopened)["audit"] == current["audit"]


def test_concurrent_writes_only_one_succeeds(client):
    current = generate(client)
    store = client.app.state.store
    def update(_):
        try:
            store.mutate(current["id"], current["revision"], lambda c: c.update(status="draft"))
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, range(2))) == [200, 409]


def test_unknown_sources_and_empty_sections_rejected(client):
    current = generate(client)
    sections = current["draft"]["sections"]
    sections[0]["text"] = ""
    assert client.put("/api/cases/DEMO-014/draft", json={"revision": current["revision"], "sections": sections}).status_code == 422


def test_demo_records_are_not_mixed_by_edit(client):
    first = generate(client)
    second = generate(client, "DEMO-027")
    first["draft"]["sections"][0]["text"] = "Nur in DEMO-014 geändert."
    client.put("/api/cases/DEMO-014/draft", json={"revision": first["revision"], "sections": first["draft"]["sections"]})
    assert case(client, "DEMO-027")["draft"] == second["draft"]


def test_live_service_failure_has_no_rehearsal_fallback(tmp_path):
    config = Settings(database_path=tmp_path / "failure.sqlite3", foundry_model="test-deployment", _env_file=None)
    with TestClient(create_app(config, serve_frontend=False)) as client:
        with patch("app.generation.AIProjectClient", side_effect=AzureError("unavailable")):
            response = client.post("/api/cases/DEMO-014/generate", json={"revision": 0, "mode": "foundry"})
        assert response.status_code == 502
        assert case(client)["draft"] is None
        assert case(client)["revision"] == 0


def test_blank_review_note_and_reviewer_rejected(client):
    current = generate(client)
    response = client.post("/api/cases/DEMO-014/findings/conflicting-followup", json={
        "revision": current["revision"], "reviewer": "   ", "note": "         ",
        "decision": "acknowledged",
    })
    assert response.status_code == 422


def test_missing_citation_and_wrong_section_order_rejected(client):
    current = generate(client)
    sections = current["draft"]["sections"]
    sections[0]["citations"] = []
    assert client.put("/api/cases/DEMO-014/draft", json={"revision": current["revision"], "sections": sections}).status_code == 422
    sections = current["draft"]["sections"]
    sections.reverse()
    assert client.put("/api/cases/DEMO-014/draft", json={"revision": current["revision"], "sections": sections}).status_code == 422


def test_model_references_are_expanded_from_trusted_originals(client):
    current = case(client)
    template = rehearsal(current)
    parsed = ModelLetter(sections=[
        ModelSection(id=s.id, text=s.text, source_refs=[
            EvidenceReference(document_id=c.document_id, paragraph_id=c.paragraph_id)
            for c in s.citations
        ]) for s in template.sections
    ])
    expanded = attach_evidence(parsed, current)
    validate_sections(expanded.sections, current)
    assert expanded == template
    parsed.sections[0].source_refs[0].paragraph_id = "invented-paragraph"
    with pytest.raises(ValueError, match="unbekannten Quellenabsatz"):
        attach_evidence(parsed, current)


def resolve_followup(client, current, date="30.10.2026", **overrides):
    payload = {
        "revision": current["revision"], "date": date, "reviewer": "Demo-Prüfer",
        "note": "Termin nach organisatorischer Rücksprache ausdrücklich bestätigt.",
        "confirmed": True,
    } | overrides
    return client.post(f"/api/cases/{current['id']}/resolve-followup", json=payload)


@pytest.mark.parametrize("date", ["29.10.2026", "30.10.2026"])
def test_term_confirmation_only_changes_followup_and_preserves_originals(client, date):
    current = generate(client)
    sections = current["draft"]["sections"]
    sections[0]["text"] += " Manuelle Ergänzung bleibt erhalten."
    sections[-1]["text"] += " Alte manuelle Nachsorgeergänzung."
    current = client.put("/api/cases/DEMO-014/draft", json={
        "revision": current["revision"], "sections": sections,
    }).json()
    original_docs = current["documents"]
    response = resolve_followup(client, current, date)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["draft"]["sections"][:-1] == sections[:-1]
    followup = updated["draft"]["sections"][-1]
    assert date in followup["text"]
    assert ("29.10.2026" if date == "30.10.2026" else "30.10.2026") not in followup["text"]
    assert "Alte manuelle" not in followup["text"]
    assert "Abschlussbefund noch ausstehend" in followup["text"]
    assert updated["documents"][:-1] == original_docs
    assert updated["source_version"] == updated["draft"]["source_version"] == 2
    assert updated["followup_resolution"]["date"] == date
    assert updated["draft"]["edited"] is True
    validate_sections(GeneratedLetter(sections=updated["draft"]["sections"]).sections, updated)
    conflict = next(f for f in updated["findings"] if f["id"] == "conflicting-followup")
    assert conflict["resolved"] is True
    assert conflict["review"]["reviewer"] == "Demo-Prüfer"
    assert updated["audit"][-1]["action"] == "Termin bestätigt und Nachsorgeabschnitt aktualisiert"
    export = client.get("/api/cases/DEMO-014/export").text
    assert updated["followup_resolution"]["document_id"] in export
    assert "ohne neuen KI-Aufruf" in export


def test_term_confirmation_survives_generation_and_late_report(client):
    current = resolve_followup(client, generate(client)).json()
    current = client.post("/api/cases/DEMO-014/release-report", json={"revision": current["revision"]}).json()
    assert current["decisions"]["conflicting-followup"]
    current = generate(client)
    followup = current["draft"]["sections"][-1]
    assert "30.10.2026" in followup["text"]
    assert "29.10.2026" not in followup["text"]
    assert "kein Wachstum" in followup["text"]
    assert "ausstehend" not in followup["text"]
    assert current["draft"]["source_version"] == current["source_version"]
    assert next(f for f in current["findings"] if f["id"] == "conflicting-followup")["resolved"]


def test_term_confirmation_does_not_mark_other_stale_sections_current(client):
    current = generate(client)
    current = client.post("/api/cases/DEMO-014/release-report", json={"revision": current["revision"]}).json()
    current = resolve_followup(client, current).json()
    assert current["source_version"] == 3
    assert current["draft"]["source_version"] == 1
    response = client.post("/api/cases/DEMO-014/approve", json={
        "revision": current["revision"], "reviewer": "Demo", "confirmed": True,
    })
    assert response.status_code == 409


def test_term_confirmation_requires_valid_input_case_and_revision(client):
    current = generate(client)
    for overrides in [
        {"confirmed": False}, {"date": "31.10.2026"}, {"reviewer": "  "},
        {"note": "        "}, {"note": "fsdfg"}, {"note": "1234567"},
        {"note": " 1234567 "},
    ]:
        assert resolve_followup(client, current, **overrides).status_code == 422
    assert case(client)["revision"] == current["revision"]
    assert resolve_followup(client, current, revision=0).status_code == 409
    assert resolve_followup(client, generate(client, "DEMO-027")).status_code == 409
    assert resolve_followup(client, case(client, "DEMO-031")).status_code == 409


@pytest.mark.parametrize("date", ["29.10.2026", "30.10.2026"])
def test_confirmation_before_first_draft_becomes_a_source_not_a_letter(client, date):
    original = case(client)
    response = resolve_followup(client, original, date, note="12345678")
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["draft"] is None
    assert current["status"] == "new"
    assert current["approval"] is None
    assert current["source_version"] == 2
    assert current["documents"][:-1] == original["documents"]
    assert current["followup_resolution"]["date"] == date
    assert current["audit"][-1]["action"] == "Termin vor Entwurfserstellung bestätigt"
    assert "Kein KI-Aufruf" in current["audit"][-1]["detail"]
    conflict = next(f for f in current["findings"] if f["id"] == "conflicting-followup")
    assert conflict["resolved"]
    assert "ersten Entwurf" in conflict["action"]
    assert client.post("/api/cases/DEMO-014/approve", json={
        "revision": current["revision"], "reviewer": "Demo", "confirmed": True,
    }).status_code == 409
    current = generate(client)
    followup = current["draft"]["sections"][-1]
    assert date in followup["text"]
    assert ("29.10.2026" if date == "30.10.2026" else "30.10.2026") not in followup["text"]
    assert "Abschlussbefund noch ausstehend" in followup["text"]
    assert any(ref["document_id"] == current["followup_resolution"]["document_id"]
               for ref in followup["citations"])
    assert current["draft"]["source_version"] == current["source_version"]
    validate_sections(GeneratedLetter(sections=current["draft"]["sections"]).sections, current)


def test_reconfirmation_preserves_audit_and_invalidates_approval(client):
    current = generate(client)
    current = client.post("/api/cases/DEMO-014/release-report", json={"revision": current["revision"]}).json()
    current = generate(client)
    current = resolve_followup(client, current).json()
    current = client.post("/api/cases/DEMO-014/approve", json={
        "revision": current["revision"], "reviewer": "Demo", "confirmed": True,
    }).json()
    assert current["status"] == "approved"
    original_confirmation = current["followup_resolution"]["document_id"]
    current = resolve_followup(client, current, "29.10.2026").json()
    assert current["approval"] is None
    assert current["status"] == "draft"
    assert any(d["id"] == original_confirmation for d in current["documents"])
    assert original_confirmation != current["followup_resolution"]["document_id"]
    assert "29.10.2026" in current["draft"]["sections"][-1]["text"]
    assert "30.10.2026" not in current["draft"]["sections"][-1]["text"]
    response = client.post("/api/cases/DEMO-014/findings/conflicting-followup", json={
        "revision": current["revision"], "reviewer": "Demo", "note": "Generische Bewertung",
        "decision": "rejected",
    })
    assert response.status_code == 409


def reset_payload(client):
    return {
        "confirmed": True,
        "revisions": {item["id"]: item["revision"] for item in client.get("/api/cases").json()},
    }


def test_reset_restores_all_original_content_and_preserves_snapshot(client):
    first = generate(client)
    first = resolve_followup(client, first).json()
    client.post("/api/cases/DEMO-014/release-report", json={"revision": first["revision"]})
    complete = generate(client, "DEMO-027")
    client.post("/api/cases/DEMO-027/approve", json={
        "revision": complete["revision"], "reviewer": "Demo", "confirmed": True,
    })
    missing = generate(client, "DEMO-031")
    missing["draft"]["sections"][0]["text"] += " Bearbeitung vor Reset."
    client.put("/api/cases/DEMO-031/draft", json={
        "revision": missing["revision"], "sections": missing["draft"]["sections"],
    })
    previous = {identifier: case(client, identifier) for identifier in CASES}
    response = client.post("/api/demo/reset", json=reset_payload(client))
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["cases"]) == 3
    for identifier in CASES:
        expected = initial_case(identifier)
        expected["revision"] = previous[identifier]["revision"] + 1
        actual = client.app.state.store.get(identifier)
        assert actual == expected
        assert case(client, identifier)["draft"] is None
        assert case(client, identifier)["audit"] == []
        assert client.get(f"/api/cases/{identifier}/export").status_code == 409
    with client.app.state.store.connection() as db:
        snapshot = json.loads(db.execute(
            "SELECT state FROM demo_backups WHERE id = ?", (result["backup_id"],),
        ).fetchone()[0])
    saved = {item["id"]: item for item in snapshot}
    for identifier in CASES:
        original = previous[identifier]
        assert saved[identifier] == {
            key: value for key, value in original.items() if key not in {"findings", "synthetic"}
        }
    assert case(client)["documents"][-1]["status"] == "pending"
    assert case(client, "DEMO-031")["documents"][-1]["status"] == "pending"
    assert case(client, "DEMO-027")["documents"][-1]["status"] == "available"


def test_reset_requires_confirmation_and_every_current_revision(client):
    payload = reset_payload(client)
    assert client.post("/api/demo/reset", json={**payload, "confirmed": False}).status_code == 422
    assert client.post("/api/demo/reset", json={}).status_code == 422
    assert client.post("/api/demo/reset", json={**payload, "revisions": {}}).status_code == 422
    assert client.post("/api/demo/reset", json={
        **payload, "revisions": {**payload["revisions"], "unknown": 0},
    }).status_code == 422
    generate(client, "DEMO-031")
    previous = {identifier: case(client, identifier) for identifier in CASES}
    assert client.post("/api/demo/reset", json=payload).status_code == 409
    assert previous == {identifier: case(client, identifier) for identifier in CASES}
    with client.app.state.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM demo_backups").fetchone()[0] == 0


def test_reset_invalidates_inflight_generation_and_old_mutations(client):
    current = generate(client)
    original_generate = rehearsal(current).model_dump()
    original_generate.update(mode="rehearsal", model="test", source_version=1,
                             edited=False, duration_seconds=0, usage=None)

    def reset_during_generation(*args):
        assert client.post("/api/demo/reset", json=reset_payload(client)).status_code == 200
        return original_generate

    with patch("app.main.generate", side_effect=reset_during_generation):
        response = client.post("/api/cases/DEMO-014/generate", json={
            "revision": current["revision"], "mode": "rehearsal",
        })
    assert response.status_code == 409
    assert case(client)["draft"] is None
    assert client.post("/api/cases/DEMO-014/release-report", json={
        "revision": current["revision"],
    }).status_code == 409


def test_reset_rolls_back_if_backup_cannot_be_saved(client):
    generate(client)
    previous = {identifier: case(client, identifier) for identifier in CASES}
    with client.app.state.store.connection() as db:
        db.execute(
            "CREATE TRIGGER fail_backup BEFORE INSERT ON demo_backups "
            "BEGIN SELECT RAISE(ABORT, 'backup unavailable'); END"
        )
    response = client.post("/api/demo/reset", json=reset_payload(client))
    assert response.status_code == 500
    assert "bisherigen Demo-Fälle bleiben erhalten" in response.json()["detail"]
    assert previous == {identifier: case(client, identifier) for identifier in CASES}


def test_reset_rolls_back_snapshot_and_all_cases_if_one_write_fails(client):
    generate(client)
    previous = {identifier: case(client, identifier) for identifier in CASES}
    with client.app.state.store.connection() as db:
        db.execute(
            "CREATE TRIGGER fail_case_reset BEFORE UPDATE ON cases "
            "WHEN NEW.id = 'DEMO-027' "
            "BEGIN SELECT RAISE(ABORT, 'reset write failed'); END"
        )
    assert client.post("/api/demo/reset", json=reset_payload(client)).status_code == 500
    assert previous == {identifier: case(client, identifier) for identifier in CASES}
    with client.app.state.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM demo_backups").fetchone()[0] == 0


def test_reset_and_older_backups_survive_restart_and_repeated_resets(client):
    generate(client)
    first = client.post("/api/demo/reset", json=reset_payload(client)).json()
    second = client.post("/api/demo/reset", json=reset_payload(client)).json()
    assert second["backup_id"] != first["backup_id"]
    config = Settings(database_path=client.app.state.store.path, foundry_model="", _env_file=None)
    with TestClient(create_app(config, serve_frontend=False)) as reopened:
        assert case(reopened)["draft"] is None
        assert case(reopened)["revision"] == 3
        with reopened.app.state.store.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM demo_backups").fetchone()[0] == 2
