"""Approved-letter retrieval and staff hand-off for the patient voice demo.

The voice agent never sees the letter in its instructions. It must ask for an
approved section through ``get_discharge_information`` (executed here, by the
app), so every factual answer is traceable to a released letter section.
``request_staff_callback`` records a hand-off that staff can see on /staff.
"""

import json
import threading
import time
import uuid
from pathlib import Path

LETTER = json.loads((Path(__file__).parent / "letter.json").read_text(encoding="utf-8"))
SECTIONS = {section["id"]: section for section in LETTER["sections"]}

CATEGORIES = ["medication", "appointment", "symptoms", "pending_result", "other"]
URGENCY = ["routine", "urgent", "emergency"]

_lock = threading.Lock()
SESSIONS: dict[str, dict] = {}
REQUESTS: list[dict] = []
# Demo only: the next medication lookup returns a wrong Ramipril dose, to show the safety check.
FAULT = {"armed": False}
FAULT_TEXT = ("Ramipril 5 mg", "Ramipril 10 mg")


def letter_summary() -> dict:
    """Public, non-content metadata shown on the patient page."""
    return {key: LETTER[key] for key in
            ["letter_id", "hospital", "department", "patient", "admission_date", "discharge_date", "approval"]}


def start_session(language: str) -> str:
    session_id = uuid.uuid4().hex[:8]
    with _lock:
        SESSIONS[session_id] = {"id": session_id, "language": language, "started": time.time(),
                                "transcript": [], "sources": [], "requests": []}
    return session_id


def log(session_id: str, role: str, text: str, channel: str = "voice"):
    if not text:
        return
    with _lock:
        session = SESSIONS.get(session_id)
        if session is not None:
            session["transcript"].append({"role": role, "text": text, "channel": channel, "at": time.time()})


def set_language(session_id: str, language: str):
    with _lock:
        if session_id in SESSIONS:
            SESSIONS[session_id]["language"] = language


def get_discharge_information(section_ids, session_id=None):
    unknown = [s for s in section_ids if s not in SECTIONS]
    if unknown or not section_ids:
        return {"ok": False, "message": f"Unknown sections {unknown}. Valid: {', '.join(SECTIONS)}."}
    sections = [SECTIONS[s] for s in dict.fromkeys(section_ids)]
    if FAULT["armed"] and any(s["id"] == "medication" for s in sections):
        FAULT["armed"] = False
        sections = [dict(s, text=s["text"].replace(*FAULT_TEXT)) if s["id"] == "medication" else s
                    for s in sections]
    if session_id:
        with _lock:
            session = SESSIONS.get(session_id)
            if session is not None:
                for section in sections:
                    if section["id"] not in session["sources"]:
                        session["sources"].append(section["id"])
    return {
        "ok": True,
        "source": f"{LETTER['letter_id']}, {LETTER['approval']['status']} am {LETTER['approval']['approved_at']}",
        "language_of_source": "de",
        "answer_language": "the language of the patient's most recent message (translate from German)",
        "sections": [{"id": s["id"], "title": s["title"], "text": s["text"]} for s in sections],
    }


def request_staff_callback(category, urgency, summary_de, patient_question, session_id=None):
    if category not in CATEGORIES or urgency not in URGENCY:
        return {"ok": False, "message": f"category must be one of {CATEGORIES}, urgency one of {URGENCY}."}
    if not summary_de or not summary_de.strip():
        return {"ok": False, "message": "summary_de is required."}
    with _lock:
        if urgency in ("urgent", "emergency"):
            # A rule may already have raised this (warning sign or emergency): complete that request
            # instead of creating a duplicate, and keep the higher urgency.
            for request in reversed(REQUESTS):
                if (request["session_id"] == session_id and request["category"] == "symptoms"
                        and request.get("origin") == "regel" and time.time() - request["created"] < 300):
                    request.update(summary_de=summary_de.strip(), origin="regel+agent",
                                   urgency="emergency" if "emergency" in (urgency, request["urgency"]) else "urgent",
                                   patient_question=(patient_question or "").strip() or request["patient_question"])
                    return {"ok": True, "request_id": request["id"], "urgency": request["urgency"],
                            "message": "Request already recorded for the clinical team (demo)."}
    return _add_request(session_id, category, urgency, summary_de.strip(), (patient_question or "").strip(), "agent")


def _add_request(session_id, category, urgency, summary_de, patient_question, origin, **extra) -> dict:
    with _lock:
        language = SESSIONS.get(session_id, {}).get("language")
        request = {"id": uuid.uuid4().hex[:6].upper(), "session_id": session_id, "created": time.time(),
                   "category": category, "urgency": urgency, "summary_de": summary_de,
                   "patient_question": patient_question, "language": language,
                   "patient": LETTER["patient"]["name"], "case_id": LETTER["patient"]["case_id"],
                   "status": "offen", "origin": origin, **extra}
        REQUESTS.append(request)
        if session_id in SESSIONS:
            SESSIONS[session_id]["requests"].append(request["id"])
    return {"ok": True, "request_id": request["id"], "urgency": urgency,
            "message": "Request recorded for the clinical team (demo, no real notification)."}


def rule_emergency(session_id, term, patient_text) -> bool:
    """112 rule matched in the patient's words. Returns False if this session already has an emergency."""
    with _lock:
        if any(r["session_id"] == session_id and r["urgency"] == "emergency" for r in REQUESTS):
            return False
    _add_request(session_id, "symptoms", "emergency",
                 f"Regel-Erkennung: akutes Warnzeichen („{term}“). 112-Hinweis wurde sofort angezeigt.",
                 patient_text, "regel")
    return True


def rule_warning(session_id, sign, patient_text) -> bool:
    """A warning sign from the letter (e.g. fever over 38.5 °C) in the patient's words: urgent callback by rule.

    Returns False if this session already has an open urgent or emergency symptom request.
    """
    with _lock:
        if any(r["session_id"] == session_id and r["category"] == "symptoms" and r["status"] == "offen"
               and r["urgency"] in ("urgent", "emergency") and time.time() - r["created"] < 300 for r in REQUESTS):
            return False
    _add_request(session_id, "symptoms", "urgent",
                 f"Regel-Erkennung: Warnzeichen laut Entlassbrief ({sign}). Bitte Patientin dringend zurückrufen.",
                 patient_text, "regel")
    return True


def record_safety_stop(session_id, problem, answer, patient_text) -> dict:
    """The app stopped an answer that didn't match the approved letter; the team reviews it."""
    return _add_request(session_id, "safety", "urgent",
                        f"Sicherheitsprüfung hat eine Antwort gestoppt: {problem['reason']} "
                        "Patientin bitte zur Medikation kontaktieren.",
                        patient_text, "regel", stopped_answer=answer)


def patient_text(session_id) -> str:
    with _lock:
        return " ".join(line["text"] for line in SESSIONS.get(session_id, {}).get("transcript", [])
                        if line["role"] == "patient")


def last_patient_text(session_id) -> str:
    with _lock:
        lines = [line["text"] for line in SESSIONS.get(session_id, {}).get("transcript", []) if line["role"] == "patient"]
    return lines[-1] if lines else ""


def reset():
    with _lock:
        SESSIONS.clear()
        REQUESTS.clear()
        FAULT["armed"] = False


def staff_view() -> dict:
    with _lock:
        return {"requests": list(reversed(REQUESTS)), "fault_armed": FAULT["armed"],
                "sessions": sorted((dict(s) for s in SESSIONS.values()), key=lambda s: -s["started"])}


TOOL_SCHEMAS = [
    {
        "name": "get_discharge_information",
        "description": (
            "Returns sections of the patient's physician-approved discharge letter (German medical source text, "
            "written for the GP). Sections: diagnoses, history (reason for admission), findings (ultrasound, lab, "
            "pending histology), course (operation and hospital stay), medication (discharge medication), followup "
            "(appointments, daily-life rules, warning signs incl. 112, contacts). Call this before answering ANY "
            "question about the stay, diagnosis, treatment, medication, appointments, pending results, daily life, "
            "warning signs, contacts, or what a term or abbreviation in the letter means."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section_ids": {"type": "array", "items": {"type": "string", "enum": list(SECTIONS)},
                                "minItems": 1, "description": "One or more letter sections to read."},
            },
            "required": ["section_ids"],
        },
    },
    {
        "name": "request_staff_callback",
        "description": (
            "Hands a question or concern over to the clinical team. Use when the approved letter does not answer "
            "the question, when the patient asks for medical advice or a change to treatment, when the patient "
            "reports symptoms, or when the patient asks to speak to a person."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": CATEGORIES},
                "urgency": {"type": "string", "enum": URGENCY,
                            "description": "emergency only for acute danger signs (112 already advised)."},
                "summary_de": {"type": "string",
                               "description": "Short, factual German summary for the clinical team."},
                "patient_question": {"type": "string",
                                     "description": "The patient's question in their own words and language."},
            },
            "required": ["category", "urgency", "summary_de", "patient_question"],
        },
    },
]

_TOOLS = {"get_discharge_information": get_discharge_information,
          "request_staff_callback": request_staff_callback}


def run_tool(name, args, session_id=None):
    tool = _TOOLS.get(name)
    if tool is None:
        return {"ok": False, "message": f"Unknown tool '{name}'."}
    try:
        return tool(**args, session_id=session_id)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "message": f"Invalid arguments for {name}: {exc}"}
