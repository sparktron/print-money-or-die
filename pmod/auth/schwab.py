"""Schwab OAuth2 flow + token refresh logic."""

import sys

import structlog
from schwab.auth import client_from_login_flow, client_from_token_file
from schwab.client import Client

from pmod.config import get_settings

log = structlog.get_logger()


def run_oauth_flow() -> Client:
    """Run the interactive browser-based OAuth2 login.

    Opens the Schwab login page in the user's default browser.
    After the user authorises, the callback URL is captured and
    tokens are saved to disk for future use.
    """
    settings = get_settings()

    if not settings.schwab_app_key or not settings.schwab_app_secret:
        log.error(
            "missing Schwab credentials",
            hint="Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env",
        )
        sys.exit(1)

    log.info("starting Schwab OAuth2 login flow")
    client = client_from_login_flow(
        api_key=settings.schwab_app_key,
        app_secret=settings.schwab_app_secret,
        callback_url=settings.schwab_callback_url,
        token_path=str(settings.schwab_token_path),
    )
    log.info("login successful", token_path=str(settings.schwab_token_path))
    return client


def auth_status() -> dict:
    """Return a dict describing the current Schwab auth state.

    Keys:
        connected (bool): True if a usable token exists.
        reason (str): Human-readable status line.
    """
    import json
    import time

    settings = get_settings()
    path = settings.schwab_token_path

    if not settings.schwab_app_key or not settings.schwab_app_secret:
        return {"connected": False, "reason": "Credentials not set in .env"}

    if not path.exists():
        return {"connected": False, "reason": "Run `pmod auth login` to connect"}

    try:
        data = json.loads(path.read_text())
        creation_ts: float = float(data.get("creation_timestamp", 0))
        token = data.get("token", {})
        access_expires_at: float = float(token.get("expires_at", 0))

        # Schwab refresh tokens expire after 7 days
        refresh_expires_at = creation_ts + 7 * 24 * 3600
        now = time.time()

        if now > refresh_expires_at:
            return {"connected": False, "reason": "Refresh token expired — run `pmod auth login`"}
        if now > access_expires_at:
            return {"connected": True, "reason": "Connected (access token will auto-refresh)"}
        return {"connected": True, "reason": "Connected"}
    except Exception as exc:
        log.warning("auth_status parse error", error=str(exc))
        return {"connected": False, "reason": "Token file unreadable — run `pmod auth login`"}


def get_client() -> Client:
    """Return an authenticated Schwab client, using cached tokens when available."""
    settings = get_settings()

    if settings.schwab_token_path.exists():
        log.info("loading cached Schwab token", path=str(settings.schwab_token_path))
        return client_from_token_file(
            token_path=str(settings.schwab_token_path),
            api_key=settings.schwab_app_key,
            app_secret=settings.schwab_app_secret,
        )

    log.warning("no cached token found, starting login flow")
    return run_oauth_flow()
