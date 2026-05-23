from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Episode(BaseModel):
    imdb_id: str
    series_imdb_id: str
    season: int
    episode: int
    title: str
    air_date: Optional[str] = None


class SubtitleResult(BaseModel):
    source: str  # "subdl" | "opensubtitles"
    file_id: str
    name: str
    language: str
    format: str
    hearing_impaired: bool = False
    download_url: Optional[str] = None  # pre-resolved for subdl
    file_id_numeric: Optional[int] = None  # for opensubtitles POST /download


class SubtitleStatus(str, Enum):
    missing = "missing"
    english = "english"
    translated = "translated"
    translating = "translating"
    source_only = "source_only"  # non-english downloaded, awaiting translation


class EpisodeStatus(BaseModel):
    series_imdb_id: str
    season: int
    episode: int
    status: SubtitleStatus
    srt_path: Optional[str] = None
    job_id: Optional[str] = None


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TranslationJob(BaseModel):
    id: str
    series_imdb_id: str
    season: int
    episode: int
    source_path: str
    output_path: str
    source_language: str
    status: JobStatus = JobStatus.queued
    progress: int = 0  # 0-100
    error: Optional[str] = None
    created_at: str
    updated_at: str
