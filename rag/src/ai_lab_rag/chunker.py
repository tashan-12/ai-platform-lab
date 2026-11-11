"""结构感知切分：按 Markdown 标题层级切块，代码块不切断。

为什么不用固定窗口：工程文档的语义边界就是标题。按 800 字硬切，
会把"一个 ADR 的决策段"劈成两半，检索时两头都不像。

三条规则：
1. 标题是强边界——遇到新标题先 flush；
2. 围栏代码块内部绝不切（否则检索到的代码片段是残的）；
3. 单行超长（> max_chars）才硬切，硬切处留 overlap 保证上下文连续。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import RagConfig

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# 围栏用 \x60 表示反引号，避免源码里出现三个连续反引号
_FENCE = re.compile(r"^\s*(\x60{3}|~~~)")


@dataclass(frozen=True)
class Chunk:
    """一个可检索的文本块。"""

    id: str
    doc: str
    ordinal: int
    heading_path: tuple[str, ...]
    text: str
    start_line: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "doc": self.doc,
            "ordinal": self.ordinal,
            "heading_path": list(self.heading_path),
            "text": self.text,
            "start_line": self.start_line,
        }

    @staticmethod
    def from_dict(payload: dict) -> "Chunk":
        return Chunk(
            id=payload["id"],
            doc=payload["doc"],
            ordinal=int(payload["ordinal"]),
            heading_path=tuple(payload.get("heading_path", [])),
            text=payload["text"],
            start_line=int(payload.get("start_line", 0)),
        )


def _hard_split_chars(text: str, max_chars: int, overlap: int) -> list[str]:
    """纯文本硬切，切点处保留 overlap 个字符作为上下文。"""

    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    start = 0
    step = max(1, max_chars - overlap)
    while start < len(text):
        pieces.append(text[start : start + max_chars])
        if start + max_chars >= len(text):
            break
        start += step
    return pieces


def _split_outside_fence(body: str, max_chars: int) -> list[str]:
    """按行切，但只在围栏之外切——保证代码块不被劈开。"""

    pieces: list[str] = []
    buffer: list[str] = []
    in_fence = False

    for line in body.splitlines(keepends=True):
        if _FENCE.match(line):
            in_fence = not in_fence
        buffer.append(line)
        if not in_fence and sum(len(item) for item in buffer) >= max_chars:
            pieces.append("".join(buffer))
            buffer = []

    if buffer:
        tail = "".join(buffer)
        if pieces and len(tail) < 40:
            pieces[-1] += tail
        else:
            pieces.append(tail)

    return pieces


def split_block(body: str, max_chars: int, overlap: int) -> list[str]:
    """块的二次切分。

    含代码块的块优先整块保留：工程文档里的代码示例一旦被切成两半，
    检索出来就是残的，比不检索还糟。只有明显过大（超过 4 倍上限）才按围栏边界拆。
    """

    if len(body) <= max_chars:
        return [body]

    if _FENCE.search(body):
        if len(body) <= max_chars * 4:
            return [body]
        return _split_outside_fence(body, max_chars)

    return _hard_split_chars(body, max_chars, overlap)


def chunk_markdown(rel_path: str, text: str, cfg: RagConfig) -> list[Chunk]:
    """把一份 Markdown 切成若干块；返回顺序稳定（按出现位置）。"""

    if not text.strip():
        return []

    blocks: list[tuple[tuple[str, ...], str, int]] = []
    heading_stack: list[str] = []
    buffer: list[str] = []
    buffer_start = 1
    in_fence = False

    def flush() -> None:
        nonlocal buffer
        body = "\n".join(buffer).strip()
        if body:
            blocks.append((tuple(heading_stack), body, buffer_start))
        buffer = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            if not buffer:
                buffer_start = line_no
            buffer.append(line)
            continue

        heading = None if in_fence else _HEADING.match(line)
        if heading is not None:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            while len(heading_stack) < level - 1:
                heading_stack.append("")
            heading_stack.append(title)
            buffer_start = line_no
            continue

        if not buffer:
            buffer_start = line_no
        buffer.append(line)

        if not in_fence and sum(len(item) + 1 for item in buffer) >= cfg.max_chars:
            flush()

    flush()

    merged: list[tuple[tuple[str, ...], str, int]] = []
    for heading_path, body, start_line in blocks:
        if (
            merged
            and len(body) < cfg.min_chars
            and merged[-1][0] == heading_path
            and len(merged[-1][1]) + len(body) < cfg.max_chars * 1.5
        ):
            prev_heading, prev_body, prev_start = merged[-1]
            merged[-1] = (prev_heading, prev_body + "\n\n" + body, prev_start)
        else:
            merged.append((heading_path, body, start_line))

    chunks: list[Chunk] = []
    ordinal = 0
    for heading_path, body, start_line in merged:
        for piece in split_block(body, cfg.max_chars, cfg.hard_overlap):
            chunks.append(
                Chunk(
                    id=f"{rel_path}#{ordinal}",
                    doc=rel_path,
                    ordinal=ordinal,
                    heading_path=heading_path,
                    text=piece,
                    start_line=start_line,
                )
            )
            ordinal += 1
    return chunks
