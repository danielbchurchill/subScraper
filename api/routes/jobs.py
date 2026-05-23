from __future__ import annotations
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.config import Settings, get_settings
from api.models import TranslationJob
from api.services import translation as trans_svc

router = APIRouter(prefix="/jobs", tags=["jobs"])

# In-memory event bus: job_id -> list of asyncio.Queue
_subscribers: dict[str, list[asyncio.Queue]] = {}


def publish_event(job_id: str, event: dict) -> None:
    for q in _subscribers.get(job_id, []):
        q.put_nowait(event)
    # Also push to wildcard listeners
    for q in _subscribers.get("*", []):
        q.put_nowait({"job_id": job_id, **event})


@router.get("", response_model=list[TranslationJob])
async def list_jobs(settings: Settings = Depends(get_settings)):
    return trans_svc.list_jobs(settings.jobs_dir)


@router.get("/{job_id}", response_model=TranslationJob)
async def get_job(job_id: str, settings: Settings = Depends(get_settings)):
    job = trans_svc.get_job(settings.jobs_dir, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/stream/all")
async def stream_all_jobs(settings: Settings = Depends(get_settings)):
    """SSE stream — sends all job events to the client."""

    async def generator() -> AsyncGenerator[str, None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        _subscribers.setdefault("*", []).append(q)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            subs = _subscribers.get("*", [])
            if q in subs:
                subs.remove(q)

    return StreamingResponse(generator(), media_type="text/event-stream")
