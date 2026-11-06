import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

import tools
from app import app


class FakeAgent:
    """Stands in for a realtime voice connection; optionally drops after a short delay."""

    def __init__(self, drop: bool):
        self.drop, self.items, self.responses = drop, [], 0
        self.conversation = SimpleNamespace(item=SimpleNamespace(create=self._create_item))
        self.response = SimpleNamespace(create=self._create_response, cancel=self._noop)
        self.input_audio_buffer = SimpleNamespace(append=self._noop)

    async def _create_item(self, item):
        self.items.append(item)

    async def _create_response(self):
        self.responses += 1

    async def _noop(self, **_):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0.2 if self.drop else 30)
        raise ConnectionResetError("The realtime connection was closed abnormally (code 1006).")


class FakeClient:
    def __init__(self):
        self.agents = [FakeAgent(drop=True), FakeAgent(drop=False)]
        self.connects = 0
        self.beta = SimpleNamespace(voice_agents=SimpleNamespace(realtime=SimpleNamespace(connect=self.connect)))

    def connect(self, agent_name):
        agent = self.agents[self.connects]
        self.connects += 1

        class Context:
            async def __aenter__(self):
                return agent

            async def __aexit__(self, *_):
                return False

        return Context()


def text_of(item):
    return item.content[0].text


def test_dropped_realtime_connection_reconnects_with_conversation_context():
    tools.reset()
    fake = FakeClient()
    app.state.client = fake
    client = TestClient(app)
    with client.websocket_connect("/ws?lang=en&greet=1") as ws:
        assert ws.receive_json()["type"] == "config"
        session = next(iter(tools.SESSIONS))
        tools.log(session, "patient", "Can I stop the Ramipril?")
        assert ws.receive_json() == {"type": "status", "text": "connected"}
        assert ws.receive_json() == {"type": "status", "text": "reconnecting"}
        assert ws.receive_json() == {"type": "status", "text": "reconnected"}
        ws.send_json({"type": "text", "text": "And my appointments?"})
        for _ in range(50):
            if len(fake.agents[1].items) == 2:
                break
            asyncio.run(asyncio.sleep(0.05))
    first, second = fake.agents
    assert fake.connects == 2
    assert "Greet the patient" in text_of(first.items[0]) and first.responses == 1
    resume = text_of(second.items[0])
    assert "interrupted" in resume and "do not greet again" in resume
    assert "Patient: Can I stop the Ramipril?" in resume and "English" in resume
    assert text_of(second.items[1]) == "And my appointments?"
    tools.reset()
