from __future__ import annotations

import argparse
from typing import Any

from google_connect.runners.common import bootstrap, google_service
from google_connect.transformers import sheet_rows_to_document


def fetch_sheet_values(service: Any, spreadsheet_id: str, range_name: str) -> list[dict[str, Any]]:
    resp = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = resp.get('values', [])
    if not values:
        return []
    headers = values[0]
    rows = []
    for row in values[1:]:
        rows.append({headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, 'sheets_reader')
    service = google_service(config, 'sheets', 'v4')

    summaries = []
    for sheet_name, range_name in [('contacts', config.google.sheets.contacts_range), ('deals', config.google.sheets.deals_range)]:
        rows = fetch_sheet_values(service, config.google.sheets.spreadsheet_id, range_name)
        doc = sheet_rows_to_document('google_sheets', sheet_name, rows)
        result = ekg.ingest_and_extract_document(
            doc,
            {
                'document_id': doc['document_id'],
                'document_class': doc['document_class'],
                'document_traits': doc['document_traits'],
                'extraction_mode': config.runtime.extraction_mode,
            },
        )
        summaries.append({'sheet': sheet_name, 'rows': len(rows), 'document_id': doc['document_id'], 'result': result})
        logger.info('processed sheet=%s rows=%s document_id=%s', sheet_name, len(rows), doc['document_id'])

    state.save('sheets_reader_last_run', {'summaries': summaries})
    print({'ok': True, 'summaries': summaries})


if __name__ == '__main__':
    main()
