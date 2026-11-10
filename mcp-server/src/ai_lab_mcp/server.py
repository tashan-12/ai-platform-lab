"""MCP 服务入口：把 registry 里的工具暴露给 Claude Desktop / Cursor / 任意 MCP 客户端。

这一层只做协议接线：工具的名字、描述、参数、错误包装都在 registry.py 里，
所以同一份定义可以被 MCP（这里）和进程内调用（graph-agent）共用。
"""

from __future__ import annotations

try:  # mcp 2.x：FastMCP 改名为 MCPServer（from mcp.server import MCPServer）
    from mcp.server import MCPServer as _Server
except ImportError:  # mcp 1.x 兼容
    from mcp.server.fastmcp import FastMCP as _Server

from .config import load_settings
from .registry import build_registry

settings = load_settings()
registry = build_registry(settings)
mcp = _Server("ai-platform-lab")


@mcp.tool()
def read_file(path: str, max_bytes: int | None = None) -> str:
    """读取工作区内的文本文件（只读，限制大小，禁止读取密钥与环境变量）。

    Args:
        path: 相对工作区根目录的路径，例如 README.md 或 src/app.py。
        max_bytes: 最多读取的字节数，默认 1000000（1MB）。
    """

    return registry.call_json("read_file", path=path, max_bytes=max_bytes)


@mcp.tool()
def run_test(command: str, cwd: str = ".") -> str:
    """在工作区内执行一条命令并返回结果（仅限白名单命令，有超时与输出截断）。

    只允许 pytest / python / python3 / npm / pnpm / go / make 这几类，
    可通过环境变量 LAB_ALLOWED_COMMANDS 覆盖。

    Args:
        command: 完整命令行，例如 "pytest -q tests" 或 "python -m unittest discover"。
        cwd: 相对工作区的工作目录，默认 "."。
    """

    return registry.call_json("run_test", command=command, cwd=cwd)


@mcp.tool()
def search_issues(query: str, limit: int = 5) -> str:
    """在本地问题库中检索相关 issue（关键词匹配，按相关度排序）。

    Args:
        query: 关键词，例如 "登录 超时"。
        limit: 最多返回几条，默认 5。
    """

    return registry.call_json("search_issues", query=query, limit=limit)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
