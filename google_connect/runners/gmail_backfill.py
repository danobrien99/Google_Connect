from __future__ import annotations

import argparse
from typing import Any

from google_connect.runners.common import bootstrap, google_service
from google_connect.transformers import gmail_message_to_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--query', default='')
    parser.add_argument('--max-messages', type=int, default=250)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, 'gmail_backfill')
    service = google_service(config, 'gmail', 'v1')

    query = args.query or config.runtime.__dict__.get('gmail_query', '') or ''
    resp = service.users().messages().list(
        userId=config.google.gmail_user_id,
        q=query,
        maxResults=args.max_messages,
    ).execute()
    messages = resp.get('messages', [])

    successes = 0
    failures: list[dict[str, str]] = []
    for item in messages:
        try:
            detail = service.users().messages().get(userId=config.google.gmail_user_id, id=item['id'], format='full').execute()
            doc = gmail_message_to_document(item, detail)
            ekg.ingest_and_extract_document(
                doc,
                {
                    'document_id': doc['document_id'],
                    'document_class': doc['document_class'],
                    'document_traits': doc['document_traits'],
                    'extraction_mode': config.runtime.extraction_mode,
                },
            )
            successes += 1
        except Exception as exc:  # noqa: BLE001
            failures.append({'gmail_id': item.get('id', 'unknown'), 'error': str(exc)})
            logger.exception('backfill failure gmail_id=%s', item.get('id'))

    summary = {'ok': True, 'count': len(messages), 'successes': successes, 'failures': failures}
    state.save('gmail_backfill_last_run', summary)
    print(summary)


if __name__ == '__main__':
    main()
