from __future__ import annotations

import argparse
from typing import Any

from google_connect.runner_utils import ingest_document
from google_connect.runners.common import bootstrap, google_service, runner_summary
from google_connect.transformers import sheet_rows_to_document


def fetch_sheet_values(service: Any, spreadsheet_id: str, range_name: str) -> list[dict[str, Any]]:
    response = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = response.get("values", [])
    if not values:
        return []
    headers = values[0]
    rows = []
    for row in values[1:]:
        rows.append({headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, "sheets_reader")
    service = google_service(config, "sheets", "v4")

    summaries = []
    for sheet_name, range_name in [
        ("contacts", config.google.sheets.contacts_range),
        ("deals", config.google.sheets.deals_range),
    ]:
        rows = fetch_sheet_values(service, config.google.sheets.spreadsheet_id, range_name)
        document = sheet_rows_to_document("google_sheets", config.google.sheets.spreadsheet_id, sheet_name, rows)
        result = ingest_document(ekg, document, config.runtime.extraction_mode)
        summaries.append(
            {
                "sheet": sheet_name,
                "rows": len(rows),
                "document_id": document["document_id"],
                "result": result,
            }
        )

    summary = {
        "ok": True,
        "fetched_count": sum(item["rows"] for item in summaries),
        "ingested_count": len(summaries),
        "failed_count": 0,
        "partial_failure": False,
        "summaries": summaries,
    }
    state.save("sheets_reader_last_run", summary)
    runner_summary("sheets_reader", summary, logger)


if __name__ == "__main__":
    main()
