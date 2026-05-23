"""Provider credential rows derived from :data:`config.provider_catalog.PROVIDER_CATALOG`.

URLs, proxies, and other non-credential defaults stay in ``fields_providers.py``.
"""

from api.admin.manifest_types import ConfigFieldSpec
from config.provider_catalog import PROVIDER_CATALOG, SUPPORTED_PROVIDER_IDS

_CREDENTIAL_LABEL_AND_HELP: dict[str, tuple[str, str]] = {
    "NVIDIA_NIM_API_KEY": (
        "NVIDIA NIM API Key",
        "Used by NVIDIA NIM chat and optional NIM voice transcription.",
    ),
    "OPENROUTER_API_KEY": ("OpenRouter API Key", ""),
    "DEEPSEEK_API_KEY": ("DeepSeek API Key", ""),
    "KIMI_API_KEY": ("Kimi API Key", ""),
    "WAFER_API_KEY": ("Wafer API Key", ""),
    "OPENCODE_API_KEY": (
        "OpenCode API Key",
        (
            "OpenCode Zen curated gateway (opencode.ai/zen/v1) and OpenCode Go subscription "
            "gateway (opencode.ai/zen/go/v1); single key from opencode.ai/auth."
        ),
    ),
    "ZAI_API_KEY": ("Z.ai API Key", "Z.ai Coding Plan API key."),
    "FIREWORKS_API_KEY": ("Fireworks API Key", "Fireworks AI inference API key."),
}


def _credential_field_from_catalog(
    env_key: str, credential_attr: str
) -> ConfigFieldSpec:
    label, description = _CREDENTIAL_LABEL_AND_HELP.get(env_key, (env_key, ""))
    if label == env_key:
        slug = env_key.removesuffix("_API_KEY").replace("_", " ").title()
        label = f"{slug} API Key" if env_key.endswith("_API_KEY") else slug
    return ConfigFieldSpec(
        env_key,
        label,
        "providers",
        "secret",
        settings_attr=credential_attr,
        secret=True,
        description=description,
    )


def catalog_credential_field_specs() -> tuple[ConfigFieldSpec, ...]:
    """One admin field per unique ``credential_env`` in catalog order."""
    seen: set[str] = set()
    out: list[ConfigFieldSpec] = []
    for pid in SUPPORTED_PROVIDER_IDS:
        descriptor = PROVIDER_CATALOG[pid]
        env_key = descriptor.credential_env
        if env_key is None:
            continue
        attr = descriptor.credential_attr
        if attr is None:
            raise AssertionError(
                f"{pid}: credential_env={env_key!r} but credential_attr is None"
            )
        if env_key in seen:
            continue
        seen.add(env_key)
        out.append(_credential_field_from_catalog(env_key, attr))
    return tuple(out)
