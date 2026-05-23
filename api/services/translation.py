from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from api.config import Settings
from api.models import JobStatus, TranslationJob


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_job(jobs_dir: Path, job_id: str) -> Optional[TranslationJob]:
    p = jobs_dir / f"{job_id}.json"
    if not p.exists():
        return None
    return TranslationJob.model_validate_json(p.read_text())


def _save_job(jobs_dir: Path, job: TranslationJob) -> None:
    p = jobs_dir / f"{job.id}.json"
    p.write_text(job.model_dump_json(indent=2))


def create_job(
    jobs_dir: Path,
    series_imdb_id: str,
    season: int,
    episode: int,
    source_path: str,
    output_path: str,
    source_language: str,
) -> TranslationJob:
    job = TranslationJob(
        id=str(uuid.uuid4()),
        series_imdb_id=series_imdb_id,
        season=season,
        episode=episode,
        source_path=source_path,
        output_path=output_path,
        source_language=source_language,
        status=JobStatus.queued,
        created_at=_now(),
        updated_at=_now(),
    )
    _save_job(jobs_dir, job)
    return job


def list_jobs(jobs_dir: Path) -> list[TranslationJob]:
    jobs = []
    for p in sorted(jobs_dir.glob("*.json"), reverse=True):
        try:
            jobs.append(TranslationJob.model_validate_json(p.read_text()))
        except Exception:
            pass
    return jobs


def get_job(jobs_dir: Path, job_id: str) -> Optional[TranslationJob]:
    return _load_job(jobs_dir, job_id)


async def run_translation(
    settings: Settings,
    job: TranslationJob,
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> TranslationJob:
    jobs_dir = settings.jobs_dir
    source = Path(job.source_path)
    output = Path(job.output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    job.status = JobStatus.running
    job.updated_at = _now()
    _save_job(jobs_dir, job)

    def _translate_sync():
        from PySubtrans import init_options, init_subtitles, init_translator

        opts = init_options(
            provider="Custom Server",
            server_address=settings.ollama_host,
            endpoint="/v1/chat/completions",
            model=settings.ollama_model,
            target_language="English",
            max_retries=3,
            retry_on_error=True,
            stop_on_error=False,
        )

        subs = init_subtitles(filepath=str(source), options=opts)
        translator = init_translator(opts)

        total_batches = [0]
        done_batches = [0]

        def on_batch(batch):
            done_batches[0] += 1
            pct = int(done_batches[0] / max(total_batches[0], 1) * 100)
            if on_progress:
                on_progress(pct, f"Translated batch {done_batches[0]}/{total_batches[0]}")

        def on_scene(scene):
            pass

        translator.events.batch_translated += on_batch
        translator.events.scene_translated += on_scene

        # Count total batches for progress
        if hasattr(subs, "scenes"):
            for scene in (subs.scenes or []):
                total_batches[0] += len(getattr(scene, "batches", []) or [])
        if total_batches[0] == 0:
            total_batches[0] = 1

        translator.TranslateSubtitles(subs)
        subs.SaveSubtitles(str(output))

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _translate_sync)
        job.status = JobStatus.completed
        job.progress = 100
    except Exception as e:
        job.status = JobStatus.failed
        job.error = str(e)
    finally:
        job.updated_at = _now()
        _save_job(jobs_dir, job)

    return job
