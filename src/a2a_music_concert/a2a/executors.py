from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Message, Part, Role, TextPart

from a2a_music_concert.concert_agent.service import answer_concert_question
from a2a_music_concert.music_agent.service import answer_music_question
from a2a_music_concert.shared.models import MusicAgentResponse


class BaseTextExecutor(AgentExecutor, ABC):
    @abstractmethod
    async def _run(self, prompt: str) -> str:
        raise NotImplementedError

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        prompt = context.get_user_input()
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.submit()
        await updater.start_work()
        try:
            content = await self._run(prompt)
        except Exception as exc:  # noqa: BLE001
            error_message = Message(
                role=Role.agent,
                message_id=str(uuid4()),
                task_id=context.task_id,
                context_id=context.context_id,
                parts=[Part(TextPart(text=f"Execution failed: {exc}"))],
            )
            await updater.failed(error_message)
            return

        message = Message(
            role=Role.agent,
            message_id=str(uuid4()),
            task_id=context.task_id,
            context_id=context.context_id,
            parts=[Part(TextPart(text=content))],
        )
        await updater.complete(message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


class MusicAgentExecutor(BaseTextExecutor):
    async def _run(self, prompt: str) -> str:
        response = await answer_music_question(prompt)
        return _render_music_response(response)


class ConcertAgentExecutor(BaseTextExecutor):
    async def _run(self, prompt: str) -> str:
        return await answer_concert_question(prompt)


def _render_music_response(response: MusicAgentResponse) -> str:
    if response.message and response.message.strip():
        return response.message.strip()

    if response.artist_name:
        return response.artist_name.strip()

    return "I couldn't find a Spotify result for that request."
