"""Discord outbound message operations (send, edit, delete, queues)."""

import asyncio
from collections.abc import Awaitable
from typing import Any, cast

from .constants import DISCORD_MESSAGE_LIMIT, _get_discord


class DiscordOutboundMixin:
    """Outbound API mixed into DiscordPlatform."""

    _client: Any
    _limiter: Any | None
    _connected: bool

    def _truncate(self, text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> str:
        """Truncate text to Discord's message limit."""
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = None,
        message_thread_id: str | None = None,
    ) -> str:
        """Send a message to a channel."""
        channel = self._client.get_channel(int(chat_id))
        if not channel or not hasattr(channel, "send"):
            raise RuntimeError(f"Channel {chat_id} not found")

        text = self._truncate(text)
        channel = cast(Any, channel)

        discord = _get_discord()
        if reply_to:
            ref = discord.MessageReference(
                message_id=int(reply_to),
                channel_id=int(chat_id),
            )
            msg = await channel.send(content=text, reference=ref)
        else:
            msg = await channel.send(content=text)

        return str(msg.id)

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        """Edit an existing message."""
        channel = self._client.get_channel(int(chat_id))
        if not channel or not hasattr(channel, "fetch_message"):
            raise RuntimeError(f"Channel {chat_id} not found")

        discord = _get_discord()
        channel = cast(Any, channel)
        try:
            msg = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            return

        text = self._truncate(text)
        await msg.edit(content=text)

    async def delete_message(
        self,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Delete a message from a channel."""
        channel = self._client.get_channel(int(chat_id))
        if not channel or not hasattr(channel, "fetch_message"):
            return

        discord = _get_discord()
        channel = cast(Any, channel)
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.delete()
        except discord.NotFound, discord.Forbidden:
            pass

    async def delete_messages(self, chat_id: str, message_ids: list[str]) -> None:
        """Delete multiple messages (best-effort)."""
        for mid in message_ids:
            await self.delete_message(chat_id, mid)

    async def queue_send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = None,
        fire_and_forget: bool = True,
        message_thread_id: str | None = None,
    ) -> str | None:
        """Enqueue a message to be sent."""
        if not self._limiter:
            return await self.send_message(
                chat_id, text, reply_to, parse_mode, message_thread_id
            )

        async def _send():
            return await self.send_message(
                chat_id, text, reply_to, parse_mode, message_thread_id
            )

        if fire_and_forget:
            self._limiter.fire_and_forget(_send)
            return None
        return await self._limiter.enqueue(_send)

    async def queue_edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = None,
        fire_and_forget: bool = True,
    ) -> None:
        """Enqueue a message edit."""
        if not self._limiter:
            await self.edit_message(chat_id, message_id, text, parse_mode)
            return

        async def _edit():
            await self.edit_message(chat_id, message_id, text, parse_mode)

        dedup_key = f"edit:{chat_id}:{message_id}"
        if fire_and_forget:
            self._limiter.fire_and_forget(_edit, dedup_key=dedup_key)
        else:
            await self._limiter.enqueue(_edit, dedup_key=dedup_key)

    async def queue_delete_message(
        self,
        chat_id: str,
        message_id: str,
        fire_and_forget: bool = True,
    ) -> None:
        """Enqueue a message delete."""
        if not self._limiter:
            await self.delete_message(chat_id, message_id)
            return

        async def _delete():
            await self.delete_message(chat_id, message_id)

        dedup_key = f"del:{chat_id}:{message_id}"
        if fire_and_forget:
            self._limiter.fire_and_forget(_delete, dedup_key=dedup_key)
        else:
            await self._limiter.enqueue(_delete, dedup_key=dedup_key)

    async def queue_delete_messages(
        self,
        chat_id: str,
        message_ids: list[str],
        fire_and_forget: bool = True,
    ) -> None:
        """Enqueue a bulk delete."""
        if not message_ids:
            return

        if not self._limiter:
            await self.delete_messages(chat_id, message_ids)
            return

        async def _bulk():
            await self.delete_messages(chat_id, message_ids)

        dedup_key = f"del_bulk:{chat_id}:{hash(tuple(message_ids))}"
        if fire_and_forget:
            self._limiter.fire_and_forget(_bulk, dedup_key=dedup_key)
        else:
            await self._limiter.enqueue(_bulk, dedup_key=dedup_key)

    def fire_and_forget(self, task: Awaitable[Any]) -> None:
        """Execute a coroutine without awaiting it."""
        if asyncio.iscoroutine(task):
            _ = asyncio.create_task(task)
        else:
            _ = asyncio.ensure_future(task)
