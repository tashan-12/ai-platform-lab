"""索引：构建、增量更新、持久化。

只持久化最小信息（文档哈希 + 块文本），词频、倒排、向量都在加载时重算。
理由：这些量都能从文本确定性推导，存下来只会让索引文件胖十倍、还容易不一致。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .chunker import Chunk, chunk_markdown
from .config import RagConfig
from .embedder import embed
from .loader import load_corpus
from .tokenizer import tokenize

INDEX_VERSION = 1


@dataclass
class BuildStats:
    """一次构建的结果摘要，CLI 和评测都会用。"""

    docs_total: int = 0
    docs_rebuilt: int = 0
    docs_reused: int = 0
    docs_removed: int = 0
    chunks: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class Index:
    cfg: RagConfig
    docs: dict[str, dict]
    chunks: list[Chunk]
    term_freq: list[dict[str, int]] = field(default_factory=list)
    doc_len: list[int] = field(default_factory=list)
    df: dict[str, int] = field(default_factory=dict)
    postings: dict[str, list[int]] = field(default_factory=dict)
    vectors: list[list[float]] = field(default_factory=list)
    token_sets: list[set[str]] = field(default_factory=list)
    avg_len: float = 0.0

    # ---------- 派生数据 ----------
    def _recompute(self) -> None:
        self.term_freq = []
        self.doc_len = []
        self.df = {}
        self.postings = {}
        self.vectors = []
        self.token_sets = []

        for position, chunk in enumerate(self.chunks):
            # 标题参与检索：工程文档里"## 检索"这种标题本身就是强信号
            searchable = " ".join(part for part in chunk.heading_path if part)
            searchable = f"{searchable}\n{chunk.text}" if searchable else chunk.text

            tokens = tokenize(searchable)
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1

            self.term_freq.append(counts)
            self.doc_len.append(len(tokens))
            self.token_sets.append(set(counts))
            self.vectors.append(embed(searchable, self.cfg.vector_dim))

            for token, frequency in counts.items():
                if token not in self.postings:
                    self.postings[token] = []
                    self.df[token] = 0
                self.postings[token].append(position)
                self.df[token] = frequency  # 占位，稍后重算

        # df 必须是"包含该词的块数"，不是词频
        self.df = {token: len(positions) for token, positions in self.postings.items()}
        total = sum(self.doc_len)
        self.avg_len = (total / len(self.chunks)) if self.chunks else 0.0

    # ---------- 持久化 ----------
    def save(self, path: Path) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INDEX_VERSION,
            "config": {
                "max_chars": self.cfg.max_chars,
                "min_chars": self.cfg.min_chars,
                "vector_dim": self.cfg.vector_dim,
            },
            "docs": self.docs,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }
        text = json.dumps(payload, ensure_ascii=False)
        path.write_text(text, encoding="utf-8")
        return len(text.encode("utf-8"))

    @staticmethod
    def load(path: Path) -> "Index":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != INDEX_VERSION:
            raise ValueError(f"索引版本不匹配：{payload.get('version')}，请重建")

        config = payload.get("config", {})
        cfg = RagConfig(
            max_chars=int(config.get("max_chars", 800)),
            min_chars=int(config.get("min_chars", 60)),
            vector_dim=int(config.get("vector_dim", 512)),
        )
        index = Index(
            cfg=cfg,
            docs=payload.get("docs", {}),
            chunks=[Chunk.from_dict(item) for item in payload.get("chunks", [])],
        )
        index._recompute()
        return index

    def summary(self) -> dict:
        return {
            "docs": len(self.docs),
            "chunks": len(self.chunks),
            "avg_chunk_len": round(self.avg_len, 1),
            "vocab": len(self.postings),
        }


def build_index(
    corpus: Path,
    cfg: RagConfig | None = None,
    previous: Index | None = None,
    rebuild: bool = False,
) -> tuple[Index, BuildStats]:
    """构建或增量更新索引。

    incremental：文档内容哈希未变则复用旧块，只重算变更/新增的文档。
    """

    cfg = cfg or RagConfig()
    documents, warnings = load_corpus(corpus, cfg)
    stats = BuildStats(docs_total=len(documents), warnings=list(warnings))

    previous = None if rebuild else previous
    old_chunks_by_doc: dict[str, list[Chunk]] = {}
    old_docs: dict[str, dict] = {}
    if previous is not None:
        old_docs = previous.docs
        for chunk in previous.chunks:
            old_chunks_by_doc.setdefault(chunk.doc, []).append(chunk)

    new_chunks: list[Chunk] = []
    new_docs: dict[str, dict] = {}

    for document in documents:
        same_hash = old_docs.get(document.path, {}).get("sha1") == document.sha1
        if same_hash and document.path in old_chunks_by_doc:
            reused = old_chunks_by_doc[document.path]
            new_chunks.extend(reused)
            new_docs[document.path] = {
                "sha1": document.sha1,
                "size": document.size,
                "chunks": len(reused),
            }
            stats.docs_reused += 1
            continue

        produced = chunk_markdown(document.path, document.content, cfg)
        new_chunks.extend(produced)
        new_docs[document.path] = {
            "sha1": document.sha1,
            "size": document.size,
            "chunks": len(produced),
        }
        stats.docs_rebuilt += 1

    stats.docs_removed = len(set(old_docs) - set(new_docs))
    stats.chunks = len(new_chunks)

    new_chunks.sort(key=lambda chunk: (chunk.doc, chunk.ordinal))
    index = Index(cfg=cfg, docs=new_docs, chunks=new_chunks)
    index._recompute()
    return index, stats
