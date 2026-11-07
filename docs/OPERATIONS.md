# Operations and troubleshooting

## Before each presentation

- Rehearse as the actual presenter/test account, not only the resource builder.
- Check Azure CLI authentication, model availability, network connectivity,
  active Fabric capacity, and current tenant policies.
- Confirm the clinical case is at the intended starting point and the research
  conversation has an explicit baseline.
- Keep original/source inspection available, but avoid admin portals and
  credentials on the shared screen.
- Budget for live response latency; do not show fabricated progress or claim
  a fixed service response time.

## Common failures

| Symptom | Check / action |
|---|---|
| Cockpit: agents take longer than usual | Typical: first draft 30–45 s, update 15–30 s, plus up to two correction rounds. The live log shows progress; keep explaining. |
| Cockpit: "Server-Prüfung: Korrektur angefordert" in the log | Expected behaviour: server checks send faulty drafts back to the agent. Only an aborted run ("Validierung fehlgeschlagen") needs **↺ Zurücksetzen** and a new start. |
| Cockpit: reviewer finds no error this time | Real, not staged; the verdict varies between runs. Explain the check instead of promising a finding. |
| Agent unavailable or unauthorized | Check the configured tenant, project, deployment, agent version (`create_agents.py` / `create_agent.py`), and signed-in identity. Restart after `.env` changes. |
| Fabric SQL verification fails | Inspect table-load and endpoint readiness, SQL access, capacity, and the actual reported error. Counts must match before agent setup. |
| Missing cloud configuration | Complete the root `.env`; no sample tenant IDs are supplied. Process environment overrides `.env`. |
| Teams request submitted to admin | Complete custom-app approval and user availability in the correct Microsoft 365 tenant. |
| Teams says user cannot access agent | Check project-scoped Foundry Agent Consumer access as well as Teams app availability. |
| Fabric workspace invisible | Check the intended tenant/account, workspace permission, licensing and feature entitlement. |
| MCP enumeration error | Test direct Fabric as that same user first. Check data access; if direct Fabric works, investigate channel delegated authentication/consent. The generic error alone does not identify a root cause. |
| Different cohort counts | Compare exact criteria, fixed dates, distinct patients vs. episodes, null semantics and retained conversation context against independent SQL. Do not patch answers with stored numbers. |
| Agent refuses identifiers | Expected behavior; aggregate alternatives are allowed. This is not evidence of database-level row protection. |
| Voice: assistant interrupts itself | Use a headset or lower speaker volume; open speakers feed its own voice back into the microphone. |
| Voice: "Verbindung wird wiederhergestellt …" | The realtime connection dropped; the app reconnects up to three times and passes the recent conversation. Keep talking. If it fails, end and restart the conversation. |
| Voice: no callback on `/team` | Use a question that requires one (medication change, fever, unanswered question); the page refreshes every 3 seconds. Requests are in memory and cleared on restart. |
| Voice: microphone blocked on a phone | Browsers need `https://` or `localhost`; use the laptop or an HTTPS tunnel/deployment. |
| Voice: an answer is stopped unexpectedly | The app's safety check found a drug, dose or phrase not in the letter (reason on `/team`, *Sicherheitsprüfung*). Expected if **Fehler einschleusen** was armed; otherwise review the word lists in `safety.py`. |
| Voice: `setup_guardrail.py` fails with 403 | Needs Foundry Account Owner or Contributor on the Foundry resource and `FOUNDRY_ACCOUNT_RESOURCE_ID`. The demo runs without the guardrail; the app's checks still apply. |

## Reset and recovery

The cockpit and voice demo keep their state in memory only; **↺ Zurücksetzen**
or a restart returns them to the starting point. A run interrupted by a restart
is not replayed. No failed cloud call is converted automatically to a prepared
result.

Research scripts record resource IDs and hashes in ignored
`.local\research-deployment.json`. Keep it privately with the matching
environment. Do not copy it to a different tenant or workspace.
Changing agent instructions/setup can create a new agent version and affect
an endpoint that routes to latest.

## Costs and cleanup

Clinical and voice inference incur usage. Research consumes Fabric
capacity, storage/query resources, and inference. Teams publishing can create
additional Azure resources; inspect the actual resource inventory and billing.

These scripts do not automatically suspend a capacity, unregister providers,
remove role assignments, delete bots, or delete agents. After the event:

1. Stop the local cockpit and voice servers with Ctrl+C.
2. Remove test-user access and app distribution when no longer needed.
3. Suspend only an explicitly identified demo capacity after checking other
   workloads; suspension affects the whole capacity.
4. Review dedicated demo items/resources before deleting anything. Never use
   broad subscription/resource-group cleanup against shared infrastructure.
5. Retain or remove local synthetic runtime files under your own retention
   policy. Keep all credentials and runtime output out of source control.
