import unittest

import _bootstrap  # noqa: F401
from ai_lab_rag.chunker import chunk_markdown
from ai_lab_rag.config import RagConfig

CFG = RagConfig(max_chars=200, min_chars=20, hard_overlap=20)

SAMPLE = """# 标题一

第一段正文，讲一些背景。

## 子标题

第二段正文，稍微长一点点，用来测试切分是否按标题走。

### 更深一层

第三段。
"""


class ChunkerTest(unittest.TestCase):
    def test_splits_by_heading(self) -> None:
        chunks = chunk_markdown("a.md", SAMPLE, CFG)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].heading_path, ("标题一",))
        self.assertIn(("标题一", "子标题"), [chunk.heading_path for chunk in chunks])

    def test_ids_are_stable_and_ordered(self) -> None:
        chunks = chunk_markdown("a.md", SAMPLE, CFG)
        self.assertEqual([chunk.ordinal for chunk in chunks], list(range(len(chunks))))
        self.assertTrue(all(chunk.id.startswith("a.md#") for chunk in chunks))

    def test_code_fence_not_split(self) -> None:
        text = "# A\n\n" + "x" * 150 + "\n\n" + chr(96) * 3 + "python\n" + "y = 1\n" * 60 + chr(96) * 3 + "\n"
        chunks = chunk_markdown("b.md", text, RagConfig(max_chars=120, min_chars=10))
        block = [chunk for chunk in chunks if "y = 1" in chunk.text]
        self.assertTrue(block, "代码块应至少出现在一个块里")
        # 代码块内的内容不应被切成多块
        self.assertEqual(sum(1 for chunk in chunks if "y = 1" in chunk.text), 1)

    def test_long_paragraph_hard_split(self) -> None:
        text = "# A\n\n" + "字" * 900 + "\n"
        chunks = chunk_markdown("c.md", text, RagConfig(max_chars=200, min_chars=10, hard_overlap=20))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.text) <= 210 for chunk in chunks))

    def test_empty_input(self) -> None:
        self.assertEqual(chunk_markdown("d.md", "   \n\n", CFG), [])

    def test_small_tail_merged(self) -> None:
        text = "# A\n\n主体内容足够长一些吧至少超过二十个字符才不会被并掉。\n\n短尾。\n"
        chunks = chunk_markdown("e.md", text, RagConfig(max_chars=400, min_chars=50))
        self.assertEqual(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
