from __future__ import annotations
import re
import logging
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

from api.models import SubtitleResult

BASE = "https://kitsunekko.net"
INDEX_DIR = "subtitles/japanese/"
_EXT_RE = re.compile(r'\.(srt|ass|ssa|vtt)$', re.IGNORECASE)
_HEADERS = {"User-Agent": "SubScraper/1.0"}

log = logging.getLogger(__name__)


def _detect_format(name: str) -> str:
    m = _EXT_RE.search(name)
    return m.group(1).lower() if m else "srt"


def _normalize(text: str) -> str:
    return re.sub(r'[^\w]', '', text.lower())


def _parse_dir_links(html: str) -> list[tuple[str, str]]:
    """Return [(display_name, decoded_dir_path)] from a dirlist page."""
    results = []
    for m in re.finditer(r'href="(/dirlist\.php\?dir=([^"]+))"[^>]*>([^<]+)</a>', html, re.IGNORECASE):
        raw_dir = urllib.parse.unquote(m.group(2))
        name = m.group(3).strip()
        # Only include entries that are direct children of the japanese/ index
        if raw_dir.startswith(INDEX_DIR) and raw_dir != INDEX_DIR and raw_dir.count('/') == 3:
            results.append((name, raw_dir))
    return results


def _parse_file_links(html: str) -> list[tuple[str, str]]:
    """Return [(filename, relative_url)] for subtitle files."""
    results = []
    for m in re.finditer(r'href="(/subtitles/[^"]+\.(srt|ass|ssa|vtt))"', html, re.IGNORECASE):
        url = m.group(1)
        name = Path(urllib.parse.unquote(url)).name
        results.append((name, url))
    return results


def _matches_episode(name: str, season: int, episode: int) -> bool:
    if re.search(rf'[Ss]0*{season}[Ee]0*{episode}(?!\d)', name):
        return True
    if re.search(rf'[Ee][Pp]?0*{episode}(?!\d)', name):
        return True
    if re.search(rf'第\s*0*{episode}\s*話', name):
        return True
    if re.search(rf'[-_\s]0*{episode}(?!\d)', name):
        return True
    return False


def _best_dir_match(dirs: list[tuple[str, str]], *titles: str) -> Optional[str]:
    """Return the dir_path for the best matching show, or None."""
    norm_titles = [_normalize(t) for t in titles if t]
    for name, dir_path in dirs:
        norm_name = _normalize(name)
        for nt in norm_titles:
            if nt and (nt in norm_name or norm_name in nt):
                return dir_path
    return None


async def search(series_title: str, season: int, episode: int, alt_title: str = "") -> list[SubtitleResult]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
        r = await client.get(f"{BASE}/dirlist.php", params={"dir": INDEX_DIR})
        if r.status_code != 200:
            log.warning("Kitsunekko index returned %d", r.status_code)
            return []
        index_html = r.text

    dirs = _parse_dir_links(index_html)
    if not dirs:
        return []

    best = _best_dir_match(dirs, series_title, alt_title)
    if not best:
        log.info("Kitsunekko: no directory match for %r", series_title)
        return []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
        r = await client.get(f"{BASE}/dirlist.php", params={"dir": best})
        if r.status_code != 200:
            return []
        show_html = r.text

    files = _parse_file_links(show_html)
    results = []
    for name, url in files:
        if not _matches_episode(name, season, episode):
            continue
        results.append(SubtitleResult(
            source="kitsunekko",
            file_id=name,
            name=name,
            language="ja",
            format=_detect_format(name),
            download_url=BASE + url,
        ))
    return results


async def download(result: SubtitleResult, dest_dir: Path) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=_HEADERS) as client:
        r = await client.get(result.download_url)
        r.raise_for_status()
    out = dest_dir / result.name
    out.write_bytes(r.content)
    return out
