import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_rag.config import RagConfig
from ai_lab_rag.loader import load_corpus


class LoaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "a.md").write_text("# A\n", encoding="utf-8")
        (self.root / "skip.log").write_text("x", encoding="utf-8")
        (self.root / ".venv").mkdir()
        (self.root / ".venv" / "hidden.md").write_text("# H\n", encoding="utf-8")
        (self.root / "big.md").write_text("x" * 200, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_filters_suffix_and_dirs(self) -> None:
        docs, _ = load_corpus(self.root, RagConfig())
        paths = {doc.path for doc in docs}
        self.assertIn("a.md", paths)
        self.assertNotIn("skip.log", paths)
        self.assertNotIn(".venv/hidden.md", paths)

    def test_size_limit_warns(self) -> None:
        docs, warnings = load_corpus(self.root, RagConfig(max_file_bytes=50))
        self.assertNotIn("big.md", {doc.path for doc in docs})
        self.assertTrue(any("big.md" in item for item in warnings))

    def test_hash_is_stable(self) -> None:
        first, _ = load_corpus(self.root, RagConfig())
        second, _ = load_corpus(self.root, RagConfig())
        self.assertEqual(
            {doc.path: doc.sha1 for doc in first},
            {doc.path: doc.sha1 for doc in second},
        )

    def test_missing_corpus(self) -> None:
        with self.assertRaises(NotADirectoryError):
            load_corpus(self.root / "nope", RagConfig())


if __name__ == "__main__":
    unittest.main()
