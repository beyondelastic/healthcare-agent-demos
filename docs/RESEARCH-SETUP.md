# Research setup: Fabric, Foundry, and Teams

This is a manual setup into **your own** existing resources, not an IaC
deployment. The reference build used F8 Fabric capacity and a Foundry
`gpt-5.5` deployment. Those are reference details, not a promise of availability
or a minimum capacity recommendation. Fabric IQ is preview.

## 1. Prerequisites and isolation

- Windows, Python 3.11+, PowerShell 7, and authenticated Azure CLI.
- An active Fabric capacity and a dedicated workspace for synthetic demo data.
- Lakehouse, SQL analytics endpoint, and Fabric data agent capabilities enabled
  for the builder under the tenant's current licensing and policies.
- An existing Foundry project with a Responses-compatible model deployment.
- Builder permissions to create Fabric items, query the SQL endpoint, create
  Foundry agents, and write project connections. Tenant approval may be needed.
- For Teams, a suitable Microsoft 365 test tenant/account and an administrator
  able to approve the custom app. Prefer a native test user for the initial
  cross-service validation rather than mixing guest and home-tenant sessions.

No Azure resource, capacity, role assignment, tenant policy, or model deployment
is provisioned by this guide's Python commands. The commands do create or
update the named demo items, agent, and connection and incur service usage.

## 2. Configure your resources

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r research\requirements.txt
Copy-Item .env.example .env
```

If `.env` already exists for the clinical demo, edit it instead of overwriting.
Fill these values from your actual resources:

| Variable | Meaning |
|---|---|
| `AZURE_TENANT_ID` | Directory owning the project/workspace |
| `FABRIC_WORKSPACE_ID` | Dedicated synthetic workspace GUID |
| `FOUNDRY_PROJECT_ENDPOINT` | Your Foundry project API endpoint |
| `FOUNDRY_PROJECT_RESOURCE_ID` | Full project ARM resource ID copied from Azure |

Project ARM ID shape:

```text
/subscriptions/YOUR-SUBSCRIPTION/resourceGroups/YOUR-GROUP/providers/Microsoft.CognitiveServices/accounts/YOUR-ACCOUNT/projects/YOUR-PROJECT
```

The scripts load the root `.env`; existing process environment variables take
precedence. Azure CLI credentials explicitly request the configured tenant.
Confirm it before running any write operations.

```powershell
az login --tenant YOUR-DIRECTORY-ID
$env:PYTHONPATH = Join-Path (Get-Location) 'research'
```

## 3. Generate, load, and independently verify

Run in order from that same PowerShell session:

```powershell
.\.venv\Scripts\python.exe -m research_demo
.\.venv\Scripts\python.exe -m research_demo.fabric --stage lakehouse
.\.venv\Scripts\python.exe -m research_demo.verify
```

This generates five deterministic CSV tables, uploads and checks OneLake
round trips, loads Delta tables in **research_feasibility_v1**, and compares
live SQL counts with an independent local reference. SQL endpoint readiness
can lag table loading; if verification fails for readiness, wait and rerun
verification after checking the actual error, not the upload stage blindly.

SQL verification uses PowerShell 7 and native SqlClient with encrypted
transport, certificate validation, and an Entra token sent over process stdin.
No SQL password or ODBC setup is required.

Generated files and deployment state stay under ignored `.local/`.
Do not reuse a state file from another tenant/workspace. Use a fresh checkout
or separate state/data paths for each independent deployment. The loaders
refuse conflicting owned-item metadata and mismatching recorded dataset hashes;
they are demo utilities, not a general production migration system.

## 4. Create the Fabric and Foundry agents

```powershell
.\.venv\Scripts\python.exe -m research_demo.fabric --stage agent
.\.venv\Scripts\python.exe -m research_demo.foundry --model YOUR-EXISTING-DEPLOYMENT
```

Creates **research_cohort_agent_v2**, a **research-fabric-iq-v1** project
connection, and a version of **research-feasibility**. The Fabric definition
contains published configuration. Confirm the agent is published/available
in Fabric and that it answers a baseline query there before proceeding.

The connection uses `UserEntraToken`, with audience
`https://analysis.windows.net/powerbi/api` and the published Fabric data-agent
MCP endpoint. Foundry invokes it server-side. Do not replace this with a
static bearer token or assume a project managed identity automatically
grants each user data access.

Rerunning Foundry setup creates a new version. A published endpoint targeting
`@latest` can consequently change behavior; control versions deliberately.

## 5. Check the live grounding

```powershell
.\.venv\Scripts\python.exe -m research_demo.invoke --smoke
```

This makes real multi-turn Foundry/Fabric calls, compares three cohort results
against live SQL verification, and checks aggregate-only refusal.
Saved output is local and can contain environment details; do not commit it.
Fabric may return moderation annotations alongside usable answers; the
invocation utility warns and retains the trace rather than disabling filters.

## 6. Publish and approve Teams

1. In Foundry, open **research-feasibility** and its publishing option for
   **Teams and Microsoft Copilot**. Choose the narrow demo audience offered
   by the current portal. Publishing UI and preview availability can differ.
2. If publishing reports `MissingSubscriptionRegistration` for
   `Microsoft.BotService`, have an authorized administrator register that
   provider in the correct subscription. Registration alone does not publish
   an app or create a bot.
3. Complete the native publishing flow and record the created bot/endpoint
   privately. Keep the existing Responses protocol and required endpoint
   authorization; do not overwrite the endpoint configuration wholesale.
4. Install through the generated Teams distribution flow. If the share link
   does not work across browser identities, use the actual Foundry-generated
   app package rather than manufacturing a manifest. Package generation is
   also available through Foundry's documented Microsoft 365 ZIP API:

   ```text
   POST {project-endpoint}/agents/{agent-name}/microsoft365/zip?api-version=v1
   ```

   Use the current API documentation/schema for the body, including the
   actual published Bot Service ARM ID. This is a package-generation endpoint,
   not a substitute for publication or administrator approval. Do not put
   tokens, generated packages, or tenant-specific manifests in the repository.
5. If Teams says **request submitted to your admin**, the app is not yet
   installed/approved. The demo-tenant administrator must review the submitted
   custom app in Teams admin center's app-management area and permit it for
   the intended test users under the applicable policies.
6. Sign into Teams as the intended demo user and install/open the app.
   A browser already signed into another tenant can redirect unexpectedly;
   use a separate browser profile for the administrator and the test user.

## 7. Grant the user both agent and data access

App availability alone is not enough:

| Gate | Reference deployment |
|---|---|
| Teams app | Administrator-approved custom app available to the test user |
| Foundry invocation | **Foundry Agent Consumer**, at project scope |
| Fabric data | **Viewer** on the synthetic demo workspace |

Have the appropriate administrator assign the Foundry role and Fabric
workspace access. Resolve the user's object ID in the owning tenant, not
in an unrelated home directory. Do not grant editor/admin rights just to fix
an invocation error.

**Match the role to the actual published resource type.** The reference
deployment used a direct agent endpoint with `BotServiceRbac`. The newer
**Agent Application** resource has a different invocation permission:
current documentation requires **Foundry User** (or a suitable custom invoke
role) scoped to the Agent Application; Foundry Agent Consumer does not grant
that application permission. Do not copy the reference role blindly into
a different publication architecture. See the current
[Agent Applications guidance](https://learn.microsoft.com/azure/foundry/agents/how-to/agent-applications)
and [Teams publishing guidance](https://learn.microsoft.com/azure/foundry/agents/how-to/publish-copilot).

**Workspace Viewer gives access to all items in that workspace.** Use a
dedicated synthetic workspace. For real data, design and verify narrower
item/source permissions and the actual SQL/OneLake protection model.
Licensing and tenant feature entitlements still apply.

In the reference setup, the test user could invoke Foundry but the MCP tool
failed to enumerate until Fabric Viewer was granted. Granting it resolved
the error without changing the existing connection. This does not mean
every MCP enumeration error is a permission issue.

## 8. Verify as the actual Teams user

1. Open Fabric as that user and run the published data-agent baseline question.
2. In Teams, complete the agent sign-in prompt using the same intended account.
3. Run all four checks in the [presenter script](RESEARCH-SCRIPT-DE.md):
   baseline, lab/follow-up refinement, age refinement, and patient-ID refusal.
4. Compare the three result tables, not only whether an answer appears.
5. If direct Fabric works but Teams fails, investigate delegated identity,
   consent, and connection support for that channel. Preserve the working
   configuration; do not silently broaden access or disable authentication.

The reference deployment passed these four Teams checks on 2026-10-27.
Microsoft 365 Copilot is a separate channel and was not tested. No tenant-wide
compatibility or production-readiness guarantee is implied.
