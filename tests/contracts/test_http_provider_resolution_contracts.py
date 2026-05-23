from pathlib import Path


def test_live_api_handlers_do_not_call_process_cached_provider_helpers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    watched = ("api/routes.py", "api/services.py")

    needles = (
        "get_provider(",
        "get_provider_for_type(",
        "get_process_cached_provider(",
        "get_process_cached_provider_for_type(",
    )
    for relative in watched:
        body = (repo_root / relative).read_text(encoding="utf-8")
        banned_hits = [token for token in needles if token in body]
        assert banned_hits == [], f"{relative} must avoid {banned_hits!r}"
