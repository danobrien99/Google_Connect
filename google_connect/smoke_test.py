from __future__ import annotations

from google_connect.ekg_client import EkgClient
from google_connect.transformers import stable_document_id


def main() -> None:
    client = EkgClient('http://127.0.0.1:8000')
    payload = {
        'kind': 'smoke_test',
        'note': 'Google_Connect pipeline validation',
    }
    doc_id = stable_document_id('google-connect-smoke', payload)
    ingest = client.ingest_document({
        'document_id': doc_id,
        'title': 'Google_Connect smoke test',
        'text': '{"kind":"smoke_test","note":"Google_Connect pipeline validation"}',
        'document_class': 'integration_smoke_test',
        'document_traits': ['google_connect', 'smoke_test'],
        'source_type': 'google_connect',
        'artifact_type': 'smoke_document',
        'mime_type': 'application/json',
        'metadata': payload,
    })
    extract = client.extract_document({
        'document_id': doc_id,
        'document_class': 'integration_smoke_test',
        'document_traits': ['google_connect', 'smoke_test'],
        'extraction_mode': 'hybrid_llm_validated',
    })
    print({'document_id': doc_id, 'ingest': ingest, 'extract_count': extract.get('count')})


if __name__ == '__main__':
    main()
