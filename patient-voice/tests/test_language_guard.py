"""Language guard: an answer that drifts into another language than the patient's is stopped and restarted once."""
import asyncio

import app


class FakeBrowser:
    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)


class FakeAgent:
    def __init__(self):
        self.items, self.cancelled = [], 0
        agent = self

        class Item:
            async def create(self, item):
                agent.items.append(item)

        class Conversation:
            item = Item()

        class Response:
            async def cancel(self):
                agent.cancelled += 1

        self.conversation, self.response = Conversation(), Response()


def state(answer, **extra):
    return {"answer": answer, "answer_language": "de", "response_active": True, "respond_after": False,
            "language_checked": False, "language_restarts": 0, **extra}


def run(s):
    agent, browser = FakeAgent(), FakeBrowser()
    asyncio.run(app.check_answer_language(agent, browser, s))
    return agent, browser


def test_english_answer_for_german_patient_is_restarted():
    s = state("Okay, thanks for telling me, let me check what your discharge letter says")
    agent, browser = run(s)
    assert agent.cancelled == 1 and s["drop_transcript"] and s["respond_after"]
    assert {"type": "interrupt"} in browser.sent
    assert "Deutsch" in str(agent.items[0]) or "German" in str(agent.items[0])


def test_german_answer_is_left_alone():
    s = state("Im Entlassbrief steht, dass Sie sich bei Fieber über 38,5 Grad wieder vorstellen sollen")
    agent, _ = run(s)
    assert agent.cancelled == 0 and s["language_checked"] and not s["respond_after"]


def test_only_one_restart_per_question():
    s = state("Okay, thanks for telling me, let me check what your discharge letter says", language_restarts=1)
    agent, _ = run(s)
    assert agent.cancelled == 0


def test_waits_for_spoken_transcript():
    s = state("Okay, thanks for telling me, let me check what your discharge letter says", awaiting_transcript=True)
    agent, _ = run(s)
    assert agent.cancelled == 0 and not s["language_checked"]
