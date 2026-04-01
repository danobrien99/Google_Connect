from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from google_connect.runners.common import bootstrap, google_service
from google_connect.transformers import calendar_events_to_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, 'calendar_reader')
    service = google_service(config, 'calendar', 'v3')

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=1)).isoformat()
    time_max = (now + timedelta(days=14)).isoformat()

    resp = service.events().list(
        calendarId=config.google.calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime',
    ).execute()
    events = resp.get('items', [])

    doc = calendar_events_to_document(events, config.google.calendar_id)
    result = ekg.ingest_and_extract_document(
        doc,
        {
            'document_id': doc['document_id'],
            'document_class': doc['document_class'],
            'document_traits': doc['document_traits'],
            'extraction_mode': config.runtime.extraction_mode,
        },
    )
    state.save('calendar_reader_last_run', {'event_count': len(events), 'document_id': doc['document_id']})
    logger.info('processed calendar events=%s document_id=%s', len(events), doc['document_id'])
    print({'ok': True, 'event_count': len(events), 'document_id': doc['document_id'], 'result': result})


if __name__ == '__main__':
    main()
