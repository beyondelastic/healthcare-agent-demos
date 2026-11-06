"""Configuration for the patient voice demo, loaded from patient-voice/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
TENANT_ID = os.environ.get("AZURE_TENANT_ID") or None
AGENT_NAME = os.environ.get("FOUNDRY_VOICE_AGENT_NAME", "patient-discharge-voice")
MODEL = os.environ.get("FOUNDRY_VOICE_AGENT_MODEL", "gpt-realtime-2.1")
VOICE = os.environ.get("FOUNDRY_VOICE_AGENT_VOICE", "de-DE-Seraphina:DragonHDLatestNeural")
TRANSCRIPTION_MODEL = os.environ.get("FOUNDRY_VOICE_TRANSCRIPTION_MODEL", "gpt-4o-transcribe")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8010").rstrip("/")

# Languages offered on the patient page: code -> (English name for the agent, BCP-47 locale)
LANGUAGES = {
    "de": ("German", "de-DE"),
    "en": ("English", "en-US"),
    "tr": ("Turkish", "tr-TR"),
    "ar": ("Arabic", "ar-SA"),
    "uk": ("Ukrainian", "uk-UA"),
}
LANGUAGES_BCP47 = [locale for _, locale in LANGUAGES.values()]


def credential():
    """Azure CLI sign-in for an explicit tenant; the browser never receives a token."""
    if not ENDPOINT or "<" in ENDPOINT:
        raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT in patient-voice/.env")
    from azure.identity import AzureCliCredential
    return AzureCliCredential(tenant_id=TENANT_ID, process_timeout=45)


def async_credential():
    if not ENDPOINT or "<" in ENDPOINT:
        raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT in patient-voice/.env")
    from azure.identity.aio import AzureCliCredential
    return AzureCliCredential(tenant_id=TENANT_ID, process_timeout=45)
