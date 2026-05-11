from typing import Any

import orjson

JSONDecodeError = orjson.JSONDecodeError


def dumps(obj: Any, default: Any = None, **kwargs) -> str:
    """Wrapper for orjson.dumps that returns a string and handles kwargs loosely."""
    # orjson.dumps doesn't accept ensure_ascii (it always returns UTF-8 bytes)
    # default works if we pass it
    options = 0

    try:
        if default:
            return orjson.dumps(obj, default=default, option=options).decode("utf-8")
        return orjson.dumps(obj, option=options).decode("utf-8")
    except Exception:
        if default:
            return orjson.dumps(obj, default=default).decode("utf-8")
        return orjson.dumps(obj).decode("utf-8")


def loads(s: str | bytes) -> Any:
    return orjson.loads(s)
