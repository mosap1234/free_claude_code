# Produkt-E2E-Smoke-Tests

Sprachen: [English](README.md) · [Deutsch](README.de.md)

`smoke/` ist nur für lokale Nutzung gedacht. Es kann Subprozesse starten, echte
Provider ansprechen, lokale Model-Server verwenden und optional Bot-Nachrichten
senden/löschen. Hermetische Vertrags-Tests gehören unter `tests/` und müssen mit
normalem `uv run pytest` grün bleiben.

## Taxonomie

- `smoke/prereq/`: Liveness-Checks, die nachweisen, dass Server, Routen, Auth,
  CLI-Skripte, Provider-Pings, lokales `/models` und Bot-Rechte erreichbar sind.
  Das sind nur Voraussetzungen.
- `smoke/product/`: End-to-End-Produktszenarien. Feature-Smoke-Abdeckung kommt
  aus diesen Tests, nicht aus Route/Header/Provider-Pings.
- `smoke/features.py`: Source of Truth für das Feature-Mapping:
  feature -> subfeature -> scenario -> env -> expected behavior -> failure class.

## Erforderliche lokale Befehle

```powershell
uv run pytest smoke --collect-only -q
uv run pytest smoke -n 0 -s --tb=short
```

Der zweite Befehl überspringt alles, sofern `FCC_LIVE_SMOKE=1` nicht gesetzt ist,
schreibt aber trotzdem Skip-Einträge in `.smoke-results/`.

## Produkt-Smoke-Run

```powershell
$env:FCC_LIVE_SMOKE = "1"
uv run pytest smoke -n 0 -s --tb=short
```

Provider-Produkt-E2E läuft einmal pro konfiguriertem Provider, unabhängig von
`MODEL`, `MODEL_OPUS`, `MODEL_SONNET` und `MODEL_HAIKU`. Standardwerte kommen
aus dem Provider-Katalog bzw. der Doku und können mit `FCC_SMOKE_MODEL_<PROVIDER>`
überschrieben werden, z. B. `FCC_SMOKE_MODEL_DEEPSEEK=deepseek-v4-pro` (oder
`deepseek-v4-flash`). Wenn kein Provider-Smoke-Modell konfiguriert ist, schlägt
Live-Produkt-Smoke als `missing_env` fehl, außer du setzt explizit
`FCC_ALLOW_NO_PROVIDER_SMOKE=1`.

## Targets

Standard-Targets senden keine echten Bot-Nachrichten und laden keine Voice-Backends:

| Target | Produktszenarien | Erforderliche Umgebung |
| --- | --- | --- |
| `api` | messages, count_tokens full payload, errors, `/stop`, optimizations | konfigurierter Provider nur für Streaming-Messages |
| `auth` | x-api-key, bearer, anthropic-auth-token, invalid/missing auth | keine; Test setzt ein isoliertes Token |
| `cli` | `fcc-init`, Server-Entrypoint, Claude CLI adaptive thinking, Session-Cleanup | Claude-CLI-Binary und Provider nur für echte CLI |
| `clients` | VS Code und JetBrains-Protokoll-Payloads | konfigurierter Provider |
| `config` | Env-Priorität, Removed-Env-Migration, Proxy/Timeouts | keine |
| `extensibility` | Provider-Registry und Platform-Factory-Konstruktion | keine |
| `messaging` | kompletter Fake-Discord/Telegram-Flow, Commands, Trees, Persistenz, Voice-Cancel | keine |
| `providers` | Multi-Turn-Text, adaptive-thinking-Historie, Tools, Disconnect, Fehler | konfigurierte Provider, optional `FCC_SMOKE_MODEL_*` |
| `tools` | erzwungene `tool_use`- und `tool_result`-Fortsetzung | Tool-fähiger konfigurierter Provider |
| `rate_limit` | Disconnect-Cleanup und Folge-Request | konfigurierter Provider |
| `lmstudio` | lokales `/models` plus natives `/messages` über Proxy | laufender LM-Studio-Server |
| `llamacpp` | lokales `/models` plus natives `/messages` über Proxy | laufender llama-server |
| `ollama` | lokales `/api/tags` plus native Anthropic-Messages über Proxy | laufender Ollama-Server |

Schwere/seiteneffektreiche Targets sind opt-in:

| Target | Produktszenarien | Erforderliche Umgebung |
| --- | --- | --- |
| `nvidia_nim_cli` | Claude-Code-CLI-Feature-Matrix über NIM-Modelle | `NVIDIA_NIM_API_KEY`, Claude CLI |
| `openrouter_free_cli` | Claude-Code-CLI-Feature-Matrix über OpenRouter-Free-Modelle | `OPENROUTER_API_KEY`, Claude CLI |
| `telegram` | getMe, send, edit, delete, optional manueller Inbound | Token und Chat/User-ID |
| `discord` | Channel-Zugriff, send, edit, delete, optional manueller Inbound | Token und Channel-ID |
| `voice` | erzeugte WAV über lokales Whisper oder NVIDIA-NIM-Transkription | `VOICE_NOTE_ENABLED=true`, `FCC_SMOKE_RUN_VOICE=1` |

## Beispiele

```powershell
$env:FCC_LIVE_SMOKE = "1"
$env:FCC_SMOKE_PROVIDER_MATRIX = "open_router,nvidia_nim,deepseek,lmstudio,llamacpp,ollama"
uv run pytest smoke/product -n 0 -s --tb=short
```

```powershell
$env:FCC_LIVE_SMOKE = "1"
$env:FCC_SMOKE_TARGETS = "ollama"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
uv run pytest smoke/prereq smoke/product -n 0 -s --tb=short
```

```powershell
$env:FCC_LIVE_SMOKE = "1"
$env:FCC_SMOKE_TARGETS = "telegram,discord,voice"
$env:FCC_SMOKE_RUN_VOICE = "1"
uv run pytest smoke/product -n 0 -s --tb=short
```

```powershell
$env:FCC_LIVE_SMOKE = "1"
$env:FCC_SMOKE_TARGETS = "nvidia_nim_cli"
$env:FCC_SMOKE_NIM_MODELS = "z-ai/glm-5.1,moonshotai/kimi-k2.6,minimaxai/minimax-m2.7,nvidia/nemotron-3-super-120b-a12b,deepseek-ai/deepseek-v4-pro,deepseek-ai/deepseek-v4-flash"
uv run pytest smoke/product -n 0 -s --tb=short
```

```powershell
$env:FCC_LIVE_SMOKE = "1"
$env:FCC_SMOKE_TARGETS = "openrouter_free_cli"
$env:FCC_SMOKE_OPENROUTER_FREE_MODELS = "nvidia/nemotron-3-super-120b-a12b:free,openai/gpt-oss-120b:free,minimax/minimax-m2.5:free,inclusionai/ring-2.6-1t:free,poolside/laguna-m.1:free"
uv run pytest smoke/product -n 0 -s --tb=short
```

```powershell
$env:FCC_LIVE_SMOKE = "1"
$env:FCC_SMOKE_TARGETS = "messaging,config,extensibility"
uv run pytest smoke/product -n 0 -s --tb=short
```

## Umgebung

- `FCC_ENV_FILE`: expliziter dotenv-Pfad für Startup-/Konfigurationsszenarien.
- `FCC_LIVE_SMOKE=1`: aktiviert Live-Smoke-Ausführung.
- `FCC_ALLOW_NO_PROVIDER_SMOKE=1`: erlaubt No-Provider-Live-Smoke für Harness-Arbeit.
- `FCC_SMOKE_TARGETS`: comma-separierte Targets oder `all`.
- `FCC_SMOKE_PROVIDER_MATRIX`: comma-separierte Provider-Präfixe, die erforderlich sind.
- `FCC_SMOKE_MODEL_NVIDIA_NIM`, `FCC_SMOKE_MODEL_OPEN_ROUTER`,
  `FCC_SMOKE_MODEL_MISTRAL`, `FCC_SMOKE_MODEL_MISTRAL_CODESTRAL`,
  `FCC_SMOKE_MODEL_DEEPSEEK`, `FCC_SMOKE_MODEL_KIMI`,
  `FCC_SMOKE_MODEL_WAFER`, `FCC_SMOKE_MODEL_OPENCODE`, `FCC_SMOKE_MODEL_OPENCODE_GO`,
  `FCC_SMOKE_MODEL_ZAI`, `FCC_SMOKE_MODEL_FIREWORKS`, `FCC_SMOKE_MODEL_GEMINI`,
  `FCC_SMOKE_MODEL_GROQ`, `FCC_SMOKE_MODEL_CEREBRAS`,
  `FCC_SMOKE_MODEL_LMSTUDIO`,
  `FCC_SMOKE_MODEL_LLAMACPP`, `FCC_SMOKE_MODEL_OLLAMA`: optionale Smoke-Modell-Overrides
  je Provider. Werte können das Provider-Präfix enthalten oder nur den Modellnamen.
- `FCC_SMOKE_NIM_MODELS`: optionale comma-separierte NVIDIA-NIM-CLI-Matrixmodelle,
  die den Standard-Charakterisierungssatz ersetzen.
- `FCC_SMOKE_NIM_EXTRA_MODELS`: optionale comma-separierte NVIDIA-NIM-CLI-Matrixmodelle,
  die zum Standard- oder Ersatzsatz hinzugefügt werden.
- `FCC_SMOKE_OPENROUTER_FREE_MODELS`: optionale comma-separierte OpenRouter-Free-CLI-Matrixmodelle,
  die den Standard-Charakterisierungssatz ersetzen.
- `FCC_SMOKE_OPENROUTER_FREE_EXTRA_MODELS`: optionale comma-separierte OpenRouter-Free-CLI-Matrixmodelle,
  die zum Standard- oder Ersatzsatz hinzugefügt werden.
- `FCC_SMOKE_TIMEOUT_S`: Timeout pro Request/Subprozess, Standard `45`.
- `FCC_SMOKE_CLAUDE_BIN`: Name der Claude-CLI-Executable, Standard `claude`.
- `FCC_SMOKE_TELEGRAM_CHAT_ID`: Telegram-Chat/User-ID für send/edit/delete.
- `FCC_SMOKE_DISCORD_CHANNEL_ID`: Discord-Channel-ID für send/edit/delete.
- `FCC_SMOKE_INTERACTIVE=1`: aktiviert manuelle Telegram/Discord-Inbound-Checks.
- `FCC_SMOKE_RUN_VOICE=1`: erlaubt Laden/Ausführen von Voice-Transkriptions-Backends.

## Windows / verschachteltes `uv run`

Führe Smoke genauso aus wie Tests (`uv run pytest smoke` aus dem Repo). Child-Prozesse
nutzen **denselben Python-Interpreter** wie der Test-Runner, nicht verschachteltes
`uv run`, damit Windows nicht versucht, `free-claude-code.exe` zu ersetzen,
während die Datei gelockt ist.

## Fehlerklassen

Smoke-Artefakte werden in `.smoke-results/` geschrieben und redigieren Env-Werte,
deren Namen `KEY`, `TOKEN`, `SECRET`, `WEBHOOK` oder `AUTH` enthalten.

- `missing_env`: erforderliche Credentials, Binary, Provider-Config, lokaler Server
  oder Opt-in-Flag fehlt.
- `upstream_unavailable`: ein echter Provider, eine Bot-API oder ein lokaler
  Model-Server ist nicht erreichbar.
- `probe_timeout`: der Smoke-Treiber hat das Target erreicht, aber CLI/Probe wurde
  nicht innerhalb des Smoke-Timeouts abgeschlossen.
- `product_failure`: die App hat das Szenario akzeptiert, aber die falsche Form
  zurückgegeben, ist abgestürzt, hat State geleakt oder den Produktvertrag verletzt.
- `harness_bug`: der Smoke-Test oder Treiber hat eine ungültige Annahme getroffen.
- `target_disabled`: übersprungen, weil `FCC_SMOKE_TARGETS` bewusst ein anderes
  Target ausgewählt hat.

`product_failure` und `harness_bug` sind Fehler. `missing_env`,
`upstream_unavailable` und `probe_timeout` sind Skips, außer der Nutzer hat einen
Provider explizit in `FCC_SMOKE_PROVIDER_MATRIX` ausgewählt; dann führen
ausgewählte-aber-fehlende Provider zu Fehlern.
