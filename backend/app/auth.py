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
MOBILE_SESSION_TTL_SECONDS = int(os.environ.get("WATCHDOG_MOBILE_SESSION_TTL_SECONDS", "7776000"))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def auth_configured() -> bool:
    return bool(ADMIN_PASSWORD and SESSION_SECRET)


def create_scoped_token(scope: str, ttl_seconds: int, extra: Optional[dict] = None) -> tuple[str, int]:
    if not auth_configured():
        raise HTTPException(status_code=503, detail="WatchDog login is not configured")
    expires_at = int(time.time()) + max(60, int(ttl_seconds))
    payload = {
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(16),
        "scope": scope,
    }
    if extra:
        payload.update(extra)
    encoded = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64url_encode(signature)}", expires_at


def create_session_token() -> tuple[str, int]:
    return create_scoped_token("watchdog-admin", SESSION_TTL_SECONDS)


def create_mobile_session_token(device_name: str) -> tuple[str, int]:
    return create_scoped_token(
        "watchdog-mobile",
        MOBILE_SESSION_TTL_SECONDS,
        {"device_name": (device_name or "Android companion")[:80]},
    )


def validate_password(password: str) -> bool:
    if not auth_configured():
        return False
    return hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))


def verify_scoped_token(token: str, allowed_scopes: set[str]) -> dict:
    if not auth_configured():
        raise HTTPException(status_code=503, detail="WatchDog login is not configured")
    try:
        encoded, signature_text = token.split(".", 1)
        expected = hmac.new(SESSION_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        supplied = _b64url_decode(signature_text)
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("signature")
        payload = json.loads(_b64url_decode(encoded))
        if payload.get("scope") not in allowed_scopes or int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("expired or wrong scope")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Session is invalid or expired") from exc


def verify_session_token(token: str) -> dict:
    return verify_scoped_token(token, {"watchdog-admin"})


def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    return authorization[7:].strip()


def require_session(authorization: Optional[str] = Header(default=None)) -> dict:
    return verify_session_token(_bearer_token(authorization))


def require_mobile_session(authorization: Optional[str] = Header(default=None)) -> dict:
    return verify_scoped_token(_bearer_token(authorization), {"watchdog-admin", "watchdog-mobile"})
