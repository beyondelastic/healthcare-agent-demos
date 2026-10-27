import argparse
import base64
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx
from azure.identity import AzureCliCredential

from .cohort import Criteria, counts_sql
from .config import TENANT, WORKSPACE, require_configuration

FABRIC = "https://api.fabric.microsoft.com/v1"
NAME = "research_feasibility_v1"

DATA_INSTRUCTIONS = """Use only the attached research_feasibility_v1 lakehouse.
ALL records are wholly synthetic; no clinical evidence, treatment, consent, or recruitment claim.
Answer in the user's language. Return aggregate counts only, not patient or episode IDs.
Never estimate counts: execute a read-only SQL query and report its result and the query.
The observation cutoff is 2026-10-27. "Last two years" means 2024-10-28 through 2026-10-27 inclusive.
research_episodes has one row per surgery; a patient can have more than one surgery.
Count DISTINCT patient_id, never COUNT(*) as patients. A patient qualifies if ANY episode meets ALL criteria.
For unassessable patients: no qualifying episode exists but at least one episode is not ruled out
and has unknown criteria. A known false criterion excludes an episode even when other values are null.
Never count NULL age, admission_type, procedure_group, preop_egfr or followup_days as normal, false,
or eligible. Return eligible, excluded and unassessable patient counts, which must sum to the population.
Baseline: adult age_at_surgery>=18, procedure_group='abdominal', admission_type='elective',
and surgery_date in the specified interval.
The research_episodes.preop_egfr field already selects a measurement within 14 days BEFORE OR ON
surgery, NEVER a postoperative laboratory result. research_laboratory also deliberately contains
postoperative measurements for some patients; do not treat these as preoperative evidence.
If preoperative renal laboratory evidence is required, NULL preop_egfr makes the episode unassessable.
For 90-day follow-up use followup_days>=90. NULL is unassessable; a known value below 90 fails.
Known follow-up is bounded by the observation cutoff, so recent operations cannot have future outcomes.
Use research_episodes alone for cohort counts; do not multiply records by joining laboratory/outcome rows.
For site comparisons, GROUP BY site_id and count DISTINCT patient_id within each site.
Provide criterion definitions, data cutoff, missing-data limitations, and an exclusion waterfall when asked.
Never interpret synthetic complications or site differences as clinical effectiveness or real hospital performance.
Do not extrapolate to prospective recruitment or institutional data access.
IMPORTANT: Preoperative eGFR and follow-up are OPTIONAL criteria. Do not apply either unless the user
explicitly requests it. Baseline does NOT require laboratory documentation or 90-day follow-up.
Classify the ENTIRE distinct-patient population in research_episodes. Do not prefilter the population by
age, procedure, admission or dates before classifying. Those failures belong in the excluded group.
Evaluate known failures BEFORE missing values. Never let a missing variable override a known failure.
Use T-SQL for this SQL analytics endpoint, not Spark SQL. Do not use TRUE or DATE '...' literals.
For the two standard scenarios execute the corresponding reference SQL below without adding criteria.
These queries contain logic, not cached results: execute them against the live source.
"""
DATA_INSTRUCTIONS += (
    "\nBASELINE reference SQL (no lab or follow-up requirement):\n" + counts_sql(Criteria())
    + "\n\nREFINED reference SQL (baseline plus documented preoperative eGFR and >=90 days follow-up):\n"
    + counts_sql(Criteria(require_preop_egfr=True, min_followup_days=90))
)


class Fabric:
    def __init__(self):
        require_configuration(AZURE_TENANT_ID=TENANT, FABRIC_WORKSPACE_ID=WORKSPACE)
        self.credential = AzureCliCredential(tenant_id=TENANT, process_timeout=45)
        self.client = httpx.Client(timeout=120)

    def close(self):
        self.client.close()
        self.credential.close()

    def request(self, method, url, *, storage=False, **kwargs):
        expected = "onelake.dfs.fabric.microsoft.com" if storage else "api.fabric.microsoft.com"
        parsed = urlparse(url)
        regional_operation = not storage and re.fullmatch(
            r"wabi-[a-z0-9-]+\.analysis\.windows\.net", parsed.hostname or "")
        if parsed.scheme != "https" or parsed.username or parsed.password or (
                parsed.hostname != expected and not regional_operation):
            raise ValueError(f"Unexpected service host: {parsed.hostname}")
        scope = "https://storage.azure.com/.default" if storage else "https://api.fabric.microsoft.com/.default"
        token = self.credential.get_token(scope).token
        response = self.client.request(method, url, headers={
            "Authorization": f"Bearer {token}", "x-ms-version": "2021-06-08",
        }, **kwargs)
        if not response.is_success:
            raise RuntimeError(f"{method} {urlparse(url).path}: HTTP {response.status_code}: {response.text[:2000]}")
        return response

    def wait(self, response, return_result=True):
        if response.status_code != 202:
            return response.json() if response.content else {}
        location = response.headers.get("Location")
        if not location:
            raise RuntimeError("Fabric accepted the operation but supplied no operation URL.")
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            time.sleep(min(max(int(response.headers.get("Retry-After", "5")), 1), 30))
            response = self.request("GET", location)
            operation = response.json()
            status = operation.get("status", "").lower()
            if status in {"failed", "cancelled"}:
                raise RuntimeError(f"Fabric operation {status}: {json.dumps(operation)}")
            if status == "succeeded":
                if not return_result:
                    return operation
                result = self.request("GET", location.rstrip("/") + "/result")
                return result.json() if result.content else {}
        raise TimeoutError(f"Fabric operation did not complete: {location}")

    def items(self):
        url = f"{FABRIC}/workspaces/{WORKSPACE}/items"
        items = []
        while url:
            page = self.request("GET", url).json()
            items.extend(page["value"])
            url = page.get("continuationUri")
        return items

    def ensure_item(self, item_type, route, payload):
        found = [item for item in self.items() if item["displayName"] == payload["displayName"]
                 and item["type"] == item_type]
        if found:
            if len(found) != 1:
                raise RuntimeError("Name conflict with a different Fabric item; no overwrite attempted.")
            if not found[0].get("description", "").startswith("Entirely synthetic research demo"):
                raise RuntimeError("Existing item is not marked as this synthetic demo; refusing to modify.")
            return found[0]
        item = self.wait(self.request("POST", f"{FABRIC}/workspaces/{WORKSPACE}/{route}", json=payload))
        if not item.get("id"):
            matches = [item for item in self.items() if item["displayName"] == payload["displayName"]
                       and item["type"] == item_type]
            if len(matches) != 1:
                raise RuntimeError("New Fabric item could not be resolved unambiguously.")
            return matches[0]
        return item

    def upload(self, lakehouse_id, filename, content):
        base = f"https://onelake.dfs.fabric.microsoft.com/{WORKSPACE}/{lakehouse_id}/Files"
        self.request("PUT", base + "/research_v1?resource=directory", storage=True)
        url = base + "/research_v1/" + filename
        self.request("PUT", url + "?resource=file", storage=True)
        self.request("PATCH", url + "?action=append&position=0", storage=True, content=content)
        self.request("PATCH", url + f"?action=flush&position={len(content)}", storage=True)
        fetched = self.request("GET", url, storage=True).content
        if fetched != content:
            raise RuntimeError(f"OneLake round-trip content mismatch for {filename}.")


def part(path, content):
    return {"path": path, "payloadType": "InlineBase64",
            "payload": base64.b64encode(json.dumps(content).encode()).decode()}


def data_agent_definition(lakehouse_id, examples, table_schema=()):
    schema = "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/"
    datasource = {
        "$schema": schema + "dataSource/1.0.0/schema.json",
        "artifactId": lakehouse_id, "workspaceId": WORKSPACE, "displayName": NAME,
        "type": "lakehouse_tables", "userDescription": "Entirely fabricated research cohort, never real patients.",
        "dataSourceInstructions": DATA_INSTRUCTIONS,
        "elements": [{
            "id": str(uuid5(NAMESPACE_URL, f"{lakehouse_id}/dbo")),
            "display_name": "dbo", "type": "lakehouse_tables.schema", "is_selected": False,
            "children": [{
                "id": str(uuid5(NAMESPACE_URL, f"{lakehouse_id}/dbo/{table}")),
                "display_name": table, "type": "lakehouse_tables.table", "is_selected": True,
                "children": [{
                    "id": str(uuid5(NAMESPACE_URL, f"{lakehouse_id}/dbo/{table}/{column['column_name']}")),
                    "display_name": column["column_name"], "type": "lakehouse_tables.column",
                    "data_type": column["data_type"], "is_selected": True,
                } for column in table_schema if column["table_name"] == table],
            } for table in ["research_episodes", "research_sites"]],
        }],
    }
    stage = {"$schema": schema + "stageConfiguration/1.0.0/schema.json", "aiInstructions": DATA_INSTRUCTIONS}
    fewshots = {"$schema": schema + "fewShots/1.0.0/schema.json", "fewShots": examples}
    parts = [part("Files/Config/data_agent.json", {"$schema": schema + "dataAgent/2.1.0/schema.json"})]
    for version in ["draft", "published"]:
        prefix = f"Files/Config/{version}"
        parts.extend([
            part(prefix + "/stage_config.json", stage),
            part(prefix + f"/lakehouse-tables-{NAME}/datasource.json", datasource),
            part(prefix + f"/lakehouse-tables-{NAME}/fewshots.json", fewshots),
        ])
    parts.append(part("Files/Config/publish_info.json", {
        "$schema": schema + "publishInfo/1.0.0/schema.json",
        "description": "Entirely synthetic research demo - aggregate cohort feasibility v1",
    }))
    return {"parts": parts}


def main():
    parser = argparse.ArgumentParser(description="Provision only isolated synthetic research items in Fabric.")
    parser.add_argument("--data", type=Path, default=Path(".local/research-data"))
    parser.add_argument("--state", type=Path, default=Path(".local/research-deployment.json"))
    parser.add_argument("--stage", choices=["lakehouse", "agent"], required=True)
    args = parser.parse_args()
    state = json.loads(args.state.read_text()) if args.state.exists() else {"workspace_id": WORKSPACE, "tenant_id": TENANT}
    fabric = Fabric()
    try:
        if args.stage == "lakehouse":
            manifest = json.loads((args.data / "manifest.json").read_text())
            import hashlib
            for name, metadata in manifest["tables"].items():
                if hashlib.sha256((args.data / f"{name}.csv").read_bytes()).hexdigest() != metadata["sha256"]:
                    raise ValueError(f"Dataset integrity check failed for {name}.")
            item = fabric.ensure_item("Lakehouse", "lakehouses", {
                "displayName": NAME, "description": "Entirely synthetic research demo - isolated v1 dataset"})
            state["lakehouse_id"] = item["id"]
            args.state.write_text(json.dumps(state, indent=2))
            loaded = state.setdefault("loaded", {})
            for name, metadata in manifest["tables"].items():
                if name in loaded:
                    if loaded[name] != metadata["sha256"]:
                        raise RuntimeError("A different dataset was already loaded; create a new version instead.")
                    continue
                fabric.upload(item["id"], f"{name}.csv", (args.data / f"{name}.csv").read_bytes())
                fabric.wait(fabric.request("POST",
                    f"{FABRIC}/workspaces/{WORKSPACE}/lakehouses/{item['id']}/tables/{name}/load",
                    json={"relativePath": f"Files/research_v1/{name}.csv", "pathType": "File",
                          "mode": "Overwrite", "recursive": False,
                          "formatOptions": {"format": "Csv", "header": True, "delimiter": ","}}),
                    return_result=False)
                loaded[name] = metadata["sha256"]
                args.state.write_text(json.dumps(state, indent=2))
                print(f"Loaded and round-trip verified: {name} ({metadata['rows']} rows)", flush=True)
        else:
            table_schema = state.get("sql_verification", {}).get("source_schema")
            if not table_schema:
                raise RuntimeError("Run independent SQL verification to resolve the actual source schema first.")
            examples = [{"id": "6291c513-fbac-452e-9efb-8824d3070a81",
                         "question": "How many distinct adult elective abdominal-surgery patients in the last two years are eligible, excluded or unassessable?",
                         "query": counts_sql(Criteria())},
                        {"id": "6291c513-fbac-452e-9efb-8824d3070a82",
                         "question": "Require documented preoperative renal laboratory evidence and at least 90 days of follow-up. Show eligible, excluded, unassessable patient counts.",
                         "query": counts_sql(Criteria(require_preop_egfr=True, min_followup_days=90))}]
            item = fabric.ensure_item("DataAgent", "dataAgents", {
                "displayName": "research_cohort_agent_v2",
                "description": "Entirely synthetic research demo - aggregate-only feasibility agent",
                "definition": data_agent_definition(state["lakehouse_id"], examples, table_schema)})
            if state.get("data_agent_id") == item["id"]:
                fabric.wait(fabric.request("POST",
                    f"{FABRIC}/workspaces/{WORKSPACE}/dataAgents/{item['id']}/updateDefinition",
                    json={"definition": data_agent_definition(state["lakehouse_id"], examples, table_schema)}),
                    return_result=False)
            state["data_agent_id"] = item["id"]
            args.state.write_text(json.dumps(state, indent=2))
        print(json.dumps(state, indent=2))
    finally:
        fabric.close()


if __name__ == "__main__":
    main()
