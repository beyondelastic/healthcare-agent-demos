"""Live end-to-end check of the app's safety layer through the running app (typed input, real agent).

    .\\Start-VoiceDemo.ps1            # in another terminal
    python e2e_safety_test.py

1. A medication question shows the medication card from the letter, and no answer is stopped.
2. With the demo fault armed, the wrong Ramipril dose is stopped, the team gets a safety request,
   and the agent answers again with the letter's dose.
3. Chest pain triggers the 112 rule, independent of the model.
"""

import asyncio
import json
import sys
import time

import httpx
import websockets

BASE = "127.0.0.1:8010"


async def conversation(question: str, seconds: float = 45) -> list[dict]:
    events = []
    async with websockets.connect(f"ws://{BASE}/ws?lang=de&greet=0", max_size=None) as ws:
        sent, end = False, time.time() + seconds
        while time.time() < end:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, end - time.time()))
            except asyncio.TimeoutError:
                break
            if isinstance(raw, bytes):
                continue
            event = json.loads(raw)
            events.append(event)
            if event.get("type") == "status" and event.get("text") == "connected" and not sent:
                await ws.send(json.dumps({"type": "text", "text": question}))
                sent = True
            answers = [e for e in events if e.get("type") == "transcript" and e.get("role") == "assistant"
                       and not e.get("stopped")]
            if answers and any(ch.isdigit() for ch in answers[-1]["text"]) and len(answers) >= 2:
                await asyncio.sleep(2)
                break
    return events


def of(events, kind):
    return [e for e in events if e.get("type") == kind]


def answers(events):
    return [e["text"] for e in of(events, "transcript") if e.get("role") == "assistant"]


async def main():
    problems = []
    async with httpx.AsyncClient(base_url=f"http://{BASE}") as http:
        await http.post("/api/reset")

        events = await conversation("Welche Tabletten muss ich wann nehmen?")
        print("1 answers:", answers(events))
        if not of(events, "medication_card"):
            problems.append("1: no medication card")
        if of(events, "guard"):
            problems.append(f"1: unexpected stop {of(events, 'guard')}")

        await http.post("/api/demo/fault")
        events = await conversation("Wie viel Ramipril muss ich nehmen?", seconds=70)
        guard = of(events, "guard")
        final = [e["text"] for e in of(events, "transcript") if e.get("role") == "assistant" and not e.get("stopped")]
        print("2 guard:", guard, "\n2 answers:", answers(events))
        if not guard or guard[0]["rule"] != "verwechslung":
            problems.append("2: wrong dose was not stopped")
        if not any("5" in a and "10" not in a for a in final):
            problems.append("2: no corrected answer with the letter's dose")
        staff = (await http.get("/api/staff")).json()
        if not any(r["category"] == "safety" for r in staff["requests"]):
            problems.append("2: no safety request for the team")

        events = await conversation("Ich habe plötzlich starke Brustschmerzen.", seconds=25)
        print("3 rule:", of(events, "rule_emergency"), "\n3 answers:", answers(events))
        if not of(events, "rule_emergency"):
            problems.append("3: emergency rule did not fire")

        events = await conversation("Ich habe neununddreißig Grad Fieber bekommen.", seconds=30)
        staff = (await http.get("/api/staff")).json()
        urgent = [r for r in staff["requests"] if r["category"] == "symptoms" and r["urgency"] == "urgent"]
        print("4 rule:", of(events, "rule_callback"), "\n4 answers:", answers(events), "\n4 requests:",
              [(r["origin"], r["patient_question"]) for r in urgent])
        if not of(events, "rule_callback"):
            problems.append("4: warning-sign rule did not fire")
        if len(urgent) != 1:
            problems.append(f"4: expected exactly one urgent symptom request, got {len(urgent)}")
        await http.post("/api/reset")

    for p in problems:
        print("!", p)
    print("PASS" if not problems else "FAIL")
    return len(problems)


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
