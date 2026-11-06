"""List deployments in the explicitly configured project without provisioning anything."""
import json
import sys

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential

from app.config import settings


def main():
    try:
        with AzureCliCredential(tenant_id=settings.azure_tenant_id, process_timeout=20) as credential:
            with AIProjectClient(
                endpoint=settings.foundry_project_endpoint, credential=credential,
                connection_timeout=10, read_timeout=15,
            ) as project:
                models = [
                    {"deployment": item.name, "model": getattr(item, "model_name", None)}
                    for item in project.deployments.list()
                ]
                print(json.dumps(models, indent=2))
    except AzureError as exc:
        print(f"Foundry discovery failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        print("Sign in to the directory owning this project and set AZURE_TENANT_ID if required.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
