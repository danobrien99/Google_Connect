from __future__ import annotations

import argparse
from typing import Any

from google_connect.runner_utils import ingest_document
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.runners.gmail_incremental import list_message_details, timestamp_from_message
from google_connect.transformers import gmail_message_to_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--max-messages", type=int, default=250)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, "gmail_backfill")
    service = google_service(config, "gmail", "v1")

    details = list_message_details(service, config.google.gmail_user_id, args.query or "", args.max_messages)
    ordered_details = sorted(details, key=timestamp_from_message)

    successes = 0
    failures: list[dict[str, str]] = []
    for detail in ordered_details:
        try:
            document = gmail_message_to_document(detail)
            ingest_document(ekg, document, config.runtime.extraction_mode)
            successes += 1
        except Exception as exc:  # noqa: BLE001
            failures.append({"gmail_id": detail.get("id", "unknown"), "error": str(exc)})
            logger.exception("backfill failure gmail_id=%s", detail.get("id"))

    summary = {
        "ok": not failures,
        "fetched_count": len(ordered_details),
        "ingested_count": successes,
        "failed_count": len(failures),
        "partial_failure": bool(failures),
        "failures": failures,
    }
    state.save("gmail_backfill_last_run", summary)
    runner_summary("gmail_backfill", summary, logger)


if __name__ == "__main__":
    main()
