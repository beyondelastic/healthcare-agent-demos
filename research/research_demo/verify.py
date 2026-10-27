import argparse
import json
import subprocess
from pathlib import Path

from .cohort import Criteria, counts_sql, reference_counts
from .dataset import generate
from .fabric import FABRIC, NAME, WORKSPACE, Fabric


def main():
    parser = argparse.ArgumentParser(description="Independently verify live Fabric cohort counts, without a model.")
    parser.add_argument("--state", type=Path, default=Path(".local/research-deployment.json"))
    parser.add_argument("--data", type=Path, default=Path(".local/research-data"))
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    expected = json.loads((args.data / "reference-counts.json").read_text())
    fabric = Fabric()
    try:
        lakehouse = fabric.request("GET",
            f"{FABRIC}/workspaces/{WORKSPACE}/lakehouses/{state['lakehouse_id']}").json()
        endpoint = lakehouse["properties"]["sqlEndpointProperties"]
        queries = {
            "baseline": counts_sql(Criteria()),
            "refined": counts_sql(Criteria(require_preop_egfr=True, min_followup_days=90)),
            "older_refined": counts_sql(Criteria(min_age=65, require_preop_egfr=True, min_followup_days=90)),
            "episode_rows": "SELECT COUNT(*) AS row_count FROM research_episodes",
            "site_data_quality": """SELECT site_id, COUNT(DISTINCT patient_id) AS distinct_patients,
                    SUM(CASE WHEN preop_egfr IS NULL THEN 1 ELSE 0 END) AS missing_preop_episode_count
                    FROM research_episodes GROUP BY site_id ORDER BY site_id""",
            "source_schema": """SELECT t.name AS table_name, c.name AS column_name, ty.name AS data_type
                FROM sys.tables t JOIN sys.columns c ON t.object_id=c.object_id
                JOIN sys.types ty ON c.user_type_id=ty.user_type_id
                WHERE t.name IN ('research_episodes', 'research_sites')
                ORDER BY t.name, c.column_id""",
        }
        # Windows' native SqlClient understands Fabric's named-instance routing.
        completed = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(Path(__file__).with_name("query_sql.ps1"))],
            input=json.dumps({
                "server": endpoint["connectionString"], "database": NAME, "queries": queries,
                "token": fabric.credential.get_token("https://database.windows.net/.default").token,
            }), text=True, capture_output=True, timeout=360)
        if completed.returncode:
            raise RuntimeError(f"Native SQL verification failed:\n{completed.stderr}")
        raw = json.loads(completed.stdout)
        results = {}
        manifest = json.loads((args.data / "manifest.json").read_text())
        expected["older_refined"] = reference_counts(
            generate(count=manifest["patient_count"], seed=manifest["seed"])["research_episodes"],
            Criteria(min_age=65, require_preop_egfr=True, min_followup_days=90))
        for label in ["baseline", "refined", "older_refined"]:
            actual = {row["assessment"]: row["patient_count"] for row in raw[label]}
            wanted = {key: expected[label]["final"][key]
                      for key in ["eligible", "excluded", "unassessable"]}
            if actual != wanted:
                raise AssertionError(f"Fabric {label} differs from independently generated reference: {actual} != {wanted}")
            results[label] = actual
        results["episode_rows"] = raw["episode_rows"][0]["row_count"]
        results["site_data_quality"] = raw["site_data_quality"]
        results["source_schema"] = raw["source_schema"]
        state["sql_verification"] = results
        state["sql_endpoint_id"] = endpoint["id"]
        state["sql_server"] = endpoint["connectionString"]
        args.state.write_text(json.dumps(state, indent=2))
        print(json.dumps(results, indent=2))
    finally:
        fabric.close()


if __name__ == "__main__":
    main()
