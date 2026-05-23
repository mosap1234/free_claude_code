"""Tests for :mod:`messaging.bootstrap`."""

from __future__ import annotations

from config.settings import Settings


def test_create_optional_platform_none_when_disabled(monkeypatch) -> None:
    from messaging.bootstrap import create_optional_messaging_platform

    monkeypatch.setitem(Settings.model_config, "env_file", ())
    monkeypatch.setenv("MESSAGING_PLATFORM", "none")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    settings = Settings()
    assert create_optional_messaging_platform(settings) is None


def test_build_options_reflects_hf_token(monkeypatch) -> None:
    from messaging.bootstrap import build_messaging_platform_options

    monkeypatch.setitem(Settings.model_config, "env_file", ())
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    settings = Settings()
    opts = build_messaging_platform_options(settings)
    assert opts.hf_token == "hf-test-token"
