"""Configuration for the hospital welcome avatar demo, loaded from hospital-avatar/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
TENANT_ID = os.environ.get("AZURE_TENANT_ID") or None
AGENT_NAME = os.environ.get("FOUNDRY_AVATAR_AGENT_NAME", "hospital-welcome-avatar")
MODEL = os.environ.get("FOUNDRY_AVATAR_AGENT_MODEL", "gpt-realtime-2.1")
VOICE = os.environ.get("FOUNDRY_AVATAR_AGENT_VOICE", "de-DE-Seraphina:DragonHDLatestNeural")
TRANSCRIPTION_MODEL = os.environ.get("FOUNDRY_AVATAR_TRANSCRIPTION_MODEL", "gpt-4o-transcribe")
AVATAR_CHARACTER = os.environ.get("FOUNDRY_AVATAR_CHARACTER", "nia")
AVATAR_STYLE = os.environ.get("FOUNDRY_AVATAR_STYLE") or None

# Languages offered on the kiosk: code -> (English name for the agent, BCP-47 locale)
LANGUAGES = {
    "de": ("German", "de-DE"),
    "en": ("English", "en-US"),
    "tr": ("Turkish", "tr-TR"),
    "ar": ("Arabic", "ar-SA"),
    "uk": ("Ukrainian", "uk-UA"),
}


def _check():
    if not ENDPOINT or "<" in ENDPOINT:
        raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT in hospital-avatar/.env")


def credential():
    """Azure CLI sign-in for an explicit tenant; the browser never receives a token."""
    _check()
    from azure.identity import AzureCliCredential
    return AzureCliCredential(tenant_id=TENANT_ID, process_timeout=45)


def async_credential():
    _check()
    from azure.identity.aio import AzureCliCredential
    return AzureCliCredential(tenant_id=TENANT_ID, process_timeout=45)
