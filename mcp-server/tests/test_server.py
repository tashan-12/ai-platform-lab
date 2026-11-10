import unittest

import _bootstrap  # noqa: F401

try:
    import mcp  # noqa: F401

    HAS_MCP = True
except ImportError:  # mcp 未安装时跳过，保证核心测试零依赖可跑
    HAS_MCP = False


@unittest.skipUnless(HAS_MCP, "需要安装 mcp 才能验证协议接线")
class ServerWiringTest(unittest.TestCase):
    def test_three_tools_registered(self) -> None:
        from ai_lab_mcp import server

        names = sorted(tool.name for tool in server.mcp._tool_manager.list_tools())
        self.assertEqual(names, ["read_file", "run_test", "search_issues"])

    def test_mcp_signature_matches_registry(self) -> None:
        """防止 server.py 的 MCP 签名和 registry 的工具定义漂移。"""

        import inspect

        from ai_lab_mcp import server

        for spec in server.registry.specs():
            func = getattr(server, spec.name)
            self.assertEqual(
                list(inspect.signature(func).parameters),
                [param.name for param in spec.params],
                msg=f"{spec.name} 的 MCP 签名与 registry 定义不一致",
            )

    def test_tool_errors_are_structured(self) -> None:
        from ai_lab_mcp import server

        payload = server.read_file("../outside.txt")
        self.assertIn('"ok": false', payload)
        self.assertIn("PathEscapeError", payload)


if __name__ == "__main__":
    unittest.main()
