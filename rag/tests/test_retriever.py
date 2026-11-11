import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from ai_lab_rag.config import RagConfig
from ai_lab_rag.index import build_index
from ai_lab_rag.retriever import Retriever


class RetrieverTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self._write(
            "adr.md",
            """# ADR-004 工具通道

## 决策

采用双通道：对外走 MCP 协议，对内直接调用 ToolRegistry。

## 后果

多了一层"看起来重复"的抽象，但避免了进程间序列化开销。
""",
        )
        self._write(
            "rag.md",
            """# 检索设计

## 切分

按 Markdown 标题切块，代码块不切断。

## 检索

BM25 与哈希向量按 0.5 加权，再做覆盖率重排。
""",
        )
        self._write(
            "misc.md",
            """# 杂项

这里讲的是完全不相干的内容，关于团餐结算与订单拆分。
""",
        )
        cfg = RagConfig(max_chars=500, min_chars=10)
        index, _ = build_index(self.root, cfg)
        self.retriever = Retriever(index)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_exact_term_hits_right_doc(self) -> None:
        hits = self.retriever.search("ToolRegistry 双通道", k=3)
        self.assertTrue(hits)
        self.assertEqual(hits[0].chunk.doc, "adr.md")

    def test_heading_match_gets_bonus(self) -> None:
        hits = self.retriever.search("检索", k=3)
        self.assertEqual(hits[0].chunk.doc, "rag.md")

    def test_coverage_filled_after_rerank(self) -> None:
        hits = self.retriever.search("BM25 重排", k=3, rerank=True)
        self.assertGreater(hits[0].coverage, 0.0)

    def test_no_rerank_still_returns(self) -> None:
        hits = self.retriever.search("BM25", k=2, rerank=False)
        self.assertTrue(hits)
        self.assertEqual(hits[0].coverage, 0.0)

    def test_empty_query(self) -> None:
        self.assertEqual(self.retriever.search("   "), [])

    def test_irrelevant_query_returns_nothing_or_low(self) -> None:
        hits = self.retriever.search("量子计算 光刻机", k=3)
        self.assertTrue(all(hit.chunk.doc != "misc.md" for hit in hits) or not hits)


if __name__ == "__main__":
    unittest.main()
