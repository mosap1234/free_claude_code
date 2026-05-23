"""Telegram outbound sends/edits/deletes (mirrors discord/outbound composition)."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from telegram.error import NetworkError, RetryAfter, TelegramError


class TelegramOutboundMixin:
    """Retry, send/edit/delete, and limiter-queue helpers for Telegram."""

    _application: Any
    _limiter: Any | None

    async def _with_retry(
        self, func: Callable[..., Awaitable[Any]], *args, **kwargs
    ) -> Any:
        """Helper to execute a function with exponential backoff on network errors."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except (TimeoutError, NetworkError) as e:
                if "Message is not modified" in str(e):
                    return None
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"Telegram API network error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Telegram API failed after {max_retries} attempts: {e}"
                    )
                    raise
            except RetryAfter as e:
                # Telegram explicitly tells us to wait (PTB_TIMEDELTA: retry_after is timedelta)
                from datetime import timedelta

                retry_after = e.retry_after
                if isinstance(retry_after, timedelta):
                    wait_secs = retry_after.total_seconds()
                else:
                    wait_secs = float(retry_after)

                logger.warning(f"Rate limited by Telegram, waiting {wait_secs}s...")
                await asyncio.sleep(wait_secs)
                # We don't increment attempt here, as this is a specific instruction
                return await func(*args, **kwargs)
            except TelegramError as e:
                # Non-network Telegram errors
                err_lower = str(e).lower()
                if "message is not modified" in err_lower:
                    return None
                # Best-effort no-op cases (common during chat cleanup / /clear).
                if any(
                    x in err_lower
                    for x in [
                        "message to edit not found",
                        "message to delete not found",
                        "message can't be deleted",
                        "message can't be edited",
                        "not enough rights to delete",
                    ]
                ):
                    return None
                if "Can't parse entities" in str(e) and kwargs.get("parse_mode"):
                    logger.warning("Markdown failed, retrying without parse_mode")
                    kwargs["parse_mode"] = None
                    return await func(*args, **kwargs)
                raise

    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = "MarkdownV2",
        message_thread_id: str | None = None,
    ) -> str:
        """Send a message to a chat."""
        app = self._application
        if not app or not app.bot:
            raise RuntimeError("Telegram application or bot not initialized")

        async def _do_send(parse_mode=parse_mode):
            bot = app.bot
            kwargs: dict[str, Any] = {
                "chat_id": chat_id,
                "text": text,
                "reply_to_message_id": int(reply_to) if reply_to else None,
                "parse_mode": parse_mode,
            }
            if message_thread_id is not None:
                kwargs["message_thread_id"] = int(message_thread_id)
            msg = await bot.send_message(**kwargs)
            return str(msg.message_id)

        return await self._with_retry(_do_send, parse_mode=parse_mode)

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = "MarkdownV2",
    ) -> None:
        """Edit an existing message."""
        app = self._application
        if not app or not app.bot:
            raise RuntimeError("Telegram application or bot not initialized")

        async def _do_edit(parse_mode=parse_mode):
            bot = app.bot
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(message_id),
                text=text,
                parse_mode=parse_mode,
            )

        await self._with_retry(_do_edit, parse_mode=parse_mode)

    async def delete_message(
        self,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Delete a message from a chat."""
        app = self._application
        if not app or not app.bot:
            raise RuntimeError("Telegram application or bot not initialized")

        async def _do_delete():
            bot = app.bot
            await bot.delete_message(chat_id=chat_id, message_id=int(message_id))

        await self._with_retry(_do_delete)

    async def delete_messages(self, chat_id: str, message_ids: list[str]) -> None:
        """Delete multiple messages (best-effort)."""
        if not message_ids:
            return
        app = self._application
        if not app or not app.bot:
            raise RuntimeError("Telegram application or bot not initialized")

        bot = app.bot
        if hasattr(bot, "delete_messages"):

            async def _do_bulk():
                mids = []
                for mid in message_ids:
                    try:
                        mids.append(int(mid))
                    except Exception:
                        continue
                if not mids:
                    return None
                await bot.delete_messages(chat_id=chat_id, message_ids=mids)

            await self._with_retry(_do_bulk)
            return

        for mid in message_ids:
            await self.delete_message(chat_id, mid)

    async def queue_send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = "MarkdownV2",
        fire_and_forget: bool = True,
        message_thread_id: str | None = None,
    ) -> str | None:
        """Enqueue a message to be sent (using limiter)."""
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
        parse_mode: str | None = "MarkdownV2",
        fire_and_forget: bool = True,
    ) -> None:
        """Enqueue a message edit."""
        if not self._limiter:
            return await self.edit_message(chat_id, message_id, text, parse_mode)

        async def _edit():
            return await self.edit_message(chat_id, message_id, text, parse_mode)

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
            return await self.delete_message(chat_id, message_id)

        async def _delete():
            return await self.delete_message(chat_id, message_id)

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
        """Enqueue a bulk delete (if supported) or a sequence of deletes."""
        if not message_ids:
            return

        if not self._limiter:
            return await self.delete_messages(chat_id, message_ids)

        async def _bulk():
            return await self.delete_messages(chat_id, message_ids)

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
