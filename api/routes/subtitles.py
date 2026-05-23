from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from api.config import Settings, get_settings
from api.models import EpisodeStatus, SubtitleStatus, TranslationJob
from api.services import subdl as subdl_svc
from api.services.opensubtitles import OpenSubtitlesClient
from api.services import translation as trans_svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/subtitles", tags=["subtitles"])

_LANG_PRIORITY = ["en", "EN"]
_FALLBACK_LANGS = ["ja", "JA", "zh", "ZH", "ko", "KO", "fr", "FR", "es", "ES"]


def _ep_dir(settings: Settings, series_imdb_id: str, season: int, episode: int) -> Path:
    return settings.subtitles_dir / series_imdb_id / f"S{season:02d}E{episode:02d}"


def _episode_status(settings: Settings, series_imdb_id: str, season: int, episode: int) -> EpisodeStatus:
    ep_dir = _ep_dir(settings, series_imdb_id, season, episode)
    srt_path = None
    status = SubtitleStatus.missing

    # Check for English or translated SRT
    for fname in ["translated.srt", "english.srt"]:
        p = ep_dir / fname
        if p.exists():
            srt_path = str(p)
            status = SubtitleStatus.english if fname == "english.srt" else SubtitleStatus.translated
            break

    # Check for in-progress job
    jobs = trans_svc.list_jobs(settings.jobs_dir)
    for job in jobs:
        if job.series_imdb_id == series_imdb_id and job.season == season and job.episode == episode:
            if job.status.value == "running" or job.status.value == "queued":
                status = SubtitleStatus.translating
            break

    return EpisodeStatus(
        series_imdb_id=series_imdb_id,
        season=season,
        episode=episode,
        status=status,
        srt_path=srt_path,
    )


@router.get("/status/{series_imdb_id}/{season}/{episode}", response_model=EpisodeStatus)
async def episode_status(
    series_imdb_id: str,
    season: int,
    episode: int,
    settings: Settings = Depends(get_settings),
):
    return _episode_status(settings, series_imdb_id, season, episode)


@router.post("/fetch/{series_imdb_id}/{season}/{episode}", response_model=EpisodeStatus)
async def fetch_subtitles(
    series_imdb_id: str,
    season: int,
    episode: int,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    ep_dir = _ep_dir(settings, series_imdb_id, season, episode)

    # Try English first
    en_result = await _search_language(settings, series_imdb_id, season, episode, "en", "EN")
    if en_result:
        srt = await _download_result(settings, en_result, ep_dir, "english.srt")
        if srt:
            return _episode_status(settings, series_imdb_id, season, episode)

    # Try non-English fallbacks, queue for translation
    for lang_code, lang_code2 in [("ja", "JA"), ("zh", "ZH"), ("ko", "KO"), ("fr", "FR"), ("es", "ES")]:
        result = await _search_language(settings, series_imdb_id, season, episode, lang_code, lang_code2)
        if result:
            source_srt = await _download_result(settings, result, ep_dir, f"source_{lang_code}.srt")
            if source_srt:
                output_path = str(ep_dir / "translated.srt")
                job = trans_svc.create_job(
                    settings.jobs_dir,
                    series_imdb_id=series_imdb_id,
                    season=season,
                    episode=episode,
                    source_path=str(source_srt),
                    output_path=output_path,
                    source_language=lang_code,
                )
                background_tasks.add_task(_run_translation_bg, settings, job)
                return _episode_status(settings, series_imdb_id, season, episode)

    return _episode_status(settings, series_imdb_id, season, episode)


async def _search_language(
    settings: Settings,
    series_imdb_id: str,
    season: int,
    episode: int,
    lang: str,
    lang_upper: str,
) -> Optional[object]:
    log.info("Searching %s S%02dE%02d lang=%s subdl_key=%s os_key=%s",
             series_imdb_id, season, episode, lang,
             bool(settings.subdl_api_key), bool(settings.opensubtitles_api_key))
    tasks = [
        subdl_svc.search(settings, series_imdb_id, season, episode, language=lang_upper),
        _opensubtitles_search(settings, series_imdb_id, season, episode, lang),
    ]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    for source, results in zip(["subdl", "opensubtitles"], results_list):
        if isinstance(results, Exception):
            log.warning("%s search error: %s", source, results)
            continue
        log.info("%s returned %d results", source, len(results))
        if results:
            return results[0]
    return None


async def _opensubtitles_search(settings, series_imdb_id, season, episode, lang):
    client = OpenSubtitlesClient(settings)
    if settings.opensubtitles_username:
        try:
            await client.login()
        except Exception:
            pass
    return await client.search(series_imdb_id, season, episode, language=lang)


async def _download_result(settings, result, ep_dir: Path, filename: str) -> Optional[Path]:
    dest = ep_dir / filename
    ep_dir.mkdir(parents=True, exist_ok=True)
    try:
        if result.source == "subdl":
            downloaded = await subdl_svc.download(settings, result, ep_dir)
        else:
            client = OpenSubtitlesClient(settings)
            if settings.opensubtitles_username:
                await client.login()
            downloaded = await client.download(result, ep_dir)

        if downloaded and downloaded.exists():
            downloaded.rename(dest)
            return dest
        log.warning("Download returned no file for %s", result)
    except Exception as e:
        log.warning("Download failed for %s: %s", result.source, e)
    return None


async def _run_translation_bg(settings: Settings, job: TranslationJob):
    await trans_svc.run_translation(settings, job)


@router.get("/download/{series_imdb_id}/{season}/{episode}")
async def download_srt(
    series_imdb_id: str,
    season: int,
    episode: int,
    settings: Settings = Depends(get_settings),
):
    status = _episode_status(settings, series_imdb_id, season, episode)
    if not status.srt_path:
        raise HTTPException(status_code=404, detail="No subtitle available")
    return FileResponse(
        status.srt_path,
        media_type="text/plain",
        filename=f"{series_imdb_id}_S{season:02d}E{episode:02d}.srt",
    )
