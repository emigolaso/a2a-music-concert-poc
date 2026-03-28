from __future__ import annotations

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentProvider, AgentSkill

from a2a_music_concert.shared.config import Settings


def build_agent_card(
    *,
    name: str,
    description: str,
    url: str,
    skill_id: str,
    skill_name: str,
    skill_description: str,
) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        version="0.1.0",
        url=url,
        protocolVersion="0.3.0",
        preferredTransport="JSONRPC",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["application/json", "text/plain"],
        capabilities=AgentCapabilities(streaming=False, pushNotifications=False),
        provider=AgentProvider(
            organization="Local POC",
            url="https://github.com/a2aproject/a2a-python",
        ),
        skills=[
            AgentSkill(
                id=skill_id,
                name=skill_name,
                description=skill_description,
                tags=["poc", "a2a"],
                examples=[],
            )
        ],
    )


def build_a2a_app(agent_card: AgentCard, executor) -> object:
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        queue_manager=InMemoryQueueManager(),
    )
    return A2AFastAPIApplication(agent_card=agent_card, http_handler=handler).build()


def music_card(settings: Settings) -> AgentCard:
    return build_agent_card(
        name="Spotify Music Agent",
        description="Answers personalized Spotify listening questions and returns a canonical artist.",
        url=f"{settings.music_agent_public_url}/",
        skill_id="spotify-personalized-artist",
        skill_name="Spotify Personalized Artist Lookup",
        skill_description="Find the user's top or recently listened artist from Spotify.",
    )


def concert_card(settings: Settings) -> AgentCard:
    return build_agent_card(
        name="Concert Agent",
        description="Finds likely upcoming concerts for a given artist using internet search.",
        url=f"{settings.concert_agent_public_url}/",
        skill_id="concert-search-lookup",
        skill_name="Concert Lookup",
        skill_description="Search the web for likely upcoming concerts for an artist and summarize the best results.",
    )
