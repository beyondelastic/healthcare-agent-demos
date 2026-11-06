"""Configuration for the agent cockpit demo, loaded from agent-cockpit/.env."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
TENANT_ID = os.environ.get("AZURE_TENANT_ID") or None
WRITER_NAME = os.environ.get("WRITER_AGENT_NAME", "cockpit-writer")
REVIEWER_NAME = os.environ.get("REVIEWER_AGENT_NAME", "cockpit-reviewer")
WRITER_MODEL = os.environ.get("WRITER_MODEL", "gpt-4.1")
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gpt-5.5")
# Patient copy QR code: opens the voice demo (Entlass-Assistent) for this letter.
VOICE_ASSISTANT_URL = os.environ.get("VOICE_ASSISTANT_URL", "http://127.0.0.1:8010/patient?brief=DEMO-EB-2026-1106")
VERSIONS_FILE = ROOT / ".agents.json"


def agent_versions() -> dict:
    """Versions recorded by create_agents.py; sessions are pinned to them."""
    if not VERSIONS_FILE.exists():
        raise RuntimeError("Agents not created yet: run python create_agents.py")
    return json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))


def credential():
    if not ENDPOINT or "<" in ENDPOINT:
        raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT in agent-cockpit/.env")
    from azure.identity import AzureCliCredential
    return AzureCliCredential(tenant_id=TENANT_ID, process_timeout=45)
