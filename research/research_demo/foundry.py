import argparse
import json
from pathlib import Path

import httpx
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FabricIQPreviewTool, PromptAgentDefinition
from azure.identity import AzureCliCredential

from .fabric import DATA_INSTRUCTIONS, TENANT, WORKSPACE
from .config import PROJECT, PROJECT_ARM, require_configuration

AGENT = "research-feasibility"
CONNECTION = "research-fabric-iq-v1"

INSTRUCTIONS = """You are Forschungsnavigator, a research study-feasibility assistant for a synthetic
German university-hospital demonstration. This is a separate research use case, not clinical advice.
Use German unless the user uses another language. Be concise but explain the actual cohort definition.
Keep normal answers presentation-friendly: a small result table, criteria, source/cutoff and the key
limitation, normally within 250 words. Do not print SQL unless explicitly requested; tool traces retain it.
For every numerical cohort answer you MUST call the connected Fabric research data agent. Never
calculate, guess or recall cohort counts from model knowledge or a previous question with different criteria.
Keep the previous criteria during conversational refinement unless the user explicitly changes them.
Always show eligible, excluded and unassessable DISTINCT PATIENT counts separately. Do not mix episodes
and patients. State the actual dataset cutoff and analysis interval and source. Supply executed SQL only on request.
For baseline or the standard renal-lab/90-day refinement, tell Fabric to execute the matching reference SQL
from the data definitions. For changed age, interval or follow-up, adapt that logic without dropping criteria.
An excluded patient has ALL episodes excluded, not just one failed episode.
Distinguish a missing variable from a known exclusion. The presence of postoperative tests does not prove a
preoperative result was available. Explain why recently performed surgery lacks mature follow-up.
Use only aggregate outputs. Never return individual patient or episode identifiers. Do not claim real
patient access, recruitment eligibility, consent, power analysis, causality or institutional performance.
If the tool is unavailable, unauthenticated, ambiguous or does not return the requested counts, say so plainly.
Never fill in missing counts. Ask one focused clarification if the research protocol cannot be operationalized.
No literature-search capability is configured in this first version. Do not invent references or imply a
systematic review has been performed. You may help formulate a study question, labelled as a proposal.
Every cohort result must prominently say SYNTHETISCHE DEMODATEN.
""" + "\n\nData definitions:\n" + DATA_INSTRUCTIONS


def create_agent(state_path: Path, model: str):
    require_configuration(AZURE_TENANT_ID=TENANT, FABRIC_WORKSPACE_ID=WORKSPACE,
                          FOUNDRY_PROJECT_ENDPOINT=PROJECT,
                          FOUNDRY_PROJECT_RESOURCE_ID=PROJECT_ARM)
    state = json.loads(state_path.read_text())
    if "sql_verification" not in state:
        raise RuntimeError("Independently verify the live Fabric counts before creating the research agent.")
    if "data_agent_id" not in state:
        raise RuntimeError("Publish the Fabric research data agent first.")
    credential = AzureCliCredential(tenant_id=TENANT, process_timeout=45)
    server = f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{WORKSPACE}/dataagents/{state['data_agent_id']}/agent"
    url = f"https://management.azure.com{PROJECT_ARM}/connections/{CONNECTION}?api-version=2025-10-01-preview"
    headers = {"Authorization": "Bearer " + credential.get_token("https://management.azure.com/.default").token}
    with httpx.Client(timeout=90) as client:
        existing = client.get(url, headers=headers)
        properties = {
            "category": "RemoteTool", "authType": "UserEntraToken", "target": server,
            "audience": "https://analysis.windows.net/powerbi/api",
            "metadata": {"type": "generic_mcp"},
        }
        if existing.status_code == 404:
            response = client.put(url, headers=headers, json={"properties": properties})
            response.raise_for_status()
            connection = response.json()
        else:
            existing.raise_for_status()
            connection = existing.json()
            if connection["properties"]["target"] != server:
                raise RuntimeError("A different connection already uses this name; no replacement attempted.")
            if connection["properties"].get("audience") != properties["audience"]:
                if state.get("foundry_agent", {}).get("connection_id") != connection["id"]:
                    raise RuntimeError("Refusing to change an untracked connection.")
                response = client.put(url, headers=headers, json={"properties": properties})
                response.raise_for_status()
                connection = response.json()
    with AIProjectClient(endpoint=PROJECT, credential=credential) as project:
        deployments = {deployment.name for deployment in project.deployments.list()}
        if model not in deployments:
            raise RuntimeError(f"Model deployment is not available in this project: {model}")
        if any(agent.name == AGENT for agent in project.agents.list()) and not state.get("foundry_agent"):
            raise RuntimeError("A pre-existing agent has this name; refusing to replace it.")
        created = project.agents.create_version(
            agent_name=AGENT,
            definition=PromptAgentDefinition(
                model=model, instructions=INSTRUCTIONS,
                tools=[FabricIQPreviewTool(
                    project_connection_id=connection["id"], server_label="research-fabric",
                    server_url=server, require_approval="never")]),
            description="Synthetic university-hospital cohort feasibility, grounded in live Fabric queries.",
            metadata={"demo": "research-synthetic-v1", "synthetic_only": "true"},
        )
    state["foundry_agent"] = {"name": created.name, "version": created.version, "model": model,
                              "project_endpoint": PROJECT, "connection_id": connection["id"],
                              "fabric_mcp_endpoint": server, "authentication": "UserEntraToken",
                              "teams_authentication_validated": False}
    state_path.write_text(json.dumps(state, indent=2))
    print(json.dumps(state["foundry_agent"], indent=2))


def main():
    parser = argparse.ArgumentParser(description="Create the isolated Foundry research agent with a server-side Fabric tool.")
    parser.add_argument("--state", type=Path, default=Path(".local/research-deployment.json"))
    parser.add_argument("--model", required=True, help="Name of an existing project deployment; no model is provisioned.")
    args = parser.parse_args()
    create_agent(args.state, args.model)


if __name__ == "__main__":
    main()
