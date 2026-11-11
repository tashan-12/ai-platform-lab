"""检索模块的配置。默认值面向"几百个文档、几千个块"的单机场景。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_SUFFIXES: tuple[str, ...] = (".md", ".markdown", ".txt", ".json")
DEFAULT_SKIP_DIRS: tuple[str, ...] = (
    ".git",
    ".venv",
    "node_modules",
    ".agent",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
)
VECTOR_DIM = 512
# 索引文件放在语料目录里时，必须自我排除，否则重建会把上一次的索引也当语料
DEFAULT_INDEX_NAME = "rag-index.json"


@dataclass(frozen=True)
class RagConfig:
    """索引与检索的全部可调参数。"""

    max_chars: int = 800          # 单块上限（字符）
    min_chars: int = 60           # 过短的块会尝试并入上一条
    hard_overlap: int = 80        # 超长段落硬切时的重叠
    max_file_bytes: int = 512_000
    suffixes: tuple[str, ...] = DEFAULT_SUFFIXES
    skip_dirs: tuple[str, ...] = DEFAULT_SKIP_DIRS
    vector_dim: int = VECTOR_DIM
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    hybrid_alpha: float = 0.5     # 0 = 纯 BM25，1 = 纯向量
    rerank_pool: int = 20         # 进入重排的候选数


@dataclass(frozen=True)
class Paths:
    """一次运行涉及的文件路径。"""

    corpus: Path
    index: Path


def default_index_path(corpus: Path) -> Path:
    return corpus / "rag-index.json"
