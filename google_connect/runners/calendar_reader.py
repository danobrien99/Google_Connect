from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

from google_connect.runner_utils import ingest_document
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import calendar_events_to_document


def list_events(service: Any, calendar_id: str, time_min: str, time_max: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, "calendar_reader")
    service = google_service(config, "calendar", "v3")

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=1)).isoformat()
    time_max = (now + timedelta(days=14)).isoformat()
    events = list_events(service, config.google.calendar_id, time_min, time_max)

    document = calendar_events_to_document(events, config.google.calendar_id)
    result = ingest_document(ekg, document, config.runtime.extraction_mode)
    summary = {
        "ok": True,
        "fetched_count": len(events),
        "ingested_count": 1,
        "failed_count": 0,
        "partial_failure": False,
        "document_id": document["document_id"],
        "result": result,
    }
    state.save("calendar_reader_last_run", summary)
    runner_summary("calendar_reader", summary, logger)


if __name__ == "__main__":
    main()
