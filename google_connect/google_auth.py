from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import socket
from contextlib import contextmanager
import wsgiref.simple_server

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


AUTH_MODE_DESKTOP = "desktop"
AUTH_MODE_WSL = "wsl"
DEFAULT_DESKTOP_AUTH_TIMEOUT_SECONDS = 120
DEFAULT_WSL_AUTH_TIMEOUT_SECONDS = 300
VALID_AUTH_MODES = {AUTH_MODE_DESKTOP, AUTH_MODE_WSL}


class _SingleRequestCallbackServer(wsgiref.simple_server.WSGIServer):
    """Capture a single OAuth callback request, then stop serving."""

    allow_reuse_address = False

    def __init__(self, server_address, handler_cls):
        super().__init__(server_address, handler_cls)
        self.authorization_response: str | None = None


@contextmanager
def _relax_oauthlib_token_scope():
    """Allow Google to return a superset of the requested scopes.

    Google often returns the full granted scope set during incremental auth.
    oauthlib raises a Warning for that by default, so we scope-relax only while
    exchanging the authorization code for tokens.
    """
    previous = os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE")
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("OAUTHLIB_RELAX_TOKEN_SCOPE", None)
        else:
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = previous


def _normalize_auth_mode(auth_mode: str | None) -> str:
    normalized = (auth_mode or AUTH_MODE_DESKTOP).strip().lower()
    if normalized not in VALID_AUTH_MODES:
        raise ValueError(f"unsupported auth mode: {auth_mode}")
    return normalized


def _build_success_message() -> bytes:
    body = (
        "<html><body><h1>Google_Connect authorization complete.</h1>"
        "<p>You may close this window and return to OpenClaw.</p></body></html>"
    )
    return body.encode("utf-8")


def _attempt_browser_launch(auth_url: str) -> bool:
    try:
        return bool(webbrowser.open(auth_url, new=1, autoraise=True))
    except webbrowser.Error:
        return False


def _authorization_response_from_input(user_input: str, redirect_uri: str) -> str:
    raw = user_input.strip()
    if not raw:
        raise ValueError("authorization response was empty")

    parsed = urlparse(raw)
    if not parsed.scheme:
        return f"{redirect_uri}?code={raw}"
    if parsed.scheme in {"http", "https"}:
        if parse_qs(parsed.query).get("code"):
            return raw
        raise ValueError("authorization response URL did not contain a code")
    raise ValueError("authorization response must be a code or http(s) redirect URL")


def _handle_manual_fallback(flow: InstalledAppFlow) -> Credentials:
    authorization_response = input("Paste the full returned URL or just the code: ").strip()
    with _relax_oauthlib_token_scope():
        flow.fetch_token(authorization_response=_authorization_response_from_input(authorization_response, flow.redirect_uri))
    return flow.credentials


def _run_desktop_installed_flow(
    credentials_path: Path,
    scopes: list[str],
    *,
    timeout_seconds: int = DEFAULT_DESKTOP_AUTH_TIMEOUT_SECONDS,
) -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    callback_message = _build_success_message()

    def _app(environ, start_response):
        path = environ.get("PATH_INFO", "")
        query = environ.get("QUERY_STRING", "")
        flow_server.authorization_response = f"http://localhost:{flow_server.server_port}{path}"
        if query:
            flow_server.authorization_response += f"?{query}"
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(callback_message))),
            ],
        )
        return [callback_message]

    with _SingleRequestCallbackServer(("localhost", 0), wsgiref.simple_server.WSGIRequestHandler) as flow_server:
        flow_server.set_app(_app)
        flow.redirect_uri = f"http://localhost:{flow_server.server_port}"
        auth_url, _state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        if not _attempt_browser_launch(auth_url):
            print("Could not auto-open your browser. Falling back to a pasted URL or code.")
            print("Please visit this URL to authorize this application:")
            print(auth_url)
            return _handle_manual_fallback(flow)
        print("Please visit this URL to authorize this application:")
        print(auth_url, flush=True)
        flow_server.timeout = timeout_seconds
        try:
            flow_server.handle_request()
        except socket.timeout:
            pass

        if flow_server.authorization_response:
            with _relax_oauthlib_token_scope():
                flow.fetch_token(authorization_response=flow_server.authorization_response)
            return flow.credentials

    print(f"Automatic callback was not received in desktop mode after {timeout_seconds} seconds.")
    print("Falling back to one-time manual completion.")
    return _handle_manual_fallback(flow)


def _run_wsl_installed_flow(
    credentials_path: Path,
    scopes: list[str],
    *,
    timeout_seconds: int = DEFAULT_WSL_AUTH_TIMEOUT_SECONDS,
) -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)

    callback_message = _build_success_message()

    def _app(environ, start_response):
        path = environ.get("PATH_INFO", "")
        query = environ.get("QUERY_STRING", "")
        flow_server.authorization_response = f"http://localhost:{flow_server.server_port}{path}"
        if query:
            flow_server.authorization_response += f"?{query}"
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(callback_message))),
            ],
        )
        return [callback_message]

    with _SingleRequestCallbackServer(("0.0.0.0", 0), wsgiref.simple_server.WSGIRequestHandler) as flow_server:
        flow_server.set_app(_app)
        flow_server.timeout = timeout_seconds
        flow.redirect_uri = f"http://localhost:{flow_server.server_port}"
        auth_url, _state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        print("Open this URL in your Windows browser to authorize Google_Connect:")
        print(auth_url, flush=True)
        print(
            f"Waiting up to {timeout_seconds} seconds for Google to redirect back to "
            f"http://localhost:{flow_server.server_port} ..."
        )
        try:
            flow_server.handle_request()
        except socket.timeout:
            pass

        if flow_server.authorization_response:
            with _relax_oauthlib_token_scope():
                flow.fetch_token(authorization_response=flow_server.authorization_response)
            return flow.credentials

    print("Automatic callback was not received in WSL. Falling back to one-time manual completion.")
    return _handle_manual_fallback(flow)


def _run_installed_flow(credentials_path: Path, scopes: list[str], auth_mode: str) -> Credentials:
    mode = _normalize_auth_mode(auth_mode)
    if mode == AUTH_MODE_WSL:
        return _run_wsl_installed_flow(credentials_path, scopes)
    return _run_desktop_installed_flow(credentials_path, scopes)


def load_credentials(
    credentials_path: Path,
    token_path: Path,
    scopes: list[str],
    *,
    force_fresh: bool = False,
    auth_mode: str = AUTH_MODE_DESKTOP,
) -> Credentials:
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
            creds = _run_installed_flow(credentials_path, scopes, auth_mode)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
    return creds


def build_service(api_name: str, version: str, credentials: Credentials):
    return build(api_name, version, credentials=credentials, cache_discovery=False)
