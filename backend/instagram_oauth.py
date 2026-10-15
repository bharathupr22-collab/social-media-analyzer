"""Instagram OAuth (Instagram Login flow) helpers.

Flow:
  1. oauth-start    -> authorize URL (admin logs in on instagram.com)
  2. oauth-callback -> code -> short-lived token -> long-lived token (60 days)
  3. long-lived token stored encrypted in connected_accounts (see vault.py)

The admin's password is entered only on Meta's own site; this server
never sees it.
"""

import json
import os
import secrets
import time
import urllib.parse
import urllib.request

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_URL = "https://graph.instagram.com"

SCOPE = "instagram_business_basic"

STATE_TTL_SECONDS = 600  # authorize links expire after 10 minutes


def _config():
    app_id = os.environ.get("INSTAGRAM_APP_ID", "")
    app_secret = os.environ.get("INSTAGRAM_APP_SECRET", "")
    redirect_uri = os.environ.get("INSTAGRAM_REDIRECT_URI", "")
    missing = [
        name
        for name, value in (
            ("INSTAGRAM_APP_ID", app_id),
            ("INSTAGRAM_APP_SECRET", app_secret),
            ("INSTAGRAM_REDIRECT_URI", redirect_uri),
        )
        if not value
    ]
    return app_id, app_secret, redirect_uri, missing


def _require_config():
    app_id, app_secret, redirect_uri, missing = _config()
    if missing:
        raise RuntimeError(
            "Instagram is not configured yet. Set in backend/.env: "
            + ", ".join(missing)
        )
    return app_id, app_secret, redirect_uri


def build_authorize_url(state: str) -> str:
    app_id, _, redirect_uri = _require_config()
    params = urllib.parse.urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{params}"


def _post_form(url: str, fields: dict) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def _graph_get(path: str, params: dict) -> dict:
    url = f"{GRAPH_URL}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


def _meta_error(data: dict) -> str:
    err = data.get("error", {})
    if isinstance(err, dict):
        return err.get("message") or err.get("error_user_msg") or "Unknown Instagram error"
    return str(err) if err else "Unknown Instagram error"


def exchange_code(code: str) -> dict:
    """Authorization code -> short-lived token + app-scoped user id."""
    app_id, app_secret, redirect_uri = _require_config()
    data = _post_form(
        TOKEN_URL,
        {
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
    )
    if "access_token" not in data:
        raise RuntimeError(f"Instagram login failed: {_meta_error(data)}")
    return data


def get_long_lived_token(short_token: str) -> dict:
    """Short-lived token -> long-lived token (valid ~60 days)."""
    _, app_secret, _ = _require_config()
    data = _graph_get(
        "/access_token",
        {
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        },
    )
    if "access_token" not in data:
        raise RuntimeError(f"Instagram token exchange failed: {_meta_error(data)}")
    return data


def get_profile(access_token: str) -> dict:
    data = _graph_get("/me", {"fields": "id,username", "access_token": access_token})
    if "id" not in data:
        raise RuntimeError(f"Could not read Instagram profile: {_meta_error(data)}")
    return data


# In-memory one-time state tokens (CSRF protection for the OAuth dance).
_pending_states: dict[str, float] = {}


def new_state() -> str:
    state = secrets.token_urlsafe(24)
    _pending_states[state] = time.time() + STATE_TTL_SECONDS
    return state


def consume_state(state: str) -> bool:
    expiry = _pending_states.pop(state, None)
    return expiry is not None and expiry > time.time()
