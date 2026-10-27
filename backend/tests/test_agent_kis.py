import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent import build_proposal, invoke_tool, run_agent
from app.config import Settings
from app.data import CASES, initial_case
from app.generation import rehearsal
from app.kis import read_tool, release_medication
from app.main import create_app
from app.models import AgentResult
from app.store import Store


@pytest.fixture()
def client(tmp_path):
    config = Settings(database_path=tmp_path / "test.sqlite3", foundry_model="test-model",
                      foundry_agent_version="test", _env_file=None)
    with TestClient(create_app(config, serve_frontend=False)) as result:
        result.test_config = config
        yield result


def get_case(client, identifier="DEMO-031"):
    return client.get(f"/api/cases/{identifier}").json()


def confirm(client, path, identifier="DEMO-031", **extra):
    return client.post(path, json={
        "revision": get_case(client, identifier)["revision"],
        "reviewer": "Demo", "confirmed": True, **extra,
    })


def parsed_letter(case):
    return AgentResult(
        sections=[{"id": s.id, "text": s.text,
                   "source_refs": [{"document_id": c.document_id, "paragraph_id": c.paragraph_id}
                                   for c in s.citations]} for s in rehearsal(case).sections],
        summary="Quellenbasierter Testvorschlag.", next_actions=["Menschlich prüfen."],
    )


def pending_proposal(client, identifier="DEMO-031"):
    store = client.app.state.store
    case = store.get(identifier)
    run, snapshot = store.start_run(identifier, case["revision"])
    proposal = build_proposal(parsed_letter(snapshot), snapshot,
                              {d["id"] for d in snapshot["documents"]}, "test-model", {}, 1, ["resp_test"])
    def finish(current):
        current.update(status="awaiting_approval", proposal=proposal)
    return store.update_run(run["id"], finish)


def test_inventory_withholds_unreleased_medication_content():
    case = initial_case("DEMO-031")
    inventory = read_tool(case, "list_case_documents", {})
    assert inventory["documents"][-1]["status"] == "not_released"
    assert "Amlodipin" not in json.dumps(inventory)
    withheld = read_tool(case, "read_case_document", {"document_id": "demo-031-medication"})
    assert withheld["status"] == "not_released"
    assert "document" not in withheld and "Amlodipin" not in json.dumps(withheld)
    with pytest.raises(HTTPException) as error:
        read_tool(case, "read_case_document", {"document_id": "demo-014-admission"})
    assert error.value.status_code == 404


def test_strict_tool_arguments_and_no_write_tools(client):
    store = client.app.state.store
    run, snapshot = store.start_run("DEMO-031", 0)
    with pytest.raises(ValidationError):
        invoke_tool(store, run, snapshot, "list_case_documents", '{"patient_id":"DEMO-014"}', set(), "call1")
    with pytest.raises(HTTPException) as error:
        invoke_tool(store, run, snapshot, "writeback", "{}", set(), "call2")
    assert error.value.status_code == 422
    assert len([e for e in store.runs("DEMO-031")[0]["events"] if e["kind"] == "tool_error"]) == 2
    assert get_case(client)["draft"] is None


def test_retrieval_fault_is_error_not_missing_document():
    case = initial_case("DEMO-031")
    case["kis"]["retrieval_fault"] = True
    for tool, args in [("list_case_documents", {}), ("get_case_workflow", {}),
                       ("read_case_document", {"document_id": "demo-031-admission"})]:
        with pytest.raises(HTTPException) as error:
            read_tool(case, tool, args)
        assert error.value.status_code == 503
        assert "kein Nachweis fehlender" in error.value.detail


def test_medication_release_requires_consent_and_only_updates_sources(client):
    original = get_case(client)
    path = "/api/kis/cases/DEMO-031/release-medication"
    assert client.post(path, json={"revision": 0, "reviewer": "Demo"}).status_code == 422
    assert client.post(path, json={"revision": 0, "reviewer": "Demo", "confirmed": False}).status_code == 422
    released = confirm(client, path).json()
    assert released["draft"] is None
    assert released["source_version"] == original["source_version"] + 1
    assert not any(f["id"] == "missing-medication" for f in released["findings"])
    assert "Amlodipin" in json.dumps(released["documents"])
    assert confirm(client, path).status_code == 409
    assert get_case(client, "DEMO-014")["revision"] == 0


def test_releasing_plan_preserves_old_letter_and_revokes_approval(client):
    store = client.app.state.store
    def setup(case):
        case["draft"] = {"sections": [s.model_dump() for s in rehearsal(case).sections], "source_version": 1}
        case["status"] = "approved"
        case["approval"] = {"reviewer": "Demo"}
    before = store.mutate("DEMO-031", 0, setup)
    released = confirm(client, "/api/kis/cases/DEMO-031/release-medication").json()
    assert released["draft"] == before["draft"]
    assert released["draft"]["source_version"] != released["source_version"]
    assert released["approval"] is None


def test_build_proposal_requires_every_read_and_original_quotes():
    snapshot = initial_case("DEMO-031")
    parsed = parsed_letter(snapshot)
    with pytest.raises(ValueError, match="Nicht alle Quellen"):
        build_proposal(parsed, snapshot, set(), "model", {}, 1, [])
    proposal = build_proposal(parsed, snapshot, {d["id"] for d in snapshot["documents"]}, "model", {}, 1, [])
    assert "Amlodipin" not in proposal["sections"][4]["text"]
    assert proposal["sections"][0]["citations"][0]["quote"] == snapshot["documents"][0]["paragraphs"][0]["text"]
    parsed.sections[0].source_refs[0].document_id = "demo-014-admission"
    with pytest.raises(ValueError):
        build_proposal(parsed, snapshot, {d["id"] for d in snapshot["documents"]}, "model", {}, 1, [])


def test_proposal_is_not_automatically_applied_and_acceptance_is_guarded(client):
    run = pending_proposal(client)
    assert get_case(client)["draft"] is None
    path = f"/api/cases/DEMO-031/agent-runs/{run['id']}/accept"
    assert client.post(path, json={"revision": 0}).status_code == 422
    assert confirm(client, f"/api/cases/DEMO-014/agent-runs/{run['id']}/accept", "DEMO-014").status_code == 404
    accepted = confirm(client, path)
    assert accepted.status_code == 200
    assert accepted.json()["draft"]["sections"] == run["proposal"]["sections"]
    assert accepted.json()["status"] == "draft"
    assert accepted.json()["approval"] is None
    assert confirm(client, path).status_code == 409
    assert client.app.state.store.runs("DEMO-031")[0]["status"] == "applied"


def test_stale_proposal_never_overwrites_a_source_or_letter_change(client):
    run = pending_proposal(client)
    confirm(client, "/api/kis/cases/DEMO-031/release-medication")
    response = confirm(client, f"/api/cases/DEMO-031/agent-runs/{run['id']}/accept")
    assert response.status_code == 409
    assert get_case(client)["draft"] is None
    assert client.app.state.store.runs("DEMO-031")[0]["status"] == "awaiting_approval"


def test_acceptance_revalidates_citations_and_rolls_back(client):
    run = pending_proposal(client)
    client.app.state.store.update_run(run["id"], lambda r: r["proposal"]["sections"][0]["citations"][0].update(quote="fake"))
    response = confirm(client, f"/api/cases/DEMO-031/agent-runs/{run['id']}/accept")
    assert response.status_code == 422
    assert get_case(client)["revision"] == 0 and get_case(client)["draft"] is None


def test_reject_preserves_letter(client):
    run = pending_proposal(client)
    assert confirm(client, f"/api/cases/DEMO-031/agent-runs/{run['id']}/reject").status_code == 200
    assert get_case(client)["draft"] is None
    assert client.app.state.store.runs("DEMO-031")[0]["status"] == "rejected"


def test_writeback_requires_current_demo_approval_and_consent(client):
    path = "/api/kis/cases/DEMO-031/writeback"
    assert confirm(client, path).status_code == 409
    current = client.post("/api/cases/DEMO-031/generate", json={"revision": 0, "mode": "rehearsal"}).json()
    assert confirm(client, path).status_code == 409
    for finding in current["findings"]:
        current = client.post(f"/api/cases/DEMO-031/findings/{finding['id']}", json={
            "revision": current["revision"], "decision": "acknowledged",
            "reviewer": "Demo", "note": "Offenen Punkt ausdrücklich zur Nachverfolgung dokumentiert.",
        }).json()
    assert confirm(client, "/api/cases/DEMO-031/approve").status_code == 200
    assert client.post(path, json={"revision": get_case(client)["revision"], "reviewer": "Demo"}).status_code == 422
    response = confirm(client, path)
    assert response.status_code == 200
    receipt = response.json()["kis"]["letters"][0]
    assert receipt["sections"] == response.json()["draft"]["sections"]
    assert "keine klinische Signatur" in receipt["label"]
    assert confirm(client, path).status_code == 409
    original = deepcopy(receipt)
    sections = response.json()["draft"]["sections"]
    sections[0]["text"] += " Manuell ergänzt."
    client.put("/api/cases/DEMO-031/draft", json={"revision": get_case(client)["revision"], "sections": sections})
    assert get_case(client)["kis"]["letters"][0] == original
    assert confirm(client, path).status_code == 409


def test_reset_backs_up_runs_and_kis_and_prevents_resurrection(client):
    run = pending_proposal(client)
    confirm(client, "/api/kis/cases/DEMO-031/release-medication")
    client.post("/api/kis/cases/DEMO-031/retrieval-fault", json={"revision": get_case(client)["revision"], "enabled": True})
    revisions = {identifier: get_case(client, identifier)["revision"] for identifier in CASES}
    response = client.post("/api/demo/reset", json={"confirmed": True, "revisions": revisions})
    assert response.status_code == 200
    assert client.app.state.store.runs("DEMO-031") == []
    assert get_case(client)["kis"] == initial_case("DEMO-031")["kis"]
    with pytest.raises(HTTPException) as error:
        client.app.state.store.update_run(run["id"], lambda r: r.update(status="awaiting_approval"))
    assert error.value.status_code == 409
    with client.app.state.store.connection() as db:
        state, runs = db.execute("SELECT state, run_state FROM demo_backups WHERE id = ?", (response.json()["backup_id"],)).fetchone()
    assert json.loads(runs)[0]["id"] == run["id"]
    assert next(c for c in json.loads(state) if c["id"] == "DEMO-031")["kis"]["retrieval_fault"]


def test_start_conflicts_and_restart_recovery(client):
    with patch("app.main.run_agent"):
        response = client.post("/api/cases/DEMO-031/agent-runs", json={"revision": 0})
    assert response.status_code == 202
    assert client.post("/api/cases/DEMO-031/agent-runs", json={"revision": 0}).status_code == 409
    store = client.app.state.store
    Store(store.path)
    assert store.runs("DEMO-031")[0]["status"] == "running"
    store.recover_runs()
    assert store.runs("DEMO-031")[0]["status"] == "failed"
    assert "neu gestartet" in store.runs("DEMO-031")[0]["error"]


def response(output, text=""):
    return SimpleNamespace(id="resp_test", model="test-model", usage=None, output=output, output_text=text)


def call(name, arguments=None):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(arguments or {}), call_id=name)


def test_worker_executes_tools_and_saves_only_a_proposal(client):
    store = client.app.state.store
    run, snapshot = store.start_run("DEMO-031", 0)
    responses = [
        response([call("list_case_documents"), call("get_case_workflow")]),
        response([call("read_case_document", {"document_id": d["id"]}) for d in snapshot["documents"]]),
        response([], parsed_letter(snapshot).model_dump_json()),
    ]
    with patch("app.agent.AzureCliCredential"), patch("app.agent.AIProjectClient") as project:
        model = project.return_value.__enter__.return_value.get_openai_client.return_value.__enter__.return_value
        model.responses.create.side_effect = responses
        run_agent(store, run, snapshot, client.test_config)
    result = store.runs("DEMO-031")[0]
    assert result["status"] == "awaiting_approval"
    assert len([e for e in result["events"] if e["kind"] == "tool_result"]) == len(snapshot["documents"]) + 2
    assert get_case(client)["draft"] is None and get_case(client)["revision"] == 0


def test_worker_fault_marks_failed_without_a_success_fallback(client):
    store = client.app.state.store
    store.mutate("DEMO-031", 0, lambda c: c["kis"].update(retrieval_fault=True))
    run, snapshot = store.start_run("DEMO-031", 1)
    with patch("app.agent.AzureCliCredential"), patch("app.agent.AIProjectClient") as project:
        model = project.return_value.__enter__.return_value.get_openai_client.return_value.__enter__.return_value
        model.responses.create.return_value = response([call("list_case_documents")])
        run_agent(store, run, snapshot, client.test_config)
    result = store.runs("DEMO-031")[0]
    assert result["status"] == "failed" and result["proposal"] is None
    assert "Abrufstörung" in result["error"]
    assert any(e["kind"] == "tool_error" for e in result["events"])
    assert get_case(client)["draft"] is None


def test_worker_revision_change_blocks_reads(client):
    store = client.app.state.store
    run, snapshot = store.start_run("DEMO-031", 0)
    store.mutate("DEMO-031", 0, lambda c: release_medication(c, "Demo"))
    with pytest.raises(HTTPException) as error:
        invoke_tool(store, run, snapshot, "list_case_documents", "{}", set(), "test")
    assert error.value.status_code == 409


def test_worker_requires_corrective_read_when_model_skips_pending_source(client):
    store = client.app.state.store
    run, snapshot = store.start_run("DEMO-031", 0)
    pending = next(d for d in snapshot["documents"] if d["status"] == "pending")
    responses = [
        response([call("list_case_documents"), call("get_case_workflow")]),
        response([call("read_case_document", {"document_id": d["id"]})
                  for d in snapshot["documents"] if d["id"] != pending["id"]]),
        response([], parsed_letter(snapshot).model_dump_json()),
        response([call("read_case_document", {"document_id": pending["id"]})]),
        response([], parsed_letter(snapshot).model_dump_json()),
    ]
    with patch("app.agent.AzureCliCredential"), patch("app.agent.AIProjectClient") as project:
        model = project.return_value.__enter__.return_value.get_openai_client.return_value.__enter__.return_value
        model.responses.create.side_effect = responses
        run_agent(store, run, snapshot, client.test_config)
    result = store.runs("DEMO-031")[0]
    assert result["status"] == "awaiting_approval"
    validation = next(e for e in result["events"] if e["kind"] == "validation")
    assert validation["document_ids"] == [pending["id"]]
    assert model.responses.create.call_count == 5


def test_worker_model_error_and_reset_do_not_create_a_draft(client):
    store = client.app.state.store
    run, snapshot = store.start_run("DEMO-031", 0)
    def reset_during_call(**kwargs):
        store.reset({identifier: store.get(identifier)["revision"] for identifier in CASES})
        raise ValueError("Model response interrupted by reset")
    with patch("app.agent.AzureCliCredential"), patch("app.agent.AIProjectClient") as project:
        model = project.return_value.__enter__.return_value.get_openai_client.return_value.__enter__.return_value
        model.responses.create.side_effect = reset_during_call
        run_agent(store, run, snapshot, client.test_config)
    assert store.runs("DEMO-031") == []
    assert get_case(client)["draft"] is None


def test_document_reads_expose_only_exact_original_reference_pairs():
    case = initial_case("DEMO-031")
    for doc in case["documents"]:
        result = read_tool(case, "read_case_document", {"document_id": doc["id"]})
        assert result["source_refs"] == [
            {"document_id": doc["id"], "paragraph_id": paragraph["id"]}
            for paragraph in doc["paragraphs"]
        ]
    withheld = read_tool(case, "read_case_document", {"document_id": "demo-031-medication"})
    assert "source_refs" not in withheld


@pytest.mark.parametrize("fault", ["unknown-paragraph", "foreign-document", "unreleased-document", "malformed-output"])
def test_worker_rejects_invalid_output_and_requests_a_valid_correction(client, fault):
    store = client.app.state.store
    run, snapshot = store.start_run("DEMO-031", 0)
    valid = parsed_letter(snapshot)
    invalid = valid.model_copy(deep=True)
    if fault == "unknown-paragraph":
        invalid.sections[0].source_refs[0].paragraph_id = "invented-paragraph"
    elif fault == "foreign-document":
        invalid.sections[0].source_refs[0].document_id = "demo-014-admission"
    elif fault == "unreleased-document":
        invalid.sections[4].source_refs[0].document_id = "demo-031-medication"
    bad_output = '{"sections":[]}' if fault == "malformed-output" else invalid.model_dump_json()
    responses = [
        response([call("list_case_documents"), call("get_case_workflow")]),
        response([call("read_case_document", {"document_id": d["id"]}) for d in snapshot["documents"]]),
        response([], bad_output),
        response([], valid.model_dump_json()),
    ]
    with patch("app.agent.AzureCliCredential"), patch("app.agent.AIProjectClient") as project:
        model = project.return_value.__enter__.return_value.get_openai_client.return_value.__enter__.return_value
        model.responses.create.side_effect = responses
        run_agent(store, run, snapshot, client.test_config)
        feedback = json.loads(model.responses.create.call_args.kwargs["input"][-1]["content"])
    assert feedback["allowed_source_refs"] == [
        {"document_id": d["id"], "paragraph_id": p["id"]}
        for d in snapshot["documents"] for p in d["paragraphs"]
    ]
    assert not any(r["document_id"] == "demo-031-medication" for r in feedback["allowed_source_refs"])
    result = store.runs("DEMO-031")[0]
    assert result["status"] == "awaiting_approval"
    assert result["proposal"]["sections"][0]["citations"][0]["paragraph_id"] == "p1"
    events = [e for e in result["events"] if e["kind"] == "validation"]
    assert len(events) == 1 and events[0]["repair_attempt"] == 1 and events[0]["retry"]
    assert get_case(client)["draft"] is None and get_case(client)["revision"] == 0


def test_repeated_invalid_citations_fail_after_two_repairs_without_fallback(client):
    store = client.app.state.store
    run, snapshot = store.start_run("DEMO-031", 0)
    invalid = parsed_letter(snapshot)
    invalid.sections[0].source_refs[0].paragraph_id = "not-a-real-paragraph"
    responses = [
        response([call("list_case_documents"), call("get_case_workflow")]),
        response([call("read_case_document", {"document_id": d["id"]}) for d in snapshot["documents"]]),
        *[response([], invalid.model_dump_json()) for _ in range(3)],
    ]
    with patch("app.agent.AzureCliCredential"), patch("app.agent.AIProjectClient") as project:
        model = project.return_value.__enter__.return_value.get_openai_client.return_value.__enter__.return_value
        model.responses.create.side_effect = responses
        run_agent(store, run, snapshot, client.test_config)
        assert model.responses.create.call_count == 5
    result = store.runs("DEMO-031")[0]
    assert result["status"] == "failed" and result["proposal"] is None
    assert "nach zwei Korrekturversuchen" in result["error"]
    assert "not-a-real-paragraph" in result["error"]
    assert [e["retry"] for e in result["events"] if e["kind"] == "validation"] == [True, True, False]
    assert get_case(client)["draft"] is None and get_case(client)["revision"] == 0
