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
