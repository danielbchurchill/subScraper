from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.config import Settings, get_settings
from api.services.env_manager import load_env_dict, save_env_dict

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    subdl_api_key: Optional[str] = None
    opensubtitles_api_key: Optional[str] = None
    opensubtitles_username: Optional[str] = None
    opensubtitles_password: Optional[str] = None
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None


@router.get("")
async def get_settings_view(settings: Settings = Depends(get_settings)):
    env = load_env_dict()
    return {
        "ollama_host": settings.ollama_host,
        "ollama_model": settings.ollama_model,
        "subdl_api_key": _mask(env.get("SUBDL_API_KEY", "")),
        "subdl_configured": bool(settings.subdl_api_key),
        "opensubtitles_api_key": _mask(env.get("OPENSUBTITLES_API_KEY", "")),
        "opensubtitles_username": env.get("OPENSUBTITLES_USERNAME", ""),
        "opensubtitles_configured": bool(settings.opensubtitles_api_key),
    }


@router.post("")
async def save_settings(payload: SettingsPayload):
    updates: dict[str, str] = {}

    if payload.subdl_api_key is not None:
        updates["SUBDL_API_KEY"] = payload.subdl_api_key
    if payload.opensubtitles_api_key is not None:
        updates["OPENSUBTITLES_API_KEY"] = payload.opensubtitles_api_key
    if payload.opensubtitles_username is not None:
        updates["OPENSUBTITLES_USERNAME"] = payload.opensubtitles_username
    if payload.opensubtitles_password is not None:
        updates["OPENSUBTITLES_PASSWORD"] = payload.opensubtitles_password
    if payload.ollama_host is not None:
        updates["OLLAMA_HOST"] = payload.ollama_host
    if payload.ollama_model is not None:
        updates["OLLAMA_MODEL"] = payload.ollama_model

    if updates:
        save_env_dict(updates)
        # Bust the settings cache so next request picks up new values
        get_settings.cache_clear()

    return {"ok": True, "updated": list(updates.keys())}


def _mask(value: str) -> str:
    if not value or len(value) < 8:
        return ""
    return value[:4] + "•" * (len(value) - 8) + value[-4:]
