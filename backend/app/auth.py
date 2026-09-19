import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from fastapi import Header, HTTPException

ADMIN_PASSWORD = os.environ.get("WATCHDOG_ADMIN_PASSWORD", "").strip()
SESSION_SECRET = os.environ.get("WATCHDOG_SESSION_SECRET", "").strip()
SESSION_TTL_SECONDS = int(os.environ.get("WATCHDOG_SESSION_TTL_SECONDS", "28800"))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def auth_configured() -> bool:
    return bool(ADMIN_PASSWORD and SESSION_SECRET)


def create_session_token() -> tuple[str, int]:
    if not auth_configured():
        raise HTTPException(status_code=503, detail="WatchDog login is not configured")
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = {
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(16),
        "scope": "watchdog-admin",
    }
    encoded = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64url_encode(signature)}", expires_at


def validate_password(password: str) -> bool:
    if not auth_configured():
        return False
    return hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))


def verify_session_token(token: str) -> dict:
    if not auth_configured():
        raise HTTPException(status_code=503, detail="WatchDog login is not configured")
    try:
        encoded, signature_text = token.split(".", 1)
        expected = hmac.new(SESSION_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        supplied = _b64url_decode(signature_text)
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("signature")
        payload = json.loads(_b64url_decode(encoded))
        if payload.get("scope") != "watchdog-admin" or int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Session is invalid or expired") from exc


def require_session(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    return verify_session_token(authorization[7:].strip())
