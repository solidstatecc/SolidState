"""Thin Supabase client. REST only — no SDK dependency.

Tables expected:
  skills(id, slug, title, status, bundle_url, sha256, seller_id, ...)
  runs(id, skill_id, buyer_id, payment_proof, status, result, error, created_at)
  payouts(seller_id, amount_usd, status, ...)
"""
import os
import uuid
from typing import Optional

import httpx


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def log_run(
    skill_id: str,
    buyer_id: str,
    payment_proof: str,
    status: str,
) -> str:
    run_id = str(uuid.uuid4())
    payload = {
        "id": run_id,
        "skill_id": skill_id,
        "buyer_id": buyer_id,
        "payment_proof": payment_proof,
        "status": status,
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{SUPABASE_URL}/rest/v1/runs", headers=_headers(), json=payload)
        r.raise_for_status()
    return run_id


async def mark_run_status(
    run_id: str,
    status: str,
    result: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    payload: dict = {"status": status}
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.patch(
            f"{SUPABASE_URL}/rest/v1/runs?id=eq.{run_id}",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()


async def queue_depth() -> int:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{SUPABASE_URL}/rest/v1/runs?status=in.(queued,running)&select=id",
            headers={**_headers(), "Prefer": "count=exact"},
        )
        r.raise_for_status()
        return int(r.headers.get("content-range", "0/0").split("/")[-1] or 0)


async def recent_runs(limit: int = 5) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{SUPABASE_URL}/rest/v1/runs?select=id,skill_id,status&order=created_at.desc&limit={limit}",
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


async def set_skill_status(skill_id: str, status: str, reason: Optional[str] = None) -> None:
    payload: dict = {"status": status}
    if reason is not None:
        payload["rejection_reason"] = reason
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.patch(
            f"{SUPABASE_URL}/rest/v1/skills?id=eq.{skill_id}",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()


async def set_featured(skill_id: str) -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        # clear existing featured
        await c.patch(
            f"{SUPABASE_URL}/rest/v1/skills?featured=eq.true",
            headers=_headers(),
            json={"featured": False},
        )
        r = await c.patch(
            f"{SUPABASE_URL}/rest/v1/skills?id=eq.{skill_id}",
            headers=_headers(),
            json={"featured": True},
        )
        r.raise_for_status()


async def pending_payouts() -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{SUPABASE_URL}/rest/v1/payouts?status=eq.pending&select=seller_id,amount_usd",
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()
