from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.config import Settings, get_settings
from api.models import Episode
from api.services import imdb as imdb_svc

router = APIRouter(prefix="/shows", tags=["shows"])


@router.get("/{imdb_id}/episodes", response_model=list[Episode])
async def list_episodes(
    imdb_id: str,
    season: Optional[int] = None,
    settings: Settings = Depends(get_settings),
):
    try:
        episodes = await imdb_svc.get_episodes(imdb_id, season=season)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IMDB lookup failed: {e}")
    return episodes


@router.get("/{imdb_id}/title")
async def get_title(imdb_id: str):
    try:
        title = await imdb_svc.get_series_title(imdb_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IMDB lookup failed: {e}")
    return {"title": title, "imdb_id": imdb_id}
