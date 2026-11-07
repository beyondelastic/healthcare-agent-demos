import pytest
from fastapi.testclient import TestClient

import safety
import tools
from app import app, ice_servers


@pytest.fixture(autouse=True)
def clean():
    tools.reset()
    yield
    tools.reset()


def test_every_location_has_a_route_and_map_path_from_the_kiosk():
    kiosk = tools.CAMPUS["kiosk"]["point"]
    for location in tools.CAMPUS["locations"]:
        assert location["route"] and location["path"][0] == kiosk and location["pin"]
        assert location["building"] in tools.BUILDINGS or location["building"] == "-"


def test_find_location_returns_route_and_optional_step_free_note():
    plain = tools.run_tool("find_location", {"location_id": "radiologie"})
    assert plain["ok"] and plain["route"]["floor"] == 0 and plain["route"]["barrier_free"] is None
    step_free = tools.run_tool("find_location", {"location_id": "labor", "barrier_free": True})
    assert "Aufzug" in step_free["route"]["barrier_free"]
    assert not tools.run_tool("find_location", {"location_id": "mars"})["ok"]


@pytest.mark.parametrize("name,dob", [("Novak", "14.03.1959"), ("novak", "14.3.1959"), ("NOVAK", "1959-03-14")])
def test_elena_novak_checks_in_for_her_follow_up(name, dob):
    session = tools.start_session("de")
    result = tools.run_tool("check_in_appointment", {"last_name": name, "date_of_birth": dob}, session)
    assert result["ok"] and result["appointment_time"] == "10:30"
    assert result["route"]["id"] == "chirurgische_ambulanz" and result["route"]["floor"] == 2
    assert "Entlassbrief" in result["bring"] and result["arrival"] == "on_time"
    assert "internal_note" not in result and "Cholezystektomie" not in str(result)
    checkin = tools.team_view()["checkins"][0]
    assert checkin["last_name"] == "Novak" and "Histologie" in checkin["internal_note"]


def test_check_in_is_idempotent_and_accent_insensitive():
    first = tools.run_tool("check_in_appointment", {"last_name": "Yilmaz", "date_of_birth": "21.09.1985"})
    second = tools.run_tool("check_in_appointment", {"last_name": "Yılmaz", "date_of_birth": "21.09.1985"})
    assert first["ok"] and first["waiting_number"] == second["waiting_number"]
    assert len(tools.team_view()["checkins"]) == 1


@pytest.mark.parametrize("name,dob", [("Novak", "15.03.1959"), ("Nowak", "14.03.1959"), ("Novak", "")])
def test_wrong_details_reveal_nothing(name, dob):
    result = tools.run_tool("check_in_appointment", {"last_name": name, "date_of_birth": dob})
    assert not result["ok"] and "10:30" not in str(result) and "Novak" not in str(result)
    assert not tools.team_view()["checkins"]


def test_visitor_information_and_staff_call():
    assert tools.run_tool("get_visitor_information", {"topic": "visiting_hours"})["text"].startswith("Allgemein")
    assert not tools.run_tool("get_visitor_information", {"topic": "salaries"})["ok"]
    session = tools.start_session("en")
    call = tools.run_tool("call_staff", {"need": "wheelchair", "urgency": "routine",
                                         "summary_de": "Rollstuhl am Kiosk benötigt"}, session)
    assert call["ok"] and tools.team_view()["requests"][0]["language"] == "en"
    assert not tools.run_tool("call_staff", {"need": "x", "urgency": "routine", "summary_de": "?"})["ok"]


def test_emergency_rule_and_agent_call_are_merged():
    session = tools.start_session("de")
    assert safety.detect_emergency("Mein Mann ist zusammengebrochen!")
    assert safety.detect_emergency("Wo ist die Cafeteria?") is None
    tools.call_staff("unwell", "urgent", "Regel", session_id=session, origin="regel")
    tools.run_tool("call_staff", {"need": "unwell", "urgency": "urgent", "summary_de": "Person kollabiert"}, session)
    requests = tools.team_view()["requests"]
    assert len(requests) == 1 and requests[0]["origin"] == "regel+agent"


def test_ice_servers_are_extracted_from_the_session_event():
    event = {"session": {"avatar": {"ice_servers": [{"urls": ["turn:relay.example:3478"], "username": "u",
                                                     "credential": "c"}]}}}
    assert ice_servers(event) == [{"urls": ["turn:relay.example:3478"], "username": "u", "credential": "c"}]
    assert ice_servers({"session": {}}) is None
    assert ice_servers({"session": {"avatar": None}}) is None


def test_pages_and_api():
    client = TestClient(app)
    assert client.get("/").status_code == 200 and client.get("/team").status_code == 200
    campus = client.get("/api/campus").json()
    assert campus["demo_now"]["date"] == "24.11.2026" and "appointments" not in campus
    assert "path" in campus["locations"][0]
    tools.run_tool("check_in_appointment", {"last_name": "Novak", "date_of_birth": "14.03.1959"})
    checkin_id = client.get("/api/team").json()["checkins"][0]["id"]
    assert client.post(f"/api/team/checkins/{checkin_id}/done").json()["status"] == "erledigt"
    assert client.post("/api/team/checkins/NOPE/done").status_code == 404
    assert client.post("/api/reset").json()["ok"] and not client.get("/api/team").json()["checkins"]
