from __future__ import annotations
import sys

from mcp.server.fastmcp import FastMCP

from a2a_music_concert.shared.config import get_settings
from a2a_music_concert.spotify_mcp.spotify_client import SpotifyClient

settings = get_settings()
client = SpotifyClient(settings)
mcp = FastMCP(
    name="spotify-personalized-mcp",
    instructions="Spotify tools for personalized music questions such as top artists and recent listening.",
    host=settings.spotify_mcp_host,
    port=settings.spotify_mcp_port,
)


@mcp.tool()
async def get_top_artists(time_range: str = "short_term", limit: int = 5) -> list[dict]:
    artists = await client.get_top_artists(time_range=time_range, limit=limit)
    return [artist.model_dump() for artist in artists]


@mcp.tool()
async def get_top_tracks(time_range: str = "short_term", limit: int = 10) -> list[dict]:
    tracks = await client.get_top_tracks(time_range=time_range, limit=limit)
    return [track.model_dump() for track in tracks]


@mcp.tool()
async def get_recently_played(limit: int = 20) -> list[dict]:
    tracks = await client.get_recently_played(limit=limit)
    return [track.model_dump() for track in tracks]


@mcp.tool()
async def search_artist(query: str, limit: int = 5) -> list[dict]:
    artists = await client.search_artist(query=query, limit=limit)
    return [artist.model_dump() for artist in artists]


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "sse"
    mcp.run(transport=transport)
