from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import httpx


@dataclass
class EkgClient:
    base_url: str
    webhook_secret: str | None = None
    timeout_seconds: int = 60

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.webhook_secret:
            headers["X-Webhook-Secret"] = self.webhook_secret
        return headers

    def ingest_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/api/ingest/document", json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()

    def extract_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/api/extract/document", json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()

    def ingest_and_extract_document(self, ingest_payload: dict[str, Any], extract_payload: dict[str, Any]) -> dict[str, Any]:
        ingest_result = self.ingest_document(ingest_payload)
        extract_result = self.extract_document(extract_payload)
        return {"ingest": ingest_result, "extract": extract_result}
