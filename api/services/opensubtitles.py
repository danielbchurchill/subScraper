from __future__ import annotations
from pathlib import Path
from typing import Optional

import httpx

from api.config import Settings
from api.models import SubtitleResult

_BASE = "https://api.opensubtitles.com/api/v1"


class OpenSubtitlesClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._jwt: Optional[str] = None
        self._base_url = _BASE

    def _headers(self) -> dict:
        h = {
            "Api-Key": self._settings.opensubtitles_api_key,
            "Content-Type": "application/json",
            "User-Agent": "SubScraper/1.0",
        }
        if self._jwt:
            h["Authorization"] = f"Bearer {self._jwt}"
        return h

    async def login(self) -> None:
        if not self._settings.opensubtitles_username or not self._settings.opensubtitles_password:
            return
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{_BASE}/login",
                json={
                    "username": self._settings.opensubtitles_username,
                    "password": self._settings.opensubtitles_password,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            self._jwt = data.get("token")
            base = data.get("base_url", "").strip("/")
            if base:
                self._base_url = f"https://{base}/api/v1"

    async def search(
        self,
        imdb_id: str,
        season: int,
        episode: int,
        language: str = "en",
    ) -> list[SubtitleResult]:
        if not self._settings.opensubtitles_api_key:
            return []

        numeric_id = imdb_id.lstrip("t")
        params = {
            "parent_imdb_id": numeric_id,
            "season_number": season,
            "episode_number": episode,
            "languages": language,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/subtitles",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            for f in attrs.get("files", []):
                results.append(
                    SubtitleResult(
                        source="opensubtitles",
                        file_id=str(f.get("file_id", "")),
                        name=f.get("file_name", ""),
                        language=attrs.get("language", language),
                        format="srt",
                        hearing_impaired=attrs.get("hearing_impaired", False),
                        file_id_numeric=int(f["file_id"]) if f.get("file_id") else None,
                    )
                )
        return results

    async def download(self, result: SubtitleResult, dest_dir: Path) -> Optional[Path]:
        if not result.file_id_numeric:
            return None

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/download",
                json={"file_id": result.file_id_numeric},
                headers=self._headers(),
            )
            resp.raise_for_status()
            meta = resp.json()

        link = meta.get("link")
        if not link:
            return None

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(link)
            resp.raise_for_status()
            content = resp.content

        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = meta.get("file_name") or f"{result.file_id}.srt"
        out = dest_dir / filename
        out.write_bytes(content)
        return out
