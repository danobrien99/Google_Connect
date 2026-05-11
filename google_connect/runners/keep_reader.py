from __future__ import annotations

import argparse
from typing import Any

from google_connect.runner_utils import ingest_document, parse_rfc3339
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import keep_note_to_document


def list_notes(service: Any, page_size: int, include_trashed: bool) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    page_token = None
    note_filter = "" if include_trashed else "trashed = false"
    while True:
        response = (
            service.notes()
            .list(pageSize=page_size, pageToken=page_token, filter=note_filter)
            .execute()
        )
        notes.extend(response.get("notes", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return notes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, "keep_reader")
    if not config.google.keep.enabled:
        runner_summary("keep_reader", {"ok": True, "skipped": True, "reason": "keep disabled"}, logger)
        return

    service = google_service(config, "keep", "v1")
    previous_high_water_mark = (state.load("keep_reader_cursor", {}) or {}).get("update_time")
    notes = list_notes(service, config.google.keep.page_size, config.google.keep.include_trashed)
    filtered_notes = []
    for note in notes:
        update_time = note.get("updateTime")
        if previous_high_water_mark and update_time and parse_rfc3339(update_time) <= parse_rfc3339(previous_high_water_mark):
            continue
        filtered_notes.append(note)
    ordered_notes = sorted(filtered_notes, key=lambda item: parse_rfc3339(item.get("updateTime")).timestamp())

    failures: list[dict[str, str]] = []
    ingested_count = 0
    high_water_mark = previous_high_water_mark
    for note in ordered_notes:
        try:
            document = keep_note_to_document(note)
            ingest_document(ekg, document, config.runtime.extraction_mode)
            ingested_count += 1
            high_water_mark = note.get("updateTime", high_water_mark)
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": str(note.get("name", "unknown")), "error": str(exc)})
            logger.exception("keep_reader failure note=%s", note.get("name"))
            break

    summary = {
        "ok": not failures,
        "fetched_count": len(ordered_notes),
        "ingested_count": ingested_count,
        "failed_count": len(failures),
        "next_cursor": previous_high_water_mark if failures else high_water_mark,
        "partial_failure": bool(failures),
        "failures": failures,
    }
    state.save("keep_reader_cursor", {"update_time": summary["next_cursor"]})
    runner_summary("keep_reader", summary, logger)


if __name__ == "__main__":
    main()
