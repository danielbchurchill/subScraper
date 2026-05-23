from __future__ import annotations
import asyncio
from functools import lru_cache
from typing import Optional

from api.models import Episode


def _strip_tt(imdb_id: str) -> str:
    return imdb_id.lstrip("t")


@lru_cache(maxsize=32)
def _fetch_episodes_sync(numeric_id: str) -> dict:
    """Returns {season_num: {ep_num: {title, air_date, imdb_id}}}."""
    from imdb import Cinemagoer

    ia = Cinemagoer()
    series = ia.get_movie(numeric_id)
    ia.update(series, "episodes")
    seasons: dict = {}
    for season_num, eps in (series.get("episodes") or {}).items():
        seasons[int(season_num)] = {}
        for ep_num, ep in eps.items():
            seasons[int(season_num)][int(ep_num)] = {
                "title": ep.get("title", f"Episode {ep_num}"),
                "air_date": ep.get("original air date", None),
                "imdb_id": f"tt{ep.movieID}" if ep.movieID else "",
            }
    return seasons


async def get_episodes(imdb_id: str, season: Optional[int] = None) -> list[Episode]:
    """Fetch episode list for a series. Optionally filter to one season."""
    numeric_id = _strip_tt(imdb_id)
    loop = asyncio.get_event_loop()
    seasons = await loop.run_in_executor(None, _fetch_episodes_sync, numeric_id)

    episodes: list[Episode] = []
    for s_num, eps in seasons.items():
        if season is not None and s_num != season:
            continue
        for ep_num, meta in sorted(eps.items()):
            episodes.append(
                Episode(
                    imdb_id=meta["imdb_id"],
                    series_imdb_id=imdb_id if imdb_id.startswith("tt") else f"tt{imdb_id}",
                    season=s_num,
                    episode=ep_num,
                    title=meta["title"],
                    air_date=meta.get("air_date"),
                )
            )
    return episodes


async def get_series_title(imdb_id: str) -> str:
    numeric_id = _strip_tt(imdb_id)

    def _fetch():
        from imdb import Cinemagoer
        ia = Cinemagoer()
        m = ia.get_movie(numeric_id)
        return m.get("title", imdb_id)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)
