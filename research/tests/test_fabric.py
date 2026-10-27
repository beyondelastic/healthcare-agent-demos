from types import SimpleNamespace

import httpx
import pytest

from research_demo.fabric import FABRIC, WORKSPACE, Fabric, data_agent_definition


def fake_fabric(handler):
    fabric = Fabric.__new__(Fabric)
    fabric.credential = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="synthetic-test-token"))
    fabric.client = httpx.Client(transport=httpx.MockTransport(handler))
    return fabric


def test_unknown_hosts_cannot_receive_tokens():
    f = fake_fabric(lambda request: pytest.fail("No network call expected"))
    for url in ["https://example.com/v1/operation", "http://api.fabric.microsoft.com/v1/test",
                "https://api.fabric.microsoft.com.example.com/v1/test",
                "https://user:password@api.fabric.microsoft.com/v1/test"]:
        with pytest.raises(ValueError):
            f.request("GET", url)


def test_regional_operation_url_is_supported_without_accepting_arbitrary_suffixes():
    f = fake_fabric(lambda request: httpx.Response(200, json={"status": "Succeeded"}))
    r = f.request("GET", "https://wabi-west-us3-a-primary-redirect.analysis.windows.net/operation")
    assert r.json()["status"] == "Succeeded"
    with pytest.raises(ValueError):
        f.request("GET", "https://arbitrary.analysis.windows.net/operation")


def test_auto_created_sql_endpoint_does_not_conflict_with_lakehouse():
    f = Fabric.__new__(Fabric)
    lakehouse = {"id": "lakehouse", "displayName": "research_feasibility_v1",
                 "type": "Lakehouse", "description": "Entirely synthetic research demo"}
    f.items = lambda: [lakehouse, {**lakehouse, "id": "sql", "type": "SQLEndpoint"}]
    assert f.ensure_item("Lakehouse", "lakehouses", {"displayName": "research_feasibility_v1"}) == lakehouse


def test_existing_unowned_item_is_not_modified():
    f = Fabric.__new__(Fabric)
    f.items = lambda: [{"id": "external", "displayName": "research_feasibility_v1",
                        "type": "Lakehouse", "description": "Existing hospital work"}]
    with pytest.raises(RuntimeError, match="refusing to modify"):
        f.ensure_item("Lakehouse", "lakehouses", {"displayName": "research_feasibility_v1"})


def test_published_definition_contains_only_own_source_and_no_reference_answers():
    import base64
    import json
    definition = data_agent_definition("own-lakehouse", [], [
        {"table_name": "research_episodes", "column_name": "patient_id", "data_type": "varchar"},
    ])
    parts = {item["path"]: json.loads(base64.b64decode(item["payload"])) for item in definition["parts"]}
    source = parts["Files/Config/published/lakehouse-tables-research_feasibility_v1/datasource.json"]
    assert source["artifactId"] == "own-lakehouse"
    assert source["workspaceId"] == WORKSPACE
    assert source["type"] == "lakehouse_tables"
    schema = source["elements"][0]
    assert schema["display_name"] == "dbo"
    assert schema["type"] == "lakehouse_tables.schema"
    tables = schema["children"]
    assert [table["display_name"] for table in tables] == ["research_episodes", "research_sites"]
    assert all(table["is_selected"] and table["id"] for table in tables)
    column = tables[0]["children"][0]
    assert column["display_name"] == "patient_id"
    assert column["data_type"] == "varchar"
    assert column["type"] == "lakehouse_tables.column"
    assert "Files/Config/publish_info.json" in parts
    assert "2697" not in str(parts)
    assert "960" not in str(parts)
