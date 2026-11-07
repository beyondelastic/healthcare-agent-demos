# Voice demo setup: Entlass-Assistent

These instructions use Windows and an existing Foundry project. They do not
provision a subscription, project, or model deployment. Keep all data synthetic.
The demo is independent of the clinical cockpit and runs on port 8010.

## 1. Prerequisites

- Python 3.11+, Azure CLI, Microsoft Edge or Google Chrome, a microphone
  (a headset avoids the assistant hearing itself through open speakers).
- A Foundry project in a region where **voice agents** (preview) are available.
  The reference build used Sweden Central with the service-managed
  `gpt-realtime-2.1` model; check the project's model list for what your region offers.
- The **Foundry User** role on the project for the signed-in identity, which is
  enough to create agent versions and open realtime voice sessions.
- No model deployment is needed: the voice agent uses a service-managed model.
  Voice sessions incur normal usage charges.

## 2. Configure

From `patient-voice`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set in `patient-voice\.env`:

| Variable | Value |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Endpoint copied from your Foundry project |
| `AZURE_TENANT_ID` | Directory that owns the project |
| `FOUNDRY_VOICE_AGENT_NAME` | Defaults to `patient-discharge-voice` |
| `FOUNDRY_VOICE_AGENT_MODEL` | Realtime model available to voice agents, e.g. `gpt-realtime-2.1` |
| `FOUNDRY_VOICE_AGENT_VOICE` | Multilingual Azure voice, default `de-DE-Seraphina:DragonHDLatestNeural` |
| `FOUNDRY_VOICE_TRANSCRIPTION_MODEL` | Display transcripts, default `gpt-4o-transcribe` |
| `PUBLIC_BASE_URL` | URL in the QR code; default `http://127.0.0.1:8010` |

Sign in to the owning tenant:

```powershell
az login --tenant YOUR-DIRECTORY-ID
```

## 3. Create the voice agent

```powershell
.\.venv\Scripts\python.exe create_agent.py
```

Each run saves a new, immutable agent version; sessions use the latest. The
definition contains the instructions ([instructions.md](../patient-voice/instructions.md)),
audio settings, and two function tools. There is no separate deployment step.

Turn detection uses the language-independent Azure semantic VAD. The multilingual
variant rejected Ukrainian (`Unsupported locales: uk-UA`) in the reference build.

### Optional: Foundry guardrail

Set `FOUNDRY_ACCOUNT_RESOURCE_ID` (Foundry resource > JSON view > ID) in `.env`, then run
`setup_guardrail.py` **before** `create_agent.py`. It needs Foundry Account Owner (or
Contributor) on the resource and creates:

- the guardrail (RAI policy) `patient-voice-guardrail`: content-harm controls, Prompt Shields
  (jailbreak in input, indirect attacks in tool results), Task Adherence (preview) on tool calls;
- the blocklist `patientvoiceadvice` with advice phrases (same list as `safety.py`), on output.

`create_agent.py` then assigns it through `rai_config`; check it under **Guardrails** in the
Foundry portal. In the reference build the guardrail blocked these phrases for a text prompt
agent, but realtime voice sessions did **not** enforce the blocklist (preview). The app's own
checks ([safety.py](../patient-voice/safety.py)) therefore enforce the same list; see
[architecture](ARCHITECTURE.md). Groundedness detection isn't available for agents.

## 4. Start and check

```powershell
.\Start-VoiceDemo.ps1
```

| Page | Purpose |
|---|---|
| <http://127.0.0.1:8010/> | Fictional printed discharge letter with QR code |
| <http://127.0.0.1:8010/patient> | Patient page: language, microphone, typed questions |
| <http://127.0.0.1:8010/team> | Care-team view: callback requests, transcripts, reset |

Checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # local, no Azure calls (incl. safety rules)
.\.venv\Scripts\python.exe smoke_test.py   # live, 9 typed cases in 5 languages
.\.venv\Scripts\python.exe e2e_safety_test.py   # live, app running: card, stopped mix-up, 112 rule
```

The live test opens real voice sessions with typed input and checks grounding
(letter sections, dates, doses), the explanation of medical jargon, the medication-change refusal, 112 for acute
symptoms, urgent callbacks for warning signs, callbacks for unanswered
questions, and a mid-conversation language switch; every answer must also pass
the app's safety check. The safety test runs through the app and injects a wrong
dose to confirm it is stopped. Then rehearse with the
microphone using the [presenter script](VOICE-SCRIPT-DE.md): speech recognition,
turn-taking, voice quality and latency can only be judged by ear.

## 5. Phones (optional)

Browsers allow the microphone only on `https://` or `localhost`. To scan the QR
code with a phone, expose the app through an HTTPS address with access control,
for example a [dev tunnel](https://learn.microsoft.com/azure/developer/dev-tunnels/overview)
restricted to your account, or deploy it (e.g. Azure Container Apps with managed
identity and authentication). Set `PUBLIC_BASE_URL` to that address. The app has
no user authentication of its own; never expose it publicly.

## Completion checklist

- Live smoke test passes; answers show their letter section.
- Live safety test passes (medication card, stopped mix-up, 112 rule).
- The **Fehler einschleusen (Demo)** button on `/team` is off (reset) before the presentation.
- A medication question and a fever report create callbacks on `/team`.
- Chest pain produces an immediate 112 instruction and an emergency entry.
- Speaking another language mid-conversation switches the answer language.
- The team view is reset before the presentation.

Callback requests and transcripts live in memory only and are cleared on restart
or with **Demo zurücksetzen**. See [operations](OPERATIONS.md) for troubleshooting.
