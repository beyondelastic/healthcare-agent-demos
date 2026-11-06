"""Explicitly register a versioned, read-only documentation agent in the selected project."""
import json

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential

from app.agent import definition
from app.config import settings


def main():
    if not settings.foundry_model:
        raise SystemExit("FOUNDRY_MODEL fehlt.")
    with AzureCliCredential(tenant_id=settings.azure_tenant_id, process_timeout=20) as credential:
        with AIProjectClient(endpoint=settings.foundry_project_endpoint, credential=credential) as project:
            agent = project.agents.create_version(
                agent_name=settings.foundry_agent_name, definition=definition(settings),
                description="Klinik Studio: synthetic documentation demo, case-scoped read-only KIS tools, human-approved proposals.",
                metadata={"application": "klinik-studio", "synthetic_only": "true"},
            )
            print(json.dumps({"name": agent.name, "version": agent.version, "id": agent.id}, indent=2))
            print(f"FOUNDRY_AGENT_NAME={agent.name}")
            print(f"FOUNDRY_AGENT_VERSION={agent.version}")


if __name__ == "__main__":
    main()
