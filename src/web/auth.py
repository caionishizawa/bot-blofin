"""
Dashboard Authentication — JWT-based login for 2 users.

Users are configured via environment variables:
    DASHBOARD_USER_1=username:password
    DASHBOARD_USER_2=username:password

JWT secret via:
    DASHBOARD_SECRET=your-secret-key
"""

import hashlib
import hmac
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# JWT implementation without external crypto dependencies
# Uses HMAC-SHA256 for signing
import base64
import json as _json


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += "=" * (padding % 4)
    return base64.urlsafe_b64decode(s)


def _get_secret() -> str:
    secret = os.environ.get("DASHBOARD_SECRET", "")
    if not secret:
        logger.warning("DASHBOARD_SECRET not set — using insecure default. Set it in .env!")
        secret = "npk-sinais-default-secret-change-me"
    return secret


def create_token(username: str, expires_hours: int = 12) -> str:
    """Create a signed JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_hours * 3600,
    }
    header_enc = _b64url_encode(_json.dumps(header, separators=(",", ":")).encode())
    payload_enc = _b64url_encode(_json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_enc}.{payload_enc}"
    secret = _get_secret()
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_enc = _b64url_encode(sig)
    return f"{signing_input}.{sig_enc}"


def verify_token(token: str) -> Optional[str]:
    """Verify JWT token. Returns username or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_enc, payload_enc, sig_enc = parts
        signing_input = f"{header_enc}.{payload_enc}"
        secret = _get_secret()
        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        expected_sig_enc = _b64url_encode(expected_sig)
        if not hmac.compare_digest(sig_enc, expected_sig_enc):
            return None
        payload = _json.loads(_b64url_decode(payload_enc))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("sub")
    except Exception:
        return None


def _load_users() -> dict:
    """Load users from environment variables."""
    users = {}
    for i in range(1, 6):  # Support up to 5 users
        env_val = os.environ.get(f"DASHBOARD_USER_{i}", "")
        if ":" in env_val:
            username, password = env_val.split(":", 1)
            username = username.strip()
            password = password.strip()
            if username and password:
                users[username] = password
    if not users:
        # Fallback defaults (should be overridden in .env)
        users = {"admin": "npksinais2024", "socio": "npksinais2024"}
        logger.warning("No DASHBOARD_USER_N configured — using insecure defaults!")
    return users


def authenticate(username: str, password: str) -> Optional[str]:
    """Verify credentials. Returns JWT token or None."""
    users = _load_users()
    stored_password = users.get(username)
    if stored_password is None:
        return None
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(stored_password, password):
        return None
    return create_token(username)
