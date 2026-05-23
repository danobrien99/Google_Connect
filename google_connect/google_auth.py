from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def _run_installed_flow(credentials_path: Path, scopes: list[str]) -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    return flow.run_local_server(
        port=0,
        prompt="consent",
        include_granted_scopes="true",
    )


def load_credentials(credentials_path: Path, token_path: Path, scopes: list[str], force_fresh: bool = False) -> Credentials:
    creds = None
    if not force_fresh and token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
            if not creds.has_scopes(scopes):
                creds = None
        except ValueError:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = _run_installed_flow(credentials_path, scopes)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
    return creds


def build_service(api_name: str, version: str, credentials: Credentials):
    return build(api_name, version, credentials=credentials, cache_discovery=False)
