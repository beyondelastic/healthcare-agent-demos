# Healthcare Agent Demos

Four complementary, German-language healthcare demonstrations
using Azure and Microsoft Foundry. All patient records,
institutions, and clinical documents in the application are intentionally
fictional.

| Demo | Business story | Presentation surface |
|---|---|---|
| **Klinik Cockpit · KI-Agenten** | Two Foundry agents read eight simulated hospital systems, draft and cross-check the discharge letter, react to a new event on their own, and hand over for **one** physician approval; then simulated KIM/ePA sending. | Local German web cockpit |
| **Forschungsnavigator** | Trial cohort feasibility: refine inclusion criteria conversationally and distinguish missing data from exclusions. | Foundry playground or published Teams agent |
| **Entlass-Assistent** | The patient scans the QR code on their copy of that approved letter and asks questions by voice in their own language; jargon is explained, open questions go to the care team. | Patient web page (voice or text) and care-team view |
| **Empfangs-Avatar** | An avatar at the main entrance welcomes visitors in their language, shows the way on a campus map, checks patients in for today's appointment (the same patient arrives for her follow-up), and calls staff when needed; no medical content. | Kiosk with avatar video and an information-desk view |

**Start here:** [90-minute session guide](docs/SESSION-DE.md) ·
[Klinik presenter script](docs/KLINIK-SCRIPT-DE.md) ·
[Research presenter script](docs/RESEARCH-SCRIPT-DE.md) ·
[Voice presenter script](docs/VOICE-SCRIPT-DE.md) ·
[Avatar presenter script](docs/AVATAR-SCRIPT-DE.md) ·
[End-to-end rehearsal](docs/PROBELAUF-DE.md)

**Slides:** [German use-case and architecture deck](docs/slides/Healthcare-Agent-Demos-DE.pptx)
— nine editable slides, with speaker notes, covering all four demonstrations and the voice agent's guardrails.

## What is real, and what is simulated?

Real: Foundry prompt agents (writer and reviewer) with function tools and
structured output, Fabric Lakehouse tables and live
queries, Teams publication and signed-in access, and the Foundry voice agent
(realtime speech, multilingual voice, function tools), its Foundry guardrail, and the app's safety checks that stop answers deviating from the letter, and a Foundry voice agent with a real-time avatar (WebRTC video).

Simulated: hospital source systems and their data, the medication-release event,
approval, KIM/ePA sending, the
patient portal and QR identity check, care-team notification, and the hospital campus, appointments and staff paging for the avatar.
Research data is deterministic and wholly synthetic. There is no real EHR
connection, clinical decision making, patient recruitment, or consent assessment.

## Run the demos

Windows prerequisites: Python 3.11+, PowerShell 7, and Azure CLI. Each demo has
its own folder, virtual environment and `.env`; they run independently.

```powershell
Set-Location agent-cockpit
Copy-Item .env.example .env      # your Foundry project and model deployments
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe create_agents.py
.\Start-AgentCockpit.ps1
```

Open http://127.0.0.1:8020. Details: [clinical setup](docs/KLINIK-SETUP.md) and the
[cockpit technical reference](agent-cockpit/README.md).

For research, follow [research setup and Teams publishing](docs/RESEARCH-SETUP.md)
and the [research technical reference](research/README.md).
For the voice demo, follow [voice setup](docs/VOICE-SETUP.md) and the [voice technical reference](patient-voice/README.md); it
runs on port 8010.
For the avatar, follow [avatar setup](docs/AVATAR-SETUP.md) and the [avatar technical reference](hospital-avatar/README.md); it
runs on port 8030.
There is no one-command Azure provisioning or preconfigured shared tenant.

## Prepare and test before a presentation

Once every demo is set up, two scripts in the repository root cover the day before and the hour before:

```powershell
.\Test-Demos.ps1                                  # day before: unit + live tests, order 01 -> 03 -> 04 -> 02 (~20 min, usage)
.\Prepare-Demos.ps1 -ResumeFabric -CheckResearch  # hour before: checks, start servers, reset, open tabs
.\Prepare-Demos.ps1 -Stop -PauseFabric            # afterwards: stop servers, pause the Fabric capacity
```

The manual end-to-end rehearsal with expected results is [docs/PROBELAUF-DE.md](docs/PROBELAUF-DE.md).
`FABRIC_CAPACITY_RESOURCE_ID` in the root `.env` is optional; without it the capacity isn't checked.

## Repository map

```text
agent-cockpit/           Klinik Cockpit: writer/reviewer agents, workflow, UI, tests
research/                Synthetic generator, Fabric/Foundry setup and checks
patient-voice/           Voice agent for discharge-letter questions, patient and care-team pages
hospital-avatar/         Welcome and wayfinding avatar kiosk, information-desk view
docs/                    Presenter scripts, setup, architecture, operations, slides
archive/                 Earlier approval-heavy cockpit (v1), kept for reference only
.env.example             Research configuration template; contains no credentials
```

The public export deliberately excludes local databases, agent conversations,
Teams packages, tenant/resource bindings, original presentation decks, and
credentials. `.local/` and `.env` are generated privately on each machine.

## Boundaries and costs

**Demonstration software only. Not a medical device or production clinical
system.** Do not upload real patient data. The local servers have no
end-user authentication and must remain loopback-only. Agent instructions
are not database-enforced access controls.

Azure inference and Fabric capacity can incur charges.
No subscription, Foundry resource/model deployment, or Fabric capacity is
created automatically. Preview behavior and tenant policies may vary.
Read [architecture and safety boundaries](docs/ARCHITECTURE.md) and
[operations/troubleshooting](docs/OPERATIONS.md).

## Local checks

```powershell
agent-cockpit\.venv\Scripts\python.exe -m pytest -c agent-cockpit\pytest.ini agent-cockpit\tests -q
patient-voice\.venv\Scripts\python.exe -m pytest patient-voice\tests -q
hospital-avatar\.venv\Scripts\python.exe -m pytest -c hospital-avatar\pytest.ini hospital-avatar\tests -q
.\.venv\Scripts\python.exe -m pip install -r research\requirements.txt
$env:PYTHONPATH = Join-Path (Get-Location) 'research'
.\.venv\Scripts\python.exe -m pytest -c research\pytest.ini research\tests -q
```

These are local tests, not cloud deployment or production certification.
Live checks (`agent-cockpit\e2e_test.py`, `patient-voice\smoke_test.py`, `hospital-avatar\smoke_test.py`, research
verification) are opt-in and incur usage.
