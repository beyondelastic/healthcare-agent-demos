# Forschungsnavigator: synthetic study feasibility

A separate, conversational R&D demo for German university hospitals. The
clinical documentation cockpit is unchanged.

**Positioning:** Forschungsnavigator demonstrates conversational **cohort
feasibility analysis for clinical trials** (cohort discovery): testing study
inclusion and exclusion criteria against structured data before recruitment
begins. It applies criteria, counts distinct patients, refines criteria step by
step, separates missing data from known exclusions, and can compare synthetic
sites. It does **not** identify individual recruitment candidates, perform
patient pre-screening, check consent or contact rules, or estimate expected
enrolment or statistical power. Results are aggregate only.

The reference Foundry prompt agent **research-feasibility** used a **gpt-5.5**
deployment and a native **Fabric IQ (preview)** tool. Fabric's published
**research_cohort_agent_v2** queries the dedicated
**research_feasibility_v1** Lakehouse in your configured workspace. There are no laptop-hosted
tool callbacks, patient-system connections, or cached numeric answers in the
agent instructions.

The aggregate-only instruction is a demo behavior guardrail, not a substitute
for database-level access controls. Real data would require separately
enforced least privilege and governance.

## Try the demo

After completing [setup](../docs/RESEARCH-SETUP.md), open your Foundry project,
select **Agents > research-feasibility**, and use its playground. Configure your
own project endpoint in the root `.env`, for example:

`https://YOUR-FOUNDRY-ACCOUNT.services.ai.azure.com/api/projects/YOUR-PROJECT`

For a simple live presentation, use the
[German Teams presenter script](../docs/RESEARCH-SCRIPT-DE.md).

Suggested German conversation:

1. "Wie viele volljaehrige Patienten hatten in den letzten zwei Jahren einen
   elektiven abdominalchirurgischen Eingriff? Noch keine weiteren Labor- oder
   Nachbeobachtungskriterien."
2. "Verlange zusaetzlich ein dokumentiertes praeoperatives eGFR und mindestens
   90 Tage Nachbeobachtung. Behalte die anderen Kriterien bei."
3. "Wie veraendert sich das Ergebnis, wenn wir das Mindestalter auf 65 erhoehen?"
4. "Vergleiche die Datenqualitaet zwischen den Standorten. Unterscheide fehlende
   Angaben von bekannten Ausschluessen."
5. "Zeige mir die ausgefuehrte SQL-Abfrage."

Normal answers should be short result tables with criteria, data cutoff, source,
and limitations. SQL is available on request; actual Fabric calls remain visible
in the response/tool trace. The story is **question -> live data query ->
criterion refinement -> feasibility/data-quality insight**, not an approval
workflow.

## Data and interpretation

All records are wholly fabricated: **10,000 fictional patients**, **12,214
surgery episodes**, three fictional hospitals, laboratory evidence, and
follow-up/outcomes. No real patient records, hospital performance, or actual
institutional recruitment capacity are represented.

The fixed observation cutoff is **2026-10-27**. "Last two years" means
**2024-10-28 through 2026-10-27**, inclusive, rather than a moving wall-clock
interval. Site-specific missingness is deliberately different.

A patient qualifies if **any one episode meets all requested criteria**. If
none qualifies but an episode remains potentially eligible with unknown
criteria, the patient is unassessable. Otherwise the patient is excluded.
Known failures take precedence over missing values within an episode.

Baseline does not implicitly require laboratory evidence or follow-up. When
requested, preoperative eGFR must have been measured within 14 days before/on
surgery; a postoperative measurement cannot satisfy that requirement. Recent
operations cannot have follow-up beyond the observation cutoff.

Live SQL reference results, independently compared with the deterministic
local dataset:

| Cohort | Eligible | Excluded | Unassessable |
|---|---:|---:|---:|
| Adults, elective abdominal surgery, study interval | 2,697 | 7,039 | 264 |
| Same, plus preoperative eGFR and >=90-day follow-up | 960 | 8,105 | 935 |
| Same refinement, minimum age 65 | 362 | 9,243 | 395 |

These are distinct-patient counts across the full population, not episode
counts. Missing information is not equivalent to a known exclusion. The demo
does not establish consent, prospective recruitment, power, causality,
treatment recommendations, or clinical effectiveness.

## Run and reproduce on Windows

Use the existing root virtual environment. Python, PowerShell 7, Azure CLI, and
an authenticated account with access to the target tenant/project/workspace
are required. Set `AZURE_TENANT_ID`, `FABRIC_WORKSPACE_ID`,
`FOUNDRY_PROJECT_ENDPOINT`, and `FOUNDRY_PROJECT_RESOURCE_ID` in the root `.env`
using your own resources. Scripts request that directory explicitly without
changing the global Azure CLI subscription. Missing or template cloud
configuration fails explicitly; local dataset generation needs no Azure access.

From the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r research\requirements.txt
$env:PYTHONPATH = Join-Path (Get-Location) 'research'

# Deterministic local CSVs, hashes, and independent reference counts
.\.venv\Scripts\python.exe -m research_demo

# These commands create/update the dedicated demo resources and incur usage.
.\.venv\Scripts\python.exe -m research_demo.fabric --stage lakehouse
.\.venv\Scripts\python.exe -m research_demo.verify
.\.venv\Scripts\python.exe -m research_demo.fabric --stage agent
.\.venv\Scripts\python.exe -m research_demo.foundry --model YOUR-EXISTING-DEPLOYMENT

# Real server-side, multi-turn agent checks against the live SQL reference
.\.venv\Scripts\python.exe -m research_demo.invoke --smoke

# Optional direct chat; reuse the returned response ID for a follow-up.
.\.venv\Scripts\python.exe -m research_demo.invoke --prompt "Stelle dich kurz vor."
.\.venv\Scripts\python.exe -m research_demo.invoke --prompt "Welche Daten nutzt du?" --previous-response-id <response-id>

# Local regression checks; no Azure calls
.\.venv\Scripts\python.exe -m pytest -c research\pytest.ini research\tests -q
```

The SQL check uses Windows' native SqlClient through PowerShell, with Entra
authentication, encrypted transport, and certificate validation. It does not
need a separately registered ODBC driver. Its access token travels only in
process memory/stdin, never in arguments or saved state.

Local generated data and actual resource/version IDs live under
`.local\research-data` and `.local\research-deployment.json`. Agent response
records are saved in `.local\research-agent-responses.json`, including actual
Fabric tool calls. The deployment state records the exact created version.
Foundry metadata overlays are not shipped with tenant bindings.
No remote evaluation suite is implied by these local checks.

Provisioning does not target unrelated Lakehouses or clinical agents/data.
It only uses dedicated synthetic-demo item names. Hashes prevent silently
replacing a previously loaded dataset with a different version. Rerunning
Foundry provisioning creates a new research-agent version.

The Fabric source definition uses the documented `lakehouse-tables-` folder
prefix, `lakehouse_tables` source type, a `dbo` schema, selected tables, and
actual SQL column metadata. The REST API can accept an incomplete definition
that still fails at runtime; creation alone is not proof of working grounding.

## Publishing and operational boundaries

**Reference deployment published to Teams as Forschungsnavigator.** On 2026-10-27, a signed-in
demo user successfully ran the baseline cohort question in Teams and returned
the independently verified counts (2,697 eligible, 7,039 excluded, 264
unassessable). This verifies the current deployment's Teams-to-Fabric path
using delegated **UserEntraToken** authentication; this repository does not
give access to that deployment and it is not a blanket
compatibility guarantee for other tenants or channels. Microsoft 365 Copilot
has not been tested separately. A custom web UI is not required.

Access has three separate gates: Teams app approval/availability, Foundry
agent invocation authorization, and the user's Fabric permissions. The test
user has **Foundry Agent Consumer** at project scope and **Viewer** on
the reference demo workspace. Workspace Viewer covers every item in a workspace,
not only the research demo. Production data would
require more narrowly scoped access. Granting Fabric Viewer resolved the
test user's tool-enumeration failure; no connection change was needed.

User-provided Teams screenshots on 2026-10-27 also confirm multi-turn
refinement (960 eligible, 8,105 excluded, 935 unassessable), retention of those
criteria when raising minimum age to 65 (362 / 9,243 / 395), and refusal to
return individual patient IDs with aggregate alternatives offered instead.
All three cohort results match the independent SQL reference. Site analysis
was checked through Foundry, but has not yet been confirmed in Teams.
The refusal is an instruction-level guardrail, not database-enforced row
protection.

Fabric IQ is preview. If a response includes a provider moderation annotation,
the invocation tool warns and preserves it in the saved trace for review;
filters are not disabled. Tool failures are explicit, with no synthetic
success-shaped fallback. Numeric correctness is checked against independent
live SQL, not merely a fluent answer or a successful HTTP response.

No literature-search capability is configured in this first version. The agent
must not invent citations or claim it performed a literature review.

**Capacity cost:** the reference build used an active F8 Fabric capacity.
No capacity is included or automatically resumed by these scripts. Normal
capacity and inference charges apply in your environment.
Suspend a demo capacity when it is no longer needed, after checking
that no other workload needs it; suspension affects the whole capacity, not
only this research Lakehouse.

The reference Fabric and Foundry resources were in Sweden Central. This is not a guarantee of
model-inference residency: verify the deployed model's SKU/routing and the
complete service path before considering any real hospital data.
