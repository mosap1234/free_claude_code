# Testing the Transport-Error Retry Workaround

Since `fcc-server.exe` runs the **installed** package, it won't pick up local source changes. Use one of the methods below to run from source instead.

## Option 1: `uv run` (simplest)

```bash
uv run --system-certs fcc-server
```

This runs the project from the local source tree using the `.venv` that already has Python 3.14 + all deps.

## Option 2: Run via venv Python

From the project root:

```bash
.venv\Scripts\python.exe -m cli.entrypoints
```

Or equivalently, if the scripts were installed:

```bash
.venv\Scripts\fcc-server.exe
```

## Option 3: Quick inline test

```bash
.venv\Scripts\python.exe -c "from cli.entrypoints import serve; serve()"
```

## Steps to Swap In-Place

1. **Stop** your current `fcc-server.exe` (Ctrl+C or kill the process)
2. **From the project root**, run one of the above commands
3. Your modified `providers/openai_compat.py` will be loaded — the transport-error retry is active

## How to Verify It's Working

When a `RemoteProtocolError` hits, you should see this in `server.log`:

```
NIM_RETRY: transport error on attempt 1/3, restarting stream (request_id=...)
```

And in the trace events:

```
provider.response.transport_retry  retry_attempt=1  max_retries=2
```

If all retries fail, the client error message will start with:

```
fcc-server 2 retry ...
```

## To Switch Back

Just stop the source-run server and restart `fcc-server.exe` as before.

## TL;DR

Kill `fcc-server.exe`, then from the project root:

```bash
.venv\Scripts\python.exe -m cli.entrypoints
```
