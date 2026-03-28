from __future__ import annotations
import os
import re
import sys

from agents import Agent, ModelSettings, Runner
from agents.extensions.models.litellm_model import LitellmModel
from agents.mcp import MCPServerStdio, MCPServerStdioParams

from a2a_music_concert.shared.config import get_settings
from a2a_music_concert.shared.models import MusicAgentResponse


def _normalize_question(question: str) -> str:
    cleaned = question.strip()
    cleaned = re.sub(r'^\s*User asks:\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or question


def build_music_agent() -> tuple[Agent, MCPServerStdio]:
    settings = get_settings()

    missing = [
        name
        for name, value in (
            ("WATSONX_PROJECT_ID", settings.watsonx_project_id),
            ("WATSONX_APIKEY", settings.watsonx_apikey),
            ("WATSONX_URL", settings.watsonx_url),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"Missing watsonx configuration: {', '.join(missing)}")

    # LiteLLM picks up project routing from the environment.
    os.environ["WATSONX_PROJECT_ID"] = settings.watsonx_project_id
    os.environ["WATSONX_APIKEY"] = settings.watsonx_apikey
    os.environ["WATSONX_URL"] = settings.watsonx_url

    watsonx_model = LitellmModel(
        model=f"watsonx/{settings.watsonx_model_id}",
        api_key=settings.watsonx_apikey,
        base_url=settings.watsonx_url,
    )

    spotify_mcp_server = MCPServerStdio(
        params=MCPServerStdioParams(
            command=sys.executable,
            args=["-m", "a2a_music_concert.spotify_mcp.server", "stdio"],
            env=dict(os.environ),
        ),
        name="spotify-personalized-mcp",
        cache_tools_list=True,
        client_session_timeout_seconds=30,
    )

    agent = Agent(
        name="Spotify Music Agent",
        instructions=(
            "You are a Spotify music agent. "
            "You can chat naturally, and you also have Spotify MCP tools available when they are useful. "
            "Do not call tools unless they help answer the user's request. "
            "If the message includes wrapper text like 'User asks:', ignore that wrapper and answer the underlying user question. "
            "For conversational prompts like 'who are you?' or other non-Spotify questions, respond directly without using tools. "
            "For Spotify listening questions, choose the tool that best fits the request. "
            "Prefer get_top_artists for ranking questions like top artist or most listened. "
            "Use get_recently_played for very recent listening questions. "
            "Use search_artist only when you need to resolve an artist name. "
            "If a Spotify tool returns valid artist or track data, answer from that data. "
            "Do not claim the Spotify connection is missing, not configured, or unavailable unless a tool call actually fails and gives you evidence of that failure. "
            "Always return a MusicAgentResponse object. "
            "If the user is asking about a Spotify artist/listening result, use answer_type='artist_answer' and fill artist_name plus any other relevant fields. "
            "If the user is asking something conversational or outside Spotify listening, use answer_type='general_response' and put the natural-language reply in message."
        ),
        model=watsonx_model,
        mcp_servers=[spotify_mcp_server],
        model_settings=ModelSettings(include_usage=True),
        output_type=MusicAgentResponse,
    )
    return agent, spotify_mcp_server


async def answer_music_question(question: str) -> MusicAgentResponse:
    agent, spotify_mcp_server = build_music_agent()
    try:
        async with spotify_mcp_server:
            result = await Runner.run(agent, _normalize_question(question))
        final_output = result.final_output
        if isinstance(final_output, MusicAgentResponse):
            return final_output
        if isinstance(final_output, dict):
            return MusicAgentResponse.model_validate(final_output)
        if isinstance(final_output, str):
            try:
                return MusicAgentResponse.model_validate_json(final_output)
            except Exception:  # noqa: BLE001
                return MusicAgentResponse(
                    answer_type="general_response",
                    message=final_output.strip(),
                )
        return MusicAgentResponse(
            answer_type="general_response",
            message=str(final_output),
        )
    finally:
        await spotify_mcp_server.cleanup()
