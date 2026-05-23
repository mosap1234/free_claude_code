"""Wire Discord/Telegram handler + Claude CLI session manager (composition under ``api``).

``messaging`` must not import ``cli``; ``api.runtime`` delegates here so lifecycle
stays in ``AppRuntime`` while construction details live in one place.
"""

import os
from typing import TYPE_CHECKING

from loguru import logger

from cli.manager import CLISessionManager
from config.settings import Settings
from messaging.bootstrap import restore_tree_queue_state
from messaging.handler import ClaudeMessageHandler
from messaging.session import SessionStore

if TYPE_CHECKING:
    from api.runtime import AppRuntime


def create_cli_session_manager_for_messaging(
    settings: Settings, *, workspace: str
) -> CLISessionManager:
    """Build :class:`~cli.manager.CLISessionManager` for the messaging stack."""
    api_url = f"http://{settings.host}:{settings.port}/v1"
    allowed_dirs = [workspace] if settings.allowed_dir else []
    plans_dir_abs = os.path.abspath(os.path.join(settings.claude_workspace, "plans"))
    plans_directory = os.path.relpath(plans_dir_abs, workspace)
    return CLISessionManager(
        workspace_path=workspace,
        api_url=api_url,
        allowed_dirs=allowed_dirs,
        plans_directory=plans_directory,
        claude_bin=settings.claude_cli_bin,
        auth_token=getattr(settings, "anthropic_auth_token", ""),
        log_raw_cli_diagnostics=settings.log_raw_cli_diagnostics,
        log_messaging_error_details=settings.log_messaging_error_details,
    )


def resolve_messaging_workspace_paths(settings: Settings) -> tuple[str, str]:
    """Return ``(workspace_abs, claude_data_path_abs)`` for session + handler setup."""
    workspace = (
        os.path.abspath(settings.allowed_dir) if settings.allowed_dir else os.getcwd()
    )
    os.makedirs(workspace, exist_ok=True)
    data_path = os.path.abspath(settings.claude_workspace)
    os.makedirs(data_path, exist_ok=True)
    return workspace, data_path


async def start_messaging_handler_stack(runtime: AppRuntime) -> None:
    """Attach CLI manager, handler, session store, tree restore, and start the platform."""
    settings = runtime.settings
    platform = runtime.messaging_platform
    assert platform is not None

    workspace, data_path = resolve_messaging_workspace_paths(settings)
    runtime.cli_manager = create_cli_session_manager_for_messaging(
        settings, workspace=workspace
    )

    session_store = SessionStore(
        storage_path=os.path.join(data_path, "sessions.json"),
        message_log_cap=settings.max_message_log_entries_per_chat,
    )
    runtime.message_handler = ClaudeMessageHandler(
        platform=platform,
        cli_manager=runtime.cli_manager,
        session_store=session_store,
        debug_platform_edits=settings.debug_platform_edits,
        debug_subagent_stack=settings.debug_subagent_stack,
        log_raw_messaging_content=settings.log_raw_messaging_content,
        log_raw_cli_diagnostics=settings.log_raw_cli_diagnostics,
        log_messaging_error_details=settings.log_messaging_error_details,
    )
    restore_tree_queue_state(settings, runtime.message_handler, session_store)

    platform.on_message(runtime.message_handler.handle_message)
    await platform.start()
    logger.info("{} platform started with message handler", platform.name)
