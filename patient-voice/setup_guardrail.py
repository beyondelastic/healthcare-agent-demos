"""Create (or update) the Foundry guardrail for the voice agent: a blocklist plus controls.

    python setup_guardrail.py            # then: python create_agent.py (assigns it to the agent)

A guardrail is an RAI policy on the Foundry account (Azure Resource Manager). It contains:
- the default content-harm controls (hate, sexual, violence, self-harm) on input and output,
- Prompt Shields: jailbreak attempts in the patient's input, indirect attacks in tool results,
- Task Adherence (preview) on tool calls: blocks a tool call that doesn't fit the patient's request,
- a custom blocklist on the output with phrases that would be medication advice.

Requires FOUNDRY_ACCOUNT_RESOURCE_ID in .env and Foundry Account Owner (or Contributor) on the account.
Writes the guardrail ID to .guardrail.json for create_agent.py.
"""

import json
import re
from pathlib import Path

import requests

import safety
import settings

ROOT = Path(__file__).parent
API = "api-version=2025-10-01-preview"
POLICY = "patient-voice-guardrail"
BLOCKLIST = "patientvoiceadvice"
# Same patterns the app enforces itself (safety.py); see the README for why both exist.
BLOCKLIST_ITEMS = safety.ADVICE_PATTERNS


def controls(blocking_filters: list[tuple[str, str]]) -> list[dict]:
    rules = []
    for name, source in blocking_filters:
        rule = {"name": name, "source": source, "enabled": True, "blocking": True}
        if name in ("Hate", "Sexual", "Violence", "Selfharm"):
            rule["severityThreshold"] = "Medium"
        rules.append(rule)
    return rules


def main():
    account = settings.ACCOUNT_RESOURCE_ID
    if not account.startswith("/subscriptions/"):
        raise SystemExit("Set FOUNDRY_ACCOUNT_RESOURCE_ID in patient-voice/.env (Foundry resource > JSON view > ID).")
    with settings.credential() as credential:
        token = credential.get_token("https://management.azure.com/.default").token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = f"https://management.azure.com{account}"

    def put(path, body):
        response = requests.put(f"{base}/{path}?{API}", headers=headers, json=body, timeout=60)
        if not response.ok:
            raise SystemExit(f"PUT {path} failed: {response.status_code} {response.text}")
        return response.json()

    put(f"raiBlocklists/{BLOCKLIST}", {"properties": {
        "description": "Patient voice demo: phrases that would be medication advice (output only)."}})
    for item, pattern in BLOCKLIST_ITEMS.items():
        re.compile(pattern)
        put(f"raiBlocklists/{BLOCKLIST}/raiBlocklistItems/{item}",
            {"properties": {"pattern": pattern, "isRegex": True}})

    filters = [(name, source) for name in ("Hate", "Sexual", "Violence", "Selfharm")
               for source in ("Prompt", "Completion")]
    filters += [("Jailbreak", "Prompt"), ("Indirect Attack", "PostToolCall"),
                ("Protected Material Text", "Completion"), ("Task Adherence", "PreToolCall")]
    policy = put(f"raiPolicies/{POLICY}", {"properties": {
        "basePolicyName": "Microsoft.DefaultV2", "mode": "Blocking",
        "contentFilters": controls(filters),
        "customBlocklists": [{"blocklistName": BLOCKLIST, "blocking": True, "source": "Completion"}],
    }})
    (ROOT / ".guardrail.json").write_text(json.dumps({"rai_policy_id": policy["id"]}, indent=2), encoding="utf-8")
    names = ", ".join(f"{f['name']} ({f['source']})" for f in policy["properties"]["contentFilters"])
    print(f"Guardrail '{POLICY}' saved: {names}; blocklist '{BLOCKLIST}' ({len(BLOCKLIST_ITEMS)} patterns).")
    print("Next: python create_agent.py  (assigns the guardrail to the voice agent)")


if __name__ == "__main__":
    main()
