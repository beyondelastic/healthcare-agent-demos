"""Agent workflow: writer drafts, reviewer checks, writer revises; events update the letter.

State lives in memory and is streamed to the UI by polling /api/state. Every event in
the timeline is a real model call, tool call, validation, or human action; nothing is
simulated progress.
"""

import json
import threading
import time
from copy import deepcopy

from case import LETTER, PATIENT, SECTIONS, SYSTEMS, initial_sources, release_medication

_lock = threading.RLock()
STATE: dict = {}
MAX_ROUNDS = 8
MAX_REVISIONS = 2


def reset():
    with _lock:
        STATE.clear()
        STATE.update({
            "phase": "idle", "busy": False, "error": None,
            "sources": initial_sources(), "events": [], "draft": None, "review": None, "review_rounds": [],
            "approval": None, "update_count": 0, "dispatch": {},
            "stats": {"model_calls": 0, "tool_calls": 0, "sources_read": [], "seconds": 0.0, "tokens": 0},
        })


reset()


def snapshot() -> dict:
    with _lock:
        state = deepcopy(STATE)
    state["patient"] = PATIENT
    state["systems"] = SYSTEMS
    state["letter"] = LETTER
    if state.get("run_started"):
        state["stats"]["seconds"] = round(state["stats"]["seconds"] + time.monotonic() - state["run_started"], 1)
    state.pop("run_started", None)
    state["stats"]["systems"] = sorted({s["system"] for s in state["sources"] if s["id"] in state["stats"]["sources_read"]})
    state["stats"]["sources_read"] = len(state["stats"]["sources_read"])
    return state


def log(agent: str, kind: str, title: str, **details):
    with _lock:
        STATE["events"].append({"at": time.time(), "agent": agent, "kind": kind, "title": title, **details})


def _source(source_id: str) -> dict | None:
    return next((s for s in STATE["sources"] if s["id"] == source_id), None)


# ---------- Tools (executed here, requested by the agents) ----------

def list_patient_sources() -> dict:
    with _lock:
        return {"patient": PATIENT, "sources": [
            {"id": s["id"], "system": s["system"], "system_name": SYSTEMS[s["system"]], "title": s["title"],
             "date": s["date"], "status": s["status"]} for s in STATE["sources"]]}


def read_source(source_id: str) -> dict:
    with _lock:
        source = _source(source_id)
        if source is None:
            return {"ok": False, "error": f"Unbekannte Quelle {source_id}."}
        if source["status"] == "unreleased":
            return {"ok": True, "id": source_id, "system": source["system"], "title": source["title"],
                    "status": "unreleased",
                    "content": None, "notice": "Inhalt noch nicht freigegeben (Prüfung durch Stationsapotheke). Nicht verwenden."}
        if source_id not in STATE["stats"]["sources_read"]:
            STATE["stats"]["sources_read"].append(source_id)
        return {"ok": True, "id": source_id, "system": source["system"], "title": source["title"],
                "date": source["date"], "status": source["status"], "content": source["text"]}


def run_tool(name: str, arguments: str) -> dict:
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "error": "Ungültige Argumente."}
    if name == "list_patient_sources":
        return list_patient_sources()
    if name == "read_source" and isinstance(args.get("source_id"), str):
        return read_source(args["source_id"])
    return {"ok": False, "error": f"Unbekanntes Werkzeug {name}."}


# ---------- Validation ----------

def validate_draft(parsed: dict, read: set[str], required_reads: set[str]) -> list[str]:
    problems = []
    ids = [s["id"] for s in parsed.get("sections", [])]
    if sorted(ids) != sorted(SECTIONS):
        problems.append(f"Genau sechs Abschnitte mit den IDs {list(SECTIONS)} erforderlich, erhalten: {ids}.")
    missing = required_reads - read
    if missing:
        problems.append(f"Diese Quellen wurden nicht gelesen: {sorted(missing)}. Mit read_source lesen.")
    with _lock:
        readable = {s["id"] for s in STATE["sources"] if s["status"] != "unreleased"}
        med_released = _source("med-entlassplan")["status"] != "unreleased"
        not_final = {s["id"]: s["status"] for s in STATE["sources"] if s["status"] in ("pending", "unreleased")}
    flagged = {sid for point in parsed.get("open_points", []) for sid in point.get("source_ids", [])}
    for sid, status in not_final.items():
        if sid not in flagged:
            problems.append(f"Quelle {sid} ist {status}: dafür muss ein offener Punkt mit source_ids [{sid!r}] bestehen bleiben.")
    for point in parsed.get("open_points", []):
        if point.get("kind") in ("unreleased", "pending") and point.get("source_ids") and not set(point["source_ids"]) & set(not_final):
            problems.append(f"Offener Punkt '{point['title']}' ist erledigt: die Quelle ist inzwischen verfügbar. Entfernen.")
    for section in parsed.get("sections", []):
        bad = [sid for sid in section["source_ids"] if sid not in read or sid not in readable]
        if bad:
            problems.append(f"Abschnitt {section['id']} zitiert nicht gelesene oder nicht freigegebene Quellen {bad}.")
        if section["id"] == "medication" and not med_released and "Pantoprazol" in section["text"]:
            problems.append("Entlassmedikation enthält Inhalte des nicht freigegebenen Plans.")
    return problems


def _diff_sections(previous: dict | None, sections: list[dict]) -> list[dict]:
    before = {s["id"]: s for s in previous["sections"]} if previous else {}
    result = []
    for section in sorted(sections, key=lambda s: list(SECTIONS).index(s["id"])):
        old = before.get(section["id"])
        changed = bool(previous) and (old is None or old["text"].strip() != section["text"].strip())
        result.append({**section, "title": SECTIONS[section["id"]], "changed": changed,
                       "previous_text": old["text"] if changed and old else None})
    return result


# ---------- Agent loop ----------

def run_agent(client, agent: dict, role: str, payload: dict, required_reads=frozenset(), validator=None,
              known_reads=frozenset()) -> dict:
    history = [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    read: set[str] = set()
    repairs = 0
    started = time.monotonic()
    for round_number in range(MAX_ROUNDS):
        log(role, "model", "Denkt nach …" if round_number == 0 else "Wertet Ergebnisse aus …")
        response = client.responses.create(
            input=history, store=False, timeout=90, max_output_tokens=6000,
            extra_body={"agent_reference": {"type": "agent_reference", "name": agent["name"], "version": agent["version"]}})
        with _lock:
            STATE["stats"]["model_calls"] += 1
            STATE["stats"]["tokens"] += getattr(response.usage, "total_tokens", 0) if response.usage else 0
        calls = [item for item in response.output if item.type == "function_call"]
        if calls:
            history.extend(response.output)
            for call in calls:
                result = run_tool(call.name, call.arguments)
                with _lock:
                    STATE["stats"]["tool_calls"] += 1
                if call.name == "read_source" and result.get("ok"):
                    read.add(result["id"])
                    log(role, "read", result["title"], source_id=result["id"], system=result["system"],
                        status=result["status"])
                elif call.name == "list_patient_sources":
                    log(role, "list", f"{len(result['sources'])} Quellen in {len({s['system'] for s in result['sources']})} Systemen gefunden")
                else:
                    log(role, "error", result.get("error", "Werkzeugfehler"))
                history.append({"type": "function_call_output", "call_id": call.call_id,
                                "output": json.dumps(result, ensure_ascii=False)})
            continue
        try:
            parsed = json.loads(response.output_text)
            problems = validator(parsed, read | set(known_reads), set(required_reads)) if validator else []
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            problems = [f"Antwort nicht im erwarteten Format: {exc}"]
        if not problems:
            parsed["_seconds"] = round(time.monotonic() - started, 1)
            return parsed
        if repairs >= 2:
            raise ValueError("Validierung fehlgeschlagen: " + " ".join(problems))
        repairs += 1
        log(role, "validation", "Server-Prüfung: Korrektur angefordert", problems=problems)
        history.extend(response.output)
        history.append({"role": "user", "content": json.dumps(
            {"server_validation": "Antwort abgelehnt. Probleme beheben und vollständig neu ausgeben.",
             "problems": problems}, ensure_ascii=False)})
    raise ValueError("Maximale Anzahl Agentenschritte erreicht.")


def _writer(client, versions, payload, required_reads, baseline):
    log("writer", "start", payload["mode_title"])
    with _lock:
        # Sources already read earlier in this demo may be cited without re-reading;
        # the content cannot have changed unless an event says so (then it is required).
        known = set(STATE["stats"]["sources_read"]) - set(required_reads) if payload["mode"] != "initial" else set()
    parsed = run_agent(client, versions["writer"], "writer", payload, required_reads, validate_draft, known)
    with _lock:
        previous = STATE["draft"]
        sections = _diff_sections(baseline, parsed["sections"])
        if payload["mode"] == "revision" and previous:
            before = {s["id"]: s for s in previous["sections"]}
            for section in sections:
                old = before.get(section["id"])
                section["revised"] = bool(old and old["text"].strip() != section["text"].strip()) or (old or {}).get("revised", False)
                section["revised_from"] = (old.get("revised_from") or old["text"]) if section["revised"] and old else None
        STATE["draft"] = {"sections": sections, "open_points": parsed["open_points"], "summary": parsed["summary"],
                          "version": (previous["version"] + 1) if previous else 1, "seconds": parsed["_seconds"]}
    changed = [s["title"] for s in sections if s["changed"] or s.get("revised")]
    log("writer", "draft", parsed["summary"], open_points=len(parsed["open_points"]), changed=changed,
        seconds=parsed["_seconds"])


def _reviewer(client, versions):
    with _lock:
        draft = {"sections": [{k: s[k] for k in ("id", "title", "text", "source_ids")} for s in STATE["draft"]["sections"]],
                 "open_points": STATE["draft"]["open_points"]}
    log("reviewer", "start", "Prüft den Entwurf unabhängig gegen die Quellen")
    parsed = run_agent(client, versions["reviewer"], "reviewer",
                       {"task": "Diesen Entlassbrief-Entwurf prüfen.", "patient": PATIENT, "draft": draft})
    errors = [f for f in parsed["findings"] if f["severity"] == "fehler"]
    parsed["verdict"] = "überarbeiten" if errors else "freigabefähig"
    with _lock:
        STATE["review"] = {k: parsed[k] for k in ("verdict", "summary", "findings")} | {"seconds": parsed["_seconds"]}
        STATE["review_rounds"].append({"draft_version": STATE["draft"]["version"], "verdict": parsed["verdict"],
                                       "errors": errors, "summary": parsed["summary"]})
    log("reviewer", "review", parsed["summary"], verdict=parsed["verdict"], errors=len(errors),
        hints=len(parsed["findings"]) - len(errors), seconds=parsed["_seconds"])
    return errors


def pipeline(mode: str, event: str | None = None):
    from azure.ai.projects import AIProjectClient

    import settings
    started = time.monotonic()
    try:
        versions = settings.agent_versions()
        with settings.credential() as credential, AIProjectClient(endpoint=settings.ENDPOINT, credential=credential) as project:
            with project.get_openai_client(max_retries=1) as client:
                with _lock:
                    readable = {s["id"] for s in STATE["sources"]}
                    baseline = deepcopy(STATE["draft"]) if mode != "initial" else None
                if mode == "initial":
                    payload = {"mode": "initial", "mode_title": "Erstellt den Entlassbrief aus allen Systemen",
                               "task": "Entlassbrief für die Hausarztpraxis erstellen.", "patient": PATIENT,
                               "sections": SECTIONS}
                    required = readable
                else:
                    with _lock:
                        previous = [{k: s[k] for k in ("id", "text", "source_ids")} for s in STATE["draft"]["sections"]]
                        points = STATE["draft"]["open_points"]
                    payload = {"mode": "update", "mode_title": "Aktualisiert den Brief nach neuem Systemereignis",
                               "task": "Entwurf nach Systemereignis aktualisieren.", "event": event,
                               "patient": PATIENT, "previous_draft": previous, "previous_open_points": points}
                    required = {"med-entlassplan"}
                _writer(client, versions, payload, required, baseline)
                errors = _reviewer(client, versions)
                for _ in range(MAX_REVISIONS):
                    if not errors:
                        break
                    with _lock:
                        previous = [{k: s[k] for k in ("id", "text", "source_ids")} for s in STATE["draft"]["sections"]]
                        points = STATE["draft"]["open_points"]
                    log("writer", "handoff", f"Übernimmt {len(errors)} Befund(e) des Prüf-Agenten")
                    _writer(client, versions, {
                        "mode": "revision", "mode_title": "Überarbeitet den Entwurf nach Prüfbefund",
                        "task": "Die Fehler des Prüf-Agenten korrigieren. Alles andere unverändert lassen.",
                        "patient": PATIENT, "previous_draft": previous, "previous_open_points": points,
                        "review_findings": errors}, set(), baseline)
                    errors = _reviewer(client, versions)
        with _lock:
            STATE["phase"] = "ready"
    except Exception as exc:  # surfaced in the UI; no fallback letter
        log("system", "error", f"Agentenlauf fehlgeschlagen: {exc}")
        with _lock:
            STATE["phase"] = "failed"
            STATE["error"] = str(exc)
    finally:
        with _lock:
            STATE["busy"] = False
            STATE["run_started"] = None
            STATE["stats"]["seconds"] = round(STATE["stats"]["seconds"] + time.monotonic() - started, 1)


def _start(mode: str, event: str | None = None, background: bool = True):
    with _lock:
        if STATE["busy"]:
            raise RuntimeError("Die Agenten arbeiten bereits.")
        STATE.update(busy=True, phase="running", error=None, run_started=time.monotonic())
    if background:
        threading.Thread(target=pipeline, args=(mode, event), daemon=True).start()
    else:
        pipeline(mode, event)


def prepare(background: bool = True):
    with _lock:
        if STATE["approval"]:
            raise RuntimeError("Der Brief ist bereits freigegeben. Demo zurücksetzen.")
    log("system", "trigger", "Auftrag: Entlassbrief für die Entlassung heute vorbereiten")
    _start("initial", background=background)


def release_medication_event(background: bool = True):
    with _lock:
        if STATE["approval"]:
            raise RuntimeError("Der Brief ist bereits freigegeben.")
        if _source("med-entlassplan")["status"] != "unreleased":
            raise RuntimeError("Der Medikationsplan ist bereits freigegeben.")
        if STATE["busy"]:
            raise RuntimeError("Die Agenten arbeiten gerade. Bitte kurz warten.")
        release_medication(STATE["sources"])
        STATE["update_count"] += 1
        has_draft = STATE["draft"] is not None
    log("system", "event", "Medikationsmodul: Stationsapotheke hat den Entlassmedikationsplan freigegeben",
        system="MED", source_id="med-entlassplan")
    if has_draft:
        _start("update", "Medikationsmodul: Der Entlassmedikationsplan (med-entlassplan) wurde soeben freigegeben.",
               background=background)


def approve(physician: str):
    with _lock:
        if STATE["busy"] or STATE["phase"] != "ready" or not STATE["draft"]:
            raise RuntimeError("Noch kein geprüfter Entwurf zur Freigabe.")
        if STATE["approval"]:
            raise RuntimeError("Bereits freigegeben.")
        STATE["approval"] = {"by": physician, "at": time.time(), "version": STATE["draft"]["version"],
                             "open_points": len(STATE["draft"]["open_points"])}
        STATE["phase"] = "approved"
    log("human", "approval", f"Ärztlich freigegeben von {physician}")


DISPATCH = {
    "kim": lambda: f"eArztbrief per KIM an {LETTER['recipient'][0]} gesendet ({LETTER['kim_address']}) – Simulation",
    "epa": lambda: f"Entlassbrief in die ePA von {PATIENT['name']} eingestellt – Simulation",
    "print": lambda: "Patientenexemplar mit QR-Code zum Entlass-Assistenten gedruckt",
}


def dispatch(channel: str):
    with _lock:
        if not STATE["approval"]:
            raise RuntimeError("Erst nach ärztlicher Freigabe möglich.")
        if channel not in DISPATCH:
            raise RuntimeError("Unbekannter Versandweg.")
        STATE["dispatch"][channel] = time.time()
    log("system", "dispatch", DISPATCH[channel](), channel=channel)
