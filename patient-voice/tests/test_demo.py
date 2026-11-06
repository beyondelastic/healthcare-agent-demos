import pytest
from fastapi.testclient import TestClient

import tools
from app import app


@pytest.fixture(autouse=True)
def clean():
    tools.reset()
    yield
    tools.reset()


def test_sections_come_only_from_the_approved_letter():
    result = tools.run_tool("get_discharge_information", {"section_ids": ["medication", "appointments"]})
    assert result["ok"] and [s["id"] for s in result["sections"]] == ["medication", "appointments"]
    assert "Ibuprofen 400 mg" in result["sections"][0]["text"]
    assert "freigegeben" in result["source"]


def test_unknown_or_empty_sections_fail_explicitly():
    assert not tools.run_tool("get_discharge_information", {"section_ids": ["lab_values"]})["ok"]
    assert not tools.run_tool("get_discharge_information", {"section_ids": []})["ok"]
    assert not tools.run_tool("not_a_tool", {})["ok"]
    assert not tools.run_tool("get_discharge_information", {"unexpected": 1})["ok"]


def test_callback_is_validated_and_visible_to_staff():
    session = tools.start_session("tr")
    bad = tools.run_tool("request_staff_callback", {"category": "x", "urgency": "routine",
                                                    "summary_de": "s", "patient_question": "q"}, session)
    assert not bad["ok"]
    ok = tools.run_tool("request_staff_callback", {"category": "medication", "urgency": "routine",
                                                   "summary_de": "Frage zu Ramipril", "patient_question": "Ramipril?"},
                        session)
    assert ok["ok"]
    view = tools.staff_view()
    assert view["requests"][0]["language"] == "tr" and view["requests"][0]["status"] == "offen"
    assert view["sessions"][0]["requests"] == [ok["request_id"]]


def test_sources_and_transcript_are_tracked_per_session():
    session = tools.start_session("de")
    tools.log(session, "patient", "Wann ist mein Termin?")
    tools.run_tool("get_discharge_information", {"section_ids": ["appointments", "appointments"]}, session)
    view = tools.staff_view()["sessions"][0]
    assert view["sources"] == ["appointments"] and view["transcript"][0]["text"] == "Wann ist mein Termin?"


def test_pages_letter_qr_and_staff_endpoints():
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/patient").status_code == 200
    assert client.get("/team").status_code == 200
    assert client.get("/api/letter").json()["patient"]["case_id"] == "DEMO-4711"
    qr = client.get("/api/qr.svg")
    assert qr.headers["content-type"].startswith("image/svg+xml")
    assert qr.headers["x-target-url"].endswith("/patient?brief=DEMO-EB-2026-1106")
    session = tools.start_session("de")
    request_id = tools.run_tool("request_staff_callback", {"category": "other", "urgency": "routine",
                                                           "summary_de": "Test", "patient_question": "?"},
                                session)["request_id"]
    assert client.post(f"/api/staff/{request_id}/done").json()["status"] == "erledigt"
    assert client.post("/api/staff/UNKNOWN/done").status_code == 404
    assert client.post("/api/reset").json()["ok"] and not client.get("/api/staff").json()["requests"]
