import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from .data import CASES, initial_case


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit(case: dict, action: str, detail: str, reviewer: str = "Demo-System"):
    case["audit"].append({
        "id": str(uuid4()), "at": now(), "action": action,
        "detail": detail, "reviewer": reviewer,
    })


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, state TEXT NOT NULL)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS demo_backups "
                "(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, state TEXT NOT NULL)"
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(demo_backups)")}
            if "run_state" not in columns:
                db.execute("ALTER TABLE demo_backups ADD COLUMN run_state TEXT NOT NULL DEFAULT '[]'")
            db.execute("CREATE TABLE IF NOT EXISTS agent_runs (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, state TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS intake_files (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, content_type TEXT NOT NULL, original BLOB NOT NULL, previews TEXT NOT NULL)")
            for identifier in CASES:
                db.execute(
                    "INSERT OR IGNORE INTO cases VALUES (?, ?)",
                    (identifier, json.dumps(initial_case(identifier), ensure_ascii=False)),
                )
            for identifier, state in db.execute("SELECT id, state FROM cases").fetchall():
                case = json.loads(state)
                changed = False
                for key, default in [("intakes", []), ("followup_tasks", []),
                                     ("event_automation", {"enabled": False, "events": []})]:
                    if key not in case:
                        case[key] = default
                        changed = True
                if "kis" not in case:
                    case["kis"] = {
                        "medication_released": any(d["kind"] == "Medikation" for d in case["documents"]),
                        "retrieval_fault": False, "letters": [],
                    }
                    changed = True
                if changed:
                    db.execute("UPDATE cases SET state = ? WHERE id = ?",
                               (json.dumps(case, ensure_ascii=False), identifier))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, identifier: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT state FROM cases WHERE id = ?", (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, "Demo-Fall nicht gefunden.")
        return json.loads(row[0])

    def mutate(self, identifier: str, revision: int, operation) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM cases WHERE id = ?", (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, "Demo-Fall nicht gefunden.")
            case = json.loads(row[0])
            if case["revision"] != revision:
                raise HTTPException(409, "Der Fall wurde zwischenzeitlich geändert. Bitte neu laden.")
            operation(case)
            case["revision"] += 1
            db.execute(
                "UPDATE cases SET state = ? WHERE id = ?",
                (json.dumps(case, ensure_ascii=False), identifier),
            )
        return case

    def reset(self, revisions: dict[str, int]) -> tuple[str, list[dict]]:
        if set(revisions) != set(CASES):
            raise HTTPException(422, "Für das Zurücksetzen sind die Versionsstände aller drei Demo-Fälle erforderlich.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            states = [
                json.loads(row[0]) for row in db.execute("SELECT state FROM cases")
            ]
            current = {case["id"]: case for case in states}
            if set(current) != set(CASES) or any(
                current[identifier]["revision"] != revision
                for identifier, revision in revisions.items()
            ):
                raise HTTPException(409, "Demo-Fälle wurden zwischenzeitlich geändert. Bitte neu laden und das Zurücksetzen erneut bestätigen.")
            backup_id = str(uuid4())
            db.execute(
                "INSERT INTO demo_backups (id, created_at, state, run_state) VALUES (?, ?, ?, ?)",
                (backup_id, now(), json.dumps(states, ensure_ascii=False),
                 json.dumps([json.loads(row[0]) for row in db.execute("SELECT state FROM agent_runs")],
                            ensure_ascii=False)),
            )
            restored = []
            for identifier in CASES:
                case = initial_case(identifier)
                # Keep revisions monotonic so pre-reset requests cannot restore old content.
                case["revision"] = current[identifier]["revision"] + 1
                db.execute(
                    "UPDATE cases SET state = ? WHERE id = ?",
                    (json.dumps(case, ensure_ascii=False), identifier),
                )
                restored.append(case)
            db.execute("DELETE FROM agent_runs")
        return backup_id, restored

    def start_run(self, identifier: str, revision: int) -> tuple[dict, dict]:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM cases WHERE id = ?", (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, "Demo-Fall nicht gefunden.")
            case = json.loads(row[0])
            if case["revision"] != revision:
                raise HTTPException(409, "Der Fall wurde geändert. Bitte neu laden.")
            runs = [json.loads(r[0]) for r in db.execute("SELECT state FROM agent_runs WHERE case_id = ?", (identifier,))]
            if any(run["status"] == "running" for run in runs):
                raise HTTPException(409, "Für diesen Fall läuft bereits ein Agentenauftrag.")
            run = {
                "id": str(uuid4()), "case_id": identifier, "created_at": now(), "status": "running",
                "base_revision": revision, "source_version": case["source_version"],
                "events": [], "proposal": None, "error": None,
                "base_sections": case["draft"]["sections"] if case["draft"] else [],
            }
            pending = [item for item in case["event_automation"]["events"] if item["status"] == "queued"]
            if case["event_automation"]["enabled"] and pending:
                selected = pending[-1]
                for item in pending[:-1]:
                    item["status"] = "superseded"
                selected.update(status="running", run_id=run["id"])
                run["trigger"] = {key: selected[key] for key in ["id", "kind", "title"]}
                db.execute("UPDATE cases SET state=? WHERE id=?", (json.dumps(case, ensure_ascii=False), identifier))
            db.execute("INSERT INTO agent_runs VALUES (?, ?, ?)",
                       (run["id"], identifier, json.dumps(run, ensure_ascii=False)))
        return run, case

    def runs(self, identifier: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT state FROM agent_runs WHERE case_id = ? ORDER BY rowid DESC LIMIT 12",
                              (identifier,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def update_run(self, identifier: str, operation) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM agent_runs WHERE id = ?", (identifier,)).fetchone()
            if not row:
                raise HTTPException(409, "Agentenauftrag wurde zurückgesetzt oder entfernt.")
            run = json.loads(row[0])
            operation(run)
            db.execute("UPDATE agent_runs SET state = ? WHERE id = ?", (json.dumps(run, ensure_ascii=False), identifier))
        return run

    def commit_run(self, identifier: str, run_id: str, revision: int, operation) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM cases WHERE id = ?", (identifier,)).fetchone()
            run_row = db.execute("SELECT state FROM agent_runs WHERE id = ? AND case_id = ?",
                                 (run_id, identifier)).fetchone()
            if not row or not run_row:
                raise HTTPException(404, "Fall oder Agentenauftrag nicht gefunden.")
            case, run = json.loads(row[0]), json.loads(run_row[0])
            if case["revision"] != revision:
                raise HTTPException(409, "Der Fall wurde geändert. Bitte neu laden.")
            operation(case, run)
            case["revision"] += 1
            db.execute("UPDATE cases SET state = ? WHERE id = ?", (json.dumps(case, ensure_ascii=False), identifier))
            db.execute("UPDATE agent_runs SET state = ? WHERE id = ?", (json.dumps(run, ensure_ascii=False), run_id))
        return case

    def recover_runs(self):
        with self.connection() as db:
            for identifier, state in db.execute("SELECT id, state FROM agent_runs").fetchall():
                run = json.loads(state)
                if run["status"] == "running":
                    run["status"] = "failed"
                    run["error"] = "Server wurde neu gestartet. Agentenauftrag bitte erneut starten; kein Vorschlag übernommen."
                    run["events"].append({"at": now(), "kind": "error", "title": run["error"]})
                    db.execute("UPDATE agent_runs SET state = ? WHERE id = ?",
                               (json.dumps(run, ensure_ascii=False), identifier))
            for identifier, state in db.execute("SELECT id, state FROM cases").fetchall():
                case = json.loads(state)
                changed = False
                for item in case.get("intakes", []):
                    if item["status"] == "analyzing":
                        item.update(status="failed", error="Server neu gestartet. Dokumentanalyse ausdrücklich erneut starten.")
                        changed = True
                for item in case.get("event_automation", {}).get("events", []):
                    if item["status"] in {"queued", "running"}:
                        item.update(status="failed", error="Server neu gestartet. Ereignisprüfung ausdrücklich erneut starten.")
                        changed = True
                if changed:
                    case["revision"] += 1
                    db.execute("UPDATE cases SET state=? WHERE id=?", (json.dumps(case, ensure_ascii=False), identifier))

    def add_intake(self, identifier: str, revision: int, intake: dict, raw: bytes,
                   content_type: str, previews: list[str]) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM cases WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, "Demo-Fall nicht gefunden.")
            case = json.loads(row[0])
            if case["revision"] != revision:
                raise HTTPException(409, "Fall geändert. Dokument nicht übernommen; aktuellen Stand laden.")
            if len(case["intakes"]) >= 4:
                raise HTTPException(409, "Maximal vier Dokumenteingänge pro Demo-Fall. Für einen neuen Durchlauf die Demo zurücksetzen.")
            db.execute("INSERT INTO intake_files VALUES (?,?,?,?,?)",
                       (intake["id"], identifier, content_type, raw, json.dumps(previews)))
            case["intakes"].append(intake)
            case["revision"] += 1
            db.execute("UPDATE cases SET state=? WHERE id=?", (json.dumps(case, ensure_ascii=False), identifier))
        return case

    def intake_file(self, identifier: str, intake_id: str) -> tuple[bytes, str, list[str]]:
        case = self.get(identifier)
        if not any(item["id"] == intake_id for item in case["intakes"]):
            raise HTTPException(404, "Dokumenteingang gehört nicht zum aktuellen Demo-Aufenthalt.")
        with self.connection() as db:
            row = db.execute("SELECT original,content_type,previews FROM intake_files WHERE id=? AND case_id=?",
                             (intake_id, identifier)).fetchone()
        if not row:
            raise HTTPException(404, "Originaldatei fehlt.")
        return row[0], row[1], json.loads(row[2])

    def update_intake(self, identifier: str, intake_id: str, operation) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM cases WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, "Demo-Fall nicht gefunden.")
            case = json.loads(row[0])
            intake = next((item for item in case["intakes"] if item["id"] == intake_id), None)
            if not intake or intake["status"] != "analyzing":
                raise HTTPException(409, "Dokumentanalyse wurde zurückgesetzt oder ist nicht mehr aktiv.")
            operation(intake)
            case["revision"] += 1
            db.execute("UPDATE cases SET state=? WHERE id=?", (json.dumps(case, ensure_ascii=False), identifier))
        return case

    def start_event_run(self, identifier: str) -> tuple[dict, dict] | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM cases WHERE id=?", (identifier,)).fetchone()
            if not row:
                return None
            case = json.loads(row[0])
            if not case["event_automation"]["enabled"]:
                return None
            pending = [item for item in case["event_automation"]["events"] if item["status"] == "queued"]
            runs = [json.loads(row[0]) for row in db.execute("SELECT state FROM agent_runs WHERE case_id=?", (identifier,))]
            if not pending or any(run["status"] == "running" for run in runs):
                return None
            selected = pending[-1]
            for item in pending[:-1]:
                item.update(status="superseded")
            selected["status"] = "running"
            run = {
                "id": str(uuid4()), "case_id": identifier, "created_at": now(), "status": "running",
                "base_revision": case["revision"], "source_version": case["source_version"],
                "events": [{"at": now(), "kind": "trigger", "title": selected["title"]}],
                "proposal": None, "error": None,
                "base_sections": case["draft"]["sections"] if case["draft"] else [],
                "trigger": {"id": selected["id"], "kind": selected["kind"], "title": selected["title"]},
            }
            selected["run_id"] = run["id"]
            db.execute("INSERT INTO agent_runs VALUES (?,?,?)", (run["id"], identifier, json.dumps(run, ensure_ascii=False)))
            db.execute("UPDATE cases SET state=? WHERE id=?", (json.dumps(case, ensure_ascii=False), identifier))
        return run, case

    def finish_event(self, identifier: str, run: dict):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM cases WHERE id=?", (identifier,)).fetchone()
            if not row:
                return
            case = json.loads(row[0])
            item = next((item for item in case["event_automation"]["events"] if item.get("run_id") == run["id"]), None)
            if item:
                item.update(status="ready" if run["status"] == "awaiting_approval" else "failed", error=run["error"])
                db.execute("UPDATE cases SET state=? WHERE id=?", (json.dumps(case, ensure_ascii=False), identifier))
