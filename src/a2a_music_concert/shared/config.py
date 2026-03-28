from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    watsonx_project_id: str = Field(default="", alias="WATSONX_PROJECT_ID")
    watsonx_apikey: str = Field(default="", alias="WATSONX_APIKEY")
    watsonx_url: str = Field(default="", alias="WATSONX_URL")
    watsonx_model_id: str = Field(default="openai/gpt-oss-120b", alias="WATSONX_MODEL_ID")

    spotify_client_id: str = Field(default="", alias="SPOTIFY_CLIENT_ID")
    spotify_client_secret: str = Field(default="", alias="SPOTIFY_CLIENT_SECRET")
    spotify_refresh_token: str = Field(default="", alias="SPOTIFY_REFRESH_TOKEN")
    spotify_redirect_uri: str = Field(
        default="http://127.0.0.1:8787/callback",
        alias="SPOTIFY_REDIRECT_URI",
    )

    ticketmaster_api_key: str = Field(default="", alias="TICKETMASTER_API_KEY")
    default_location: str = Field(default="", alias="DEFAULT_LOCATION")

    spotify_mcp_base_url: str = Field(default="", alias="SPOTIFY_MCP_BASE_URL")
    spotify_mcp_sse_url_override: str = Field(default="", alias="SPOTIFY_MCP_SSE_URL")
    app_base_url: str = Field(default="", alias="APP_BASE_URL")
    music_agent_host: str = Field(default="127.0.0.1", alias="MUSIC_AGENT_HOST")
    music_agent_port: int = Field(default=9111, alias="MUSIC_AGENT_PORT")
    concert_agent_host: str = Field(default="127.0.0.1", alias="CONCERT_AGENT_HOST")
    concert_agent_port: int = Field(default=9112, alias="CONCERT_AGENT_PORT")
    concert_app_base_url: str = Field(default="", alias="CONCERT_APP_BASE_URL")
    port: int = Field(default=9111, alias="PORT")

    @property
    def music_agent_bind_port(self) -> int:
        return self.port or self.music_agent_port

    @property
    def music_agent_public_url(self) -> str:
        if self.app_base_url:
            return self.app_base_url.rstrip("/")
        return f"http://{self.music_agent_host}:{self.music_agent_bind_port}"

    @property
    def concert_agent_public_url(self) -> str:
        if self.concert_app_base_url:
            return self.concert_app_base_url.rstrip("/")
        return f"http://{self.concert_agent_host}:{self.concert_agent_port}"

    @property
    def resolved_spotify_mcp_base_url(self) -> str:
        if self.spotify_mcp_base_url:
            return self.spotify_mcp_base_url.rstrip("/")
        return f"http://127.0.0.1:{self.music_agent_bind_port}/spotify/mcp"

    @property
    def spotify_mcp_sse_url(self) -> str:
        if self.spotify_mcp_sse_url_override:
            return self.spotify_mcp_sse_url_override
        return self.resolved_spotify_mcp_base_url.replace("/mcp", "/sse")

    @property
    def spotify_mcp_host(self) -> str:
        parsed = urlparse(self.resolved_spotify_mcp_base_url)
        return parsed.hostname or "127.0.0.1"

    @property
    def spotify_mcp_port(self) -> int:
        parsed = urlparse(self.resolved_spotify_mcp_base_url)
        return parsed.port or self.music_agent_bind_port


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
