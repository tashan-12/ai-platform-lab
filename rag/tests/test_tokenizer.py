import unittest

import _bootstrap  # noqa: F401
from ai_lab_rag.tokenizer import tokenize, unique_tokens


class TokenizerTest(unittest.TestCase):
    def test_latin_lowercased(self) -> None:
        self.assertIn("toolregistry", tokenize("ToolRegistry"))

    def test_cjk_bigrams(self) -> None:
        tokens = tokenize("增量索引")
        self.assertIn("增量", tokens)
        self.assertIn("索引", tokens)

    def test_stopwords_removed(self) -> None:
        self.assertNotIn("的", tokenize("这是测试的文档"))

    def test_unique_preserves_order(self) -> None:
        # 双字词各自成一个 bigram，重复项被去掉
        self.assertEqual(unique_tokens("索引 索引 检索"), ["索引", "检索"])

    def test_empty(self) -> None:
        self.assertEqual(tokenize(""), [])


if __name__ == "__main__":
    unittest.main()
