from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

from google_connect.runner_utils import ingest_document
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import gmail_message_to_document


def list_message_details(service: Any, user_id: str, query: str, max_results: int) -> list[dict[str, Any]]:
    message_ids: list[dict[str, Any]] = []
    page_token = None
    while len(message_ids) < max_results:
        remaining = max_results - len(message_ids)
        response = (
            service.users()
            .messages()
            .list(
                userId=user_id,
                q=query,
                maxResults=min(remaining, 500),
                pageToken=page_token,
            )
            .execute()
        )
        message_ids.extend(response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    details = []
    for item in message_ids:
        detail = service.users().messages().get(userId=user_id, id=item["id"], format="full").execute()
        details.append(detail)
    return details


def timestamp_from_message(detail: dict[str, Any]) -> int:
    return int((detail.get("internalDate") or "0")) // 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, "gmail_incremental")
    service = google_service(config, "gmail", "v1")
    cursor = state.load("gmail_incremental_cursor", {}) or {}
    previous_after_ts = int(
        cursor.get("after_ts")
        or int((datetime.now(timezone.utc) - timedelta(days=config.runtime.lookback_days)).timestamp())
    )
    query = f"after:{previous_after_ts}"
    details = list_message_details(service, config.google.gmail_user_id, query, config.runtime.max_messages or 100)
    ordered_details = sorted(details, key=timestamp_from_message)

    failures: list[dict[str, str]] = []
    ingested_count = 0
    next_after_ts = previous_after_ts
    for detail in ordered_details:
        try:
            document = gmail_message_to_document(detail)
            ingest_document(ekg, document, config.runtime.extraction_mode)
            ingested_count += 1
            next_after_ts = max(next_after_ts, timestamp_from_message(detail))
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": str(detail.get("id", "unknown")), "error": str(exc)})
            logger.exception("gmail_incremental failure gmail_id=%s", detail.get("id"))
            break

    summary = {
        "ok": not failures,
        "fetched_count": len(ordered_details),
        "ingested_count": ingested_count,
        "failed_count": len(failures),
        "next_cursor": previous_after_ts if failures else next_after_ts,
        "partial_failure": bool(failures),
        "failures": failures,
    }
    state.save("gmail_incremental_cursor", {"after_ts": summary["next_cursor"]})
    runner_summary("gmail_incremental", summary, logger)


if __name__ == "__main__":
    main()
