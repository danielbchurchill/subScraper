from __future__ import annotations
from typing import Optional

import httpx

from api.models import Episode

TVMAZE = "https://api.tvmaze.com"


async def _lookup_show(imdb_id: str) -> dict:
    norm = imdb_id if imdb_id.startswith("tt") else f"tt{imdb_id}"
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        r = await client.get(f"{TVMAZE}/lookup/shows", params={"imdb": norm})
        r.raise_for_status()
        return r.json()


async def get_series_title(imdb_id: str) -> str:
    show = await _lookup_show(imdb_id)
    return show.get("name", imdb_id)


async def get_show_names(imdb_id: str) -> tuple[str, str]:
    """Return (primary_name, original_language_name). Falls back to primary if no AKA found."""
    show = await _lookup_show(imdb_id)
    primary = show.get("name", imdb_id)
    show_id = show.get("id")
    if not show_id:
        return primary, ""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(f"{TVMAZE}/shows/{show_id}/akas")
            if r.status_code == 200:
                for aka in r.json():
                    country = aka.get("country") or {}
                    if country.get("code") == "JP":
                        return primary, aka.get("name", "")
    except Exception:
        pass
    return primary, ""


async def get_episodes(imdb_id: str, season: Optional[int] = None) -> list[Episode]:
    norm = imdb_id if imdb_id.startswith("tt") else f"tt{imdb_id}"
    show = await _lookup_show(imdb_id)
    show_id = show["id"]

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{TVMAZE}/shows/{show_id}/episodes")
        r.raise_for_status()
        raw = r.json()

    episodes: list[Episode] = []
    for ep in raw:
        s = ep.get("season")
        e = ep.get("number")
        if s is None or e is None:
            continue
        if season is not None and s != season:
            continue
        episodes.append(
            Episode(
                imdb_id="",
                series_imdb_id=norm,
                season=s,
                episode=e,
                title=ep.get("name") or f"Episode {e}",
                air_date=ep.get("airdate"),
            )
        )
    return episodes
