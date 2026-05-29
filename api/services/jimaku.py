from __future__ import annotations
import asyncio
import re
import logging
import unicodedata
from pathlib import Path
from typing import Optional

import httpx

from api.models import SubtitleResult

BASE = "https://jimaku.cc/api"
_EXT_RE = re.compile(r'\.(srt|ass|ssa|vtt)$', re.IGNORECASE)

log = logging.getLogger(__name__)


_LONG_VOWEL_MARKS = {'̂', '̄'}  # combining circumflex U+0302, combining macron U+0304


def _expand_long_vowels(s: str) -> str:
    """Convert circumflex/macron long-vowel markers to doubled vowels: ryûgi → ryuugi."""
    out = []
    for ch in unicodedata.normalize('NFD', s):
        if ch in _LONG_VOWEL_MARKS:
            if out and out[-1].lower() in 'aeiou':
                out.append(out[-1])
        else:
            out.append(ch)
    return ''.join(out)


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


async def _search_by_title(headers: dict, title: str, season: int, episode: int, language: Optional[str]) -> list[SubtitleResult]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
        anime_r, live_r = await asyncio.gather(
            client.get(f"{BASE}/entries/search", params={"query": title, "anime": "true"}),
            client.get(f"{BASE}/entries/search", params={"query": title, "anime": "false"}),
        )
    if anime_r.status_code != 200 and live_r.status_code != 200:
        log.warning("Jimaku search returned %d/%d for %r", anime_r.status_code, live_r.status_code, title)
        return []
    seen: set[int] = set()
    entries = []
    for r in (anime_r, live_r):
        if r.status_code == 200:
            for e in r.json():
                if e.get("id") not in seen:
                    seen.add(e["id"])
                    entries.append(e)

    if not entries:
        return []

    results: list[SubtitleResult] = []
    for entry in entries[:5]:
        entry_id = entry.get("id")
        if not entry_id:
            continue
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            r = await client.get(f"{BASE}/entries/{entry_id}/files", params={"episode": episode})
            if r.status_code != 200:
                continue
            files = r.json()

        for f in files:
            name = f.get("name", "")
            url = f.get("url", "")
            if not url or not _EXT_RE.search(name):
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


async def search(api_key: str, series_title: str, season: int, episode: int, language: Optional[str] = None, alt_title: Optional[str] = None) -> list[SubtitleResult]:
    if not api_key:
        return []
    headers = {"Authorization": api_key}
    results = await _search_by_title(headers, series_title, season, episode, language)
    if not results and alt_title and alt_title != series_title:
        log.info("Jimaku: retrying with alt title %r", alt_title)
        results = await _search_by_title(headers, alt_title, season, episode, language)
    if not results and alt_title:
        expanded = _expand_long_vowels(alt_title)
        if expanded != alt_title:
            log.info("Jimaku: retrying with expanded title %r", expanded)
            results = await _search_by_title(headers, expanded, season, episode, language)
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
