# Archive: Klinik Cockpit v1

This is the first version of the clinical documentation demo: a full cockpit with a simulated
KIS, scan intake (Azure Content Understanding), task follow-up and several human approval steps.
It worked, but it was too UI- and approval-heavy for a short presentation.

**It is replaced by [`agent-cockpit/`](../../agent-cockpit/README.md)**: two Foundry agents
(writer and reviewer), an event-driven update and a single approval at the end.

The code is kept unchanged for reference and is not maintained. It still runs from this folder:

```powershell
Copy-Item .env.example .env      # project endpoint, model deployment, agent version
.\Start-Cockpit.ps1 -Install
```

Old presenter script and setup: [docs/](docs/). Paths in those documents refer to the
repository root at the time; run commands from this folder instead.
