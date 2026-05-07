# Free Claude Code(中文)

把 Claude Code 的 Anthropic API 流量路由到你自选的 LLM 后端:OpenAI 兼容网关、原生 Anthropic、NVIDIA NIM、OpenRouter、DeepSeek、Kimi、LM Studio、llama.cpp、Ollama。客户端协议保持稳定,上游模型任你挑。

> 这是中文版快速上手文档,重点说明通用 `openai` / `anthropic` provider 的配置。完整英文文档见 [README.md](README.md)。

## 能做什么

- **通用 OpenAI 兼容 provider**:一个 `OPENAI_BASE_URL` + `OPENAI_API_KEY` 就能接 SiliconFlow、DashScope、OneAPI、vLLM、LocalAI、LM Studio OpenAI 模式、llama.cpp OpenAI 模式等任意 `POST /chat/completions` 服务。
- **通用 Anthropic 兼容 provider**:一个 `ANTHROPIC_UPSTREAM_BASE_URL` + `ANTHROPIC_UPSTREAM_API_KEY` 能接官方 Anthropic、DeepSeek `/anthropic`、LM Studio Anthropic 模式等 `POST /v1/messages` SSE 服务。
- 原有 7 个 vendor(`nvidia_nim/` `open_router/` `deepseek/` `kimi/` `lmstudio/` `llamacpp/` `ollama/`)全部保留,可混用。
- Claude Code `/model` 选单直通代理 `/v1/models`。
- 流式、工具调用、thinking block、token 用量的协议转换。
- 可选 Discord / Telegram 远程对话 bot 和语音转写。

## 快速上手(4 步)

### 1. 安装 uv 和 Python 3.14

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv self update
uv python install 3.14
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv self update
uv python install 3.14
```

外加已安装的 [Claude Code](https://github.com/anthropics/claude-code)。

### 2. 克隆并创建 .env

```bash
git clone https://github.com/Alishahryar1/free-claude-code.git
cd free-claude-code
cp .env.example .env
```

### 3. 配置上游(挑一种)

编辑 `.env`,按需取一段填入。

#### A. 通用 OpenAI 兼容(推荐)

```dotenv
OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
OPENAI_API_KEY="sk-your-key"

MODEL="openai/Qwen/Qwen3-Coder-480B-A35B-Instruct"
ANTHROPIC_AUTH_TOKEN="freecc"
```

把 `OPENAI_BASE_URL` 指向任何一家 OpenAI 兼容网关。常见值:

| 服务 | `OPENAI_BASE_URL` |
| --- | --- |
| 官方 OpenAI | `https://api.openai.com/v1` |
| SiliconFlow 硅基流动 | `https://api.siliconflow.cn/v1` |
| 阿里云百炼 (DashScope) | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 字节火山方舟 | `https://ark.cn-beijing.volces.com/api/v3` |
| DeepSeek OpenAI 模式 | `https://api.deepseek.com/v1` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` |
| 百川 | `https://api.baichuan-ai.com/v1` |
| OneAPI / new-api 自建 | `http://your-host:3000/v1` |
| 本地 vLLM / LocalAI | `http://localhost:8000/v1` |
| LM Studio(OpenAI 模式) | `http://localhost:1234/v1` |

`MODEL` 的语法是 `openai/<上游模型名>`,模型名原样传给上游。

#### B. 通用 Anthropic 原生

```dotenv
ANTHROPIC_UPSTREAM_BASE_URL="https://api.anthropic.com"
ANTHROPIC_UPSTREAM_API_KEY="sk-ant-xxx"

MODEL="anthropic/claude-opus-4-5"
ANTHROPIC_AUTH_TOKEN="freecc"
```

适用的上游:

| 服务 | `ANTHROPIC_UPSTREAM_BASE_URL` |
| --- | --- |
| 官方 Anthropic | `https://api.anthropic.com` |
| DeepSeek Anthropic 端点 | `https://api.deepseek.com/anthropic` |
| LM Studio(Anthropic 模式) | `http://localhost:1234` |
| 自建 Anthropic 代理 | `http://your-host/...` |

> **注意**:`ANTHROPIC_UPSTREAM_*` 和 `ANTHROPIC_AUTH_TOKEN` 是两回事。前者是代理向 **上游** 请求时用的凭据;后者是 Claude Code 向 **本代理** 请求时要通过的入站 token。

#### C. 混合路由(按模型分发)

让 Opus 走 Anthropic 官方,Sonnet 走国内某家 OpenAI 兼容网关,Haiku 走本地模型:

```dotenv
OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
OPENAI_API_KEY="sk-sf-xxx"

ANTHROPIC_UPSTREAM_BASE_URL="https://api.anthropic.com"
ANTHROPIC_UPSTREAM_API_KEY="sk-ant-xxx"

LM_STUDIO_BASE_URL="http://localhost:1234/v1"

MODEL_OPUS="anthropic/claude-opus-4-5"
MODEL_SONNET="openai/deepseek-ai/DeepSeek-V3.1"
MODEL_HAIKU="lmstudio/qwen3-30b-a3b"
MODEL="openai/Qwen/Qwen3-Coder-480B-A35B-Instruct"
```

`MODEL_OPUS` / `MODEL_SONNET` / `MODEL_HAIKU` 空值时落到 `MODEL`。

### 4. 启动代理并打开 Claude Code

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8082
```

打开另一个终端,指定代理后启动 Claude Code:

```bash
ANTHROPIC_AUTH_TOKEN="freecc" \
ANTHROPIC_BASE_URL="http://localhost:8082" \
CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1 \
claude
```

Windows PowerShell:

```powershell
$env:ANTHROPIC_AUTH_TOKEN="freecc"
$env:ANTHROPIC_BASE_URL="http://localhost:8082"
$env:CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY="1"
claude
```

> `ANTHROPIC_BASE_URL` **不要**加 `/v1`。`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` 让 Claude Code 在 `/model` 里能看到代理发现的上游模型。

## Model 路由规则

`MODEL` 的格式:

```text
<provider_id>/<上游模型名>
```

有效的 `provider_id`:

| id | transport | 环境变量 |
| --- | --- | --- |
| `openai` | OpenAI `/chat/completions` | `OPENAI_BASE_URL` + `OPENAI_API_KEY` |
| `anthropic` | Anthropic `/v1/messages` | `ANTHROPIC_UPSTREAM_BASE_URL` + `ANTHROPIC_UPSTREAM_API_KEY` |
| `nvidia_nim` | OpenAI chat | `NVIDIA_NIM_API_KEY` |
| `kimi` | OpenAI chat | `KIMI_API_KEY` |
| `open_router` | Anthropic Messages | `OPENROUTER_API_KEY` |
| `deepseek` | Anthropic Messages | `DEEPSEEK_API_KEY` |
| `lmstudio` | Anthropic Messages | `LM_STUDIO_BASE_URL` |
| `llamacpp` | Anthropic Messages | `LLAMACPP_BASE_URL` |
| `ollama` | Anthropic Messages | `OLLAMA_BASE_URL` |

解析优先级:

1. Claude Code 直接传入 `provider_id/model` 格式的模型名 → 直接用这条
2. 否则按 Opus/Sonnet/Haiku 关键字匹配对应的 `MODEL_OPUS` / `MODEL_SONNET` / `MODEL_HAIKU`
3. 都不匹配 → 落到 `MODEL`

## 其他客户端接入

### VS Code 扩展

在 settings.json 加:

```json
"claudeCode.environmentVariables": [
  { "name": "ANTHROPIC_BASE_URL", "value": "http://localhost:8082" },
  { "name": "ANTHROPIC_AUTH_TOKEN", "value": "freecc" },
  { "name": "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY", "value": "1" }
]
```

重载扩展。首次若出现登录页,过一次就好,之后走代理。

### JetBrains ACP

编辑:
- Windows: `C:\Users\%USERNAME%\AppData\Roaming\JetBrains\acp-agents\installed.json`
- Linux / macOS: `~/.jetbrains/acp.json`

在 `acp.registry.claude-acp` 下加 env:

```json
"env": {
  "ANTHROPIC_BASE_URL": "http://localhost:8082",
  "ANTHROPIC_AUTH_TOKEN": "freecc",
  "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1"
}
```

重启 IDE。

## 代理/超时/限流

```dotenv
# 每 provider 独立代理(支持 http 和 socks5)
OPENAI_PROXY=""
ANTHROPIC_UPSTREAM_PROXY=""
NVIDIA_NIM_PROXY=""
OPENROUTER_PROXY=""
LMSTUDIO_PROXY=""
LLAMACPP_PROXY=""
KIMI_PROXY=""

# 全局限流(所有 provider 共享)
PROVIDER_RATE_LIMIT=40          # 窗口内最多请求数
PROVIDER_RATE_WINDOW=60         # 窗口(秒)
PROVIDER_MAX_CONCURRENCY=5      # 最大并发连接数

# HTTP 超时(秒)
HTTP_READ_TIMEOUT=300
HTTP_WRITE_TIMEOUT=60
HTTP_CONNECT_TIMEOUT=60
```

免费 / 共享的上游建议低限流;本地 vLLM / LM Studio 按机器性能调高。

## Thinking / 推理输出

```dotenv
ENABLE_MODEL_THINKING=true
ENABLE_OPUS_THINKING=
ENABLE_SONNET_THINKING=
ENABLE_HAIKU_THINKING=
```

空值继承 `ENABLE_MODEL_THINKING`。对 GLM、DeepSeek、Claude 等推理模型开启,转写成 Claude thinking block 给客户端。

## 常见问题

**Claude Code 报 `undefined ... input_tokens` 或响应格式错**

- 确认 `ANTHROPIC_BASE_URL` 是 `http://localhost:8082`,**不带** `/v1`
- 看 `server.log` 有没有上游 4xx/5xx
- 更新到最新 commit(旧版本 SSE 元数据有已知 bug)

**某个模型在一家 provider 能用、换家不行**

工具调用 (tools) 的支持依赖上游模型实现。国产 OpenAI 兼容网关上相同模型的 tool-call 行为也可能不同。换模型或换上游再试。

**`OPENAI_API_KEY` 和 Claude Code 会冲突吗?**

不会。`OPENAI_API_KEY` 是本代理 **向上游** 用的 key,和 Claude Code 无关。Claude Code 给代理的是 `ANTHROPIC_AUTH_TOKEN`,在两边保持一致即可。

**本地 llama.cpp / LM Studio 返回 400**

- llama.cpp 启动时 `--ctx-size` 太小会拒绝正常请求,调大
- 确认模型和运行时支持工具调用
- LM Studio / llama.cpp 的 base URL 带 `/v1`;Ollama 不带

## 工作原理

```text
Claude Code CLI / IDE
        │  Anthropic Messages API
        ▼
Free Claude Code 代理 (:8082)
        │  provider 转换 / 流式适配
        ▼
OpenAI 兼容网关 / Anthropic / NIM / OpenRouter / DeepSeek / Kimi / LM Studio / llama.cpp / Ollama
```

- FastAPI 暴露 `/v1/messages` `/v1/messages/count_tokens` `/v1/models`
- `MODEL` 字段路由到 opus / sonnet / haiku 或 fallback
- `openai` / `nvidia_nim` / `kimi` 走 OpenAI chat 翻译成 Anthropic SSE
- `anthropic` / `open_router` / `deepseek` / `lmstudio` / `llamacpp` / `ollama` 走 Anthropic Messages 直通
- thinking block、tool call、token usage、错误语义统一处理成 Claude 客户端期待的形状

## 开发

```bash
uv run ruff format
uv run ruff check
uv run ty check
uv run pytest
```

CI 会按这个顺序跑一遍。

包脚本:
- `free-claude-code`:以配置好的 host/port 启动代理
- `fcc-init`:在 `~/.config/free-claude-code/.env` 生成模板

## 许可证

MIT License。详见 [LICENSE](LICENSE)。
