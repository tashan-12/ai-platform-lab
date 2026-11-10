"""工具注册表：让同一份工具定义既能被 MCP 暴露，也能被进程内直接调用。

为什么要这一层：
- server.py 只负责 MCP 协议接线，不该同时承担"工具定义 + 错误包装"两件事；
- graph-agent（LangGraph）需要在不启动子进程、不走 stdio 的情况下调用同样的工具；
- 未来接 HTTP / 别的 Agent 框架时，只要再写一个适配器，工具定义不用改。

所以这里放三样东西：工具的元信息（名字/描述/参数）、执行入口、以及给 LLM 用的 JSON Schema。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .config import Settings
from .files import read_text_file
from .issues import search_issues
from .runner import run_test


@dataclass(frozen=True)
class Param:
    """一个工具参数的元信息。"""

    name: str
    type: str          # JSON Schema 类型：string / integer / number / boolean
    description: str
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class ToolSpec:
    """一个工具的完整定义：元信息 + 执行体。"""

    name: str
    description: str
    params: tuple[Param, ...]
    handler: Callable[..., dict]

    def to_json_schema(self) -> dict:
        """转成 LLM function calling 能直接吃的 schema。"""

        properties: dict[str, Any] = {}
        required: list[str] = []
        for param in self.params:
            properties[param.name] = {"type": param.type, "description": param.description}
            if not param.required:
                properties[param.name]["default"] = param.default
            else:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


class UnknownToolError(KeyError):
    """调用了未注册的工具。"""


class ToolRegistry:
    """进程内工具调度器。"""

    def __init__(self, specs: tuple[ToolSpec, ...]) -> None:
        self._specs: dict[str, ToolSpec] = {spec.name: spec for spec in specs}

    def names(self) -> list[str]:
        return sorted(self._specs)

    def specs(self) -> list[ToolSpec]:
        return [self._specs[name] for name in self.names()]

    def get(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise UnknownToolError(f"未知工具：{name}，可用：{', '.join(self.names())}")
        return self._specs[name]

    def call(self, name: str, **kwargs: Any) -> dict:
        """执行工具并保证返回结构化结果，异常一律转成 ok=false。"""

        spec = self.get(name)
        try:
            payload = spec.handler(**kwargs)
        except Exception as exc:  # noqa: BLE001 - 工具层就该兜住所有异常
            return {"ok": False, "error": type(exc).__name__, "message": str(exc)}

        if isinstance(payload, dict):
            return {"ok": True, **payload}
        return {"ok": True, "result": payload}

    def call_json(self, name: str, **kwargs: Any) -> str:
        """MCP 工具需要的字符串形态。"""

        return json.dumps(self.call(name, **kwargs), ensure_ascii=False, indent=2)

    def openai_tools(self) -> list[dict]:
        """给 LangGraph / 任意 LLM 的函数调用用的工具列表。"""

        return [{"type": "function", "function": spec.to_json_schema()} for spec in self.specs()]


def build_registry(settings: Settings) -> ToolRegistry:
    """按当前配置构建工具集。换配置就重建，不做全局可变状态。"""

    return ToolRegistry(
        (
            ToolSpec(
                name="read_file",
                description="读取工作区内的文本文件（只读、限大小、禁止读取密钥与环境变量）",
                params=(
                    Param("path", "string", "相对工作区根目录的路径，例如 README.md"),
                    Param("max_bytes", "integer", "最多读取的字节数，默认 1000000", required=False, default=None),
                ),
                handler=lambda path, max_bytes=None: read_text_file(
                    settings, path, max_bytes=max_bytes
                ),
            ),
            ToolSpec(
                name="run_test",
                description="在工作区内执行一条白名单命令（pytest / python3 等），返回退出码与输出",
                params=(
                    Param("command", "string", "完整命令行，例如 pytest -q tests"),
                    Param("cwd", "string", "相对工作区的工作目录", required=False, default="."),
                ),
                handler=lambda command, cwd=".": run_test(settings, command, cwd).to_dict(),
            ),
            ToolSpec(
                name="search_issues",
                description="在本地问题库中检索相关 issue（关键词匹配，按相关度排序）",
                params=(
                    Param("query", "string", "关键词，例如 分表 超时"),
                    Param("limit", "integer", "最多返回几条", required=False, default=5),
                ),
                handler=lambda query, limit=5: {
                    "query": query,
                    "results": search_issues(settings, query, limit),
                },
            ),
        )
    )
