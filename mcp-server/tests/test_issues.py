import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_mcp.config import Settings
from ai_lab_mcp.issues import load_issues, search_issues


class SearchIssuesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        data = [
            {"id": "A-1", "title": "分表批量写入超时", "body": "insert 486 次", "status": "closed", "tags": ["分表"]},
            {"id": "A-2", "title": "ThreadLocal 串味", "body": "分表缓存未清理", "status": "open", "tags": ["并发"]},
            {"id": "A-3", "title": "沙箱实例泄漏", "body": "未回收", "status": "open", "tags": ["Agent"]},
        ]
        self.issues_path = self.root / "issues.json"
        self.issues_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.settings = Settings(workspace_root=self.root, issues_path=self.issues_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load(self) -> None:
        self.assertEqual(len(load_issues(self.settings)), 3)

    def test_search_hits_title_first(self) -> None:
        results = search_issues(self.settings, "分表", limit=5)
        self.assertEqual(results[0]["id"], "A-1")
        self.assertGreater(len(results), 0)

    def test_limit_honored(self) -> None:
        results = search_issues(self.settings, "分表", limit=1)
        self.assertEqual(len(results), 1)

    def test_no_match(self) -> None:
        self.assertEqual(search_issues(self.settings, "完全无关的词"), [])

    def test_missing_file(self) -> None:
        settings = Settings(workspace_root=self.root, issues_path=self.root / "nope.json")
        with self.assertRaises(FileNotFoundError):
            search_issues(settings, "分表")


if __name__ == "__main__":
    unittest.main()
