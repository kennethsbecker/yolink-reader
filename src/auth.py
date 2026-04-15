#!/usr/bin/env python3
"""YoLink authentication — token acquisition and expiry tracking."""

import json
import time
import urllib.parse
import urllib.request
from typing import Tuple

import src.config as config

# Module-level token cache
_access_token: str = ""
_token_fetched_at: float = 0.0
_TOKEN_LIFETIME: int = 7200  # seconds, per YoLink spec


def get_token() -> str:
    """Fetch a new access token from the YoLink token endpoint.

    Returns the access token string. Caches token and fetch time
    so callers can check expiry via token_expires_in().
    """
    global _access_token, _token_fetched_at

    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": config.YOLINK_UAID,
        "client_secret": config.YOLINK_SECRET,
    }).encode()

    req = urllib.request.Request(
        config.YOLINK_TOKEN_URL,
        data=data,
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode())

    _access_token = body["access_token"]
    _token_fetched_at = time.time()
    return _access_token


def token_expires_in() -> float:
    """Return seconds remaining until the cached token expires.

    Returns 0 if no token has been fetched yet.
    """
    if not _token_fetched_at:
        return 0.0
    elapsed = time.time() - _token_fetched_at
    remaining = _TOKEN_LIFETIME - elapsed
    return max(0.0, remaining)
