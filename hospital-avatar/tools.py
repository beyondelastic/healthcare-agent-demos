"""Kiosk tools for the hospital welcome avatar: wayfinding, check-in, visitor information, staff call.

All data comes from campus.json (fictional). The voice agent never sees it in its instructions; it
must call these tools, executed here by the app. Nothing here gives medical information: appointment
reasons stay internal, and health concerns are handed to staff.
"""

import json
import re
import threading
import time
import unicodedata
import uuid
from pathlib import Path

CAMPUS = json.loads((Path(__file__).parent / "campus.json").read_text(encoding="utf-8"))
LOCATIONS = {loc["id"]: loc for loc in CAMPUS["locations"]}
BUILDINGS = {b["id"]: b for b in CAMPUS["buildings"]}
TOPICS = CAMPUS["visitor_info"]
NEEDS = ["escort", "wheelchair", "unwell", "question", "other"]
URGENCY = ["routine", "urgent"]

_lock = threading.Lock()
SESSIONS: dict[str, dict] = {}
CHECKINS: list[dict] = []
REQUESTS: list[dict] = []


def _fold(text: str) -> str:
    """Case- and accent-insensitive comparison: 'Yılmaz' == 'yilmaz', 'Nowak' != 'Novak'."""
    text = unicodedata.normalize("NFKD", (text or "").replace("ı", "i").replace("İ", "I"))
    return "".join(c for c in text if not unicodedata.combining(c)).strip().lower()


def _date(value: str) -> str | None:
    """Normalise a date of birth to DD.MM.YYYY (accepts 14.3.1959, 1959-03-14, 14/03/1959)."""
    value = (value or "").strip()
    match = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value)
    if match:
        day, month, year = match.groups()
    else:
        match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
        if not match:
            return None
        year, month, day = match.groups()
    return f"{int(day):02d}.{int(month):02d}.{year}"


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def start_session(language: str) -> str:
    session_id = uuid.uuid4().hex[:8]
    with _lock:
        SESSIONS[session_id] = {"id": session_id, "language": language, "started": time.time(),
                                "transcript": [], "actions": []}
    return session_id


def log(session_id: str, role: str, text: str, channel: str = "voice"):
    if not text:
        return
    with _lock:
        if session_id in SESSIONS:
            SESSIONS[session_id]["transcript"].append({"role": role, "text": text, "channel": channel,
                                                       "at": time.time()})


def set_language(session_id: str, language: str):
    with _lock:
        if session_id in SESSIONS:
            SESSIONS[session_id]["language"] = language


def _action(session_id, kind, label):
    with _lock:
        if session_id in SESSIONS:
            SESSIONS[session_id]["actions"].append({"kind": kind, "label": label, "at": time.time()})


def route_for(location_id: str, barrier_free: bool = False) -> dict:
    loc = LOCATIONS[location_id]
    building = BUILDINGS.get(loc["building"], {}).get("name", "Außenbereich")
    return {"id": loc["id"], "name": loc["name"], "building": building, "floor": loc["floor"],
            "room": loc["room"], "walk_minutes": loc["minutes"], "steps": loc["route"],
            "barrier_free": loc["barrier_free"] if barrier_free else None,
            "barrier_free_requested": bool(barrier_free), "start": CAMPUS["kiosk"]["name"]}


def find_location(location_id, barrier_free=False, language=None, session_id=None):
    if location_id not in LOCATIONS:
        return {"ok": False, "message": f"Unknown location. Valid ids: {', '.join(LOCATIONS)}."}
    _action(session_id, "route", LOCATIONS[location_id]["name"])
    return {"ok": True, "route": route_for(location_id, barrier_free),
            "note": "The route and a map are shown on the kiosk screen. Summarise it in one or two sentences."}


def check_in_appointment(last_name, date_of_birth, language=None, session_id=None):
    dob = _date(date_of_birth)
    if not last_name or not dob:
        return {"ok": False, "message": "Ask for the last name and the date of birth (day, month, year)."}
    match = next((a for a in CAMPUS["appointments"]
                  if _fold(a["last_name"]) == _fold(last_name) and a["date_of_birth"] == dob), None)
    if not match:
        _action(session_id, "checkin_failed", "Termin nicht gefunden")
        return {"ok": False, "found": False,
                "message": "No appointment found today for this name and date of birth. Do not guess or list other "
                           "appointments. Offer to check the spelling once, or call a colleague from the information desk."}
    now = CAMPUS["demo_now"]["time"]
    delta = _minutes(match["time"]) - _minutes(now)
    timing = "early" if delta > 20 else "on_time" if delta >= -10 else "late"
    with _lock:
        existing = next((c for c in CHECKINS if c["last_name"] == match["last_name"]
                         and c["date_of_birth"] == match["date_of_birth"]), None)
        if existing:
            checkin = existing
        else:
            number = f"{LOCATIONS[match['location']]['building']}{LOCATIONS[match['location']]['floor']}-{17 + len(CHECKINS):03d}"
            checkin = {"id": uuid.uuid4().hex[:6].upper(), "session_id": session_id, "created": time.time(),
                       "last_name": match["last_name"], "first_name": match["first_name"],
                       "date_of_birth": match["date_of_birth"], "time": match["time"], "location": match["location"],
                       "location_name": LOCATIONS[match["location"]]["name"], "kind": match["kind"],
                       "internal_note": match["internal_note"], "waiting_number": number, "arrived": now,
                       "timing": timing, "status": "angekommen"}
            CHECKINS.append(checkin)
    _action(session_id, "checkin", f"{match['kind']} {match['time']} · {checkin['waiting_number']}")
    return {
        "ok": True, "address_as": f"{match['salutation']} {match['last_name']}", "appointment_time": match["time"],
        "appointment_kind": match["kind"], "waiting_number": checkin["waiting_number"],
        "arrival": timing, "minutes_until_appointment": delta, "bring": match["bring"],
        "route": route_for(match["location"]),
        "privacy": "Never say the reason for the appointment, a diagnosis or other personal data aloud. "
                   "The department and time are enough.",
        "team_notified": f"{LOCATIONS[match['location']]['name']} has been told that the patient has arrived.",
    }


def get_visitor_information(topic, language=None, session_id=None):
    if topic not in TOPICS:
        return {"ok": False, "message": f"Unknown topic. Valid: {', '.join(TOPICS)}."}
    _action(session_id, "info", TOPICS[topic]["title"])
    return {"ok": True, "topic": topic, **TOPICS[topic]}


def call_staff(need, urgency, summary_de, language=None, session_id=None, origin="agent"):
    if need not in NEEDS or urgency not in URGENCY:
        return {"ok": False, "message": f"need must be one of {NEEDS}, urgency one of {URGENCY}."}
    if not (summary_de or "").strip():
        return {"ok": False, "message": "summary_de is required."}
    with _lock:
        if urgency == "urgent":
            # The 112-style rule may already have alarmed staff for this session: update instead of duplicating.
            for request in reversed(REQUESTS):
                if request["session_id"] == session_id and request["urgency"] == "urgent" \
                        and request["origin"] == "regel" and time.time() - request["created"] < 300:
                    request.update(summary_de=summary_de.strip(), origin="regel+agent", need=need,
                                   language=SESSIONS.get(session_id, {}).get("language", request["language"]))
                    return {"ok": True, "request_id": request["id"], "message": "Staff already on the way (demo)."}
        language = SESSIONS.get(session_id, {}).get("language")
        request = {"id": uuid.uuid4().hex[:6].upper(), "session_id": session_id, "created": time.time(),
                   "need": need, "urgency": urgency, "summary_de": summary_de.strip(), "language": language,
                   "place": CAMPUS["kiosk"]["name"], "origin": origin, "status": "offen"}
        REQUESTS.append(request)
    _action(session_id, "staff", summary_de.strip())
    eta = "about 1 minute" if urgency == "urgent" else "a few minutes"
    return {"ok": True, "request_id": request["id"], "urgency": urgency,
            "message": f"A colleague from the information desk has been called to the kiosk ({eta}, demo)."}


def reset():
    with _lock:
        SESSIONS.clear()
        CHECKINS.clear()
        REQUESTS.clear()


def team_view() -> dict:
    with _lock:
        return {"checkins": list(reversed(CHECKINS)), "requests": list(reversed(REQUESTS)),
                "sessions": sorted((dict(s) for s in SESSIONS.values()), key=lambda s: -s["started"])}


TOOL_SCHEMAS = [
    {
        "name": "find_location",
        "description": (
            "Shows the walking route from the kiosk (main entrance) to a place on the hospital campus, with a map on "
            "the screen. Use for every 'where is ...' question. Places: " +
            "; ".join(f"{loc['id']} = {loc['name']}" for loc in CAMPUS["locations"])),
        "parameters": {
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "enum": list(LOCATIONS)},
                "barrier_free": {"type": "boolean",
                                 "description": "True if the person uses a wheelchair, walker or pram, or asks for a step-free route."},
            },
            "required": ["location_id"],
        },
    },
    {
        "name": "check_in_appointment",
        "description": (
            "Checks a patient in for today's outpatient appointment and notifies the department. Requires the last "
            "name and the date of birth. Returns time, waiting number, route and what to bring; never the reason."),
        "parameters": {
            "type": "object",
            "properties": {
                "last_name": {"type": "string", "description": "Last name as spoken or spelled by the patient."},
                "date_of_birth": {"type": "string", "description": "Date of birth as DD.MM.YYYY."},
            },
            "required": ["last_name", "date_of_birth"],
        },
    },
    {
        "name": "get_visitor_information",
        "description": "Hospital visitor information: " + "; ".join(f"{k} = {v['title']}" for k, v in TOPICS.items()),
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string", "enum": list(TOPICS)}},
            "required": ["topic"],
        },
    },
    {
        "name": "call_staff",
        "description": (
            "Calls a colleague from the information desk to the kiosk. Use when someone needs an escort or wheelchair, "
            "feels unwell or describes symptoms (urgency urgent), cannot be checked in, or asks for a person."),
        "parameters": {
            "type": "object",
            "properties": {
                "need": {"type": "string", "enum": NEEDS},
                "urgency": {"type": "string", "enum": URGENCY,
                            "description": "urgent if the person feels unwell or describes any symptom."},
                "summary_de": {"type": "string", "description": "Short German note for the colleague."},
            },
            "required": ["need", "urgency", "summary_de"],
        },
    },
]

LANGUAGE_PROPERTY = {"type": "string", "enum": ["de", "en", "tr", "ar", "uk"],
                     "description": "Language the visitor is speaking right now; the kiosk screen switches to it."}
for _schema in TOOL_SCHEMAS:
    _schema["parameters"]["properties"]["language"] = LANGUAGE_PROPERTY
    _schema["parameters"]["required"].append("language")

_TOOLS = {"find_location": find_location, "check_in_appointment": check_in_appointment,
          "get_visitor_information": get_visitor_information, "call_staff": call_staff}


def run_tool(name, args, session_id=None):
    tool = _TOOLS.get(name)
    if tool is None:
        return {"ok": False, "message": f"Unknown tool '{name}'."}
    try:
        return tool(**args, session_id=session_id)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "message": f"Invalid arguments for {name}: {exc}"}
