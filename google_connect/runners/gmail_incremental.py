from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

from google_connect.runners.common import bootstrap, google_service
from google_connect.transformers import gmail_message_to_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()

    config, ekg, state, logger = bootstrap(args.config, 'gmail_incremental')
    service = google_service(config, 'gmail', 'v1')
    cursor = state.load('gmail_incremental_cursor', {}) or {}
    after_ts = cursor.get('after_ts')
    if after_ts is None:
        after_ts = int((datetime.now(timezone.utc) - timedelta(days=config.runtime.lookback_days)).timestamp())
    query = f"after:{after_ts}"
    if config.runtime.max_messages:
        max_results = config.runtime.max_messages
    else:
        max_results = 100

    resp = service.users().messages().list(userId=config.google.gmail_user_id, q=query, maxResults=max_results).execute()
    messages = resp.get('messages', [])
    processed = []
    newest_ts = after_ts
    for item in messages:
        detail = service.users().messages().get(userId=config.google.gmail_user_id, id=item['id'], format='full').execute()
        doc = gmail_message_to_document(item, detail)
        result = ekg.ingest_and_extract_document(
            doc,
            {
                'document_id': doc['document_id'],
                'document_class': doc['document_class'],
                'document_traits': doc['document_traits'],
                'extraction_mode': config.runtime.extraction_mode,
            },
        )
        ts_ms = int(detail.get('internalDate', '0') or 0)
        newest_ts = max(newest_ts, ts_ms // 1000 if ts_ms else newest_ts)
        processed.append({'gmail_id': item['id'], 'document_id': doc['document_id'], 'result': result})
    state.save('gmail_incremental_cursor', {'after_ts': newest_ts})
    logger.info('processed gmail_incremental count=%s newest_ts=%s', len(processed), newest_ts)
    print({'ok': True, 'count': len(processed), 'after_ts': newest_ts})


if __name__ == '__main__':
    main()
