import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_mcp.config import Settings
from ai_lab_mcp.files import read_text_file
from ai_lab_mcp.security import PathDeniedError


class ReadFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "hello.txt").write_text("你好，世界", encoding="utf-8")
        (self.root / "big.txt").write_text("a" * 5000, encoding="utf-8")
        (self.root / ".env").write_text("SECRET=1", encoding="utf-8")
        self.settings = Settings(workspace_root=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_reads_text(self) -> None:
        result = read_text_file(self.settings, "hello.txt")
        self.assertEqual(result["content"], "你好，世界")
        self.assertEqual(result["path"], "hello.txt")
        self.assertFalse(result["truncated"])

    def test_truncates_by_max_bytes(self) -> None:
        result = read_text_file(self.settings, "big.txt", max_bytes=10)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["content"]), 10)
        self.assertEqual(result["size"], 5000)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            read_text_file(self.settings, "nope.txt")

    def test_directory_rejected(self) -> None:
        with self.assertRaises(IsADirectoryError):
            read_text_file(self.settings, ".")

    def test_secret_rejected(self) -> None:
        with self.assertRaises(PathDeniedError):
            read_text_file(self.settings, ".env")

    def test_escape_rejected(self) -> None:
        with self.assertRaises(ValueError):
            read_text_file(self.settings, "../outside.txt")


if __name__ == "__main__":
    unittest.main()
