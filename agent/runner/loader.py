"""Fetch a skill bundle from Supabase Storage.

A "skill" is a tarball: SKILL.md + scripts + references.
We pull it, verify the manifest, stage to a tmp dir, return the path.
"""
import asyncio
import hashlib
import json
import os
import tarfile
import tempfile
from pathlib import Path

import httpx


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SKILLS_BUCKET = os.environ.get("SKILLS_BUCKET", "skills")
STAGE_DIR = Path(os.environ.get("STAGE_DIR", "/tmp/solidstate-skills"))
STAGE_DIR.mkdir(parents=True, exist_ok=True)


class SkillError(Exception):
    pass


async def fetch_skill(skill_id: str) -> Path:
    """Download skill bundle, verify, extract, return staging path."""
    meta = await _fetch_meta(skill_id)
    bundle_url = meta["bundle_url"]
    expected_sha = meta.get("sha256")

    bundle_bytes = await _download(bundle_url)
    actual_sha = hashlib.sha256(bundle_bytes).hexdigest()
    if expected_sha and actual_sha != expected_sha:
        raise SkillError(f"sha mismatch for {skill_id}")

    target = STAGE_DIR / f"{skill_id}-{actual_sha[:8]}"
    if target.exists():
        return target

    target.mkdir(parents=True)
    with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tmp:
        tmp.write(bundle_bytes)
        tmp.flush()
        with tarfile.open(tmp.name) as tar:
            _safe_extract(tar, target)

    if not (target / "SKILL.md").exists():
        raise SkillError(f"{skill_id}: missing SKILL.md")

    return target


async def _fetch_meta(skill_id: str) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/skills?id=eq.{skill_id}&select=*"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, headers=headers)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            raise SkillError(f"unknown skill {skill_id}")
        return rows[0]


async def _download(bundle_url: str) -> bytes:
    headers = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(bundle_url, headers=headers)
        r.raise_for_status()
        return r.content


def _safe_extract(tar: tarfile.TarFile, target: Path) -> None:
    """Tar extraction with path traversal guard."""
    target = target.resolve()
    for member in tar.getmembers():
        member_path = (target / member.name).resolve()
        if not str(member_path).startswith(str(target)):
            raise SkillError(f"unsafe path in tarball: {member.name}")
    tar.extractall(target)
