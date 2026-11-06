# Clinical cockpit setup

These instructions use Windows and an existing Foundry project. They do not
provision a subscription, project, model deployment, or Content Understanding
resource. Keep all data synthetic.

## 1. Prepare local dependencies

Use Python 3.11+, Node.js 24 LTS, PowerShell 7, and Azure CLI.
Run from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Copy-Item .env.example .env
```

The startup script's `-Install` option can also create the virtual environment
and install backend/frontend dependencies. Do not copy someone else's `.env`
or local database into your checkout.

## 2. Configure and authenticate

In the root `.env`, set:

| Variable | Value |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Endpoint copied from your own Foundry project |
| `FOUNDRY_MODEL` | Existing deployment name supporting Responses API and structured outputs |
| `AZURE_TENANT_ID` | Directory owning that project |
| `FOUNDRY_AGENT_NAME` | `klinik-studio-discharge`, or your chosen demo agent name |

Sign into the owning tenant:

```powershell
az login --tenant YOUR-DIRECTORY-ID
.\.venv\Scripts\python.exe backend\discover_foundry.py
```

The identity must be permitted to use the project's deployments and create/use
agents. Resource provisioning and role assignments are separate administrator
actions. Never publish credentials or use another presenter's cached tokens.
The deployment name is not necessarily the model family name.

## 3. Register the actual clinical agent

```powershell
.\.venv\Scripts\python.exe backend\setup_agent.py
```

Copy the returned `FOUNDRY_AGENT_NAME` and `FOUNDRY_AGENT_VERSION` into `.env`.
Each execution creates a new version. Registration is explicit, never performed
on server startup. The clinical agent uses read-only local function tools;
the Python process executes them and sends the results back to Foundry.
No publicly reachable callback endpoint is required.

## 4. Start and rehearse

```powershell
.\Start-Cockpit.ps1 -Install
```

Open http://127.0.0.1:8000. Later, use `.\Start-Cockpit.ps1`.
Keep the terminal open; stop with Ctrl+C. Restart after changing `.env`.
Do not bind this unauthenticated demo to a public/network address.

Select Nora Testfall (DEMO-031) and follow
[the presenter script](KLINIK-SCRIPT-DE.md). A new checkout starts fresh;
subsequent runs retain state in `.local\cockpit.sqlite3`.

Without a configured agent, do not claim that **Probenmodus** represents the
agent workflow: it is explicitly labelled prepared text. There is no automatic
fallback from failed inference.

## 5. Optional: real scan extraction

Skip this section if you only need the first documentation chapter.

1. Provide an Azure Content Understanding endpoint and access for your signed-in
   identity. Check current service/model availability in your region.
2. The supplied setup helper expects existing deployments named **gpt-4.1**
   and **text-embedding-3-large** for its model mappings. If your deployment
   names differ, adapt and review the helper rather than guessing a mapping.
3. Set `CONTENT_UNDERSTANDING_ENDPOINT` and
   `CONTENT_UNDERSTANDING_ANALYZER=klinikStudioIntakeV1` in `.env`.
4. Run:

   ```powershell
   .\.venv\Scripts\python.exe backend\setup_documents.py
   ```

5. The helper uses API `2025-11-01`, adds non-conflicting default model mappings,
   creates the analyzer if absent, and refuses conflicting definitions.
   Review shared-resource defaults before running it: it does modify
   Content Understanding configuration, although it deploys no new model.
6. Restart and rehearse the scan chapter with the generated fictional report.

Only explicitly confirmed synthetic PDF/PNG/JPEG input is allowed. The demo
limits size to 5 MiB and three unencrypted pages, with four intakes per case
between resets. Returned grounding and case identifiers must support the
association before a document becomes a source.

## Completion checklist

- Actual agent source retrieval succeeds and the unreleased medication stays absent.
- Human KIS release changes the source revision; the new proposal cites the plan.
- Acceptance, review, approval, and copied handover remain separate.
- Optional scan extracts real content and follow-up is human-confirmed.
- Old KIS copies remain unchanged after late updates.
- Reset is rehearsed separately; original PowerPoint files are not needed.

Inference and optional document extraction incur normal Azure usage charges.
