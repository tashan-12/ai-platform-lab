"""向量化：特征哈希（feature hashing），零依赖、确定性。

诚实的说明放在最前面：
这不是语义向量。它把"分词后的词频"哈希进固定维度，因此余弦相似度约等于
"词面重叠度"。它比纯 BM25 多出来的价值只有一点：同义词表可以人为注入
（SYNONYMS 字段），让少量近义词也能命中。

之所以不做真 embedding：那需要下载 100-400MB 模型或调用外部 API，
会让"clone 下来就能跑"这个前提失效。升级路径见 docs/adr/0005-rag-design.md。
"""

from __future__ import annotations

import hashlib
import math

from .tokenizer import tokenize


def _bucket(token: str, dim: int) -> tuple[int, float]:
    """把一个词映射到 [0, dim) 的桶，并给出符号（reduce 碰撞偏差）。"""

    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % dim, 1.0 if (value >> 63) & 1 else -1.0


def embed(text: str, dim: int = 512) -> list[float]:
    """把文本变成 L2 归一化向量；空文本返回全零向量。"""

    vector = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vector

    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1

    for token, count in counts.items():
        index, sign = _bucket(token, dim)
        # 次线性词频，避免长文档被高频词主导
        vector[index] += sign * (1.0 + math.log(count))

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"维度不一致：{len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))
