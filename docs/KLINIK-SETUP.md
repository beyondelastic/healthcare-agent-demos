# Clinical demo setup: Klinik Cockpit · KI-Agenten

These instructions use Windows and an existing Foundry project. They do not
provision a subscription, project, or model deployment. All data is synthetic
and built into the app ([case.py](../agent-cockpit/case.py)). The demo runs on
port 8020 and is independent of the other two demos.

## 1. Prerequisites

- Python 3.11+, Azure CLI, Microsoft Edge or Google Chrome.
- A Foundry project with two model deployments that support structured outputs.
  The reference build uses `gpt-4.1` for the writer (fast) and `gpt-5.5` for the
  reviewer (more thorough). Weaker reviewer models missed real errors in tests.
- The **Foundry User** role on the project for the signed-in identity (create agent
  versions and call them).

## 2. Configure

From `agent-cockpit`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set in `agent-cockpit\.env`:

| Variable | Value |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Endpoint copied from your Foundry project |
| `AZURE_TENANT_ID` | Directory that owns the project |
| `WRITER_MODEL` / `REVIEWER_MODEL` | Exact deployment names, defaults `gpt-4.1` / `gpt-5.5` |
| `WRITER_AGENT_NAME` / `REVIEWER_AGENT_NAME` | Defaults `cockpit-writer` / `cockpit-reviewer` |
| `VOICE_ASSISTANT_URL` | URL in the QR code on the final letter (the voice demo) |

```powershell
az login --tenant YOUR-DIRECTORY-ID
```

## 3. Create the agents

```powershell
.\.venv\Scripts\python.exe create_agents.py
```

This saves a new, immutable version of both prompt agents (instructions, strict
JSON output schema, two function tools) and writes the versions to the ignored
`.agents.json`. Rerun it after changing [agents.py](../agent-cockpit/agents.py).

## 4. Start and check

```powershell
.\Start-AgentCockpit.ps1
```

Open <http://127.0.0.1:8020/> and press **↺ Zurücksetzen**.

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # local, no Azure calls
.\.venv\Scripts\python.exe e2e_test.py     # live: draft, event update, approval, sending
```

The live test runs the full flow against the real agents (about 1–2 minutes) and
checks that unreleased medication is never cited, that open points match pending
sources, that the event only updates the medication section, and that approval
and simulated sending work. Then rehearse with the
[presenter script](KLINIK-SCRIPT-DE.md); agent run times vary (first draft about
30–45 s, update 15–30 s).

## Completion checklist

- Live end-to-end test passes.
- One full rehearsal in the browser at the presentation resolution (F11).
- The QR code on the final letter opens the voice demo (if it is running).
- **↺ Zurücksetzen** pressed before the session.

The state lives in memory only and is cleared on restart or reset. See
[operations](OPERATIONS.md) for troubleshooting. The earlier cockpit is archived in
[archive/klinik-cockpit-v1](../archive/klinik-cockpit-v1/README.md).
