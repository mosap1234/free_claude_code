"""Contract checks: catalog, registry factories, admin fields, Settings, env template."""

from __future__ import annotations

from pathlib import Path

from api.admin_manifest import FIELD_BY_KEY, FIELDS
from config.provider_catalog import PROVIDER_CATALOG
from config.settings import Settings
from providers.registry import PROVIDER_FACTORIES


def test_every_catalog_entry_has_factory() -> None:
    catalog_ids = set(PROVIDER_CATALOG)
    factory_ids = set(PROVIDER_FACTORIES)
    assert catalog_ids == factory_ids, (
        "PROVIDER_CATALOG keys must equal PROVIDER_FACTORIES keys; "
        f"only_catalog={sorted(catalog_ids - factory_ids)!r} "
        f"only_factories={sorted(factory_ids - catalog_ids)!r}"
    )


def test_credential_env_providers_have_admin_field() -> None:
    keys = FIELD_BY_KEY
    missing: list[str] = []
    for pid, descriptor in PROVIDER_CATALOG.items():
        env_key = descriptor.credential_env
        if env_key is None:
            continue
        field = keys.get(env_key)
        if field is None:
            missing.append(f"{pid}: credential_env={env_key!r} missing admin field key")
            continue
        attr = descriptor.credential_attr
        assert attr is not None, (
            f"{pid}: credential_env set but credential_attr is None ({env_key!r})"
        )
        assert field.settings_attr == attr, (
            f"{pid}: admin field {env_key} settings_attr={field.settings_attr!r} "
            f"expected descriptor credential_attr={attr!r}"
        )

    assert missing == [], "Missing admin entries:\n" + "\n".join(missing)


def test_admin_settings_attrs_exist_on_settings() -> None:
    model_fields = Settings.model_fields
    missing = sorted(
        f"{field.key}: settings_attr={field.settings_attr!r}"
        for field in FIELDS
        if field.settings_attr is not None and field.settings_attr not in model_fields
    )

    assert missing == [], (
        "ConfigFieldSpec settings_attr missing from Settings.model_fields:\n"
        + "\n".join(missing)
    )


def test_env_example_covers_credential_envs() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    example_text = (repo_root / ".env.example").read_text(encoding="utf-8")
    missing: list[str] = []
    for pid, descriptor in PROVIDER_CATALOG.items():
        env_key = descriptor.credential_env
        if env_key is None:
            continue
        if env_key not in example_text:
            missing.append(
                f"{pid}: credential_env {env_key!r} absent from .env.example"
            )

    assert missing == [], "Missing from .env.example:\n" + "\n".join(missing)


def test_openai_chat_ids_are_catalog_subset() -> None:
    from config.provider_catalog import provider_ids_for_transport

    ids = provider_ids_for_transport("openai_chat")
    catalog = set(PROVIDER_CATALOG.keys())
    assert ids <= catalog
