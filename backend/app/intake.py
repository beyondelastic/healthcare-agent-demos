import base64
import hashlib
import logging
import math
import os
import re
import time
import unicodedata
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pymupdf
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from fastapi import HTTPException

from .config import Settings
from .followup import queue_event, set_automation
from .store import Store, audit, now

logger = logging.getLogger(__name__)
MAX_FILE_BYTES = 5 * 1024 * 1024
API_VERSION = "2025-11-01"


def scan_pages(raw: bytes, content_type: str) -> list[str]:
    signatures = {
        "application/pdf": (b"%PDF-", "pdf"),
        "image/png": (b"\x89PNG\r\n\x1a\n", "png"),
        "image/jpeg": (b"\xff\xd8\xff", "jpeg"),
    }
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise HTTPException(413, "Leere Datei oder Dateigröße über 5 MiB.")
    signature = signatures.get(content_type)
    if not signature or not raw.startswith(signature[0]):
        raise HTTPException(422, "Nur echte PDF-, PNG- oder JPEG-Dateien werden unterstützt.")
    try:
        with pymupdf.open(stream=raw, filetype=signature[1]) as doc:
            if doc.needs_pass or not 1 <= len(doc) <= 3:
                raise HTTPException(422, "Nur unverschlüsselte Dokumente mit ein bis drei Seiten.")
            previews = []
            for page in doc:
                width, height = page.rect.width, page.rect.height
                if not 1 <= width <= 12000 or not 1 <= height <= 12000:
                    raise HTTPException(422, "Unzulässige Seitengröße.")
                scale = min(1.6, 1500 / max(width, height))
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                previews.append(base64.b64encode(pixmap.tobytes("png")).decode("ascii"))
            return previews
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        logger.warning("Document preview rejected: %s", type(exc).__name__)
        raise HTTPException(422, "Datei ist beschädigt oder kann nicht sicher als Vorschau dargestellt werden.") from exc


def sample_scan(case: dict) -> bytes:
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.draw_rect(pymupdf.Rect(35, 35, 560, 800), color=(0.75, 0.75, 0.75))
        page.insert_text((55, 70), "EXTERNER KONSILBERICHT", fontsize=17, fontname="hebo")
        page.insert_text((55, 95), "SYNTHETISCHE DEMO - KEINE ECHTEN PATIENTENDATEN", fontsize=9)
        page.insert_text((55, 130), "Konsildienst Infektiologie - Klinikum Beispielstadt (fiktiv)", fontsize=11)
        page.insert_text((55, 153), "An: Innere Medizin, Universitätsklinikum Musterstadt (fiktiv)", fontsize=11)
        page.insert_text((55, 195), f"Patientin: {case['name']}", fontsize=12)
        page.insert_text((55, 220), f"Fallnummer des anfragenden Hauses: {case['id']}", fontsize=12)
        page.insert_text((55, 245), "Dokumentdatum: 24.10.2026", fontsize=12)
        page.insert_text((55, 285), "Anlass und Bezug", fontsize=13, fontname="hebo")
        context_space = page.insert_textbox(pymupdf.Rect(55, 303, 530, 395), (
            "Konsiliarische Rückmeldung zur organisatorischen Befundnachverfolgung "
            "bei dokumentierter Pneumonie und geplanter Entlassung. Bezug: Blutkulturen "
            "vom 20.10.2026 im aktuellen stationären Aufenthalt."
        ), fontsize=11, lineheight=1.4)
        page.insert_text((55, 425), "Empfehlung zur Befundnachverfolgung", fontsize=13, fontname="hebo")
        recommendation_space = page.insert_textbox(pymupdf.Rect(55, 445, 530, 665), (
            "Mikrobiologischen Abschlussbefund der Blutkulturen kontrollieren.\n\n"
            "Befundnachverfolgung nach Entlassung verbindlich organisieren.\n\n"
            "Eine verantwortliche Stelle ist in diesem Schreiben nicht benannt. "
            "Zuständigkeit durch das behandelnde Haus bestätigen lassen.\n\n"
            "Dies ist kein Laborbefund. Den aktuellen Status und den finalen Befund "
            "im Laborinformationssystem des anfragenden Hauses prüfen."
        ), fontsize=11, lineheight=1.4)
        if context_space < 0 or recommendation_space < 0:
            raise ValueError("Der synthetische Konsilbericht passt nicht vollständig auf die Scanvorlage.")
        page.insert_text((55, 700), "Keine Therapieempfehlung. Angaben durch Klinikteam prüfen.", fontsize=10)
        page.insert_text((55, 750), "Fiktiver Konsilbericht - nur zur Demonstration der Dokumentenverarbeitung.", fontsize=9)
        # Only pixels are delivered: the analysis must actually read a scan.
        return page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), alpha=False).tobytes("png")


def analyzer_definition() -> dict:
    descriptions = {
        "PatientName": "Vollständiger Name der Patientin oder des Patienten, exakt wie im Dokument.",
        "CaseId": "Explizit gedruckte Fallnummer, zum Beispiel DEMO-031. Nicht aus dem Namen ableiten.",
        "DocumentDate": "Im Dokument angegebenes Dokumentdatum als gedruckter Text.",
        "FollowupRecommendation": "Wörtliche Empfehlung zur Befundkontrolle oder Nachverfolgung. Keine Ergänzung oder Therapieempfehlung.",
    }
    return {
        "description": "Klinik Studio: ausschließlich synthetische Nachsorgedokumente",
        "baseAnalyzerId": "prebuilt-document",
        "models": {"completion": "gpt-4.1", "embedding": "text-embedding-3-large"},
        "config": {"returnDetails": True, "estimateFieldSourceAndConfidence": True},
        "fieldSchema": {"fields": {
            name: {"type": "string", "method": "extract", "description": description}
            for name, description in descriptions.items()
        }},
    }


def credential(settings: Settings):
    return ManagedIdentityCredential() if os.environ.get("IDENTITY_ENDPOINT") else AzureCliCredential(
        tenant_id=settings.azure_tenant_id, process_timeout=20)


def operation_url(location: str, endpoint: str) -> str:
    actual, expected = urlparse(location), urlparse(endpoint)
    if (actual.scheme != "https" or actual.netloc.lower() != expected.netloc.lower()
            or not actual.path.startswith("/contentunderstanding/")):
        raise ValueError("Azure hat eine unerwartete Ergebnisadresse geliefert. Kein Abruf dieser Adresse.")
    return location


def analyze(raw: bytes, content_type: str, settings: Settings, request_id: str) -> dict:
    if not settings.content_understanding_endpoint or not settings.content_understanding_analyzer:
        raise ValueError("Content Understanding ist noch nicht konfiguriert. Kein Ersatz-OCR verwendet.")
    endpoint = settings.content_understanding_endpoint.rstrip("/")
    if urlparse(endpoint).scheme != "https":
        raise ValueError("Content Understanding benötigt einen HTTPS-Endpunkt.")
    with credential(settings) as auth, httpx.Client(timeout=40, follow_redirects=False) as client:
        token = auth.get_token("https://cognitiveservices.azure.com/.default").token
        headers = {"Authorization": f"Bearer {token}", "x-ms-client-request-id": request_id}
        response = client.post(
            f"{endpoint}/contentunderstanding/analyzers/{settings.content_understanding_analyzer}:analyzeBinary",
            params={"api-version": API_VERSION, "stringEncoding": "codePoint"},
            content=raw, headers={**headers, "Content-Type": content_type},
        )
        response.raise_for_status()
        location = operation_url(response.headers.get("Operation-Location", ""), endpoint)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            result = client.get(location, headers=headers)
            result.raise_for_status()
            state = result.json()
            status = state.get("status", "").lower()
            if status == "succeeded":
                return state["result"]
            if status in {"failed", "canceled"}:
                logger.error("CU analysis %s failed: %s", request_id, state.get("error"))
                raise ValueError("Azure-Dokumentanalyse fehlgeschlagen. Keine Quelle oder klinische Aktion erzeugt.")
            time.sleep(2)
        raise ValueError("Zeitlimit der Azure-Dokumentanalyse erreicht. Später ausdrücklich erneut versuchen; kein Ersatz-OCR.")


def regions(source: str, pages: list[dict]) -> list[dict]:
    result = []
    sizes = {int(page["pageNumber"]): page for page in pages}
    for match in re.finditer(r"D\((\d+),([0-9eE+.,\s-]+)\)", source):
        number = int(match[1])
        coordinates = [float(value) for value in match[2].split(",")]
        size = sizes.get(number)
        if (not size or len(coordinates) != 8 or not all(math.isfinite(value) for value in coordinates)
                or size.get("width", 0) <= 0 or size.get("height", 0) <= 0):
            continue
        xs, ys = coordinates[0::2], coordinates[1::2]
        result.append({
            "page": number, "x": max(0, min(xs) / size["width"]),
            "y": max(0, min(ys) / size["height"]),
            "width": min(1, (max(xs) - min(xs)) / size["width"]),
            "height": min(1, (max(ys) - min(ys)) / size["height"]),
        })
    return result


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip()).casefold()


def extraction(result: dict, case: dict) -> dict:
    contents = result.get("contents", [])
    if len(contents) != 1:
        raise ValueError("Nur ein zusammenhängendes Dokument pro Upload wird unterstützt.")
    content = contents[0]
    pages = content.get("pages", [])
    fields = {}
    for name in ["PatientName", "CaseId", "DocumentDate", "FollowupRecommendation"]:
        field = content.get("fields", {}).get(name, {})
        fields[name] = {
            "value": field.get("valueString") or "", "confidence": field.get("confidence"),
            "regions": regions(field.get("source") or "", pages),
        }
    paragraphs = [
        {"id": f"p{index + 1}", "text": item["content"],
         "regions": regions(item.get("source") or "", pages)}
        for index, item in enumerate(content.get("paragraphs", []))
        if item.get("content", "").strip()
    ]
    if not paragraphs:
        raise ValueError("Azure hat keine belegbaren Originalabsätze geliefert. Dokument nicht als Quelle übernommen.")
    if len(paragraphs) > 160 or sum(len(item["text"]) for item in paragraphs) > 40000:
        raise ValueError("Zu viel Dokumenttext für diese begrenzte Demo. Kürzeres synthetisches Dokument verwenden.")
    original_text = normalize(" ".join(item["text"] for item in paragraphs))
    matched = (normalize(fields["PatientName"]["value"]) == normalize(case["name"])
               and normalize(fields["CaseId"]["value"]) == normalize(case["id"])
               and normalize(case["name"]) in original_text and normalize(case["id"]) in original_text
               and bool(fields["PatientName"]["regions"]) and bool(fields["CaseId"]["regions"]))
    return {
        "fields": fields, "paragraphs": paragraphs, "matched": matched,
        "match_note": "Name und Fallnummer stimmen überein; Original und OCR dennoch menschlich prüfen."
        if matched else "Name oder Fallnummer fehlen oder passen nicht zum ausgewählten Aufenthalt. Übernahme gesperrt.",
        "usage": result.get("usage"), "analyzer_id": result.get("analyzerId"),
    }


def begin_intake(store: Store, case: dict, raw: bytes, content_type: str, filename: str) -> dict:
    previews = scan_pages(raw, content_type)
    digest = hashlib.sha256(raw).hexdigest()
    if any(item["sha256"] == digest and item["status"] != "failed" for item in case["intakes"]):
        raise HTTPException(409, "Dieses Dokument wurde bereits eingelesen. Vorhandenen Dokumenteingang verwenden.")
    item = {
        "id": str(uuid4()), "at": now(), "filename": filename[:180], "sha256": digest,
        "status": "analyzing", "page_count": len(previews), "extraction": None,
        "error": None, "document_id": None, "reviewer": None,
    }
    return store.add_intake(case["id"], case["revision"], item, raw, content_type, previews)


def analyze_intake(store: Store, identifier: str, intake_id: str, settings: Settings):
    try:
        raw, content_type, _ = store.intake_file(identifier, intake_id)
        result = extraction(analyze(raw, content_type, settings, intake_id), store.get(identifier))
        store.update_intake(identifier, intake_id, lambda item: item.update(status="ready", extraction=result, error=None))
    except (AzureError, httpx.HTTPError, ValueError, KeyError, TypeError, HTTPException) as exc:
        logger.exception("Document intake failed: %s", intake_id)
        if isinstance(exc, HTTPException) and exc.status_code in {404, 409}:
            return
        message = str(exc) if isinstance(exc, ValueError) else (
            "Azure-Dokumentanalyse oder Anmeldung fehlgeschlagen. Original bleibt erhalten; keine Quelle erzeugt. "
            "Azure-Konfiguration prüfen und ausdrücklich erneut starten.")
        try:
            store.update_intake(identifier, intake_id, lambda item: item.update(status="failed", error=message))
        except HTTPException as removed:
            if removed.status_code != 409:
                raise
            logger.info("Intake removed during analysis: %s", intake_id)


def accept_intake(case: dict, intake_id: str, reviewer: str, monitor_events: bool):
    item = next((item for item in case["intakes"] if item["id"] == intake_id), None)
    if not item or item["status"] != "ready":
        raise HTTPException(409, "Keine geprüfte Dokumentanalyse zur Quellenübernahme vorhanden.")
    parsed = item["extraction"]
    if not parsed or not parsed["matched"]:
        raise HTTPException(422, "Name und Fallnummer stimmen nicht überein. Keine fallübergreifende Quellenübernahme.")
    source_id = f"{case['id'].lower()}-scan-{intake_id}"
    case["documents"].append({
        "id": source_id, "title": f"Geprüfter Scan · {item['filename']}", "kind": "Fremddokument",
        "system": "Azure Content Understanding · menschlich geprüft", "date": item["at"],
        "status": "available", "paragraphs": parsed["paragraphs"], "intake_id": intake_id,
    })
    item.update(status="accepted", document_id=source_id, reviewer=reviewer)
    case["source_version"] += 1
    case["approval"] = None
    case["status"] = "draft" if case["draft"] else "new"
    case["decisions"] = {
        key: value for key, value in case["decisions"].items()
        if key == "conflicting-followup" and case.get("followup_resolution")
    }
    set_automation(case, monitor_events, reviewer)
    queue_event(case, "external_document", "Neuer geprüfter Scan – Labor und Nachverfolgung abgleichen")
    audit(case, "Scan als Quelle ausdrücklich übernommen",
          f"{source_id} · SHA-256 {item['sha256']}. OCR und Fallzuordnung menschlich bestätigt. "
          "Vorhandener Brief ist veraltet; alte KIS-Kopien bleiben unverändert.", reviewer)
