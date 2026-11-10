# mcp-server

给 Agent 用的**工具层**：把"读文件 / 跑测试 / 查问题库"三件事做成标准 MCP 工具，
任何支持 MCP 的客户端（Claude Desktop、Cursor、自研 Agent）都能直接调用。

```text
   Agent (Claude / Cursor / LangGraph)
        │  MCP (stdio)
        ▼
   ┌─────────────────┐
   │   mcp-server    │
   └────┬───┬───┬────┘
        │   │   └── search_issues  → config/issues.json
        │   └────── run_test       → 白名单命令 + 超时 + 输出截断
        └────────── read_file      → 工作区内只读 + 禁密钥
```

## 三个工具

| 工具 | 参数 | 返回 | 关键约束 |
|---|---|---|---|
| `read_file` | `path`, `max_bytes?` | 文件内容 + 大小 + 是否截断 | 不得越出工作区；禁 `.env` / 证书 / `.git`；默认限 1MB |
| `run_test` | `command`, `cwd?` | 退出码、stdout、stderr、耗时、是否超时 | 仅白名单命令；不经过 shell；有超时；输出截断 |
| `search_issues` | `query`, `limit?` | 命中的 issue 列表（带相关度） | 只读本地 JSON；按标题 > 正文 > 标签加权 |

失败时统一返回结构化错误，模型能自己判断要不要重试：

```json
{"ok": false, "error": "PathEscapeError", "message": "路径越界：... 不在工作区内"}
```

## 安全模型（四条，缺一不可）

1. **路径收敛**：先 `resolve()` 再比较，同时挡住 `..` 越级和**符号链接逃逸**；
2. **敏感文件拒绝**：按前缀（`.env`）、后缀（`.pem/.key/.p12`）、目录片段（`.git/.ssh/node_modules`）三重拦截；
3. **命令白名单**：只允许 `pytest/python/python3/npm/pnpm/go/make`，且用 `shlex` 切分、`shell=False` 执行，杜绝命令注入；
4. **环境变量最小化**：子进程只继承 `PATH/HOME/LANG/VIRTUAL_ENV/TMPDIR`，不会把你的密钥带进去。

> 这四条都有对应的单元测试，改代码后跑一遍就知道有没有漏。

## 进程内调用（给 graph-agent 用）

工具定义收敛在 `registry.py`，所以除了 MCP，也能在**同一个进程里直接调**，不用起子进程、不走 stdio：

```python
from ai_lab_mcp.config import load_settings
from ai_lab_mcp.registry import build_registry

registry = build_registry(load_settings())

registry.names()                                  # ['read_file', 'run_test', 'search_issues']
registry.call("run_test", command="pytest -q")    # {'ok': True, 'exit_code': 0, ...}
registry.call("read_file", path="README.md")      # {'ok': True, 'content': '...', ...}
registry.call("read_file", path="../x")           # {'ok': False, 'error': 'PathEscapeError', ...}

# 直接喂给 LLM 的函数调用
tools = registry.openai_tools()
```

三个入口共用同一份定义，不存在"改了 MCP 忘了改 Agent"的问题：

```text
        registry.py（唯一定义源）
         │            │            │
     server.py     graph-agent    （未来）HTTP
      MCP stdio    进程内调用       适配器
```

有一条测试专门盯着这件事：`test_mcp_signature_matches_registry` —— 一旦 `server.py` 的函数签名和 registry 的参数对不上，测试立刻红。

## 安装

需要 Python 3.11+。

```bash
cd mcp-server

# 方式一：uv（推荐）
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 方式二：pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## 运行

```bash
# 作为 MCP 服务（stdio），由客户端拉起
LAB_WORKSPACE_ROOT=/path/to/your/repo ai-lab-mcp

# 或者直接跑模块
LAB_WORKSPACE_ROOT=/path/to/your/repo python -m ai_lab_mcp.server
```

## 接入 Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "ai-platform-lab": {
      "command": "/绝对路径/到/.venv/bin/ai-lab-mcp",
      "env": {
        "LAB_WORKSPACE_ROOT": "/你要让它读的目录",
        "LAB_ALLOWED_COMMANDS": "pytest,python3",
        "LAB_COMMAND_TIMEOUT": "60"
      }
    }
  }
}
```

重启 Claude Desktop，在对话框右下角能看到工具图标即为接入成功。

## 接入 Cursor

`~/.cursor/mcp.json`（或在 Cursor 设置里添加）：

```json
{
  "mcpServers": {
    "ai-platform-lab": {
      "command": "/绝对路径/到/.venv/bin/ai-lab-mcp",
      "env": { "LAB_WORKSPACE_ROOT": "/你要让它读的目录" }
    }
  }
}
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LAB_WORKSPACE_ROOT` | 当前目录 | 工具可访问的根目录，越界一律拒绝 |
| `LAB_ALLOWED_COMMANDS` | `pytest,python,python3,npm,pnpm,go,make` | 逗号分隔的命令白名单 |
| `LAB_MAX_FILE_BYTES` | `1000000` | 单次读取上限 |
| `LAB_MAX_OUTPUT_CHARS` | `20000` | stdout/stderr 截断阈值 |
| `LAB_COMMAND_TIMEOUT` | `120` | 单条命令超时（秒） |
| `LAB_ISSUES_PATH` | `<root>/config/issues.json` | 问题库文件路径 |

## 测试

```bash
# 不需要安装任何依赖：核心逻辑与 mcp 包解耦，测试用标准库
python -m unittest discover -s tests -v
```

当前 38 个用例，覆盖：路径越界（含符号链接）、敏感文件、命令白名单、超时、输出截断、检索排序、注册表调度与签名一致性。

```text
tests/test_security.py   9 个   路径/符号链接/禁用规则/白名单
tests/test_files.py      6 个   正常读/截断/目录/缺失/密钥/越界
tests/test_runner.py     5 个   正常执行/非零退出/拒命令/超时/越界 cwd
tests/test_issues.py     5 个   加载/命中排序/limit/无结果/文件缺失
tests/test_registry.py   8 个   名称/调度/未知工具/结构化错误/JSON/LLM schema
tests/test_server.py     3 个   MCP 三工具注册/签名一致性/错误结构（未装 mcp 时自动跳过）
```

## 一个刻意的设计取舍

业务逻辑（`security.py` / `files.py` / `runner.py` / `issues.py`）**不依赖 mcp 包**，
只有 `server.py` 做协议接线。

好处是：换 MCP SDK 版本、换 Agent 框架、甚至把它包成 HTTP 服务，核心代码都不用动；
副作用是：单元测试可以零依赖跑，CI 里不用先装一堆东西。

这个取舍记录在 [ADR-001](../docs/adr/0001-tools-via-mcp.md) 里。
