import sys
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_agent.nodes import analyze_node, report_node, verify_node
from ai_lab_mcp.config import Settings
from ai_lab_mcp.registry import build_registry

PY = Path(sys.executable).name

BAD_SOURCE = 'import os\npassword = "hunter2hunter2"\nos.system("ls")\n'


class NodesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "bad.py").write_text(BAD_SOURCE, encoding="utf-8")
        (self.root / "good.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.settings = Settings(workspace_root=self.root, allowed_commands=(PY,))
        self.registry = build_registry(self.settings)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_analyze_finds_issues(self) -> None:
        state = analyze_node({"targets": ["bad.py"]}, self.settings, self.registry)
        self.assertEqual(len(state["findings"]), 2)
        self.assertEqual(state["status"], "analyzed")

    def test_analyze_reports_missing_file(self) -> None:
        state = analyze_node({"targets": ["nope.py"]}, self.settings, self.registry)
        self.assertEqual(state["findings"], [])
        self.assertEqual(len(state["errors"]), 1)

    def test_verify_confirms_findings(self) -> None:
        analyzed = analyze_node({"targets": ["bad.py"]}, self.settings, self.registry)
        verified = verify_node(analyzed, self.settings, self.registry)
        self.assertEqual(len(verified["verified"]), 2)
        self.assertTrue(all(item["status"] == "confirmed" for item in verified["verified"]))
        self.assertEqual(verified["attempts"], 1)

    def test_verify_marks_not_found_when_pattern_gone(self) -> None:
        state = {
            "findings": [
                {
                    "id": "SEC001-L1",
                    "rule": "SEC001",
                    "title": "使用 eval 执行动态代码",
                    "severity": "high",
                    "file": "good.py",
                    "line": 1,
                    "snippet": "",
                }
            ]
        }
        verified = verify_node(state, self.settings, self.registry)
        self.assertEqual(verified["verified"][0]["status"], "not_found")

    def test_report_counts(self) -> None:
        analyzed = analyze_node({"targets": ["bad.py"]}, self.settings, self.registry)
        verified = verify_node(analyzed, self.settings, self.registry)
        reported = report_node({**analyzed, **verified}, self.settings, self.registry)
        self.assertIn("已证实 2", reported["report"])
        self.assertIn("## 已证实的问题", reported["report"])
        self.assertEqual(reported["status"], "done")

    def test_report_when_nothing_found(self) -> None:
        reported = report_node({"targets": ["good.py"], "findings": []}, self.settings, self.registry)
        self.assertIn("没有命中任何规则", reported["report"])


if __name__ == "__main__":
    unittest.main()
