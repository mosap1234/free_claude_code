"""Tree creation and enqueue path for inbound user messaging turns."""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.trace import trace_event

from .cli_event_constants import STATUS_MESSAGE_PREFIXES
from .command_dispatcher import (
    dispatch_command,
    message_kind_for_command,
    parse_command_base,
)
from .models import IncomingMessage
from .safe_diagnostics import format_exception_for_log


async def dispatch_incoming_user_message(
    handler: Any, incoming: IncomingMessage
) -> None:
    cmd_base = parse_command_base(incoming.text)

    # Record incoming message ID for best-effort UI clearing (/clear), even if
    # we later ignore this message (status/command/etc).
    try:
        if incoming.message_id is not None:
            handler.session_store.record_message_id(
                incoming.platform,
                incoming.chat_id,
                str(incoming.message_id),
                direction="in",
                kind=message_kind_for_command(cmd_base),
            )
    except Exception as e:
        logger.debug(
            "Failed to record incoming message_id: {}",
            format_exception_for_log(
                e, log_full_message=handler._log_messaging_error_details
            ),
        )

    if await dispatch_command(handler, incoming, cmd_base):
        return

    # Filter out status messages (our own messages)
    text = incoming.text or ""
    if any(text.startswith(p) for p in STATUS_MESSAGE_PREFIXES):
        return

    # Check if this is a reply to an existing node in a tree
    parent_node_id = None
    tree = None

    if incoming.is_reply() and incoming.reply_to_message_id:
        # Look up if the replied-to message is in any tree (could be a node or status message)
        reply_id = incoming.reply_to_message_id
        tree = handler.tree_queue.get_tree_for_node(reply_id)
        if tree:
            # Resolve to actual node ID (handles status message replies)
            parent_node_id = handler.tree_queue.resolve_parent_node_id(reply_id)
            if parent_node_id:
                logger.info(f"Found tree for reply, parent node: {parent_node_id}")
            else:
                logger.warning(
                    f"Reply to {incoming.reply_to_message_id} found tree but no valid parent node"
                )
                tree = None  # Treat as new conversation

    # Generate node ID
    node_id = incoming.message_id

    # Use pre-sent status (e.g. voice note) or send new
    status_text = handler._get_initial_status(tree, parent_node_id)
    if incoming.status_message_id:
        status_msg_id = incoming.status_message_id
        await handler.platform.queue_edit_message(
            incoming.chat_id,
            status_msg_id,
            status_text,
            parse_mode=handler._parse_mode(),
            fire_and_forget=False,
        )
    else:
        status_msg_id = await handler.platform.queue_send_message(
            incoming.chat_id,
            status_text,
            reply_to=incoming.message_id,
            fire_and_forget=False,
            message_thread_id=incoming.message_thread_id,
        )
    handler.record_outgoing_message(
        incoming.platform, incoming.chat_id, status_msg_id, "status"
    )

    # Create or extend tree
    if parent_node_id and tree and status_msg_id:
        # Reply to existing node - add as child
        tree, _node = await handler.tree_queue.add_to_tree(
            parent_node_id=parent_node_id,
            node_id=node_id,
            incoming=incoming,
            status_message_id=status_msg_id,
        )
        # Register status message as a node too for reply chains
        handler.tree_queue.register_node(status_msg_id, tree.root_id)
        handler.session_store.register_node(status_msg_id, tree.root_id)
        handler.session_store.register_node(node_id, tree.root_id)
    elif status_msg_id:
        # New conversation - create new tree
        tree = await handler.tree_queue.create_tree(
            node_id=node_id,
            incoming=incoming,
            status_message_id=status_msg_id,
        )
        # Register status message
        handler.tree_queue.register_node(status_msg_id, tree.root_id)
        handler.session_store.register_node(node_id, tree.root_id)
        handler.session_store.register_node(status_msg_id, tree.root_id)

    # Persist tree
    if tree:
        handler.session_store.save_tree(tree.root_id, tree.to_dict())

    # Enqueue for processing
    was_queued = await handler.tree_queue.enqueue(
        node_id=node_id,
        processor=handler._process_node,
    )

    if was_queued and status_msg_id:
        queue_size = handler.tree_queue.get_queue_size(node_id)
        trace_event(
            stage="routing",
            event="turn.queued",
            source=getattr(handler.platform, "name", "messaging"),
            chat_id=incoming.chat_id,
            platform_message_id=node_id,
            status_message_id=status_msg_id,
            queue_size=queue_size,
        )
        await handler.platform.queue_edit_message(
            incoming.chat_id,
            status_msg_id,
            handler.format_status(
                "📋", "Queued", f"(position {queue_size}) - waiting..."
            ),
            parse_mode=handler._parse_mode(),
        )
