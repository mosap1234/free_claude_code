"""Admin fields: smoke."""

from api.admin.manifest_types import ConfigFieldSpec

FIELDS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_NVIDIA_NIM",
        "Smoke NVIDIA NIM Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_OPEN_ROUTER",
        "Smoke OpenRouter Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_DEEPSEEK",
        "Smoke DeepSeek Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_LMSTUDIO",
        "Smoke LM Studio Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_LLAMACPP",
        "Smoke llama.cpp Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_OLLAMA",
        "Smoke Ollama Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_KIMI",
        "Smoke Kimi Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_WAFER",
        "Smoke Wafer Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_OPENCODE",
        "Smoke OpenCode Zen Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_OPENCODE_GO",
        "Smoke OpenCode Go Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_MODEL_ZAI",
        "Smoke Z.ai Model",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_NIM_MODELS",
        "Smoke NIM Models",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_NIM_EXTRA_MODELS",
        "Smoke NIM Extra Models",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_OPENROUTER_FREE_MODELS",
        "Smoke OpenRouter Free Models",
        "smoke",
        advanced=True,
    ),
    ConfigFieldSpec(
        "FCC_SMOKE_OPENROUTER_FREE_EXTRA_MODELS",
        "Smoke OpenRouter Free Extra Models",
        "smoke",
        advanced=True,
    ),
)
