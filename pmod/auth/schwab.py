"""Schwab OAuth2 flow + token refresh logic."""

import stat
import sys

import structlog
from schwab.auth import client_from_login_flow, client_from_token_file
from schwab.client import Client

from pmod.config import get_settings

log = structlog.get_logger()

_cached_client: Client | None = None


def _invalidate_client_cache() -> None:
    global _cached_client
    _cached_client = None


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
    _invalidate_client_cache()
    client = client_from_login_flow(
        api_key=settings.schwab_app_key,
        app_secret=settings.schwab_app_secret,
        callback_url=settings.schwab_callback_url,
        token_path=str(settings.schwab_token_path),
    )
    log.info("login successful", token_path=str(settings.schwab_token_path))
    _warn_token_permissions(settings.schwab_token_path)
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


def _warn_token_permissions(path: "Path") -> None:  # type: ignore[name-defined]
    """Log a warning if the token file is readable by group or others."""
    try:
        from pathlib import Path as _Path
        p = _Path(path) if not hasattr(path, "stat") else path
        if p.exists():
            mode = p.stat().st_mode
            if mode & (stat.S_IRGRP | stat.S_IROTH):
                log.warning(
                    "token_file_world_readable",
                    path=str(p),
                    hint="Run: chmod 600 " + str(p),
                )
    except Exception:
        pass  # permission check is best-effort


def get_client() -> Client:
    """Return an authenticated Schwab client, using a cached in-process instance when available.

    schwab-py manages access-token refresh internally on every API call, so the same
    Client object can be reused for the lifetime of the process without re-reading
    the token file on each request.
    """
    global _cached_client

    if _cached_client is not None:
        return _cached_client

    settings = get_settings()

    if settings.schwab_token_path.exists():
        log.info("loading cached Schwab token", path=str(settings.schwab_token_path))
        _warn_token_permissions(settings.schwab_token_path)
        _cached_client = client_from_token_file(
            token_path=str(settings.schwab_token_path),
            api_key=settings.schwab_app_key,
            app_secret=settings.schwab_app_secret,
        )
        return _cached_client

    log.warning("no cached token found, starting login flow")
    return run_oauth_flow()
