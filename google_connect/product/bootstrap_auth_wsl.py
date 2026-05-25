from __future__ import annotations

import argparse
import json

from google_connect.config import load_config
from google_connect.google_auth import AUTH_MODE_WSL, load_credentials


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Google OAuth token storage for WSL/OpenClaw runtime.")
    parser.add_argument("--config", required=True, help="Path to Google_Connect YAML config.")
    parser.add_argument("--fresh", action="store_true", help="Force a fresh browser grant and ignore any cached token.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    creds = load_credentials(
        cfg.google.credentials_path,
        cfg.google.token_path,
        cfg.google.scopes,
        force_fresh=args.fresh,
        auth_mode=AUTH_MODE_WSL,
    )
    print(
        json.dumps(
            {
                "ok": bool(creds and creds.valid),
                "credentials_path": str(cfg.google.credentials_path),
                "token_path": str(cfg.google.token_path),
                "scopes": cfg.google.scopes,
                "auth_mode": AUTH_MODE_WSL,
            }
        )
    )


if __name__ == "__main__":
    main()
