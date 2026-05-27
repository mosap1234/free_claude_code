"""CLI entry points for the installed package."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn

from api.admin_urls import local_admin_url, local_proxy_root_url
from api.app import GracefulLifespanApp, create_app
from cli.process_registry import (
    kill_all_best_effort,
    kill_pid_tree_best_effort,
    register_pid,
    unregister_pid,
)
from config.paths import config_dir_path, legacy_env_paths, managed_env_path
from config.settings import Settings, get_settings

PROXY_PREFLIGHT_PATH = "/health"
PROXY_PREFLIGHT_TIMEOUT_SECONDS = 1.5
SERVER_GRACEFUL_SHUTDOWN_SECONDS = 5
SERVER_READY_TIMEOUT_SECONDS = 30.0
SERVER_READY_POLL_INTERVAL_SECONDS = 0.15


def _load_env_template() -> str:
    """Load the canonical root env template from package resources or source."""
    import importlib.resources

    packaged = importlib.resources.files("cli").joinpath("env.example")
    if packaged.is_file():
        return packaged.read_text("utf-8")

    source_template = Path(__file__).resolve().parents[1] / ".env.example"
    if source_template.is_file():
        return source_template.read_text(encoding="utf-8")

    raise FileNotFoundError("Could not find bundled or source .env.example template.")


def serve() -> None:
    """Start the FastAPI server (registered as `fcc-server` script)."""
    opened_admin_browser = False
    try:
        try:
            while True:
                _migrate_legacy_env_if_missing()
                settings = get_settings()
                if not _run_supervised_server(
                    settings, open_admin_browser=not opened_admin_browser
                ):
                    return
                opened_admin_browser = True
                get_settings.cache_clear()
        except KeyboardInterrupt:
            return
    finally:
        kill_all_best_effort()


def _admin_browser_open_enabled() -> bool:
    """Whether to open /admin when the server becomes reachable (FCC_OPEN_BROWSER)."""

    raw = os.environ.get("FCC_OPEN_BROWSER", "true").strip().lower()
    return raw not in {"", "0", "false", "no"}


def _schedule_open_admin_browser(settings: Settings) -> None:
    """After /health succeeds, open the admin UI in the default browser (daemon thread)."""

    if not _admin_browser_open_enabled():
        return

    admin_url = local_admin_url(settings)
    proxy_root_url = local_proxy_root_url(settings)

    def open_when_ready() -> None:
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if _preflight_proxy(proxy_root_url) is None:
                webbrowser.open(admin_url)
                return
            time.sleep(0.15)

    threading.Thread(
        target=open_when_ready, name="fcc-open-admin-browser", daemon=True
    ).start()


def _run_supervised_server(settings: Settings, *, open_admin_browser: bool) -> bool:
    """Run one uvicorn server instance; return whether admin requested restart."""

    restart_requested = False
    server_holder: dict[str, uvicorn.Server] = {}

    def request_restart() -> None:
        nonlocal restart_requested
        restart_requested = True
        if server := server_holder.get("server"):
            server.should_exit = True

    app = create_app(lifespan_enabled=False)
    app.state.admin_restart_callback = request_restart
    asgi_app = GracefulLifespanApp(app)
    config = uvicorn.Config(
        asgi_app,
        host=settings.host,
        port=settings.port,
        log_level="debug",
        timeout_graceful_shutdown=SERVER_GRACEFUL_SHUTDOWN_SECONDS,
    )
    server = uvicorn.Server(config)
    server_holder["server"] = server
    if open_admin_browser:
        _schedule_open_admin_browser(settings)
    server.run()
    return restart_requested


def init() -> None:
    """Scaffold config at ~/.fcc/.env (registered as `fcc-init`)."""
    config_dir = config_dir_path()
    env_file = managed_env_path()

    migrated_from = _migrate_legacy_env_if_missing()
    if migrated_from is not None:
        print(f"Config migrated from {migrated_from} to {env_file}")
        print(
            "Edit it to set your API keys and model preferences, then run: fcc-server"
        )
        return

    if env_file.exists():
        print(f"Config already exists at {env_file}")
        print("Delete it first if you want to reset to defaults.")
        return

    config_dir.mkdir(parents=True, exist_ok=True)
    template = _load_env_template()
    env_file.write_text(template, encoding="utf-8")
    print(f"Config created at {env_file}")
    print("Edit it to set your API keys and model preferences, then run: fcc-server")


def _migrate_legacy_env_if_missing() -> Path | None:
    """Copy a legacy user env into the managed config path when absent."""

    env_file = managed_env_path()
    if env_file.exists():
        return None

    # TODO: Remove after the ~/.fcc/.env migration has had a release cycle.
    for legacy_env in legacy_env_paths():
        if not legacy_env.is_file():
            continue
        env_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(legacy_env, env_file)
        return legacy_env

    return None


def _claude_child_env(
    settings: Settings, base_env: Mapping[str, str]
) -> dict[str, str]:
    """Return a Claude Code environment that targets this proxy."""

    env = {
        key: value
        for key, value in base_env.items()
        if not key.startswith("ANTHROPIC_")
    }
    env.pop("ANTHROPIC_API_KEY", None)
    env["ANTHROPIC_BASE_URL"] = local_proxy_root_url(settings)
    env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] = "1"
    env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = "190000"
    if token := settings.anthropic_auth_token.strip():
        env["ANTHROPIC_AUTH_TOKEN"] = token
    return env


def _preflight_proxy(proxy_root_url: str) -> str | None:
    """Return an error message when the local proxy health check is unreachable."""

    url = f"{proxy_root_url.rstrip('/')}{PROXY_PREFLIGHT_PATH}"
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=PROXY_PREFLIGHT_TIMEOUT_SECONDS) as response:
            status_code = response.getcode()
    except HTTPError as exc:
        return f"returned HTTP {exc.code}"
    except URLError as exc:
        return str(exc.reason)
    except OSError as exc:
        return str(exc)

    if not 200 <= status_code < 300:
        return f"returned HTTP {status_code}"
    return None


def _auto_server_enabled() -> bool:
    """Whether fcc-claude may start its own proxy when none is reachable (FCC_AUTO_SERVER)."""

    raw = os.environ.get("FCC_AUTO_SERVER", "true").strip().lower()
    return raw not in {"", "0", "false", "no"}


def _managed_server_log_path() -> Path:
    """Return the log file a fcc-claude-owned proxy writes to."""

    return config_dir_path() / "managed-server.log"


def _spawn_managed_server(base_env: Mapping[str, str]) -> subprocess.Popen[bytes]:
    """Start a background proxy this CLI owns; suppress its browser and tee logs to a file."""

    env = dict(base_env)
    env["FCC_OPEN_BROWSER"] = "0"
    command = [sys.executable, "-c", "from cli.entrypoints import serve; serve()"]
    log_path = _managed_server_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    # ``with`` closes the parent's handle once the child has inherited the fd.
    with open(log_path, "ab") as log_file:
        return subprocess.Popen(command, env=env, stdout=log_file, stderr=log_file)


def _wait_for_proxy_ready(
    proxy_root_url: str,
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
) -> str | None:
    """Poll /health until the managed proxy answers; return an error message on failure."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return f"proxy process exited early with code {process.returncode}"
        if _preflight_proxy(proxy_root_url) is None:
            return None
        time.sleep(SERVER_READY_POLL_INTERVAL_SECONDS)
    return f"proxy did not become reachable within {timeout_seconds:.0f}s"


def _stop_managed_server(process: subprocess.Popen[bytes]) -> None:
    """Gracefully stop a CLI-owned proxy: SIGTERM, wait, then force-kill the tree."""

    if process.poll() is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=SERVER_GRACEFUL_SHUTDOWN_SECONDS + 2)
        return
    except subprocess.TimeoutExpired:
        pass
    if process.pid:
        kill_pid_tree_best_effort(process.pid)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=3)


def _ensure_proxy_running(proxy_root_url: str) -> subprocess.Popen[bytes] | None:
    """Make sure a proxy is reachable; return a process only when this CLI started one.

    A proxy that already answers is reused and left untouched (returns ``None``).
    Otherwise, unless ``FCC_AUTO_SERVER`` disables it, start one, wait for it to
    become healthy, and return it so the caller can stop it when the session ends.
    """

    if _preflight_proxy(proxy_root_url) is None:
        return None

    if not _auto_server_enabled():
        print(
            f"Free Claude Code proxy is not reachable at {proxy_root_url}.",
            file=sys.stderr,
        )
        print("Start it in another terminal with: fcc-server", file=sys.stderr)
        print(
            "(or set FCC_AUTO_SERVER=1 to let fcc-claude start the proxy automatically)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"Starting Free Claude Code proxy at {proxy_root_url} ...", file=sys.stderr)
    process = _spawn_managed_server(os.environ)
    if process.pid:
        register_pid(process.pid)
    if error := _wait_for_proxy_ready(
        proxy_root_url, process, SERVER_READY_TIMEOUT_SECONDS
    ):
        print(f"Could not start proxy at {proxy_root_url}: {error}", file=sys.stderr)
        print(f"See {_managed_server_log_path()} for details.", file=sys.stderr)
        _stop_managed_server(process)
        if process.pid:
            unregister_pid(process.pid)
        raise SystemExit(1)
    print("Proxy ready; it will stop when this session ends.", file=sys.stderr)
    return process


def _run_claude_client(settings: Settings, argv: Sequence[str] | None) -> None:
    """Spawn the Claude Code CLI against the proxy and propagate its exit code."""

    args = list(sys.argv[1:] if argv is None else argv)
    claude_command = shutil.which(settings.claude_cli_bin)
    if claude_command is None:
        print(
            f"Could not find Claude Code command: {settings.claude_cli_bin}",
            file=sys.stderr,
        )
        print(
            "Install Claude Code with: npm install -g @anthropic-ai/claude-code",
            file=sys.stderr,
        )
        raise SystemExit(127)

    command = [claude_command, *args]
    env = _claude_child_env(settings, os.environ)
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(command, env=env)
        if process.pid:
            register_pid(process.pid)
        return_code = process.wait()
    except FileNotFoundError:
        print(
            f"Could not find Claude Code command: {settings.claude_cli_bin}",
            file=sys.stderr,
        )
        print(
            "Install Claude Code with: npm install -g @anthropic-ai/claude-code",
            file=sys.stderr,
        )
        raise SystemExit(127) from None
    except KeyboardInterrupt:
        if process is not None and process.pid:
            kill_pid_tree_best_effort(process.pid)
            process.wait()
        raise
    finally:
        if process is not None and process.pid:
            unregister_pid(process.pid)

    raise SystemExit(return_code)


def launch_claude(argv: Sequence[str] | None = None) -> None:
    """Launch Claude Code with Free Claude Code proxy environment variables.

    When no proxy is reachable, start one this CLI owns and tear it down when the
    session ends (interactive or one-shot ``-p`` runs alike), unless
    ``FCC_AUTO_SERVER`` disables auto-start. A proxy that is already running — for
    example a separately launched ``fcc-server`` — is reused and left running.
    """

    settings = get_settings()
    proxy_root_url = local_proxy_root_url(settings)

    managed_server = _ensure_proxy_running(proxy_root_url)
    try:
        _run_claude_client(settings, argv)
    finally:
        if managed_server is not None:
            _stop_managed_server(managed_server)
            if managed_server.pid:
                unregister_pid(managed_server.pid)
