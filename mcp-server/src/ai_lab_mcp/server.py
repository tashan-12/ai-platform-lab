"""MCP 服务入口：把三个工具暴露给 Claude Desktop / Cursor / 任意 MCP 客户端。

只做协议接线与错误包装，业务逻辑都在 files / runner / issues 三个模块里，
这样它们可以在没有 mcp 依赖的情况下被单元测试。
"""

from __future__ import annotations

import json

try:  # mcp 2.x：FastMCP 改名为 MCPServer（from mcp.server import MCPServer）
    from mcp.server import MCPServer as _Server
except ImportError:  # mcp 1.x 兼容
    from mcp.server.fastmcp import FastMCP as _Server

from .config import load_settings
from .files import read_text_file as _read_text_file
from .issues import search_issues as _search_issues
from .runner import run_test as _run_test

settings = load_settings()
mcp = _Server("ai-platform-lab")


def _error(exc: Exception) -> str:
    """把异常转成结构化错误返回给模型，而不是让整个会话崩掉。"""

    return json.dumps(
        {"ok": False, "error": type(exc).__name__, "message": str(exc)},
        ensure_ascii=False,
    )


@mcp.tool()
def read_file(path: str, max_bytes: int | None = None) -> str:
    """读取工作区内的文本文件（只读，限制大小，禁止读取密钥与环境变量）。

    Args:
        path: 相对工作区根目录的路径，例如 README.md 或 src/app.py。
        max_bytes: 最多读取的字节数，默认 1000000（1MB）。
    """

    try:
        result = _read_text_file(settings, path, max_bytes=max_bytes)
    except Exception as exc:  # noqa: BLE001 - 统一转成结构化错误
        return _error(exc)
    return json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2)


@mcp.tool()
def run_test(command: str, cwd: str = ".") -> str:
    """在工作区内执行一条命令并返回结果（仅限白名单命令，有超时与输出截断）。

    只允许 pytest / python / python3 / npm / pnpm / go / make 这几类，
    可通过环境变量 LAB_ALLOWED_COMMANDS 覆盖。

    Args:
        command: 完整命令行，例如 "pytest -q tests" 或 "python -m unittest discover"。
        cwd: 相对工作区的工作目录，默认 "."。
    """

    try:
        result = _run_test(settings, command, cwd)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return json.dumps({"ok": True, **result.to_dict()}, ensure_ascii=False, indent=2)


@mcp.tool()
def search_issues(query: str, limit: int = 5) -> str:
    """在本地问题库中检索相关 issue（关键词匹配，按相关度排序）。

    Args:
        query: 关键词，例如 "登录 超时"。
        limit: 最多返回几条，默认 5。
    """

    try:
        results = _search_issues(settings, query, limit)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return json.dumps({"ok": True, "query": query, "results": results}, ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
