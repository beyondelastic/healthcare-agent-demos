"""Agent cockpit: FastAPI app serving the presentation UI and the agent workflow API.

    uvicorn app:app --port 8020
"""

import io
from pathlib import Path

import segno
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import settings
import workflow

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Klinik Cockpit · KI-Agenten")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Approval(BaseModel):
    physician: str = Field(min_length=2, max_length=80)
    confirmed: bool


def full_state() -> dict:
    result = workflow.snapshot()
    result["agents"] = {"writer": settings.WRITER_MODEL, "reviewer": settings.REVIEWER_MODEL}
    return result


def guarded(action):
    try:
        action()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return full_state()


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
async def state():
    return full_state()


@app.get("/api/sources/{source_id}")
async def source(source_id: str):
    item = next((s for s in workflow.snapshot()["sources"] if s["id"] == source_id), None)
    if item is None:
        raise HTTPException(404, "Unbekannte Quelle")
    if item["status"] == "unreleased":
        item = {**item, "text": None}
    return item


@app.post("/api/prepare")
async def prepare():
    return guarded(workflow.prepare)


@app.post("/api/events/medication-released")
async def medication_released():
    return guarded(workflow.release_medication_event)


@app.post("/api/approve")
async def approve(body: Approval):
    if not body.confirmed:
        raise HTTPException(422, "Bitte die Prüfung bestätigen.")
    return guarded(lambda: workflow.approve(body.physician.strip()))


@app.post("/api/dispatch/{channel}")
async def dispatch(channel: str):
    return guarded(lambda: workflow.dispatch(channel))


@app.get("/api/qr.svg")
async def qr_code():
    buffer = io.BytesIO()
    segno.make(settings.VOICE_ASSISTANT_URL, error="m").save(buffer, kind="svg", scale=6, border=2, dark="#0b3b35")
    return Response(buffer.getvalue(), media_type="image/svg+xml", headers={"X-Target-Url": settings.VOICE_ASSISTANT_URL})


@app.post("/api/reset")
async def reset():
    if workflow.snapshot()["busy"]:
        raise HTTPException(409, "Die Agenten arbeiten gerade. Bitte kurz warten.")
    workflow.reset()
    return full_state()
