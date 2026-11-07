"""Hospital welcome avatar: FastAPI between the kiosk browser and the Foundry voice agent with avatar.

    kiosk browser (mic, avatar video via WebRTC, map)  <-- /ws -->  app.py  <-- realtime -->  Foundry agent

- The browser streams microphone audio (PCM16 mono, 24 kHz) or typed/tapped questions to /ws.
- Avatar video and the synchronised voice reach the browser over WebRTC. app.py only relays the
  WebRTC signalling (ICE servers, SDP offer and answer); the Entra ID credential stays on the server.
- Tool calls (wayfinding, check-in, visitor information, staff call) are executed here, in tools.py.

    uvicorn app:app --port 8030
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

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
    RealtimeServerEventResponseAudioTranscriptDone,
    RealtimeServerEventResponseCreated,
    RealtimeServerEventResponseDone,
    RealtimeServerEventResponseFunctionCallArgumentsDone,
    RealtimeServerEventSessionCreated,
    RealtimeServerEventSessionUpdated,
    VoiceAgentServerEventSessionAvatarConnecting,
)
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

import safety
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
async def kiosk_page():
    return FileResponse(STATIC / "kiosk.html")


@app.get("/team")
async def team_page():
    return FileResponse(STATIC / "team.html")


@app.get("/api/campus")
async def campus():
    """Map data for the kiosk screen (no appointments)."""
    keys = ["hospital", "kiosk", "demo_now", "buildings", "streets"]
    locations = [{k: loc[k] for k in ("id", "name", "building", "floor", "room", "path", "pin")}
                 for loc in tools.CAMPUS["locations"]]
    return {**{k: tools.CAMPUS[k] for k in keys}, "locations": locations}


@app.get("/api/team")
async def team():
    return tools.team_view()


@app.post("/api/team/{kind}/{item_id}/done")
async def complete(kind: str, item_id: str):
    items = {"checkins": tools.CHECKINS, "requests": tools.REQUESTS}.get(kind)
    for item in items or []:
        if item["id"] == item_id:
            item["status"] = "erledigt"
            return item
    raise HTTPException(404, "Unknown item")


@app.post("/api/reset")
async def reset():
    tools.reset()
    return {"ok": True}


def system_item(text: str):
    return RealtimeConversationItemMessageSystem(
        content=[RealtimeConversationItemMessageSystemContent(type="input_text", text=text)])


def context(code: str) -> str:
    name = settings.LANGUAGES[code][0]
    now = tools.CAMPUS["demo_now"]
    return (f"Today is {now['weekday']}, {now['date']}, it is {now['time']}. The visitor selected {name} on the kiosk. "
            f"Start in {name}, but always answer in the language of the visitor's most recent message.")


def as_dict(event) -> dict:
    try:
        return event.as_dict()
    except AttributeError:
        return dict(event)


def ice_servers(event) -> list[dict] | None:
    """ICE servers for the avatar's WebRTC connection, sent by the service with the session."""
    servers = ((as_dict(event).get("session") or {}).get("avatar") or {}).get("ice_servers")
    if not servers:
        return None
    return [{k: s[k] for k in ("urls", "username", "credential") if s.get(k)} for s in servers]


@app.websocket("/ws")
async def kiosk_session(browser: WebSocket):
    await browser.accept()
    language = browser.query_params.get("lang", "de")
    if language not in settings.LANGUAGES:
        language = "de"
    session_id = tools.start_session(language)
    client: AIProjectClient = app.state.client
    state = {"response_active": False, "respond_after": False, "session": session_id, "language": language,
             "greeted": False, "ice_sent": False}
    try:
        await browser.send_json({"type": "config", "session": session_id})
        async with client.beta.voice_agents.realtime.connect(agent_name=settings.AGENT_NAME) as agent:
            await agent.conversation.item.create(item=system_item(context(language)))
            await browser.send_json({"type": "status", "text": "connected"})
            inbound = asyncio.create_task(browser_to_agent(browser, agent, state))
            outbound = asyncio.create_task(agent_to_browser(agent, browser, state))
            done, _ = await asyncio.wait({inbound, outbound}, return_when=asyncio.FIRST_COMPLETED)
            for task in (inbound, outbound):
                task.cancel()
            await asyncio.gather(inbound, outbound, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc and not isinstance(exc, WebSocketDisconnect):
                    raise exc
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"Session error: {exc!r}")
        await safe_send(browser, {"type": "error", "text": str(exc)})
    finally:
        await safe_send(browser, {"type": "status", "text": "ended"})
        if browser.client_state == WebSocketState.CONNECTED:
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
    """Start a response now, or right after the active one (only one may run at a time)."""
    if state["response_active"]:
        state["respond_after"] = True
    else:
        state["response_active"] = True
        await agent.response.create()


async def greet(agent, state: dict):
    if state["greeted"]:
        return
    state["greeted"] = True
    await agent.conversation.item.create(item=system_item(
        "Greet the visitor now as described in your instructions, in one or two short sentences."))
    await request_response(agent, state)


async def on_visitor_text(browser: WebSocket, state: dict, text: str):
    """Rule-based alarm on the visitor's words, independent of the model."""
    term = safety.detect_emergency(text)
    if term:
        result = tools.call_staff("unwell", "urgent", f"Regel-Erkennung: akutes Warnzeichen („{term}“) am Kiosk.",
                                  session_id=state["session"], origin="regel")
        print(f"Safety rule: emergency term '{term}' -> staff {result.get('request_id')}")
        await browser.send_json({"type": "rule_alarm", "term": term})


async def browser_to_agent(browser: WebSocket, agent, state: dict):
    """Forward microphone audio, typed/tapped questions, language changes and WebRTC signalling."""
    while True:
        message = await browser.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
        if message.get("bytes"):
            await agent.input_audio_buffer.append(audio=message["bytes"])
            continue
        data = json.loads(message.get("text") or "{}")
        kind = data.get("type")
        if kind == "avatar_offer" and data.get("sdp"):
            await agent.session.avatar_connect(client_sdp=data["sdp"])
        elif kind == "avatar_ready" or kind == "no_avatar":
            if data.get("greet", True):
                await greet(agent, state)
            else:
                state["greeted"] = True
        elif kind == "text" and data.get("text", "").strip():
            text = data["text"].strip()[:500]
            tools.log(state["session"], "visitor", text, channel="text")
            await on_visitor_text(browser, state, text)
            await agent.conversation.item.create(item=RealtimeConversationItemMessageUser(
                content=[RealtimeConversationItemMessageUserContent(type="input_text", text=text)]))
            await request_response(agent, state)
        elif kind == "language" and data.get("code") in settings.LANGUAGES:
            tools.set_language(state["session"], data["code"])
            await agent.conversation.item.create(item=system_item(
                context(data["code"]) + " Briefly confirm the language change in one sentence."))
            await request_response(agent, state)


async def agent_to_browser(agent, browser: WebSocket, state: dict):
    """Relay agent events to the browser and execute function tool calls."""
    pending_outputs = []
    async for event in agent:
        if isinstance(event, (RealtimeServerEventSessionCreated, RealtimeServerEventSessionUpdated)):
            servers = ice_servers(event)
            if servers and not state["ice_sent"]:
                state["ice_sent"] = True
                await browser.send_json({"type": "ice_servers", "servers": servers})

        elif isinstance(event, VoiceAgentServerEventSessionAvatarConnecting):
            await browser.send_json({"type": "avatar_answer", "sdp": event.server_sdp})

        elif isinstance(event, RealtimeServerEventResponseAudioDelta):
            # Only used when the avatar video is unavailable; with avatar, voice arrives over WebRTC.
            await browser.send_bytes(event.delta)

        elif isinstance(event, RealtimeServerEventResponseCreated):
            state["response_active"] = True
            await browser.send_json({"type": "response_started"})

        elif isinstance(event, RealtimeServerEventInputAudioBufferSpeechStarted):
            await browser.send_json({"type": "interrupt"})
            if state["response_active"]:
                await agent.response.cancel()

        elif isinstance(event, RealtimeServerEventConversationItemInputAudioTranscriptionCompleted):
            text = (event.transcript or "").strip()
            tools.log(state["session"], "visitor", text)
            await browser.send_json({"type": "transcript", "role": "visitor", "text": text})
            await on_visitor_text(browser, state, text)

        elif isinstance(event, RealtimeServerEventResponseAudioTranscriptDone):
            tools.log(state["session"], "assistant", event.transcript)
            await browser.send_json({"type": "transcript", "role": "assistant", "text": event.transcript})

        elif isinstance(event, RealtimeServerEventResponseFunctionCallArgumentsDone):
            try:
                args = json.loads(event.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if args.get("language") in settings.LANGUAGES:
                tools.set_language(state["session"], args["language"])
            result = tools.run_tool(event.name, args, session_id=state["session"])
            print(f"Tool call: {event.name}({args}) -> ok={result.get('ok')}")
            pending_outputs.append((event.call_id, result))
            await browser.send_json({"type": "tool", "name": event.name, "args": args, "result": result})

        elif isinstance(event, RealtimeServerEventResponseDone):
            state["response_active"] = False
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
