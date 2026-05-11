from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def _run_installed_flow(credentials_path: Path, scopes: list[str]) -> Credentials:
    client_config = json.loads(credentials_path.read_text())
    installed_config = client_config.get("installed", {})
    redirect_uris = installed_config.get("redirect_uris", [])

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)

    # Some desktop client configs only allow the exact redirect URI `http://localhost`.
    # In that case, a random loopback port causes redirect_uri_mismatch, so fall back
    # to a manual copy/paste flow that uses the configured redirect verbatim.
    if redirect_uris == ["http://localhost"]:
        flow.redirect_uri = "http://localhost"
        auth_url, _state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        print(f"Please visit this URL to authorize this application: {auth_url}")
        authorization_response = input("Paste the full redirect URL after approval: ").strip()
        parsed = urlparse(authorization_response)
        if not parsed.scheme:
            code = authorization_response
            authorization_response = f"http://localhost?code={code}"
        elif parsed.scheme != "http" or parsed.netloc not in {"localhost", "localhost:80"}:
            code = parse_qs(parsed.query).get("code", [None])[0]
            if not code:
                raise ValueError("authorization response did not contain a code")
            authorization_response = f"http://localhost?code={code}"
        flow.fetch_token(authorization_response=authorization_response)
        return flow.credentials

    return flow.run_local_server(port=0)


def load_credentials(credentials_path: Path, token_path: Path, scopes: list[str]) -> Credentials:
    creds = None
    if token_path.exists():
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
