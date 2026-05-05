"""
auth.py — Microsoft identity authentication using MSAL (client credentials flow).

Acquires an access token for the Microsoft Graph API using the application's
client credentials (client_id + client_secret + tenant_id).
Tokens are cached in memory and refreshed automatically before expiry.
"""

import logging
import os
import time
from typing import Optional

import msal

logger = logging.getLogger(__name__)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

_token_cache: Optional[str] = None
_token_expiry: float = 0.0
_msal_app: Optional[msal.ConfidentialClientApplication] = None


def _get_app() -> msal.ConfidentialClientApplication:
    global _msal_app
    if _msal_app is None:
        tenant_id = os.environ["AZURE_TENANT_ID"]
        client_id = os.environ["AZURE_CLIENT_ID"]
        client_secret = os.environ["AZURE_CLIENT_SECRET"]

        authority = f"https://login.microsoftonline.com/{tenant_id}"
        _msal_app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority,
        )
    return _msal_app


def get_access_token() -> str:
    """
    Return a valid access token for Microsoft Graph.
    Uses in-memory cache; refreshes automatically 60 seconds before expiry.
    """
    global _token_cache, _token_expiry

    if _token_cache and time.time() < _token_expiry - 60:
        return _token_cache

    app = _get_app()

    # Try cache first (MSAL internal token cache)
    result = app.acquire_token_silent(scopes=GRAPH_SCOPE, account=None)

    if not result:
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown"))
        raise RuntimeError(f"Failed to acquire Graph API token: {error}")

    _token_cache = result["access_token"]
    _token_expiry = time.time() + result.get("expires_in", 3600)

    logger.info("Acquired new Graph API token (expires_in=%ds).", result.get("expires_in"))
    return _token_cache
