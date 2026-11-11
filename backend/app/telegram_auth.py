"""Telegram Mini App initData verification (server-side, HMAC-SHA256).

NEVER trust initDataUnsafe from the client. The frontend sends the raw initData string;
the backend recomputes the hash with the bot token and checks it, the auth_date freshness,
and the user-id whitelist.

Spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from .config import get_settings


class AuthError(Exception):
    """Raised when initData is invalid, stale, or the user is not whitelisted."""


def _secret_key(bot_token: str) -> bytes:
    # secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def verify_init_data(init_data: str) -> dict:
    """Validate a Telegram WebApp initData query string. Returns the parsed user dict
    on success; raises AuthError otherwise."""
    s = get_settings()

    if s.auth_disabled:
        # LOCAL DEV ONLY — never enable in production.
        return {"id": 0, "username": "dev", "first_name": "Dev", "_auth": "disabled"}

    if not init_data:
        raise AuthError("missing initData")
    if not s.bot_token:
        raise AuthError("server bot token not configured")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise AuthError("initData has no hash")

    # data_check_string = sorted "key=value" lines joined by \n (hash excluded)
    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = _secret_key(s.bot_token)
    calc_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, received_hash):
        raise AuthError("initData hash mismatch")

    # freshness
    auth_date = pairs.get("auth_date")
    if auth_date and auth_date.isdigit():
        age = time.time() - int(auth_date)
        if age > s.initdata_max_age:
            raise AuthError(f"initData expired ({int(age)}s old)")

    # user
    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        raise AuthError("initData user not parseable")
    uid = user.get("id")
    if uid is None:
        raise AuthError("initData has no user id")

    # whitelist
    if s.allowed_user_ids and int(uid) not in s.allowed_user_ids:
        raise AuthError(f"user {uid} not whitelisted")

    return user
