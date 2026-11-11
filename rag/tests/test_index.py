import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_rag.config import RagConfig
from ai_lab_rag.index import Index, build_index


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class IndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        write(self.root, "a.md", "# A\n\n关于增量索引的说明，足够长一些以便成块。\n")
        write(self.root, "sub/b.md", "# B\n\n另一篇文档，讲检索与重排。\n")
        self.cfg = RagConfig(max_chars=400, min_chars=10)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_build_counts(self) -> None:
        index, stats = build_index(self.root, self.cfg)
        self.assertEqual(stats.docs_total, 2)
        self.assertEqual(stats.docs_rebuilt, 2)
        self.assertGreaterEqual(len(index.chunks), 2)
        self.assertIn("增量", index.postings)

    def test_incremental_reuses_unchanged(self) -> None:
        first, _ = build_index(self.root, self.cfg)
        second, stats = build_index(self.root, self.cfg, previous=first)
        self.assertEqual(stats.docs_reused, 2)
        self.assertEqual(stats.docs_rebuilt, 0)
        self.assertEqual(len(first.chunks), len(second.chunks))

    def test_incremental_rebuilds_changed(self) -> None:
        first, _ = build_index(self.root, self.cfg)
        write(self.root, "a.md", "# A\n\n内容改过了，现在讲的是分片路由。\n")
        second, stats = build_index(self.root, self.cfg, previous=first)
        self.assertEqual(stats.docs_rebuilt, 1)
        self.assertEqual(stats.docs_reused, 1)
        self.assertIn("分片", second.postings)
        self.assertNotIn("增量", second.postings)

    def test_removed_doc_counted(self) -> None:
        first, _ = build_index(self.root, self.cfg)
        (self.root / "sub" / "b.md").unlink()
        second, stats = build_index(self.root, self.cfg, previous=first)
        self.assertEqual(stats.docs_removed, 1)
        self.assertEqual(len(second.docs), 1)

    def test_save_and_load_roundtrip(self) -> None:
        index, _ = build_index(self.root, self.cfg)
        target = self.root / "idx.json"
        index.save(target)
        loaded = Index.load(target)
        self.assertEqual(len(loaded.chunks), len(index.chunks))
        self.assertEqual(loaded.postings.keys(), index.postings.keys())
        self.assertAlmostEqual(loaded.avg_len, index.avg_len, places=3)

    def test_rebuild_flag_ignores_previous(self) -> None:
        first, _ = build_index(self.root, self.cfg)
        _, stats = build_index(self.root, self.cfg, previous=first, rebuild=True)
        self.assertEqual(stats.docs_rebuilt, 2)


if __name__ == "__main__":
    unittest.main()
