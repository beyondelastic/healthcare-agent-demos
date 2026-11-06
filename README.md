# Healthcare Agent Demos

Three complementary, German-language healthcare demonstrations
using Azure and Microsoft Foundry. All patient records,
institutions, and clinical documents in the application are intentionally
fictional.

| Demo | Business story | Presentation surface |
|---|---|---|
| **Klinik Cockpit / Klinik Studio** | Assemble discharge documentation from traceable sources, handle a missing medication plan, and follow a late report with human approval gates. | Local German web cockpit and simulated blue KIS |
| **Forschungsnavigator** | Trial cohort feasibility: refine inclusion criteria conversationally and distinguish missing data from exclusions. | Foundry playground or published Teams agent |
| **Entlass-Assistent** | A patient scans the QR code on the approved discharge letter and asks questions by voice in their own language; open questions go to the care team. | Patient web page (voice or text) and care-team view |

**Start here:** [90-minute session guide](docs/SESSION-DE.md) ·
[Klinik presenter script](docs/KLINIK-SCRIPT-DE.md) ·
[Research presenter script](docs/RESEARCH-SCRIPT-DE.md) ·
[Voice presenter script](docs/VOICE-SCRIPT-DE.md)

**Slides:** [German use-case and architecture deck](docs/slides/Healthcare-Agent-Demos-DE.pptx)
— six editable slides, with speaker notes, covering all three demonstrations.

## What is real, and what is simulated?

Real: Foundry model and agent calls, clinical read-only function calls,
Azure Content Understanding scan extraction, Fabric Lakehouse tables and live
queries, Teams publication and signed-in access, and the Foundry voice agent
(realtime speech, multilingual voice, function tools).

Simulated: hospital source systems, clinical cases, medication release,
laboratory publication, task assignments, approval and KIS write-back, the
patient portal and QR identity check, and care-team notification.
Research data is deterministic and wholly synthetic. There is no real EHR
connection, clinical decision making, patient recruitment, or consent assessment.

## Run the clinical UI

Windows prerequisites: Python 3.11+, Node.js 24 LTS (also required for the
frontend tests), PowerShell 7, and Azure CLI for live cloud calls.

```powershell
Copy-Item .env.example .env
# Configure your own project and model deployment in .env.
.\Start-Cockpit.ps1 -Install
```

Open http://127.0.0.1:8000. Without cloud configuration you can inspect the UI
and explicitly use **Probenmodus** in **Vollansicht**; that is prepared text,
not live AI. Follow [clinical setup](docs/KLINIK-SETUP.md) to register the real
agent before presenting the agent journey. The optional scan chapter requires
additional Content Understanding configuration.

For research, follow [research setup and Teams publishing](docs/RESEARCH-SETUP.md)
and the [research technical reference](research/README.md).
For the voice demo, follow [voice setup](docs/VOICE-SETUP.md) and the [voice technical reference](patient-voice/README.md); it is
independent of the cockpit and runs on port 8010.
There is no one-command Azure provisioning or preconfigured shared tenant.

## Repository map

```text
backend/                 Clinical API, agent tools, synthetic cases, tests
frontend/                German cockpit and simulated KIS
research/                Synthetic generator, Fabric/Foundry setup and checks
patient-voice/           Voice agent for discharge-letter questions, patient and care-team pages
docs/                    Presenter scripts, setup, architecture and operations
.env.example             Configuration template; contains no credentials
Start-Cockpit.ps1         Local clinical startup
```

The public export deliberately excludes local databases, agent conversations,
Teams packages, tenant/resource bindings, original presentation decks, and
credentials. `.local/` and `.env` are generated privately on each machine.

## Boundaries and costs

**Demonstration software only. Not a medical device or production clinical
system.** Do not upload real patient data. The local clinical server has no
end-user authentication and must remain loopback-only. Agent instructions
are not database-enforced access controls.

Azure inference, document extraction, and Fabric capacity can incur charges.
No subscription, Foundry resource/model deployment, or Fabric capacity is
created automatically. Preview behavior and tenant policies may vary.
Read [architecture and safety boundaries](docs/ARCHITECTURE.md) and
[operations/troubleshooting](docs/OPERATIONS.md).

## Local checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r research\requirements.txt
.\.venv\Scripts\python.exe -m pytest backend\tests -q
$env:PYTHONPATH = Join-Path (Get-Location) 'research'
.\.venv\Scripts\python.exe -m pytest -c research\pytest.ini research\tests -q
Set-Location frontend
npm test
npm run build
```

These are local tests, not cloud deployment or production certification.
Live research checks are opt-in and incur usage.
