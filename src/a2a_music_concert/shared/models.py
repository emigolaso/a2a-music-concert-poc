from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SpotifyTimeRange = Literal["short_term", "medium_term", "long_term"]


class SpotifyArtist(BaseModel):
    artist_id: str
    artist_name: str
    genres: list[str] = Field(default_factory=list)
    popularity: int | None = None
    followers_total: int | None = None
    spotify_url: str | None = None


class SpotifyTrack(BaseModel):
    track_id: str
    track_name: str
    artist_names: list[str]
    album_name: str | None = None
    played_at: str | None = None
    spotify_url: str | None = None


class MusicAgentResponse(BaseModel):
    answer_type: Literal["artist_answer", "general_response"] = "artist_answer"
    message: str | None = None
    artist_name: str | None = None
    artist_id: str | None = None
    source_summary: str | None = None
    time_range: SpotifyTimeRange | Literal["recent"] | None = None


class ConcertEvent(BaseModel):
    event_name: str
    venue: str
    city: str
    date: str
    url: str | None = None


class ConcertAgentRequest(BaseModel):
    artist_name: str
    location: str | None = None
    date_range: str | None = None


class ConcertAgentResponse(BaseModel):
    status: Literal["found", "none_found"]
    artist_name: str
    events: list[ConcertEvent] = Field(default_factory=list)
