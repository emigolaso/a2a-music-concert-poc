from __future__ import annotations

import base64
from collections import Counter
from typing import Any

import httpx

from a2a_music_concert.shared.config import Settings
from a2a_music_concert.shared.models import SpotifyArtist, SpotifyTimeRange, SpotifyTrack


class SpotifyClient:
    token_url = "https://accounts.spotify.com/api/token"
    api_base = "https://api.spotify.com/v1"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def _access_token(self) -> str:
        self._require_credentials()
        auth = base64.b64encode(
            f"{self.settings.spotify_client_id}:{self.settings.spotify_client_secret}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.settings.spotify_refresh_token,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.token_url, data=data, headers=headers)
            response.raise_for_status()
            payload = response.json()
        return payload["access_token"]

    def _require_credentials(self) -> None:
        missing = [
            name
            for name, value in (
                ("SPOTIFY_CLIENT_ID", self.settings.spotify_client_id),
                ("SPOTIFY_CLIENT_SECRET", self.settings.spotify_client_secret),
                ("SPOTIFY_REFRESH_TOKEN", self.settings.spotify_refresh_token),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing Spotify configuration: {', '.join(missing)}")

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self._access_token()
        async with httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def get_top_artists(
        self, time_range: SpotifyTimeRange = "short_term", limit: int = 5
    ) -> list[SpotifyArtist]:
        payload = await self._get(
            "/me/top/artists",
            params={"time_range": time_range, "limit": min(limit, 50)},
        )
        return [self._normalize_artist(item) for item in payload.get("items", [])]

    async def get_top_tracks(
        self, time_range: SpotifyTimeRange = "short_term", limit: int = 10
    ) -> list[SpotifyTrack]:
        payload = await self._get(
            "/me/top/tracks",
            params={"time_range": time_range, "limit": min(limit, 50)},
        )
        return [self._normalize_track(item) for item in payload.get("items", [])]

    async def get_recently_played(self, limit: int = 20) -> list[SpotifyTrack]:
        payload = await self._get("/me/player/recently-played", params={"limit": min(limit, 50)})
        tracks: list[SpotifyTrack] = []
        for item in payload.get("items", []):
            track = item.get("track", {})
            tracks.append(self._normalize_track(track, played_at=item.get("played_at")))
        return tracks

    async def search_artist(self, query: str, limit: int = 5) -> list[SpotifyArtist]:
        payload = await self._get(
            "/search",
            params={"q": query, "type": "artist", "limit": min(limit, 20)},
        )
        return [self._normalize_artist(item) for item in payload.get("artists", {}).get("items", [])]

    async def infer_recent_top_artist(self, limit: int = 20) -> SpotifyArtist | None:
        tracks = await self.get_recently_played(limit=limit)
        counts = Counter(name for track in tracks for name in track.artist_names)
        if not counts:
            return None
        top_name = counts.most_common(1)[0][0]
        matches = await self.search_artist(top_name, limit=1)
        return matches[0] if matches else None

    @staticmethod
    def _normalize_artist(item: dict[str, Any]) -> SpotifyArtist:
        return SpotifyArtist(
            artist_id=item["id"],
            artist_name=item["name"],
            genres=item.get("genres", []),
            popularity=item.get("popularity"),
            followers_total=(item.get("followers") or {}).get("total"),
            spotify_url=(item.get("external_urls") or {}).get("spotify"),
        )

    @staticmethod
    def _normalize_track(item: dict[str, Any], played_at: str | None = None) -> SpotifyTrack:
        return SpotifyTrack(
            track_id=item["id"],
            track_name=item["name"],
            artist_names=[artist["name"] for artist in item.get("artists", [])],
            album_name=(item.get("album") or {}).get("name"),
            played_at=played_at,
            spotify_url=(item.get("external_urls") or {}).get("spotify"),
        )
