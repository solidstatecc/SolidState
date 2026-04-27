"""Solid State agent — webhook + run API.

Two endpoints do the work:

  POST /webhook/payment   Vercel calls this when a buyer pays.
  POST /run               Internal — triggers a skill run.

The agent is the runtime. The marketplace is the storefront.
"""
import os
import logging
from typing import Optional

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from .auth import verify_signature
from ..runner.loader import fetch_skill
from ..runner.sandbox import run_in_sandbox
from ..db.supabase import log_run, mark_run_status
from ..admin.telegram import notify_admin


log = logging.getLogger("solidstate.agent")
app = FastAPI(title="Solid State agent", version="0.1.0")


class PaymentWebhook(BaseModel):
    skill_id: str
    buyer_id: str
    payment_proof: str = Field(..., description="Stripe charge id or x402 receipt hash")
    input_payload: dict = {}
    callback_url: Optional[str] = None


class RunRequest(BaseModel):
    skill_id: str
    buyer_id: str
    input_payload: dict = {}


@app.get("/health")
def health():
    return {"ok": True, "service": "solidstate-agent"}


@app.post("/webhook/payment")
async def webhook_payment(request: Request, background: BackgroundTasks):
    body = await request.body()
    verify_signature(
        body,
        x_signature=request.headers.get("x-signature", ""),
        x_timestamp=request.headers.get("x-timestamp", ""),
    )
    payload = PaymentWebhook.model_validate_json(body)

    run_id = await log_run(
        skill_id=payload.skill_id,
        buyer_id=payload.buyer_id,
        payment_proof=payload.payment_proof,
        status="queued",
    )
    background.add_task(
        _execute,
        run_id=run_id,
        skill_id=payload.skill_id,
        buyer_id=payload.buyer_id,
        input_payload=payload.input_payload,
        callback_url=payload.callback_url,
    )
    return {"run_id": run_id, "status": "queued"}


@app.post("/run")
async def run_now(req: RunRequest):
    """Internal trigger — bypasses payment. Used for testing + admin."""
    if os.getenv("ALLOW_INTERNAL_RUN") != "1":
        raise HTTPException(403, "internal runs disabled")

    run_id = await log_run(
        skill_id=req.skill_id,
        buyer_id=req.buyer_id,
        payment_proof="internal",
        status="queued",
    )
    result = await _execute(
        run_id=run_id,
        skill_id=req.skill_id,
        buyer_id=req.buyer_id,
        input_payload=req.input_payload,
        callback_url=None,
    )
    return {"run_id": run_id, "result": result}


async def _execute(
    run_id: str,
    skill_id: str,
    buyer_id: str,
    input_payload: dict,
    callback_url: Optional[str],
) -> dict:
    """The actual run path. Fetch → sandbox → return → log."""
    log.info("run %s start skill=%s buyer=%s", run_id, skill_id, buyer_id)
    await mark_run_status(run_id, "running")

    try:
        skill_path = await fetch_skill(skill_id)
        result = await run_in_sandbox(skill_path, input_payload)
        await mark_run_status(run_id, "ok", result=result)
        if callback_url:
            await _post_callback(callback_url, run_id, result)
        return result
    except Exception as e:  # noqa: BLE001
        log.exception("run %s failed", run_id)
        await mark_run_status(run_id, "error", error=str(e))
        await notify_admin(f"Run {run_id} failed: {e}")
        raise


async def _post_callback(url: str, run_id: str, result: dict) -> None:
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json={"run_id": run_id, "result": result})
