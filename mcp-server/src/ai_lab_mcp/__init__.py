"""ai-platform-lab 的 MCP 工具服务。

设计要点：核心逻辑（安全校验 / 文件读取 / 命令执行 / issue 检索）不依赖 mcp 包，
只有 server.py 负责协议接线，这样单元测试可以零依赖运行。
"""

__version__ = "0.1.0"
