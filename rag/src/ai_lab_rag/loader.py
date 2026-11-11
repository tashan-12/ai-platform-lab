"""语料加载：遍历目录、过滤文件、算内容哈希（增量索引用）。"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_INDEX_NAME, RagConfig


@dataclass(frozen=True)
class Document:
    path: str        # 相对语料根目录的 posix 路径
    content: str
    sha1: str
    size: int


def _rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def load_corpus(corpus: Path, cfg: RagConfig) -> tuple[list[Document], list[str]]:
    """返回（文档列表，警告列表）。单个文件失败不中断整体加载。"""

    corpus = corpus.resolve()
    if not corpus.is_dir():
        raise NotADirectoryError(f"语料目录不存在：{corpus}")

    docs: list[Document] = []
    warnings: list[str] = []

    ignored_suffixes = (".egg-info", ".dist-info", ".mypy_cache", ".pytest_cache")

    for dirpath, dirnames, filenames in os.walk(corpus):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in cfg.skip_dirs
            and not name.startswith(".git")
            and not name.endswith(ignored_suffixes)
        )
        for filename in sorted(filenames):
            if not filename.endswith(cfg.suffixes):
                continue
            if filename == DEFAULT_INDEX_NAME:
                continue

            full_path = Path(dirpath) / filename
            rel = _rel_posix(full_path, corpus)

            try:
                size = full_path.stat().st_size
            except OSError as exc:
                warnings.append(f"跳过 {rel}：{exc}")
                continue

            if size > cfg.max_file_bytes:
                warnings.append(f"跳过 {rel}：{size} 字节超过上限 {cfg.max_file_bytes}")
                continue

            try:
                raw = full_path.read_bytes()
            except OSError as exc:
                warnings.append(f"跳过 {rel}：{exc}")
                continue

            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = raw.decode("utf-8", errors="replace")
                warnings.append(f"{rel} 含非 UTF-8 字节，已用替换符解码")

            docs.append(
                Document(
                    path=rel,
                    content=content,
                    sha1=hashlib.sha1(raw).hexdigest(),
                    size=size,
                )
            )

    docs.sort(key=lambda item: item.path)
    return docs, warnings
