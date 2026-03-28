from __future__ import annotations

from fastapi import FastAPI

from a2a_music_concert.a2a.executors import MusicAgentExecutor
from a2a_music_concert.a2a.server_factory import build_a2a_app, music_card
from a2a_music_concert.shared.config import get_settings

settings = get_settings()

app = FastAPI(title="Spotify Music Agent Deployment")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/", build_a2a_app(music_card(settings), MusicAgentExecutor()))
