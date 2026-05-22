from __future__ import annotations

import json
from pathlib import Path

from api.models.anthropic import ContentBlockText, Message, MessagesRequest
from core.anthropic.conversion import build_base_request_body


def test_golden_openai_conversion_matches_fixture() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "golden"
        / "conversion"
        / "build_base_simple.json"
    )
    expected = json.loads(fixture.read_text(encoding="utf-8"))

    req = MessagesRequest(
        model="claude-opus-4-latest",
        max_tokens=100,
        temperature=0.3,
        system="SYS",
        messages=[
            Message(role="user", content=[ContentBlockText(type="text", text="hello")]),
            Message(
                role="assistant", content=[ContentBlockText(type="text", text="hi")]
            ),
        ],
    )

    assert build_base_request_body(req) == expected
