"""Patient discharge voice assistant: FastAPI between the browser and the Foundry voice agent.

    browser (mic, speaker, transcript)  <-- /ws -->  app.py  <-- realtime -->  Foundry voice agent

- The browser streams microphone audio (PCM16 mono, 24 kHz) or typed questions to /ws.
- app.py forwards them to the voice agent and streams the spoken reply back.
- Tool calls (approved-letter retrieval, staff callback) are executed here, in tools.py.

The Entra ID credential stays on the server; no token reaches the browser.

    uvicorn app:app --port 8010
"""

import asyncio
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path

import segno
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import (
    RealtimeConversationItemFunctionCallOutput,
    RealtimeConversationItemMessageSystem,
    RealtimeConversationItemMessageSystemContent,
    RealtimeConversationItemMessageUser,
    RealtimeConversationItemMessageUserContent,
    RealtimeServerEventConversationItemInputAudioTranscriptionCompleted,
    RealtimeServerEventError,
    RealtimeServerEventInputAudioBufferSpeechStarted,
    RealtimeServerEventResponseAudioDelta,
    RealtimeServerEventResponseAudioTranscriptDelta,
    RealtimeServerEventResponseAudioTranscriptDone,
    RealtimeServerEventResponseCreated,
    RealtimeServerEventResponseDone,
    RealtimeServerEventResponseFunctionCallArgumentsDone,
)
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

import safety
from language import detect_language
import settings
import tools

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with (
        settings.async_credential() as credential,
        AIProjectClient(endpoint=settings.ENDPOINT, credential=credential, allow_preview=True) as client,
    ):
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
async def letter_page():
    return FileResponse(STATIC / "letter.html")


@app.get("/patient")
async def patient_page():
    return FileResponse(STATIC / "patient.html")


@app.get("/team")
async def staff_page():
    return FileResponse(STATIC / "staff.html")


@app.get("/api/letter")
async def letter():
    """Full approved letter for the printable page and the patient's own view."""
    return tools.LETTER


@app.get("/api/languages")
async def languages():
    return [{"code": code, "name": name} for code, (name, _) in settings.LANGUAGES.items()]


@app.get("/api/qr.svg")
async def qr_code():
    url = f"{settings.PUBLIC_BASE_URL}/patient?brief={tools.LETTER['letter_id']}"
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="svg", scale=6, border=2, dark="#0b3a53")
    return Response(buffer.getvalue(), media_type="image/svg+xml", headers={"X-Target-Url": url})


@app.get("/api/staff")
async def staff():
    return tools.staff_view()


@app.post("/api/staff/{request_id}/done")
async def complete_request(request_id: str):
    for request in tools.REQUESTS:
        if request["id"] == request_id:
            request["status"] = "erledigt"
            return request
    raise HTTPException(404, "Unknown request")


@app.post("/api/reset")
async def reset():
    tools.reset()
    return {"ok": True}


@app.post("/api/demo/fault")
async def arm_fault():
    """Demo: the next medication lookup returns a wrong Ramipril dose, so the safety check can be shown."""
    tools.FAULT["armed"] = not tools.FAULT["armed"]
    return {"armed": tools.FAULT["armed"]}


def system_item(text: str):
    return RealtimeConversationItemMessageSystem(
        content=[RealtimeConversationItemMessageSystemContent(type="input_text", text=text)])


def language_context(code: str) -> str:
    name = settings.LANGUAGES[code][0]
    patient = tools.LETTER["patient"]["name"]
    return (f"The patient selected {name} in the app. Start in {name}, but always answer in the language "
            f"of the patient's most recent message. The approved discharge letter belongs to {patient}.")


MAX_RECONNECTS = 3


def resume_context(session_id: str) -> str:
    """Context for a replacement voice session after the realtime connection dropped."""
    session = tools.SESSIONS.get(session_id, {})
    recent = session.get("transcript", [])[-12:]
    lines = "\n".join(f"{'Patient' if line['role'] == 'patient' else 'Assistant'}: {line['text']}" for line in recent)
    return (language_context(session.get("language", "de")) + " The connection was briefly interrupted. "
            "Continue the same conversation: do not greet again and do not repeat earlier answers unless asked. "
            "Earlier statements still need the approved letter: call get_discharge_information again before "
            "answering letter questions.\nRecent conversation:\n" + (lines or "(none)"))


@app.websocket("/ws")
async def voice_session(browser: WebSocket):
    await browser.accept()
    language = browser.query_params.get("lang", "de")
    if language not in settings.LANGUAGES:
        language = "de"
    greet = browser.query_params.get("greet", "1") != "0"
    session_id = tools.start_session(language)
    client: AIProjectClient = app.state.client
    state = {"response_active": False, "respond_after": False, "session": session_id,
             "answer": "", "stopped": None, "corrections": 0, "answer_language": language}
    reconnects = 0
    try:
        await browser.send_json({"type": "config", "channels": 1, "session": session_id})
        while True:
            try:
                async with client.beta.voice_agents.realtime.connect(agent_name=settings.AGENT_NAME) as agent:
                    state.update(response_active=False, respond_after=False)
                    if reconnects:
                        await agent.conversation.item.create(item=system_item(resume_context(session_id)))
                    elif greet:
                        await agent.conversation.item.create(item=system_item(
                            language_context(language) + " Greet the patient in one short sentence, say you can "
                            "explain the discharge letter, and ask what they would like to know."))
                        await request_response(agent, state)
                    else:
                        await agent.conversation.item.create(item=system_item(language_context(language)))
                    await browser.send_json({"type": "status", "text": "reconnected" if reconnects else "connected"})
                    inbound = asyncio.create_task(browser_to_agent(browser, agent, state))
                    outbound = asyncio.create_task(agent_to_browser(agent, browser, state))
                    await asyncio.wait({inbound, outbound}, return_when=asyncio.FIRST_COMPLETED)
                    if inbound.done():
                        # The browser hung up (or failed): end the session.
                        outbound.cancel()
                        exc = inbound.exception()
                        if exc and not isinstance(exc, WebSocketDisconnect):
                            raise exc
                        return
                    # The realtime connection ended or failed while the browser is still open.
                    inbound.cancel()
                    await asyncio.gather(inbound, return_exceptions=True)
                    if outbound.exception():
                        raise outbound.exception()
                    raise ConnectionResetError("The realtime connection closed.")
            except WebSocketDisconnect:
                return
            except Exception as exc:
                if browser.client_state != WebSocketState.CONNECTED or reconnects >= MAX_RECONNECTS:
                    raise
                reconnects += 1
                print(f"Realtime connection lost ({exc!r}); reconnect {reconnects}/{MAX_RECONNECTS}")
                await browser.send_json({"type": "status", "text": "reconnecting"})
                await asyncio.sleep(1)
    except Exception as exc:
        print(f"Session error: {exc!r}")
        await safe_send(browser, {"type": "error", "text": str(exc)})
    finally:
        await safe_send(browser, {"type": "status", "text": "ended"})
        try:
            await browser.close()
        except RuntimeError:
            pass


async def safe_send(browser: WebSocket, message: dict):
    try:
        await browser.send_json(message)
    except (WebSocketDisconnect, RuntimeError):
        pass


async def request_response(agent, state: dict):
    """Start a response now, or right after the active one finishes (only one may run at a time)."""
    if state["response_active"]:
        state["respond_after"] = True
    else:
        state["response_active"] = True
        await agent.response.create()


async def browser_to_agent(browser: WebSocket, agent, state: dict):
    """Forward microphone audio, typed questions, and language changes to the voice agent."""
    while True:
        message = await browser.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
        if message.get("bytes"):
            await agent.input_audio_buffer.append(audio=message["bytes"])
            continue
        data = json.loads(message.get("text") or "{}")
        if data.get("type") == "text" and data.get("text", "").strip():
            text = data["text"].strip()[:1000]
            tools.log(state["session"], "patient", text, channel="text")
            await on_patient_text(browser, state, text, agent)
            await agent.conversation.item.create(item=RealtimeConversationItemMessageUser(
                content=[RealtimeConversationItemMessageUserContent(type="input_text", text=text)]))
            await request_response(agent, state)
        elif data.get("type") == "language" and data.get("code") in settings.LANGUAGES:
            tools.set_language(state["session"], data["code"])
            state["answer_language"] = data["code"]
            await agent.conversation.item.create(item=system_item(
                language_context(data["code"]) + " Briefly confirm the language change in one sentence."))
            await request_response(agent, state)


async def on_patient_text(browser: WebSocket, state: dict, text: str, agent=None):
    """Rule-based checks on the patient's words, independent of the model."""
    state["corrections"] = 0
    state["language_restarts"] = 0
    state["awaiting_transcript"] = False
    spoken = detect_language(text)
    if agent is not None and spoken and spoken != state.get("answer_language"):
        state["answer_language"] = spoken
        tools.set_language(state["session"], spoken)
        name = settings.LANGUAGES[spoken][0]
        print(f"Language switch: patient now speaks {name}")
        await agent.conversation.item.create(item=system_item(
            f"LANGUAGE: The patient's latest message is in {name}. Answer in {name} from now on (also for any "
            f"answer you are giving right now), until the patient switches language again."))
        if state["response_active"]:
            # Spoken input: the answer already started (in the old language) before the transcript arrived.
            # Stop it, hide its fragment, and start again in the new language.
            await browser.send_json({"type": "interrupt"})
            state["drop_transcript"] = True
            await agent.response.cancel()
            state["respond_after"] = True
    term = safety.detect_emergency(text)
    if term and tools.rule_emergency(state["session"], term, text):
        print(f"Safety rule: emergency term '{term}'")
        await browser.send_json({"type": "rule_emergency", "term": term})
    elif not term:
        sign = safety.detect_warning(text)
        if sign and tools.rule_warning(state["session"], sign, text):
            print(f"Safety rule: warning sign '{sign}'")
            await browser.send_json({"type": "rule_callback", "sign": sign})


async def check_answer_language(agent, browser: WebSocket, state: dict):
    """The model sometimes drifts back to an earlier language. Once the first words of an answer show the
    language, compare it with the patient's; if it differs, stop the answer and start it again once."""
    if state.get("language_checked") or state.get("awaiting_transcript") or len(state["answer"]) < 25:
        return
    said = detect_language(state["answer"])
    if said is None and len(state["answer"]) < 120:
        return
    state["language_checked"] = True
    wanted = state.get("answer_language")
    if not said or not wanted or said == wanted or state.get("language_restarts", 0) >= 1:
        return
    state["language_restarts"] = state.get("language_restarts", 0) + 1
    name = settings.LANGUAGES[wanted][0]
    print(f"Language guard: answer started in {said}, patient speaks {wanted}; restarting")
    await browser.send_json({"type": "interrupt"})
    state["drop_transcript"] = True
    await agent.conversation.item.create(item=system_item(
        f"LANGUAGE: Your last answer was in the wrong language and was not delivered. The patient speaks {name}. "
        f"Answer the patient's most recent message again, entirely in {name}."))
    if state["response_active"]:
        await agent.response.cancel()
    state["respond_after"] = True


async def stop_answer(agent, browser: WebSocket, state: dict, problem: dict):
    """The streaming answer contradicts the approved letter: stop it before it is (fully) spoken."""
    state["stopped"] = problem
    print(f"Safety check stopped an answer: {problem['reason']}")
    await browser.send_json({"type": "guard", "rule": problem["rule"], "reason": problem["reason"]})
    if state["response_active"]:
        await agent.response.cancel()
    tools.record_safety_stop(state["session"], problem, state["answer"], tools.last_patient_text(state["session"]))


def correction_prompt(problem: dict, last_question: str) -> str:
    return ("SAFETY CHECK: the app stopped your last answer because it did not match the approved letter "
            f"({problem['reason']}). Do not repeat that statement. Call get_discharge_information again for the "
            "relevant section, then answer briefly using only the exact drug names and doses from the letter. "
            f"The patient's most recent message was: \"{last_question}\". Answer in exactly the same language as that "
            "message (not the language of these instructions or of earlier messages). Say that the care team has been "
            "informed and will call back about the medication.")


async def agent_to_browser(agent, browser: WebSocket, state: dict):
    """Relay agent events to the browser and execute function tool calls."""
    pending_outputs = []
    async for event in agent:
        if isinstance(event, RealtimeServerEventResponseAudioDelta):
            if not state["stopped"]:
                await browser.send_bytes(event.delta)

        elif isinstance(event, RealtimeServerEventResponseCreated):
            state["response_active"] = True
            state["answer"], state["stopped"] = "", None
            state["language_checked"] = False
            await browser.send_json({"type": "response_started"})

        elif isinstance(event, RealtimeServerEventInputAudioBufferSpeechStarted):
            state["awaiting_transcript"] = True
            await browser.send_json({"type": "interrupt"})
            if state["response_active"]:
                await agent.response.cancel()

        elif isinstance(event, RealtimeServerEventConversationItemInputAudioTranscriptionCompleted):
            text = (event.transcript or "").strip()
            state["awaiting_transcript"] = False
            tools.log(state["session"], "patient", text)
            await browser.send_json({"type": "transcript", "role": "patient", "text": text})
            await on_patient_text(browser, state, text, agent)

        elif isinstance(event, RealtimeServerEventResponseAudioTranscriptDelta):
            state["answer"] += event.delta or ""
            if not state["stopped"] and not state.get("drop_transcript"):
                await check_answer_language(agent, browser, state)
            if not state["stopped"] and not state.get("drop_transcript"):
                problem = safety.check_answer(state["answer"], tools.patient_text(state["session"]))
                if problem:
                    await stop_answer(agent, browser, state, problem)

        elif isinstance(event, RealtimeServerEventResponseAudioTranscriptDone):
            stopped = state["stopped"]
            if state.get("drop_transcript"):
                # Fragment of an answer restarted for a language switch: keep it out of the chat.
                tools.log(state["session"], "assistant", "[NEU GESTARTET: Sprachwechsel] " + (event.transcript or ""))
                continue
            tools.log(state["session"], "assistant", ("[GESTOPPT] " if stopped else "") + (event.transcript or ""))
            await browser.send_json({"type": "transcript", "role": "assistant", "text": event.transcript,
                                     "stopped": bool(stopped)})

        elif isinstance(event, RealtimeServerEventResponseFunctionCallArgumentsDone):
            try:
                args = json.loads(event.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run_tool(event.name, args, session_id=state["session"])
            print(f"Tool call: {event.name}({args}) -> ok={result.get('ok')}")
            pending_outputs.append((event.call_id, result))
            await browser.send_json({"type": "tool", "name": event.name, "args": args, "result": result})
            if event.name == "get_discharge_information" and "medication" in args.get("section_ids", []):
                # Shown from the approved letter itself, not from what the model says or the tool returned.
                await browser.send_json({"type": "medication_card", "plan": safety.MEDICATIONS,
                                         "source": tools.LETTER["letter_id"],
                                         "approved_at": tools.LETTER["approval"]["approved_at"]})

        elif isinstance(event, RealtimeServerEventResponseDone):
            state["response_active"] = False
            state["drop_transcript"] = False
            if state["stopped"]:
                problem, state["stopped"] = state["stopped"], None
                pending_outputs.clear()
                state["corrections"] += 1
                if state["corrections"] <= 1:
                    await agent.conversation.item.create(item=system_item(
                        correction_prompt(problem, tools.last_patient_text(state["session"]))))
                    state["respond_after"] = True
                else:
                    await browser.send_json({"type": "guard_final"})
            if pending_outputs:
                for call_id, result in pending_outputs:
                    await agent.conversation.item.create(item=RealtimeConversationItemFunctionCallOutput(
                        call_id=call_id, output=json.dumps(result, ensure_ascii=False)))
                pending_outputs.clear()
                state["respond_after"] = True
            if state["respond_after"]:
                state["respond_after"] = False
                await request_response(agent, state)

        elif isinstance(event, RealtimeServerEventError):
            if event.error.code == "response_cancel_not_active":
                continue
            print(f"Agent error: {event.error.message}")
            await browser.send_json({"type": "error", "text": event.error.message})
