"""Explicit, repeatable CU setup using already-deployed models; no new Azure resources."""
import json
import time

import httpx

from app.config import settings
from app.intake import API_VERSION, analyzer_definition, credential, operation_url


def main():
    if not settings.content_understanding_endpoint or not settings.content_understanding_analyzer:
        raise SystemExit("CONTENT_UNDERSTANDING_ENDPOINT und CONTENT_UNDERSTANDING_ANALYZER fehlen.")
    endpoint = settings.content_understanding_endpoint.rstrip("/")
    with credential(settings) as auth, httpx.Client(timeout=45) as client:
        client.headers["Authorization"] = f"Bearer {auth.get_token('https://cognitiveservices.azure.com/.default').token}"
        defaults_url = f"{endpoint}/contentunderstanding/defaults?api-version={API_VERSION}"
        response = client.get(defaults_url)
        response.raise_for_status()
        existing = response.json().get("modelDeployments", {})
        required = {"gpt-4.1": "gpt-4.1", "text-embedding-3-large": "text-embedding-3-large"}
        if any(key in existing and existing[key] != value for key, value in required.items()):
            raise SystemExit("CU-Modellzuordnung kollidiert mit vorhandener Konfiguration. Nichts überschrieben.")
        if not required.items() <= existing.items():
            response = client.patch(defaults_url, json={"modelDeployments": {**existing, **required}})
            response.raise_for_status()
        analyzer_url = (
            f"{endpoint}/contentunderstanding/analyzers/{settings.content_understanding_analyzer}"
            f"?api-version={API_VERSION}"
        )
        expected = analyzer_definition()
        response = client.get(analyzer_url)
        if response.status_code == 404:
            response = client.put(analyzer_url, json=expected, headers={"If-None-Match": "*"})
            response.raise_for_status()
            location = response.headers.get("Operation-Location")
            if location:
                location = operation_url(location, endpoint)
                for _ in range(60):
                    state = client.get(location)
                    state.raise_for_status()
                    status = state.json().get("status", "").lower()
                    if status == "succeeded":
                        break
                    if status in {"failed", "canceled"}:
                        raise SystemExit("CU-Analyzereinrichtung fehlgeschlagen: " + json.dumps(state.json().get("error")))
                    time.sleep(2)
                else:
                    raise SystemExit("Zeitlimit bei CU-Analyzereinrichtung.")
            response = client.get(analyzer_url)
        response.raise_for_status()
        actual = response.json()
        if actual.get("fieldSchema") != expected["fieldSchema"] or actual.get("models") != expected["models"]:
            raise SystemExit("Vorhandener Analyzer hat eine andere Definition. Nicht überschrieben.")
        print(json.dumps({"analyzer": actual["analyzerId"], "status": actual.get("status"),
                          "models": actual.get("models"), "new_resources": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"CU-Konfiguration HTTP {exc.response.status_code}: {exc.response.text}") from exc
