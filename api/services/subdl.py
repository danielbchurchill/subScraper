from __future__ import annotations
import io
import zipfile
from pathlib import Path
from typing import Optional

import httpx

from api.config import Settings
from api.models import SubtitleResult

_BASE = "https://api.subdl.com/api/v1/subtitles"
_DL_BASE = "https://dl.subdl.com"


async def search(
    settings: Settings,
    imdb_id: str,
    season: int,
    episode: int,
    language: str = "EN",
) -> list[SubtitleResult]:
    if not settings.subdl_api_key:
        return []

    params = {
        "api_key": settings.subdl_api_key,
        "imdb_id": imdb_id,
        "season": season,
        "episode": episode,
        "languages": language,
        "type": "tv",
        "unpack": 1,
        "subs_per_page": 30,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("status"):
        return []

    results = []
    for r in data.get("results", []):
        url = r.get("url", "")
        results.append(
            SubtitleResult(
                source="subdl",
                file_id=str(r.get("file_n_id", "")),
                name=r.get("name", ""),
                language=r.get("language", language).lower(),
                format=r.get("format", "srt"),
                hearing_impaired=bool(r.get("hi")),
                download_url=_DL_BASE + url if url else None,
            )
        )
    return results


async def download(settings: Settings, result: SubtitleResult, dest_dir: Path) -> Optional[Path]:
    if not result.download_url:
        return None

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(result.download_url)
        resp.raise_for_status()
        content = resp.content

    dest_dir.mkdir(parents=True, exist_ok=True)

    if result.download_url.endswith(".zip") or resp.headers.get("content-type", "").startswith("application/zip"):
        return _extract_srt_from_zip(content, dest_dir)

    out = dest_dir / f"{result.name}.srt"
    out.write_bytes(content)
    return out


def _extract_srt_from_zip(content: bytes, dest_dir: Path) -> Optional[Path]:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        srt_names = [n for n in zf.namelist() if n.lower().endswith(".srt")]
        if not srt_names:
            return None
        name = srt_names[0]
        out = dest_dir / Path(name).name
        out.write_bytes(zf.read(name))
        return out
