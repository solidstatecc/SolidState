"""HMAC verification for inbound webhooks from Vercel."""
import hmac
import hashlib
import os
import time
from fastapi import Header, HTTPException


WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
MAX_SKEW_SECONDS = 300


def verify_signature(
    body: bytes,
    x_signature: str = Header(...),
    x_timestamp: str = Header(...),
) -> None:
    """Raise 401 if HMAC or timestamp invalid.

    Vercel-side signs `f"{timestamp}.{body}"` with WEBHOOK_SECRET.
    """
    try:
        ts = int(x_timestamp)
    except ValueError:
        raise HTTPException(401, "bad timestamp")

    if abs(time.time() - ts) > MAX_SKEW_SECONDS:
        raise HTTPException(401, "stale request")

    payload = f"{x_timestamp}.".encode() + body
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, x_signature):
        raise HTTPException(401, "bad signature")
