"""Outbound queue surface used by the handler and command helpers.

Concrete platforms implement :class:`~messaging.platforms.base.MessagingPlatform`,
which satisfies this protocol structurally. Code that only needs the outbound queue paths
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PlatformOutbound(Protocol):
    """Queued delivery used by :class:`~messaging.handler.ClaudeMessageHandler`."""

    name: str

    def fire_and_forget(self, task: Awaitable[Any]) -> None:
        """Execute a coroutine without awaiting it."""
        ...

    async def queue_send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = None,
        fire_and_forget: bool = True,
        message_thread_id: str | None = None,
    ) -> str | None: ...

    async def queue_edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = None,
        fire_and_forget: bool = True,
    ) -> None: ...

    async def queue_delete_messages(
        self,
        chat_id: str,
        message_ids: list[str],
        *,
        fire_and_forget: bool = True,
    ) -> None: ...
