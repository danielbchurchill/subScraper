from __future__ import annotations
import re
import logging
from pathlib import Path
from typing import Optional

import httpx

from api.models import SubtitleResult

BASE = "https://jimaku.cc/api"
_EXT_RE = re.compile(r'\.(srt|ass|ssa|vtt)$', re.IGNORECASE)

log = logging.getLogger(__name__)


def _detect_format(name: str) -> str:
    m = _EXT_RE.search(name)
    return m.group(1).lower() if m else "srt"


def _matches_episode(name: str, season: int, episode: int) -> bool:
    # S01E01 / S1E1
    if re.search(rf'[Ss]0*{season}[Ee]0*{episode}(?!\d)', name):
        return True
    # EP01 / E01
    if re.search(rf'[Ee][Pp]?0*{episode}(?!\d)', name):
        return True
    # 第01話 / 第1話
    if re.search(rf'第\s*0*{episode}\s*話', name):
        return True
    # -01. / _01. / ' 01.'
    if re.search(rf'[-_\s]0*{episode}(?!\d)', name):
        return True
    return False


def _detect_language(name: str) -> str:
    n = name.lower()
    if re.search(r'\ben(g(lish)?)?\b|\.en\.', n):
        return "en"
    if re.search(r'\bzh\b|chin|chs|cht|traditional|simplified', n):
        return "zh"
    if re.search(r'\bko(r(ean)?)?\b|\.ko\.', n):
        return "ko"
    return "ja"  # Jimaku is primarily a Japanese drama site


async def search(api_key: str, series_title: str, season: int, episode: int, language: Optional[str] = None) -> list[SubtitleResult]:
    if not api_key:
        return []
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
        r = await client.get(f"{BASE}/entries/search", params={"q": series_title})
        if r.status_code != 200:
            log.warning("Jimaku search returned %d for %r", r.status_code, series_title)
            return []
        entries = r.json()

    if not entries:
        return []

    results: list[SubtitleResult] = []
    # Try top 5 matching entries to cover multi-season shows
    for entry in entries[:5]:
        entry_id = entry.get("id")
        if not entry_id:
            continue
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            r = await client.get(f"{BASE}/entries/{entry_id}/files")
            if r.status_code != 200:
                continue
            files = r.json()

        for f in files:
            name = f.get("name", "")
            url = f.get("url", "")
            if not url or not _EXT_RE.search(name):
                continue
            if not _matches_episode(name, season, episode):
                continue
            lang = _detect_language(name)
            if language and lang != language:
                continue
            results.append(SubtitleResult(
                source="jimaku",
                file_id=str(f.get("id", name)),
                name=name,
                language=lang,
                format=_detect_format(name),
                download_url=url,
            ))

    return results


async def download(api_key: str, result: SubtitleResult, dest_dir: Path) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        r = await client.get(result.download_url)
        r.raise_for_status()
    out = dest_dir / result.name
    out.write_bytes(r.content)
    return out
