import sys
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

try:
    import langgraph  # noqa: F401

    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

from ai_lab_mcp.config import Settings

BAD_SOURCE = 'import os\npassword = "hunter2hunter2"\nos.system("ls")\n'
PY = Path(sys.executable).name


@unittest.skipUnless(HAS_LANGGRAPH, "需要安装 langgraph 才能跑图")
class GraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "bad.py").write_text(BAD_SOURCE, encoding="utf-8")
        (self.root / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.settings = Settings(workspace_root=self.root, allowed_commands=(PY,))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, targets: list[str]) -> dict:
        from ai_lab_agent.graph import build_graph

        graph = build_graph(self.settings)
        return graph.invoke(
            {"goal": "scan", "targets": targets, "attempts": 0, "max_attempts": 2}
        )

    def test_end_to_end_on_bad_file(self) -> None:
        final = self._run(["bad.py"])
        self.assertEqual(final["status"], "done")
        self.assertIn("已证实 2", final["report"])
        self.assertEqual(len(final["verified"]), 2)

    def test_clean_file_skips_verify(self) -> None:
        final = self._run(["clean.py"])
        self.assertEqual(final["status"], "done")
        self.assertNotIn("verified", final)
        self.assertIn("没有命中任何规则", final["report"])

    def test_retrieve_is_noop_without_index(self) -> None:
        final = self._run(["bad.py"])
        # 工作区里没有 rag-index.json，检索环节应安静返回空列表
        self.assertEqual(final.get("references"), [])

    def test_missing_file_still_produces_report(self) -> None:
        final = self._run(["nope.py"])
        self.assertEqual(final["status"], "done")
        self.assertIn("没有命中任何规则", final["report"])


if __name__ == "__main__":
    unittest.main()
