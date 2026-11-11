"""检索：BM25 + 向量余弦加权，再按词覆盖率重排。

为什么不直接上向量：
- 哈希向量本质是词袋，对"精确术语"（如 ADR-004、ToolRegistry）反而不如 BM25；
- 工程文档里大量查询是"找某个函数/某个决策"，词面命中比语义相似更可靠。

所以默认 alpha=0.5 做混合，再用 rerank 把"查询词覆盖率高的块"提上来。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .chunker import Chunk
from .embedder import cosine, embed
from .index import Index
from .tokenizer import unique_tokens


@dataclass
class Hit:
    chunk: Chunk
    score: float
    position: int = -1
    bm25: float = 0.0
    cosine: float = 0.0
    coverage: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.chunk.id,
            "doc": self.chunk.doc,
            "heading_path": list(self.chunk.heading_path),
            "score": round(self.score, 4),
            "bm25": round(self.bm25, 4),
            "cosine": round(self.cosine, 4),
            "coverage": round(self.coverage, 4),
            "text": self.chunk.text,
        }


def _min_max(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return [0.5 for _ in values]
    return [(value - low) / (high - low) for value in values]


class Retriever:
    def __init__(self, index: Index) -> None:
        self.index = index

    def _bm25(self, query_tokens: list[str]) -> dict[int, float]:
        """返回 chunk 位置 -> BM25 分数（只算有命中的块）。"""

        index = self.index
        cfg = index.cfg
        total_docs = len(index.chunks)
        scores: dict[int, float] = {}

        for token in set(query_tokens):
            positions = index.postings.get(token)
            if not positions:
                continue
            df = index.df.get(token, 0)
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))

            for position in positions:
                freq = index.term_freq[position].get(token, 0)
                length = index.doc_len[position]
                denom = freq + cfg.bm25_k1 * (1 - cfg.bm25_b + cfg.bm25_b * length / (index.avg_len or 1))
                scores[position] = scores.get(position, 0.0) + idf * freq * (cfg.bm25_k1 + 1) / denom

        return scores

    def search(
        self,
        query: str,
        k: int = 5,
        rerank: bool = True,
        alpha: float | None = None,
    ) -> list[Hit]:
        if not query.strip() or not self.index.chunks:
            return []

        cfg = self.index.cfg
        alpha = cfg.hybrid_alpha if alpha is None else alpha
        query_tokens = unique_tokens(query)
        query_vector = embed(query, cfg.vector_dim)

        bm25_scores = self._bm25(query_tokens)
        candidates = set(bm25_scores)

        # 向量侧：数据量小，全量算余弦（几千块以内没问题）
        cosine_scores: dict[int, float] = {}
        for position, vector in enumerate(self.index.vectors):
            similarity = cosine(query_vector, vector)
            if similarity > 0:
                cosine_scores[position] = similarity
                candidates.add(position)

        if not candidates:
            return []

        positions = sorted(candidates)
        bm25_values = _min_max([bm25_scores.get(position, 0.0) for position in positions])
        cosine_values = _min_max([cosine_scores.get(position, 0.0) for position in positions])

        hits: list[Hit] = []
        for offset, position in enumerate(positions):
            hybrid = alpha * cosine_values[offset] + (1 - alpha) * bm25_values[offset]
            hits.append(
                Hit(
                    chunk=self.index.chunks[position],
                    score=hybrid,
                    position=position,
                    bm25=bm25_scores.get(position, 0.0),
                    cosine=cosine_scores.get(position, 0.0),
                )
            )

        hits.sort(key=lambda hit: hit.score, reverse=True)

        if not rerank:
            return hits[:k]

        pool = hits[: max(cfg.rerank_pool, k)]
        pool_scores = _min_max([hit.score for hit in pool])
        for hit, base in zip(pool, pool_scores):
            chunk_tokens = self.index.token_sets[hit.position]
            matched = sum(1 for token in query_tokens if token in chunk_tokens)
            coverage = matched / len(query_tokens) if query_tokens else 0.0

            heading = " ".join(hit.chunk.heading_path)
            bonus = 0.1 if any(token in heading for token in query_tokens) else 0.0

            hit.coverage = coverage
            hit.score = 0.7 * base + 0.3 * coverage + bonus

        pool.sort(key=lambda hit: hit.score, reverse=True)
        return pool[:k]
