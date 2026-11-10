import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_mcp.config import Settings
from ai_lab_mcp.registry import UnknownToolError, build_registry


class RegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "hello.txt").write_text("hi", encoding="utf-8")
        (self.root / "config").mkdir()
        (self.root / "config" / "issues.json").write_text(
            json.dumps(
                [{"id": "X-1", "title": "分表写入慢", "body": "486 次 insert", "status": "open", "tags": ["分表"]}],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.registry = build_registry(Settings(workspace_root=self.root))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_names(self) -> None:
        self.assertEqual(self.registry.names(), ["read_file", "run_test", "search_issues"])

    def test_call_read_file(self) -> None:
        result = self.registry.call("read_file", path="hello.txt")
        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "hi")

    def test_call_search_issues(self) -> None:
        result = self.registry.call("search_issues", query="分表", limit=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["results"][0]["id"], "X-1")

    def test_unknown_tool(self) -> None:
        with self.assertRaises(UnknownToolError):
            self.registry.call("delete_everything")

    def test_errors_are_structured(self) -> None:
        result = self.registry.call("read_file", path="../secret.txt")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "PathEscapeError")

    def test_call_json_is_valid_json(self) -> None:
        payload = self.registry.call_json("read_file", path="hello.txt")
        self.assertTrue(json.loads(payload)["ok"])

    def test_openai_tool_schema(self) -> None:
        tools = self.registry.openai_tools()
        self.assertEqual(len(tools), 3)
        by_name = {item["function"]["name"]: item["function"] for item in tools}

        read_file = by_name["read_file"]
        self.assertEqual(read_file["parameters"]["required"], ["path"])
        self.assertIn("max_bytes", read_file["parameters"]["properties"])
        self.assertEqual(read_file["parameters"]["properties"]["max_bytes"]["default"], None)


if __name__ == "__main__":
    unittest.main()
