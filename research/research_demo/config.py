import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def require_configuration(**values):
    missing = [name for name, value in values.items()
               if not value or "YOUR-" in value.upper()]
    if missing:
        raise ValueError("Configure these values in the root .env or environment: "
                         + ", ".join(missing))


TENANT = os.getenv("AZURE_TENANT_ID", "")
WORKSPACE = os.getenv("FABRIC_WORKSPACE_ID", "")
PROJECT = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
PROJECT_ARM = os.getenv("FOUNDRY_PROJECT_RESOURCE_ID", "")
