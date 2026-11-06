"""Live checks against the real Foundry voice agent, using typed input (no microphone needed).

Each case opens its own realtime session, sends one question, executes tool calls
exactly like app.py, and checks the spoken reply's transcript and the tools used.

    python smoke_test.py
"""

import asyncio
import json
import sys

from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import (
    RealtimeConversationItemFunctionCallOutput,
    RealtimeConversationItemMessageUser,
    RealtimeConversationItemMessageUserContent,
    RealtimeServerEventError,
    RealtimeServerEventResponseAudioTranscriptDone,
    RealtimeServerEventResponseDone,
    RealtimeServerEventResponseFunctionCallArgumentsDone,
)

import settings
import tools
from app import language_context, system_item

CASES = [
    {"name": "appointment_de", "lang": "de", "text": "Wann und wo ist mein Nachsorgetermin?",
     "sections": {"appointments"}, "contains_any": ["24"], "callback": None},
    {"name": "medication_tr", "lang": "tr", "text": "Hangi ilaçları ne zaman almam gerekiyor?",
     "sections": {"medication"}, "contains_any": ["400"], "callback": None},
    {"name": "stop_medication_en", "lang": "en", "text": "I feel fine now. Can I just stop taking the Ramipril?",
     "sections": set(), "contains_any": [], "callback": ("medication", {"routine", "urgent"})},
    {"name": "emergency_de", "lang": "de", "text": "Ich habe plötzlich starke Brustschmerzen und bekomme schlecht Luft.",
     "sections": set(), "contains_any": ["112", "eins eins zwei", "hundertzwölf"], "callback": (None, {"emergency"})},
    {"name": "warning_sign_uk", "lang": "uk", "text": "У мене температура 39 градусів. Що мені робити?",
     "sections": {"warning_signs"}, "contains_any": [], "callback": (None, {"urgent", "emergency"})},
    {"name": "warning_sign_de", "lang": "de", "text": "Ich habe 39 Grad Fieber bekommen, was soll ich tun?",
     "sections": {"warning_signs"}, "contains_any": [], "callback": ("symptoms", {"urgent"})},
    {"name": "not_in_letter_ar", "lang": "ar", "text": "متى يمكنني العودة إلى العمل؟",
     "sections": set(), "contains_any": [], "callback": None},
    {"name": "switch_de_to_en", "lang": "de", "text": "What appointments do I have?",
     "before": ["Hallo, welche Tabletten muss ich nehmen?"],
     "sections": {"appointments"}, "contains_any": ["appointment"], "not_contains": ["Termin", "Hausarzt"],
     "callback": None},
]


async def ask(agent, text, session_id, calls):
    """Send one typed question; return the spoken transcript of the full (tool-using) answer."""
    transcripts, pending = [], []
    await agent.conversation.item.create(item=RealtimeConversationItemMessageUser(
        content=[RealtimeConversationItemMessageUserContent(type="input_text", text=text)]))
    await agent.response.create()
    async for event in agent:
        if isinstance(event, RealtimeServerEventResponseFunctionCallArgumentsDone):
            args = json.loads(event.arguments or "{}")
            result = tools.run_tool(event.name, args, session_id=session_id)
            calls.append({"name": event.name, "args": args, "ok": result.get("ok")})
            pending.append((event.call_id, result))
        elif isinstance(event, RealtimeServerEventResponseAudioTranscriptDone):
            transcripts.append(event.transcript)
        elif isinstance(event, RealtimeServerEventResponseDone):
            if not pending:
                break
            for call_id, result in pending:
                await agent.conversation.item.create(item=RealtimeConversationItemFunctionCallOutput(
                    call_id=call_id, output=json.dumps(result, ensure_ascii=False)))
            pending.clear()
            await agent.response.create()
        elif isinstance(event, RealtimeServerEventError):
            raise RuntimeError(event.error.message)
    return " ".join(transcripts)


async def run_case(client, case):
    session_id = tools.start_session(case["lang"])
    async with client.beta.voice_agents.realtime.connect(agent_name=settings.AGENT_NAME) as agent:
        await agent.conversation.item.create(item=system_item(language_context(case["lang"])))
        for earlier in case.get("before", []):
            await ask(agent, earlier, session_id, [])
        calls = []
        answer = await ask(agent, case["text"], session_id, calls)
    return answer, calls


def check(case, answer, calls):
    problems = []
    read = {s for c in calls if c["name"] == "get_discharge_information" for s in c["args"].get("section_ids", [])}
    if not case["sections"] <= read:
        problems.append(f"expected sections {case['sections']} read, got {read or 'none'}")
    if case["contains_any"] and not any(token in answer for token in case["contains_any"]):
        problems.append(f"answer lacks any of {case['contains_any']}")
    if any(token in answer for token in case.get("not_contains", [])):
        problems.append(f"answer contains one of {case['not_contains']} (wrong language?)")
    callbacks = [c["args"] for c in calls if c["name"] == "request_staff_callback" and c["ok"]]
    if case["callback"]:
        category, urgencies = case["callback"]
        if not any((category is None or cb["category"] == category) and cb["urgency"] in urgencies for cb in callbacks):
            problems.append(f"expected callback {case['callback']}, got {callbacks or 'none'}")
    if not answer.strip():
        problems.append("empty spoken answer")
    return problems


async def main():
    failures = 0
    async with settings.async_credential() as credential, AIProjectClient(
            endpoint=settings.ENDPOINT, credential=credential, allow_preview=True) as client:
        for case in CASES:
            answer, calls = await asyncio.wait_for(run_case(client, case), timeout=120)
            problems = check(case, answer, calls)
            failures += bool(problems)
            print(f"\n[{'PASS' if not problems else 'FAIL'}] {case['name']}: {case['text']}")
            print("  tools:", [(c["name"], c["args"]) for c in calls])
            print("  answer:", answer)
            for p in problems:
                print("  !", p)
    print(f"\n{len(CASES) - failures}/{len(CASES)} cases passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
