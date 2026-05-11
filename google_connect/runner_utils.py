from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any


def build_extract_payload(document: dict[str, Any], extraction_mode: str) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "document_class": document["document_class"],
        "document_traits": document["document_traits"],
        "extraction_mode": extraction_mode,
    }


def ingest_document(ekg: Any, document: dict[str, Any], extraction_mode: str) -> dict[str, Any]:
    return ekg.ingest_and_extract_document(document, build_extract_payload(document, extraction_mode))


def parse_rfc3339(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def process_items_with_high_water_mark(
    items: list[dict[str, Any]],
    timestamp_getter: Callable[[dict[str, Any]], str | None],
    processor: Callable[[dict[str, Any]], Any],
    previous_high_water_mark: str | None,
) -> dict[str, Any]:
    ordered_items = sorted(items, key=lambda item: parse_rfc3339(timestamp_getter(item)).timestamp())
    failures: list[dict[str, str]] = []
    ingested = 0
    high_water_mark = previous_high_water_mark

    for item in ordered_items:
        try:
            processor(item)
            ingested += 1
            item_timestamp = timestamp_getter(item)
            if item_timestamp:
                high_water_mark = item_timestamp
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": str(item.get("id") or item.get("name") or "unknown"), "error": str(exc)})
            break

    return {
        "fetched_count": len(items),
        "ingested_count": ingested,
        "failed_count": len(failures),
        "high_water_mark": high_water_mark if not failures else previous_high_water_mark,
        "partial_failure": bool(failures),
        "failures": failures,
    }
