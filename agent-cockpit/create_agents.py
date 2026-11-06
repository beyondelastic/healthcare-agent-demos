"""Create (or update) the writer and reviewer agents in Microsoft Foundry.

Each run saves new, immutable versions and records them in .agents.json, which the
app uses to pin both agents.

    python create_agents.py
"""

import json

from azure.ai.projects import AIProjectClient

import settings
from agents import reviewer_definition, writer_definition


def main():
    versions = {}
    with settings.credential() as credential, AIProjectClient(endpoint=settings.ENDPOINT, credential=credential) as project:
        deployments = {d.name for d in project.deployments.list()}
        for model in {settings.WRITER_MODEL, settings.REVIEWER_MODEL}:
            if model not in deployments:
                raise SystemExit(f"Model deployment not found in project: {model}")
        for role, name, definition, description in [
            ("writer", settings.WRITER_NAME, writer_definition(settings.WRITER_MODEL),
             "Synthetic demo: drafts a discharge letter from simulated hospital systems."),
            ("reviewer", settings.REVIEWER_NAME, reviewer_definition(settings.REVIEWER_MODEL),
             "Synthetic demo: independently reviews the drafted letter against the sources."),
        ]:
            created = project.agents.create_version(
                agent_name=name, definition=definition, description=description,
                metadata={"demo": "agent-cockpit", "synthetic_only": "true", "role": role})
            versions[role] = {"name": created.name, "version": created.version}
            print(f"{role}: {created.name} version {created.version}")
    settings.VERSIONS_FILE.write_text(json.dumps(versions, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
