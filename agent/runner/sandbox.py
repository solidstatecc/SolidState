"""Run a skill inside a sandboxed container.

Default: NemoClaw. Swap via SANDBOX_RUNTIME env var.
The skill folder is mounted read-only. Output is captured from stdout.
"""
import asyncio
import json
import os
import shlex
import uuid
from pathlib import Path


SANDBOX_RUNTIME = os.environ.get("SANDBOX_RUNTIME", "nemoclaw")
NEMOCLAW_IMAGE = os.environ.get("NEMOCLAW_IMAGE", "nvidia/nemoclaw:latest")
RUN_TIMEOUT_SECS = int(os.environ.get("RUN_TIMEOUT_SECS", "120"))
MAX_OUTPUT_BYTES = int(os.environ.get("MAX_OUTPUT_BYTES", "1048576"))  # 1 MiB


class SandboxError(Exception):
    pass


async def run_in_sandbox(skill_path: Path, input_payload: dict) -> dict:
    """Spawn sandbox, run skill, return parsed JSON result."""
    if SANDBOX_RUNTIME == "nemoclaw":
        return await _run_nemoclaw(skill_path, input_payload)
    if SANDBOX_RUNTIME == "docker":
        return await _run_docker(skill_path, input_payload)
    raise SandboxError(f"unknown runtime: {SANDBOX_RUNTIME}")


async def _run_nemoclaw(skill_path: Path, input_payload: dict) -> dict:
    """Invoke the NemoClaw runtime to execute the skill.

    Contract: NemoClaw is started with the skill mounted at /skill.
    The skill's `entry.py` reads JSON input from stdin, writes JSON to stdout.
    """
    container_name = f"sscall-{uuid.uuid4().hex[:8]}"
    cmd = [
        "nemoclaw", "run",
        "--name", container_name,
        "--image", NEMOCLAW_IMAGE,
        "--mount", f"{skill_path}:/skill:ro",
        "--no-network",
        "--memory", "512m",
        "--cpus", "1",
        "--workdir", "/skill",
        "--", "python", "entry.py",
    ]
    return await _spawn(cmd, input_payload)


async def _run_docker(skill_path: Path, input_payload: dict) -> dict:
    """Fallback runtime: plain docker. Useful for local dev."""
    container_name = f"sscall-{uuid.uuid4().hex[:8]}"
    cmd = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--network", "none",
        "--memory", "512m",
        "--cpus", "1",
        "--read-only",
        "-v", f"{skill_path}:/skill:ro",
        "-w", "/skill",
        "-i",
        "python:3.12-slim",
        "python", "entry.py",
    ]
    return await _spawn(cmd, input_payload)


async def _spawn(cmd: list[str], input_payload: dict) -> dict:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    payload = json.dumps(input_payload).encode()
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=payload),
            timeout=RUN_TIMEOUT_SECS,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise SandboxError(f"timeout after {RUN_TIMEOUT_SECS}s")

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace")[:1000]
        raise SandboxError(f"exit {proc.returncode}: {err}")

    if len(stdout) > MAX_OUTPUT_BYTES:
        raise SandboxError(f"output exceeded {MAX_OUTPUT_BYTES} bytes")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        preview = stdout[:200].decode("utf-8", errors="replace")
        raise SandboxError(f"non-json output: {preview!r} ({e})")
