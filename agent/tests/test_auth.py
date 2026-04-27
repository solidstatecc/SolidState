"""Smoke test for HMAC verification.

Run: pytest agent/tests/
"""
import hashlib
import hmac
import os
import time

os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("SUPABASE_URL", "http://x")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "x")

import pytest
from fastapi import HTTPException

from agent.api.auth import verify_signature


def _sign(secret: str, ts: str, body: bytes) -> str:
    return hmac.new(
        secret.encode(),
        f"{ts}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()


def test_valid_signature_passes():
    body = b'{"hello":"world"}'
    ts = str(int(time.time()))
    sig = _sign("test-secret", ts, body)
    verify_signature(body, x_signature=sig, x_timestamp=ts)  # no raise


def test_bad_signature_rejected():
    body = b'{"hello":"world"}'
    ts = str(int(time.time()))
    with pytest.raises(HTTPException):
        verify_signature(body, x_signature="0" * 64, x_timestamp=ts)


def test_stale_timestamp_rejected():
    body = b'{"hello":"world"}'
    ts = str(int(time.time()) - 10000)
    sig = _sign("test-secret", ts, body)
    with pytest.raises(HTTPException):
        verify_signature(body, x_signature=sig, x_timestamp=ts)
